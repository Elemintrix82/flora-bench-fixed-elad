"""03d_guard_sensitivity.py - sensitivity of the main result to the BLE connection interval
T_CI and to the two coefficients of the FLOOR flush guard g = g0 + k * t_air + T_CI.
One parameter is changed at a time around the reference (g0 = 0.3 s, k = 4, T_CI = 50 ms).
10 paired seeds x 3 environments x BER multiplier {1, 10}; policies FLOOR-E, Static-Ascon,
Elad2026-rule (the latter two only depend on T_CI, through latency).
Output: outputs/results/03d_guard_sensitivity.csv  (~4 min on two cores)"""
import os, sys, time
import numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora.energy import CryptoCost
from flora import sim
from flora.traffic import generate, link_trace
from flora import policies as P

REF = {"g0": 0.3, "k": 4.0, "tci": 0.05}
CONFIGS = [dict(REF)] + [dict(REF, tci=v) for v in (0.015, 0.1)] + \
          [dict(REF, g0=v) for v in (0.1, 0.5)] + [dict(REF, k=v) for v in (2.0, 6.0)]
POLS = {"FLOOR-E": lambda: P.Floor("FLOOR-E"),
        "Static-Ascon": lambda: P.StaticImmediate("ascon_armv7m", 16, "Static-Ascon"),
        "Elad2026-rule": lambda: P.Elad2026()}
CRYPTO = None


def job(args):
    global CRYPTO
    if CRYPTO is None:
        CRYPTO = CryptoCost()
    cfg, env, seed, ber = args
    sim.GUARD_BASE, sim.GUARD_K, sim.CONN_INTERVAL = cfg["g0"], cfg["k"], cfg["tci"]
    rng = np.random.default_rng(seed)
    recs = generate(rng); trace = link_trace(rng, env); battery = rng.uniform(10, 100)
    out = []
    for name, mk in POLS.items():
        r = sim.run_day(mk(), env, seed, CRYPTO, ber_mult=ber, recs=recs, trace=trace, battery=battery)
        r.update(policy=name, g0=cfg["g0"], k=cfg["k"], tci=cfg["tci"])
        out.append(r)
    return out


def main():
    n = 2 if QUICK else 10
    jobs = [(c, env, SEED + s, ber) for c in CONFIGS for env in ("hospital", "home", "rural")
            for s in range(n) for ber in (1.0, 10.0)]
    t0 = time.time()
    with Pool(int(os.environ.get("FLORA_THREADS", os.cpu_count()))) as pool:
        rows = [r for res in pool.imap_unordered(job, jobs) for r in res]
    df = pd.DataFrame(rows)
    os.makedirs(os.path.join(OUT, "results"), exist_ok=True)
    df.to_csv(os.path.join(OUT, "results/03d_guard_sensitivity.csv"), index=False)
    print(f"{len(df)} runs in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
