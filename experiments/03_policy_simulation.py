"""03_policy_simulation.py - one node-day per (policy, environment, seed).

Main comparison: 20 seeds x 3 environments x 8 policies (same traffic, link
trace and battery per seed across policies = paired design).
Sensitivity: BER x0.1 and x10 (10 seeds) for the main policies.
Cipher ablation: FLOOR-E with each AEAD.
Output: outputs/results/03_policy_sim.csv  (~25 min on one core; FLORA_QUICK=1: ~3 min)
"""
import os, sys, time
import numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora.energy import CryptoCost
from flora.sim import run_day
from flora.traffic import generate, link_trace
from flora import policies as P


def make(name):
    return {
        "Static-Ascon": lambda: P.StaticImmediate("ascon_armv7m", 16, "Static-Ascon"),
        "Static-AES-GCM": lambda: P.StaticImmediate("aesgcm", 12, "Static-AES-GCM"),
        "Elad2026-rule": lambda: P.Elad2026(),
        "Q-learning (no floor)": lambda: P.QLearning(),
        "FLOOR-E": lambda: P.Floor("FLOOR-E"),
        "FLOOR-L(pow2)": lambda: P.Floor("FLOOR-L(pow2)", leakage_aware=True, pad="pow2"),
        "FLOOR-L(q16)": lambda: P.Floor("FLOOR-L(q16)", leakage_aware=True, pad="q16"),
        "FLOOR-C": lambda: P.FloorConstant("FLOOR-C"),
        "FLOOR-L(q64)": lambda: P.Floor("FLOOR-L(q64)", leakage_aware=True, pad="q64"),
        "FLOOR-L(q128)": lambda: P.Floor("FLOOR-L(q128)", leakage_aware=True, pad="q128"),
        "Elad2026-rule+FLOOR-framing": lambda: P.EladBatched(),
        "Q-learning (with floor)": lambda: P.QLearningFloor(),
        "FLOOR-E/no-batch": lambda: P.Floor("FLOOR-E/no-batch", batching=False),
        "FLOOR-E/tag128-single-key": lambda: P.Floor("FLOOR-E/tag128-single-key", single_tag=True),
        "FLOOR-E/explicit-nonce": lambda: P.Floor("FLOOR-E/explicit-nonce", implicit_nonce=False),
        "FLOOR-E/AES-GCM": lambda: P.Floor("FLOOR-E/AES-GCM", cipher="aesgcm"),
        "FLOOR-E/ChaCha20-Poly1305": lambda: P.Floor("FLOOR-E/ChaCha20-Poly1305", cipher="chacha20poly1305"),
        "FLOOR-E/Xoodyak": lambda: P.Floor("FLOOR-E/Xoodyak", cipher="xoodyak"),
        "FLOOR-E/GIFT-COFB": lambda: P.Floor("FLOOR-E/GIFT-COFB", cipher="giftcofb"),
        "FLOOR-E/RECTANGLE-CTR+HMAC": lambda: P.Floor("FLOOR-E/RECTANGLE-CTR+HMAC", cipher="rectangle_ctr_hmac"),
    }[name]()


MAIN = ["Static-Ascon", "Static-AES-GCM", "Elad2026-rule", "Q-learning (no floor)", "FLOOR-E",
        "FLOOR-L(pow2)", "FLOOR-L(q16)", "FLOOR-C", "Elad2026-rule+FLOOR-framing", "Q-learning (with floor)", "FLOOR-E/no-batch", "FLOOR-E/explicit-nonce",
        "FLOOR-E/tag128-single-key", "FLOOR-L(q64)", "FLOOR-L(q128)"]
CIPHER_ABL = ["FLOOR-E/AES-GCM", "FLOOR-E/ChaCha20-Poly1305", "FLOOR-E/Xoodyak", "FLOOR-E/GIFT-COFB",
              "FLOOR-E/RECTANGLE-CTR+HMAC"]
SENS = ["Static-Ascon", "Elad2026-rule", "FLOOR-E", "FLOOR-L(q16)"]
ENVS = ["hospital", "home", "rural"]
CRYPTO = None


def job(args):
    global CRYPTO
    if CRYPTO is None:
        CRYPTO = CryptoCost()
    pols, env, seed, ber = args
    rng = np.random.default_rng(seed)             # identical inputs for every policy (paired)
    recs = generate(rng)
    trace = link_trace(rng, env)
    battery = rng.uniform(10, 100)
    out = []
    for name in pols:
        r = run_day(make(name), env, seed, CRYPTO, ber_mult=ber, recs=recs, trace=trace, battery=battery)
        r["policy"] = name
        r["battery"] = battery
        out.append(r)
    return out


def main():
    only = [x for x in os.environ.get("FLORA_ONLY", "").split(",") if x]
    n_main = 4 if QUICK else 20
    n_sens = 2 if QUICK else 10
    jobs = []
    for env in ENVS:
        for s in range(n_main):
            jobs.append((only or (MAIN + CIPHER_ABL), env, SEED + s, 1.0))
        for ber in (0.1, 10.0):
            for s in range(n_sens):
                if not only:
                    jobs.append((SENS, env, SEED + s, ber))
    t0 = time.time()
    with Pool(int(os.environ.get("FLORA_THREADS", os.cpu_count()))) as pool:
        rows = [r for res in pool.imap_unordered(job, jobs) for r in res]
    df = pd.DataFrame(rows)
    os.makedirs(os.path.join(OUT, "results"), exist_ok=True)
    path = os.path.join(OUT, "results/03_policy_sim.csv")
    if only and os.path.exists(path):   # add / replace the selected policies in the existing results
        old = pd.read_csv(path)
        df = pd.concat([old[~(old.policy.isin(only) & (old.ber_mult == 1.0))], df], ignore_index=True)
    df.to_csv(os.path.join(OUT, "results/03_policy_sim.csv"), index=False)
    print(f"{len(df)} runs in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
