"""06_label_leak_2026.py - re-examines the sensitivity classifier protocol of
Elad et al. (JIS 2026), our previous work.

The protocol generated a synthetic file size from the class label (HIGH
2500 B, MEDIUM 1000 B, LOW 300 B, each x U[0.5, 1.5]; 10% of samples
replaced by U[100, 5000] B) and a file type drawn at random. We measure how
much of the reported accuracy is obtainable from the synthetic size alone:
(i) Bayes-optimal accuracy of the size feature (exact, from the generator
densities), (ii) the same Random Forest (200 trees, depth 20, 5-fold CV) on
size and type only, (iii) the same with the size drawn independently of the
class (no leakage). Class shares follow the paper (27.3/38.0/34.7 %).
Output: outputs/results/06_label_leak.json  (~2 min)
"""
import json, os, sys
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT, SEED, QUICK

BASE = {"HIGH": 2500, "MEDIUM": 1000, "LOW": 300}
SHARE = {"HIGH": 0.273, "MEDIUM": 0.380, "LOW": 0.347}
N_TOTAL = 193155


def gen(rng, n, leak=True):
    cls = rng.choice(3, n, p=list(SHARE.values()))
    base = np.array(list(BASE.values()))[cls]
    size = base * rng.uniform(0.5, 1.5, n)
    rnd = rng.random(n) < 0.10
    size[rnd] = rng.uniform(100, 5000, rnd.sum())
    if not leak:
        size = rng.permutation(size)
    ftype = rng.integers(0, 5, n)
    return np.c_[np.log(size), ftype], cls


def bayes_accuracy():
    """Exact Bayes accuracy of the size feature under the generator."""
    xs = np.linspace(100, 5000, 490001)
    dens = []
    for c, b in BASE.items():
        u = ((xs >= 0.5 * b) & (xs <= 1.5 * b)) / b          # U[0.5b, 1.5b]
        r = 1.0 / 4900                                        # U[100, 5000]
        dens.append(SHARE[c] * (0.9 * u + 0.1 * r))
    dens = np.array(dens)
    dx = xs[1] - xs[0]
    return float(dens.max(axis=0).sum() * dx)


def main():
    rng = np.random.default_rng(SEED)
    n = 30000 if QUICK else N_TOTAL
    res = {"bayes_optimal_accuracy_size_only": bayes_accuracy(),
           "majority_class_rate": max(SHARE.values())}
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    for leak in (True, False):
        X, y = gen(rng, n, leak)
        rf = RandomForestClassifier(n_estimators=200, max_depth=20, n_jobs=-1, random_state=SEED)
        acc = cross_val_score(rf, X, y, cv=cv, scoring="accuracy")
        res[f"rf_size_type_{'label_dependent' if leak else 'independent'}"] = {
            "mean": float(acc.mean()), "sd": float(acc.std(ddof=1)), "folds": acc.tolist()}
    res["reported_accuracy_2026"] = 0.924
    json.dump(res, open(os.path.join(OUT, "results/06_label_leak.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
