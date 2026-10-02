"""Figure: attacker AUC (95% cluster-bootstrap CI) for V and R-or-V frames, full attacker vs
length-only attacker, and energy per node-day (home) of the same policies."""
import json, os
import numpy as np
from figstyle import plt, save, OUT, POLICY_COLORS
from figlang import _tr
s = json.load(open(os.path.join(OUT, "results/07_summary.json")))
L = s["leakage"]
POL = [p for p in ["Static-Ascon", "Elad2026-rule", "FLOOR-E", "FLOOR-L(q16)", "FLOOR-L(pow2)", "FLOOR-L(q64)", "FLOOR-L(q128)", "FLOOR-C"] if p in L]
POLICY_COLORS.setdefault("FLOOR-C", "#8c564b")
fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.4), gridspec_kw={"width_ratios": [1.2, 1.2, 1]})
y = np.arange(len(POL))
for ax, key, title in ((axs[0], "V_detection", "AUC de l'attaquant (trames V)"),
                       (axs[1], "RV_detection", "AUC de l'attaquant (trames R ou V)")):
    m = np.array([L[p][key]["auc"] for p in POL])
    lo = np.array([L[p][key]["ci95"][0] for p in POL]); hi = np.array([L[p][key]["ci95"][1] for p in POL])
    ax.errorbar(m, y, xerr=[m - lo, hi - m], fmt="o", ms=3.5, color="k", ecolor="k", elinewidth=0.8, capsize=1.5, label="toutes variables")
    if key == "V_detection":
        ml = np.array([L[p]["V_detection_length_only"]["auc"] for p in POL])
        ax.plot(ml, y, "s", ms=3.5, mfc="white", mec="k", label="longueur seule")
        pr = s.get("04b_leakage_prior", {})
        mh = np.array([pr[p]["auc_hour_only"] if p in pr else np.nan for p in POL])
        ax.plot(mh, y, "^", ms=3.5, color="#D55E00", label="heure seule (a priori)")
    ax.axvline(0.5, color="0.4", ls="--", lw=0.8)
    ax.set_xlim(0.45, 1.02); ax.set_xlabel(title)
    ax.set_yticks(y); ax.set_yticklabels(POL if ax is axs[0] else [])
    ax.invert_yaxis(); ax.grid(axis="y", visible=False)
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.45, 1.08))
e = s["per_policy"]["home"]
axs[2].barh(y, [e[p]["E_total_J_mean"] for p in POL], color=[POLICY_COLORS.get(p, "0.5") for p in POL], height=0.6)
axs[2].set_yticks(y); axs[2].set_yticklabels([]); axs[2].invert_yaxis(); axs[2].grid(axis="y", visible=False)
axs[2].set_xlabel("Énergie par nœud-jour (J)")
save(fig, "fig_leakage")
