"""04b_leakage_prior.py - separates the attacker's prior knowledge from protocol leakage.

On the V-detection data of experiment 04 (same frames, same folds), trains the same
gradient-boosting attacker on the time of day only (prior: when V events usually
happen) and on time of day + frame length. The difference with the time-only
attacker is the information added by the protocol's observable length.
Output: outputs/results/04b_leakage_prior.json  (~10 min)"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED
from flora.adversary import make_adversary
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score


def oof_auc(X, y, g):
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, g):
        clf = make_adversary(SEED)
        clf.fit(X[tr], y[tr]); oof[te] = clf.predict_proba(X[te])[:, 1]
    return oof


def cluster_boot_diff(y, a, b, g, n=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    days = np.unique(g); idx = {d: np.where(g == d)[0] for d in days}
    ra, rb, rd = [], [], []
    for _ in range(n):
        ii = np.concatenate([idx[d] for d in rng.choice(days, len(days))])
        if y[ii].min() == y[ii].max():
            continue
        x1, x2 = roc_auc_score(y[ii], a[ii]), roc_auc_score(y[ii], b[ii])
        ra.append(x1); rb.append(x2); rd.append(x2 - x1)
    q = lambda v: [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]
    return q(ra), q(rb), q(rd)


def main():
    df = pd.read_csv(os.path.join(OUT, "results/04_leakage_oof.csv"))
    res = {}
    for pol, d in df.groupby("policy"):
        y, g = d.has_V.to_numpy(int), d.day.to_numpy()
        h = np.c_[np.sin(2 * np.pi * d.t / 86400), np.cos(2 * np.pi * d.t / 86400)]
        s_hour = oof_auc(h, y, g)
        s_hl = oof_auc(np.c_[h, d.len.to_numpy(float)], y, g)
        ci_h, ci_hl, ci_d = cluster_boot_diff(y, s_hour, s_hl, g)
        res[pol] = {"auc_hour_only": roc_auc_score(y, s_hour), "ci_hour_only": ci_h,
                    "auc_hour_length": roc_auc_score(y, s_hl), "ci_hour_length": ci_hl,
                    "auc_gain_from_length": roc_auc_score(y, s_hl) - roc_auc_score(y, s_hour), "ci_gain": ci_d}
        print(pol, {k: (round(v, 3) if isinstance(v, float) else [round(x, 3) for x in v]) for k, v in res[pol].items()})
    json.dump(res, open(os.path.join(OUT, "results/04b_leakage_prior.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
