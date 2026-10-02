"""05_downgrade.py - active attacks on the adaptation mechanism.

(a) Context manipulation: a jammer degrades the link (state 'poor', BER x10)
    from 06:00 to 22:00. Each policy is run on the same node-day with and
    without the attack (20 seeds, 'home'); Q-learning is first trained on one
    clean day. We count records protected below the tag floor, records of
    class R/V protected by a non-standardised primitive, records whose
    protection changed because of the attack, deadline misses and energy.
(b) Header tampering: with real Ascon-AEAD128 (NIST SP 800-232 reference
    implementation), an active attacker rewrites the tag-length field of
    captured frames to 8 bits and submits random tags (N forgeries). A naive
    receiver that trusts the header is compared with the FLOOR receiver
    (configuration bound as associated data + receiver-side floor).
Output: outputs/results/05_downgrade.json  (~10 min)
"""
import json, os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora.energy import CryptoCost
from flora.sim import run_day
from flora.traffic import generate, link_trace, LINK_STATES, STEP
from flora import policies as P
from flora import pyascon_ref as ascon

ATTACK = (6 * 3600, 22 * 3600)
N_SEEDS = 4 if QUICK else 20
N_FORGE = 5000 if QUICK else 40000
CRYPTO = None


class Recorder(P.Policy):
    """Wraps a policy to log the protection chosen for each frame."""
    def __init__(self, inner):
        self.inner, self.name, self.batching, self.log = inner, inner.name, inner.batching, []
    def reset(self, rng, env, battery):
        self.inner.reset(rng, env, battery); self.log = []
    def window(self, link, d):
        return self.inner.window(link, d)
    def frame(self, cls, pt, link):
        r = self.inner.frame(cls, pt, link); self.log.append((tuple(cls), r[0], r[1])); return r
    def feedback(self, *a):
        self.inner.feedback(*a)


def job(seed):
    global CRYPTO
    if CRYPTO is None:
        CRYPTO = CryptoCost()
    rng = np.random.default_rng(seed)
    recs, trace, batt = generate(rng), link_trace(rng, "home"), rng.uniform(10, 100)
    att = trace.copy()
    att[int(ATTACK[0] // STEP):int(ATTACK[1] // STEP)] = LINK_STATES.index("poor")
    out = []
    for name, mk in [("Static-Ascon", lambda: P.StaticImmediate("ascon_armv7m", 16, "Static-Ascon")),
                     ("Elad2026-rule", P.Elad2026), ("Q-learning (no floor)", P.QLearning),
                     ("FLOOR-E", lambda: P.Floor("FLOOR-E")),
                     ("FLOOR-L(q16)", lambda: P.Floor("FLOOR-L(q16)", leakage_aware=True, pad="q16"))]:
        res = {}
        for cond, tr, bm in (("clean", trace, 1.0), ("attack", att, 1.0)):
            pol = mk()
            if name.startswith("Q-learning"):   # warm-up day without attack
                run_day(pol, "home", seed + 99991, CRYPTO)
            rec = Recorder(pol)
            if cond == "attack":
                # BER x10 only inside the jamming window (v1.1 applied x10 to the 'poor' state all day)
                jam = np.ones(len(tr))
                jam[int(ATTACK[0] // STEP):int(ATTACK[1] // STEP)] = 10.0
                r = run_day(rec, "home", seed, CRYPTO, recs=recs, trace=tr, battery=batt, ber_trace=jam)
            else:
                r = run_day(rec, "home", seed, CRYPTO, recs=recs, trace=tr, battery=batt)
            r["log"] = rec.log
            res[cond] = r
        c, a = res["clean"], res["attack"]
        # protection used for V and R records, by condition
        def prot(log, cls):
            return pd.Series([f"{ci}/{8 * t}" for (cl, ci, t) in log for x in cl if x == cls]).value_counts().to_dict()
        row = {"policy": name, "seed": seed}
        for cond, r in res.items():
            row[f"{cond}_E_J"] = r["E_total_J"]
            for k in ("viol_tag_N", "viol_tag_R", "viol_tag_V", "nonstd_R", "nonstd_V", "miss_N", "miss_R", "miss_V", "n_N", "n_R", "n_V"):
                row[f"{cond}_{k}"] = r[k]
            row[f"{cond}_prot_V"] = prot(r["log"], "V")
            row[f"{cond}_prot_R"] = prot(r["log"], "R")
        out.append(row)
    return out


def forgery_test(rng):
    key = rng.bytes(16)
    floor_bytes = 16
    stats = {"naive": 0, "floor": 0}
    for i in range(N_FORGE):
        seq = i.to_bytes(4, "little")
        nonce = b"\x00" * 12 + seq
        pt = rng.bytes(24)
        cfg_ok = bytes([0x10])                      # config byte: 16-byte tag
        ct = ascon.ascon_encrypt(key, nonce, cfg_ok + seq, pt)
        # attacker: flips ciphertext bits, declares an 8-bit tag, guesses it
        forged_ct = bytes([ct[0] ^ 0xFF]) + ct[1:24]
        guess = rng.bytes(1)
        cfg_bad = bytes([0x01])                     # header now claims a 1-byte tag
        # naive receiver: trusts header tag length, MAC over the ciphertext only (header not bound)
        tag_true = _tag_for(key, nonce, seq, forged_ct)
        if tag_true[:1] == guess:
            stats["naive"] += 1
        # FLOOR receiver: tag length from its own policy table (never from the header),
        # header bytes are associated data; a 1-byte tag is rejected before any MAC check
        declared = cfg_bad[0]
        if declared >= floor_bytes:
            if ascon.ascon_decrypt(key, nonce, cfg_bad + seq, forged_ct + guess * 16) is not None:
                stats["floor"] += 1
    return stats


def in_table_downgrade_test(rng, n):
    """Downgrade *inside* the policy table: a captured R frame (K128, 16-byte tag) is rewritten to
    announce an 8-byte tag and its tag is truncated to 8 bytes. The FLOOR receiver selects K64
    (and the K64 nonce prefix), verifies with the modified header as AD, and would in any case
    discard the R record because an 8-byte tag is below the R floor. A single-key receiver that
    reads the tag length from an unauthenticated header accepts the truncated genuine tag."""
    import hmac, hashlib
    def hkdf(ikm, salt, info, L):
        prk = hmac.new(salt, ikm, hashlib.sha256).digest(); out, t, i = b"", b"", 1
        while len(out) < L:
            t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest(); out += t; i += 1
        return out[:L]
    master, sid = rng.bytes(16), b"session"
    K = {tau: hkdf(master, sid, b"FLOOR v1U" + bytes([tau]) + b"key", 16) for tau in (64, 128)}
    Pn = {tau: hkdf(master, sid, b"FLOOR v1U" + bytes([tau]) + b"nonce", 12) for tau in (64, 128)}
    res = {"n": n, "floor_tag_verified": 0, "floor_R_released": 0, "naive_single_key_accepted": 0}
    for i in range(n):
        seq = i.to_bytes(4, "little"); pt = rng.bytes(24)
        hdr = bytes([0x10]) + seq
        ct = ascon.ascon_encrypt(K[128], Pn[128] + seq, hdr, pt)          # ciphertext || 16-byte tag
        c, t16 = ct[:-16], ct[-16:]
        bad = bytes([0x08]) + seq                                          # header now announces 8 bytes
        ok = _verify_trunc(K[64], Pn[64] + seq, bad, c, t16[:8])
        res["floor_tag_verified"] += ok
        res["floor_R_released"] += ok and 64 >= 128                        # floor check: never
        # naive receiver: one key, tag length from header, header not authenticated
        # (the naive sender authenticates only the sequence number; the receiver checks the tag prefix)
        ctn = ascon.ascon_encrypt(K[128], Pn[128] + seq, seq, pt)
        res["naive_single_key_accepted"] += _verify_trunc(K[128], Pn[128] + seq, seq, ctn[:-16], ctn[-16:][:8])
    return res


def ascon_decrypt_raw(key, nonce, ad, c):
    S = [0, 0, 0, 0, 0]
    ascon.ascon_initialize(S, 128, 16, 12, 8, 1, key, nonce)
    ascon.ascon_process_associated_data(S, 8, 16, ad)
    return ascon.ascon_process_ciphertext(S, 8, 16, c)


def _verify_trunc(key, nonce, ad, c, tag8):
    """Receiver-side check of a truncated 8-byte tag under (key, nonce, ad)."""
    pt = ascon_decrypt_raw(key, nonce, ad, c)
    return ascon.ascon_encrypt(key, nonce, ad, pt)[-16:][:8] == tag8


def _tag_for(key, nonce, ad, ct):
    """Tag that makes (ct) valid under (key, nonce, ad): obtained by decrypting ct to the
    implied plaintext and re-encrypting (the naive receiver compares the first byte only)."""
    # Ascon is a duplex: the plaintext implied by ct is recovered by keystream; recompute tag
    pt = _implied_plaintext(key, nonce, ad, ct)
    return ascon.ascon_encrypt(key, nonce, ad, pt)[len(ct):]


def _implied_plaintext(key, nonce, ad, ct):
    S = [0, 0, 0, 0, 0]
    ascon.ascon_initialize(S, len(key) * 8, 16, 12, 8, 1, key, nonce)
    ascon.ascon_process_associated_data(S, 8, 16, ad)
    return ascon.ascon_process_ciphertext(S, 8, 16, ct)


def main():
    with Pool(int(os.environ.get("FLORA_THREADS", os.cpu_count()))) as pool:
        rows = [r for res in pool.map(job, [SEED + 500 + s for s in range(N_SEEDS)]) for r in res]
    df = pd.DataFrame(rows)
    summary = {}
    for name, g in df.groupby("policy"):
        s = {}
        for cond in ("clean", "attack"):
            nV, nR, nN = g[f"{cond}_n_V"].sum(), g[f"{cond}_n_R"].sum(), g[f"{cond}_n_N"].sum()
            s[cond] = {
                "E_J_mean": g[f"{cond}_E_J"].mean(),
                "below_floor_rate": {c: g[f"{cond}_viol_tag_{c}"].sum() / g[f"{cond}_n_{c}"].sum() for c in "NRV"},
                "nonstd_rate": {c: g[f"{cond}_nonstd_{c}"].sum() / g[f"{cond}_n_{c}"].sum() for c in "RV"},
                "miss_rate": {c: g[f"{cond}_miss_{c}"].sum() / g[f"{cond}_n_{c}"].sum() for c in "NRV"},
            }
            agg = {}
            for d in g[f"{cond}_prot_V"]:
                for k, v in d.items():
                    agg[k] = agg.get(k, 0) + v
            s[cond]["protection_V"] = agg
            aggR = {}
            for d in g[f"{cond}_prot_R"]:
                for k, v in d.items():
                    aggR[k] = aggR.get(k, 0) + v
            s[cond]["protection_R"] = aggR
        s["energy_increase_pct"] = 100 * (g.attack_E_J / g.clean_E_J - 1).mean()
        summary[name] = s
    rng = np.random.default_rng(SEED)
    summary["header_tampering"] = {"n_forgeries": N_FORGE, "accepted": forgery_test(rng),
                                   "expected_naive": N_FORGE / 256,
                                   "note": "FLOOR rejects the 1-byte tag by its policy table (no MAC needed); sanity check only"}
    summary["in_table_downgrade"] = in_table_downgrade_test(np.random.default_rng(SEED + 1), 2000 if QUICK else 10000)
    json.dump(summary, open(os.path.join(OUT, "results/05_downgrade.json"), "w"), indent=1, default=float)
    print(json.dumps(summary, indent=1, default=float)[:4000])


if __name__ == "__main__":
    main()
