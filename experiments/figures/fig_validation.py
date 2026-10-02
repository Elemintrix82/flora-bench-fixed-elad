"""Figure: modelled vs measured ChaChaPoly units (28 AEADs x 4 cases)."""
import json, os
import numpy as np
from figstyle import plt, save, OUT, OKABE
r = json.load(open(os.path.join(OUT, "results/00_cycle_model_validation.json")))
fig, ax = plt.subplots(figsize=(3.4, 3.0))
lab = {"enc128": "chiffrer 128 o", "dec128": "déchiffrer 128 o", "enc16": "chiffrer 16 o", "dec16": "déchiffrer 16 o"}
mk = {"enc128": "o", "dec128": "s", "enc16": "^", "dec16": "v"}
for i, case in enumerate(lab):
    pts = [p for p in r["points"] if p["case"] == case]
    ax.scatter([p["measured"] for p in pts], [p["model"] for p in pts], s=10, marker=mk[case],
               color=OKABE[i + 1], label=lab[case], alpha=0.85, linewidths=0)
lim = [0.008, 5]
ax.plot(lim, lim, color="k", lw=0.8)
ax.fill_between(lim, [l / 1.35 for l in lim], [l * 1.35 for l in lim], color="0.85", zorder=0)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel("Unités ChaChaPoly mesurées (Arduino Due)")
ax.set_ylabel("Unités ChaChaPoly modélisées")
ax.text(0.012, 2.2, f"ρ = {r['spearman_rho_all']:.3f}\nn = {r['n_points']}", fontsize=7)
ax.legend(loc="lower right", frameon=False)
save(fig, "fig_validation")
