"""03c_profiles.py - generality across device profiles: 'patch' (main), 'vitals' (no ECG),
'holter' (continuous ECG). 10 paired seeds x 3 environments x 6 policies.
Output: outputs/results/03c_profiles.csv  (~15 min)"""
import os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora.energy import CryptoCost
from flora.sim import run_day
from flora.traffic import generate, link_trace, PROFILES
from flora import policies as P
POL = {"Static-Ascon": lambda: P.StaticImmediate("ascon_armv7m", 16, "Static-Ascon"),
       "Elad2026-rule": P.Elad2026, "Elad2026-rule+FLOOR-framing": P.EladBatched,
       "Q-learning (with floor)": P.QLearningFloor,
       "FLOOR-E": lambda: P.Floor("FLOOR-E"),
       "FLOOR-L(q16)": lambda: P.Floor("FLOOR-L(q16)", leakage_aware=True, pad="q16")}
CRYPTO = None


def job(args):
    global CRYPTO
    if CRYPTO is None:
        CRYPTO = CryptoCost()
    prof, env, seed = args
    rng = np.random.default_rng(seed)
    recs, trace, batt = generate(rng, streams=PROFILES[prof]), link_trace(rng, env), rng.uniform(10, 100)
    out = []
    for name, mk in POL.items():
        r = run_day(mk(), env, seed, CRYPTO, recs=recs, trace=trace, battery=batt)
        r.update({"policy": name, "profile": prof})
        out.append(r)
    return out


def main():
    n = 2 if QUICK else 10
    jobs = [(p, e, SEED + 300 + s) for p in PROFILES for e in ("hospital", "home", "rural") for s in range(n)]
    with Pool(int(os.environ.get("FLORA_THREADS", os.cpu_count()))) as pool:
        rows = [r for res in pool.map(job, jobs) for r in res]
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "results/03c_profiles.csv"), index=False)
    w = df.pivot_table(index=["profile", "env", "seed"], columns="policy", values="E_total_J")
    for p in POL:
        w[p + " vs Static"] = w[p] / w["Static-Ascon"] - 1
    print(w.groupby(["profile", "env"])[[c for c in w.columns if "vs Static" in c]].mean().round(3))


if __name__ == "__main__":
    main()
