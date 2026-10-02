"""04_leakage.py - traffic-analysis attacker against each framing policy.

A passive eavesdropper sees, per frame: length on air, visible algorithm id
(Elad2026 only), time gaps to the previous/next frame and time of day. It
trains a gradient-boosting classifier to decide whether a frame carries
V-class (very restricted) data, and separately R-or-V data. Grouped 5-fold CV
by node-day; AUC with a cluster bootstrap 95% CI (2000 resamples of node-days).
Negatives are subsampled (AUC is invariant to the class ratio).
Output: outputs/results/04_leakage.json, 04_leakage_oof.csv  (~15 min)
"""
import json, os, sys
import numpy as np, pandas as pd
from multiprocessing import Pool

from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK
from flora.energy import CryptoCost
from flora.sim import run_day
from flora.traffic import generate, link_trace
from flora import policies as P
from flora.adversary import make_adversary

POLICIES = {
    "Static-Ascon": lambda: P.StaticImmediate("ascon_armv7m", 16, "Static-Ascon"),
    "Elad2026-rule": lambda: P.Elad2026(),
    "FLOOR-E": lambda: P.Floor("FLOOR-E"),
    "FLOOR-L(q16)": lambda: P.Floor("FLOOR-L(q16)", leakage_aware=True, pad="q16"),
    "FLOOR-L(pow2)": lambda: P.Floor("FLOOR-L(pow2)", leakage_aware=True, pad="pow2"),
    "FLOOR-L(q64)": lambda: P.Floor("FLOOR-L(q64)", leakage_aware=True, pad="q64"),
    "FLOOR-L(q128)": lambda: P.Floor("FLOOR-L(q128)", leakage_aware=True, pad="q128"),
    "FLOOR-C": lambda: P.FloorConstant("FLOOR-C"),
}
ONLY = [x for x in os.environ.get("FLORA_ONLY", "").split(",") if x]
if ONLY:
    POLICIES = {k: v for k, v in POLICIES.items() if k in ONLY}
N_DAYS = 16 if QUICK else 120
NEG_KEEP = 0.03
CRYPTO = None


def job(day):
    global CRYPTO
    if CRYPTO is None:
        CRYPTO = CryptoCost()
    seed = SEED + 10_000 + day
    rng = np.random.default_rng(seed)
    recs, trace, batt = generate(rng), link_trace(rng, "home"), rng.uniform(10, 100)
    out = {}
    sub = np.random.default_rng(seed + 1)
    for name, mk in POLICIES.items():
        _, frames = run_day(mk(), "home", seed, CRYPTO, recs=recs, trace=trace, battery=batt, log_frames=True)
        f = pd.DataFrame(frames, columns=["t", "len", "has_V", "has_R", "first_cls", "alg"])
        f["dt_prev"] = f.t.diff().fillna(60.0).clip(upper=600)
        f["dt_next"] = (-f.t.diff(-1)).fillna(60.0).clip(upper=600)
        f["hour_sin"] = np.sin(2 * np.pi * f.t / 86400)
        f["hour_cos"] = np.cos(2 * np.pi * f.t / 86400)
        f["alg_code"] = f.alg.map({"": 0, "ASCON": 1, "RECTANGLE": 2}).astype(int)
        f["day"] = day
        f["has_RV"] = ((f.has_R + f.has_V) > 0).astype(int)
        keep_V = (f.has_V == 1) | (sub.random(len(f)) < NEG_KEEP)
        keep_RV = (f.has_RV == 1) & (sub.random(len(f)) < 0.2) | (f.has_RV == 0) & (sub.random(len(f)) < NEG_KEEP)
        out[name] = (f[keep_V].copy(), f[keep_RV].copy())
    return out


FEATS = ["len", "alg_code", "dt_prev", "dt_next", "hour_sin", "hour_cos"]


def attack(df, label, seed):
    X, y, g = df[FEATS].to_numpy(float), df[label].to_numpy(int), df.day.to_numpy()
    oof = np.zeros(len(df))
    for tr, te in GroupKFold(5).split(X, y, g):
        clf = make_adversary(seed)
        clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]
    auc = roc_auc_score(y, oof)
    rng = np.random.default_rng(seed)
    days = np.unique(g)
    idx_by_day = {d: np.where(g == d)[0] for d in days}
    boots = []
    for _ in range(2000):
        pick = rng.choice(days, len(days))
        ii = np.concatenate([idx_by_day[d] for d in pick])
        if y[ii].min() == y[ii].max():
            continue
        boots.append(roc_auc_score(y[ii], oof[ii]))
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return {"auc": auc, "ci95": [lo, hi], "n_pos": int(y.sum()), "n": int(len(y)),
            "ap": float(average_precision_score(y, oof)), "prevalence_in_sample": float(y.mean())}, oof


def main():
    with Pool(int(os.environ.get("FLORA_THREADS", os.cpu_count()))) as pool:
        parts = pool.map(job, range(N_DAYS))
    res, oofs = {}, []
    for name in POLICIES:
        dV = pd.concat([p[name][0] for p in parts], ignore_index=True)
        dRV = pd.concat([p[name][1] for p in parts], ignore_index=True)
        rV, oV = attack(dV, "has_V", SEED)
        rRV, _ = attack(dRV, "has_RV", SEED)
        # ablation: attacker restricted to frame length only
        rVlen, _ = attack(dV.assign(alg_code=0, dt_prev=0, dt_next=0, hour_sin=0, hour_cos=0), "has_V", SEED)
        res[name] = {"V_detection": rV, "RV_detection": rRV, "V_detection_length_only": rVlen}
        oofs.append(dV.assign(policy=name, score=oV)[["policy", "day", "t", "len", "has_V", "score"]])
        print(name, round(rV["auc"], 3), rV["ci95"], "RV", round(rRV["auc"], 3), "lenonly", round(rVlen["auc"], 3))
    jpath, opath = os.path.join(OUT, "results/04_leakage.json"), os.path.join(OUT, "results/04_leakage_oof.csv")
    oof = pd.concat(oofs)
    if ONLY and os.path.exists(jpath):
        old = json.load(open(jpath)); old.update(res); res = old
        oo = pd.read_csv(opath); oof = pd.concat([oo[~oo.policy.isin(ONLY)], oof])
    json.dump(res, open(jpath, "w"), indent=1)
    oof.to_csv(opath, index=False)


if __name__ == "__main__":
    main()
