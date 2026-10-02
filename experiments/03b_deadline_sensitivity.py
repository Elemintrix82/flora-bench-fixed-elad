"""03b_deadline_sensitivity.py - FLOOR savings as a function of the deadline slack.
All deadlines are multiplied by f in {0.2, 0.5, 1}; 10 paired seeds per environment.
Output: outputs/results/03b_deadline_sensitivity.csv  (~5 min)"""
import os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora.energy import CryptoCost
from flora.sim import run_day
from flora.traffic import generate, link_trace
from flora import policies as P
CRYPTO = None


def job(args):
    global CRYPTO
    if CRYPTO is None:
        CRYPTO = CryptoCost()
    env, seed = args
    rng = np.random.default_rng(seed)
    recs, trace, batt = generate(rng), link_trace(rng, env), rng.uniform(10, 100)
    rows = []
    base = run_day(P.StaticImmediate("ascon_armv7m", 16, "Static-Ascon"), env, seed, CRYPTO, recs=recs, trace=trace, battery=batt)
    elad = run_day(P.Elad2026(), env, seed, CRYPTO, recs=recs, trace=trace, battery=batt)
    for f in (0.2, 0.5, 1.0):
        r2 = recs.copy(); r2["deadline"] = r2["deadline"] * f
        for mk in (lambda: P.Floor("FLOOR-E"), lambda: P.Floor("FLOOR-L(q16)", leakage_aware=True, pad="q16")):
            o = run_day(mk(), env, seed, CRYPTO, recs=r2, trace=trace, battery=batt)
            o.update({"deadline_factor": f, "E_static": base["E_total_J"], "E_elad": elad["E_total_J"]})
            rows.append(o)
    return rows


def main():
    n = 3 if QUICK else 10
    jobs = [(e, SEED + s) for e in ("hospital", "home", "rural") for s in range(n)]
    with Pool(int(os.environ.get("FLORA_THREADS", os.cpu_count()))) as pool:
        rows = [r for res in pool.map(job, jobs) for r in res]
    df = pd.DataFrame(rows)
    df["rel_vs_static"] = df.E_total_J / df.E_static - 1
    df["rel_vs_elad"] = df.E_total_J / df.E_elad - 1
    df.to_csv(os.path.join(OUT, "results/03b_deadline_sensitivity.csv"), index=False)
    print(df.groupby(["env", "policy", "deadline_factor"])[["rel_vs_static", "rel_vs_elad"]].mean().round(3))


if __name__ == "__main__":
    main()
