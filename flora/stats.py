"""stats.py - paired statistics used in the article."""
from __future__ import annotations
import numpy as np
from scipy import stats


def boot_ci(x, fn=np.mean, n=2000, seed=0, alpha=0.05):
    rng = np.random.default_rng(seed)
    x = np.asarray(x)
    b = [fn(x[rng.integers(0, len(x), len(x))]) for _ in range(n)]
    return float(np.quantile(b, alpha / 2)), float(np.quantile(b, 1 - alpha / 2))


def paired_saving(e_new, e_ref, seed=0):
    """Relative energy change (new/ref - 1) per paired run: mean, 95% bootstrap CI,
    Wilcoxon signed-rank p-value on the paired differences."""
    e_new, e_ref = np.asarray(e_new), np.asarray(e_ref)
    r = e_new / e_ref - 1.0
    w = stats.wilcoxon(e_new, e_ref)
    return {"mean_rel_change": float(r.mean()), "ci95": boot_ci(r, seed=seed),
            "median_rel_change": float(np.median(r)), "wilcoxon_p": float(w.pvalue), "n": int(len(r))}


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out
