"""policies.py - record-protection policies compared in the article.

Every policy decides, for the records produced by the node, (i) the AEAD,
(ii) the tag length, (iii) the nonce transmitted on air, (iv) the padding and
(v) when the buffered records are flushed. The simulator (sim.py) charges the
crypto and radio energy of each frame.
"""
from __future__ import annotations
import numpy as np
from .traffic import LINK_STATES, LINK_RSSI, CLASSES

APPROVED = {"ascon_armv7m", "aesgcm", "chacha20poly1305"}   # SP 800-232, SP 800-38D, RFC 8439
TAG_FLOOR_BITS = {"N": 64, "R": 128, "V": 128}                # FLOOR security floor
REC_HDR = 2                                                    # record type + length inside plaintext


def pad_pow2(n: int, minimum: int = 32) -> int:
    b = minimum
    while b < n:
        b *= 2
    return b


def pad_quantum(n: int, q: int = 16) -> int:
    return -(-n // q) * q


class Policy:
    name = "base"
    batching = False
    def reset(self, rng, env, battery):  # called at the start of each simulated day
        self.rng, self.env, self.battery = rng, env, battery
    def frame(self, recs_cls, pt_len, link):
        """Return (cipher, tag_bytes, header_bytes, padded_pt_len, visible_alg_id)."""
        raise NotImplementedError
    def window(self, link, first_deadline):  # batching window (s) for policies that batch
        return 0.0
    def feedback(self, *a):
        pass


class StaticImmediate(Policy):
    """One record per frame, explicit nonce, full tag (typical baseline)."""
    def __init__(self, cipher, nonce_bytes, name):
        self.cipher, self.nonce, self.name = cipher, nonce_bytes, name
    def frame(self, recs_cls, pt_len, link):
        return self.cipher, 16, 1 + self.nonce, pt_len, None


class Elad2026(Policy):
    """Composite-score rule of Elad et al. (JIS 2026), Algorithm 1: S >= 3 -> RECTANGLE
    (CTR + HMAC-SHA256, 32-byte tag) else Ascon; 96-bit nonce and a cipher id byte on air.
    Sensitivity mapping: V -> HIGH, R -> MEDIUM, N -> LOW (true class, no classifier error)."""
    name = "Elad2026-rule"
    SCORE = {"V": 3, "R": 2, "N": 1}
    def frame(self, recs_cls, pt_len, link):
        s = self.SCORE[recs_cls[0]]
        rssi = LINK_RSSI[link] + self.rng.normal(0, 3)
        pen_n = 2 if rssi < -90 else (1 if rssi < -70 else 0)
        bonus_l = 1 if self.env == "hospital" else 0
        pen_b = 1 if self.battery < 20 else 0
        S = s + pen_n + bonus_l - pen_b
        if S >= 3:
            return "rectangle_ctr_hmac", 32, 1 + 12, pt_len, "RECTANGLE"
        return "ascon_armv7m", 16, 1 + 12, pt_len, "ASCON"


class Floor(Policy):
    """FLOOR: fixed standardised AEAD, implicit counter nonce (4-byte sequence number on
    air, bound as associated data with the configuration byte), class-dependent tag floor,
    deadline-driven batching; optional length hiding (constant tag + padding buckets)."""
    batching = True
    def __init__(self, name="FLOOR-E", cipher="ascon_armv7m", leakage_aware=False, pad="pow2",
                 batching=True, implicit_nonce=True, single_tag=False):
        self.name, self.cipher, self.leak, self.pad = name, cipher, leakage_aware, pad
        self.single_tag = single_tag   # one 128-bit tag for every frame (single key, no subkeys)
        self.batching, self.implicit = batching, implicit_nonce
    def window(self, link, first_deadline):
        return np.inf   # flush is driven by the earliest deadline (see sim.py)
    def frame(self, recs_cls, pt_len, link):
        hdr = 1 + (4 if self.implicit else 16)
        if self.leak:
            tag = 16
            if self.pad == "pow2":
                pt_len = pad_pow2(pt_len)
            elif self.pad.startswith("q"):
                pt_len = pad_quantum(pt_len, int(self.pad[1:]))
            elif self.pad.startswith("fixed"):
                S = int(self.pad[5:])
                pt_len = max(1, -(-pt_len // S)) * S
        elif self.single_tag:
            tag = 16
        else:
            # FLOOR-E: 64-bit tag for N-only frames, 128-bit otherwise. SP 800-232 requires a
            # constant tag length per key, so each tag length has its own subkey (see article).
            tag = 16 if any(c in ("R", "V") for c in recs_cls) else 8
        return self.cipher, tag, hdr, pt_len, None


class QLearning(Policy):
    """Generic adaptive-encryption learner (in the spirit of Q-learning adaptive encryption
    for WSN): state = (link state, battery bucket); action = (cipher, tag, window);
    reward = -energy per record - penalty x deadline misses. No security floor."""
    batching = True
    CIPHERS = ("ascon_armv7m", "aesgcm", "chacha20poly1305", "xoodyak", "giftcofb")
    TAGS = (4, 8, 16)
    WINDOWS = (0.0, 1.0, 5.0, 30.0)
    def __init__(self, name="Q-learning (no floor)", eps=0.1, alpha=0.1, miss_penalty=50.0):
        self.name, self.eps0, self.alpha, self.pen = name, eps, alpha, miss_penalty
        self.actions = [(c, t, w) for c in self.CIPHERS for t in self.TAGS for w in self.WINDOWS]
        self.Q = None
    def reset(self, rng, env, battery):
        super().reset(rng, env, battery)
        if self.Q is None:
            self.Q = np.zeros((3, 2, len(self.actions)))
        self.steps = 0
        self.cur = None
    def _state(self, link):
        return LINK_STATES.index(link), int(self.battery < 20)
    def choose(self, link):
        s = self._state(link)
        eps = max(0.02, self.eps0 * (0.999 ** self.steps))
        a = self.rng.integers(len(self.actions)) if self.rng.random() < eps else int(np.argmax(self.Q[s]))
        self.cur = (s, a)
        self.steps += 1
        return self.actions[a]
    def window(self, link, first_deadline):
        return self.choose(link)[2]
    def frame(self, recs_cls, pt_len, link):
        c, t, _ = self.actions[self.cur[1]] if self.cur else self.choose(link)
        return c, t, 1 + 4, pt_len, None
    def feedback(self, energy_per_rec_uJ, misses):
        s, a = self.cur
        r = -energy_per_rec_uJ - self.pen * misses
        self.Q[s][a] += self.alpha * (r - self.Q[s][a])


class FloorConstant(Floor):
    """FLOOR-C: constant-rate variant. Frames leave on a fixed 1-s grid (the 1-Hz heart-rate
    stream guarantees one frame per slot, so no dummy frame is needed in this workload) and
    every frame is padded to a fixed size (multiples of 448 bytes). Deadline guard kept."""
    def __init__(self, name="FLOOR-C", slot=1.0, size=448):
        super().__init__(name, leakage_aware=True, pad=f"fixed{size}")
        self.slot = slot
    def window(self, link, first_deadline):
        return None   # handled by the simulator: next slot boundary


class EladBatched(Floor):
    """Ablation: the cipher-selection rule of Elad et al. (2026) applied on top of FLOOR
    framing (deadline batching, 5-byte header, implicit nonce). The rule is evaluated on the
    most sensitive class of the batch; RECTANGLE-CTR+HMAC keeps its 32-byte tag, Ascon 16 bytes.
    Isolates the effect of cryptographic agility from the effect of framing."""
    SCORE = {"V": 3, "R": 2, "N": 1}
    def __init__(self, name="Elad2026-rule+FLOOR-framing"):
        super().__init__(name)
    def frame(self, recs_cls, pt_len, link):
        s = max(self.SCORE[c] for c in recs_cls)
        rssi = LINK_RSSI[link] + self.rng.normal(0, 3)
        pen_n = 2 if rssi < -90 else (1 if rssi < -70 else 0)
        S = s + pen_n + (1 if self.env == "hospital" else 0) - (1 if self.battery < 20 else 0)
        if S >= 3:
            return "rectangle_ctr_hmac", 32, 1 + 4, pt_len, "RECTANGLE"
        return "ascon_armv7m", 16, 1 + 4, pt_len, "ASCON"


class QLearningFloor(QLearning):
    """Constrained variant of the learner: actions restricted to standardised AEADs, the tag is
    raised to the floor of the most sensitive class in the frame, and the flush time is capped
    by the deadline guard (like FLOOR). Answers: does a learner help once it is made safe?"""
    CIPHERS = ("ascon_armv7m", "aesgcm", "chacha20poly1305")
    deadline_aware = True
    def __init__(self, name="Q-learning (with floor)", **kw):
        super().__init__(name=name, **kw)
    def frame(self, recs_cls, pt_len, link):
        c, t, hdr, pt, alg = super().frame(recs_cls, pt_len, link)
        floor_bytes = max(TAG_FLOOR_BITS[x] for x in recs_cls) // 8
        return c, max(t, floor_bytes), hdr, pt, alg
