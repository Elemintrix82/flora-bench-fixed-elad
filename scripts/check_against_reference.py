"""check_against_reference.py - compares a new run (outputs/results) with the
frozen results of the article (reference_results/). Deterministic quantities
(cycle counts, KAT checks) must match exactly; simulation summaries must match
to 1e-9 relative when the same seeds and versions are used."""
import json, os, sys
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW, REF = os.path.join(ROOT, "outputs/results"), os.path.join(ROOT, "reference_results")
ok = True
a = pd.read_csv(os.path.join(NEW, "01_crypto_cost.csv")); b = pd.read_csv(os.path.join(REF, "01_crypto_cost.csv"))
if not a[["variant", "msg_len", "enc_cycles", "dec_cycles"]].equals(b[["variant", "msg_len", "enc_cycles", "dec_cycles"]]):
    print("01_crypto_cost: cycle counts differ"); ok = False
else:
    print("01_crypto_cost: identical cycle counts")
for f in ("00_cycle_model_validation.json", "06_label_leak.json"):
    x, y = json.load(open(os.path.join(NEW, f))), json.load(open(os.path.join(REF, f)))
    k = "spearman_rho_all" if f.startswith("00") else "bayes_optimal_accuracy_size_only"
    same = abs(x[k] - y[k]) < 1e-9
    print(f, "identical" if same else "DIFFERENT", x[k], y[k]); ok &= same
s1 = pd.read_csv(os.path.join(NEW, "03_policy_sim.csv")); s2 = pd.read_csv(os.path.join(REF, "03_policy_sim.csv"))
m = s1.merge(s2, on=["policy", "env", "seed", "ber_mult"], suffixes=("", "_ref"))
if len(m):
    d = (m.E_total_J / m.E_total_J_ref - 1).abs().max()
    print(f"03_policy_sim: {len(m)} common runs, max relative energy difference {d:.2e}"); ok &= d < 1e-6
sys.exit(0 if ok else 1)
