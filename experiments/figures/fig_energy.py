"""Figure: energy per node-day (mean, 95% bootstrap CI over 20 paired seeds), crypto vs radio."""
import json, os
import numpy as np, pandas as pd
from figstyle import plt, save, OUT, POLICY_COLORS
s = json.load(open(os.path.join(OUT, "results/07_summary.json")))
POL = ["Static-Ascon", "Static-AES-GCM", "Elad2026-rule", "Q-learning (no floor)", "FLOOR-E/no-batch",
       "FLOOR-E", "FLOOR-L(q16)", "FLOOR-L(pow2)"]
ENV = [("hospital", "Hôpital"), ("home", "Domicile"), ("rural", "Rural")]
fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.7))
for ax, (env, lab) in zip(axs, ENV):
    d = s["per_policy"][env]
    y = np.arange(len(POL))
    er = np.array([d[p]["E_radio_J_mean"] for p in POL])
    ec = np.array([d[p]["E_crypto_J_mean"] for p in POL])
    lo = np.array([d[p]["E_total_J_ci95"][0] for p in POL]); hi = np.array([d[p]["E_total_J_ci95"][1] for p in POL])
    ax.barh(y, er, color=[POLICY_COLORS[p] for p in POL], alpha=0.55, label="radio")
    ax.barh(y, ec, left=er, color=[POLICY_COLORS[p] for p in POL], hatch="////", edgecolor="k", lw=0.3, label="cryptographie")
    tot = er + ec
    ax.errorbar(tot, y, xerr=[tot - lo, hi - tot], fmt="none", ecolor="k", elinewidth=0.7, capsize=1.5)
    ax.set_yticks(y); ax.set_yticklabels(POL if env == "hospital" else [])
    ax.invert_yaxis(); ax.set_title(lab); ax.set_xlabel("Énergie par nœud-jour (J)")
    ax.grid(axis="y", visible=False)
h, l = axs[0].get_legend_handles_labels()
from matplotlib.patches import Patch
fig.legend([Patch(facecolor="0.7", alpha=0.55), Patch(facecolor="0.7", hatch="////", edgecolor="k")],
           ["radio", "cryptographie"], loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.55, -0.15))
save(fig, "fig_energy")
