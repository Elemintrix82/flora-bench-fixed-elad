"""04c_strong_attacker.py - stronger passive adversary: in addition to the features of
experiment 04, it sees the number of frames and bytes sent in the previous 10 s and 60 s and
in the next 10 s (traffic volume around the frame). Same protocol (home, grouped 5-fold CV by
node-day, cluster bootstrap), 60 node-days, and the gain over a time-of-day-only adversary.
Output: outputs/results/04c_strong_attacker.json  (~25 min)"""
import json, os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool

from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora.energy import CryptoCost
from flora.sim import run_day
from flora.traffic import generate, link_trace
from flora import policies as P
from flora.adversary import make_adversary

POLICIES = {"Static-Ascon": lambda: P.StaticImmediate("ascon_armv7m", 16, "Static-Ascon"),
            "Elad2026-rule": P.Elad2026, "FLOOR-E": lambda: P.Floor("FLOOR-E"),
            "FLOOR-L(q16)": lambda: P.Floor("FLOOR-L(q16)", leakage_aware=True, pad="q16"),
            "FLOOR-L(q64)": lambda: P.Floor("FLOOR-L(q64)", leakage_aware=True, pad="q64"),
            "FLOOR-L(q128)": lambda: P.Floor("FLOOR-L(q128)", leakage_aware=True, pad="q128"),
            "FLOOR-C": lambda: P.FloorConstant("FLOOR-C")}
N_DAYS = 10 if QUICK else 60
CRYPTO = None


def window_feats(t, ln):
    cs = np.concatenate([[0], np.cumsum(ln)])
    out = {}
    for w in (10.0, 60.0):
        lo = np.searchsorted(t, t - w, side="left")
        i = np.arange(len(t))
        out[f"n_prev{int(w)}"] = i - lo
        out[f"b_prev{int(w)}"] = cs[i] - cs[lo]
    hi = np.searchsorted(t, t + 10.0, side="right")
    i = np.arange(len(t))
    out["n_next10"] = hi - i - 1
    out["b_next10"] = cs[hi] - cs[i + 1]
    return out


def job(day):
    global CRYPTO
    if CRYPTO is None:
        CRYPTO = CryptoCost()
    seed = SEED + 20_000 + day
    rng = np.random.default_rng(seed)
    recs, trace, batt = generate(rng), link_trace(rng, "home"), rng.uniform(10, 100)
    sub = np.random.default_rng(seed + 1)
    out = {}
    for name, mk in POLICIES.items():
        _, frames = run_day(mk(), "home", seed, CRYPTO, recs=recs, trace=trace, battery=batt, log_frames=True)
        f = pd.DataFrame(frames, columns=["t", "len", "has_V", "has_R", "first_cls", "alg"])
        t, ln = f.t.to_numpy(), f.len.to_numpy(float)
        for k, v in window_feats(t, ln).items():
            f[k] = v
        f["dt_prev"] = f.t.diff().fillna(60.0).clip(upper=600)
        f["dt_next"] = (-f.t.diff(-1)).fillna(60.0).clip(upper=600)
        f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * f.t / 86400), np.cos(2 * np.pi * f.t / 86400)
        f["alg_code"] = f.alg.map({"": 0, "ASCON": 1, "RECTANGLE": 2}).astype(int)
        f["day"] = day
        f["has_RV"] = ((f.has_R + f.has_V) > 0).astype(int)
        kV = (f.has_V == 1) | (sub.random(len(f)) < 0.03)
        kRV = (f.has_RV == 1) & (sub.random(len(f)) < 0.2) | (f.has_RV == 0) & (sub.random(len(f)) < 0.03)
        out[name] = (f[kV].copy(), f[kRV].copy())
    return out


FEATS = ["len", "alg_code", "dt_prev", "dt_next", "hour_sin", "hour_cos",
         "n_prev10", "b_prev10", "n_prev60", "b_prev60", "n_next10", "b_next10"]


def oof(df, feats, label):
    X, y, g = df[feats].to_numpy(float), df[label].to_numpy(int), df.day.to_numpy()
    s = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, g):
        c = make_adversary(SEED).fit(X[tr], y[tr])
        s[te] = c.predict_proba(X[te])[:, 1]
    return s


def boot(y, a, b, g, n=1000):
    rng = np.random.default_rng(SEED); days = np.unique(g); idx = {d: np.where(g == d)[0] for d in days}
    A, D = [], []
    for _ in range(n):
        ii = np.concatenate([idx[d] for d in rng.choice(days, len(days))])
        if y[ii].min() == y[ii].max():
            continue
        x1, x2 = roc_auc_score(y[ii], a[ii]), roc_auc_score(y[ii], b[ii])
        A.append(x2); D.append(x2 - x1)
    q = lambda v: [float(np.quantile(v, .025)), float(np.quantile(v, .975))]
    return q(A), q(D)


def main():
    with Pool(int(os.environ.get("FLORA_THREADS", os.cpu_count()))) as pool:
        parts = pool.map(job, range(N_DAYS))
    res = {}
    for name in POLICIES:
        r = {}
        for lab, i in (("has_V", 0), ("has_RV", 1)):
            d = pd.concat([p[name][i] for p in parts], ignore_index=True)
            y, g = d[lab].to_numpy(int), d.day.to_numpy()
            s_h = oof(d, ["hour_sin", "hour_cos"], lab)
            s_all = oof(d, FEATS, lab)
            ci, cig = boot(y, s_h, s_all, g)
            r[lab] = {"auc_strong": roc_auc_score(y, s_all), "ci": ci, "auc_hour_only": roc_auc_score(y, s_h),
                      "gain_over_hour": roc_auc_score(y, s_all) - roc_auc_score(y, s_h), "ci_gain": cig,
                      "n_pos": int(y.sum()), "n": int(len(y))}
        res[name] = r
        print(name, {k: (round(v["auc_strong"], 3), round(v["gain_over_hour"], 3), [round(x, 3) for x in v["ci_gain"]]) for k, v in r.items()})
    json.dump(res, open(os.path.join(OUT, "results/04c_strong_attacker.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
