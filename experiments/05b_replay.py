"""05b_replay.py - replay of captured frames (adversary A3), real Ascon-AEAD128 reference
implementation, subkeys and nonce prefixes derived with HKDF-SHA256 (RFC 5869) as in the article.
Scenarios for the 5000 frames of a captured session:
  (a) same session, replayed after the receiver has accepted them (highest accepted s = 4999);
  (b) new session after re-pairing (new master key, fresh receiver state s_max = -1);
  (c) same key, receiver that lost its state (s_max reset to -1): shows why the gateway must
      persist its highest accepted sequence number per key.
Receivers: naive (tag check only, no freshness) and FLOOR (tag check + s > s_max).
Output: outputs/results/05b_replay.json  (<1 min)"""
import json, os, sys, hmac, hashlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora import pyascon_ref as ascon

N = 500 if QUICK else 5000


def hkdf(ikm, salt, info, length):
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, t, i = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest(); out += t; i += 1
    return out[:length]


def session(master, session_id, direction=b"U", tau=128):
    """Subkey and 96-bit nonce prefix for one direction and one tag length (labels of Table 5)."""
    lab = b"FLOOR v1" + direction + bytes([tau])
    return hkdf(master, session_id, lab + b"key", 16), hkdf(master, session_id, lab + b"nonce", 12)


def replay(frames, key, prefix, s_max):
    acc = {"naive": 0, "floor": 0}
    for hdr, ct in frames:
        seq = int.from_bytes(hdr[1:5], "little")
        ok = ascon.ascon_decrypt(key, prefix + hdr[1:5], hdr, ct) is not None
        acc["naive"] += ok
        acc["floor"] += ok and seq > s_max
    return acc


def main():
    rng = np.random.default_rng(SEED)
    master1, master2 = rng.bytes(16), rng.bytes(16)          # pairing 1 and re-pairing 2
    k1, p1 = session(master1, b"session-1")
    k2, p2 = session(master2, b"session-2")
    frames = []
    for s in range(N):                                       # legitimate traffic captured by the adversary
        seq = s.to_bytes(4, "little"); hdr = bytes([0x10]) + seq
        frames.append((hdr, ascon.ascon_encrypt(k1, p1 + seq, hdr, rng.bytes(24))))
    res = {"replayed_frames": N,
           "same_session_after_acceptance": replay(frames, k1, p1, N - 1),
           "new_session_after_repairing": replay(frames, k2, p2, -1),
           "same_key_receiver_state_lost": replay(frames, k1, p1, -1)}
    res["accepted"] = res["same_session_after_acceptance"]   # backward-compatible key
    json.dump(res, open(os.path.join(OUT, "results/05b_replay.json"), "w"), indent=1)
    print(res)


if __name__ == "__main__":
    main()
