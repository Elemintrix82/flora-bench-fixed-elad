"""Figure: accuracy obtainable from the synthetic file-size feature of the 2026 protocol."""
import json, os
import numpy as np
from figstyle import plt, save, OUT, OKABE
from figlang import _tr
r = json.load(open(os.path.join(OUT, "results/06_label_leak.json")))
lab = ["Valeur publiée (2026)", "Bayes, taille seule", "RF, taille liée à la classe", "RF, taille indépendante"]
val = [r["reported_accuracy_2026"], r["bayes_optimal_accuracy_size_only"],
       r["rf_size_type_label_dependent"]["mean"], r["rf_size_type_independent"]["mean"]]
err = [0, 0, r["rf_size_type_label_dependent"]["sd"], r["rf_size_type_independent"]["sd"]]
fig, ax = plt.subplots(figsize=(3.4, 2.2))
y = np.arange(len(lab))
ax.barh(y, [100 * v for v in val], xerr=[100 * e for e in err], color=[OKABE[6], OKABE[5], OKABE[2], OKABE[3]], height=0.6)
for yi, v in zip(y, val):
    ax.text(100 * v + 1, yi, (f"{100 * v:.1f}".replace(".", ",") if os.environ.get("FIGLANG", "fr") == "fr" else f"{100 * v:.1f}"), va="center", fontsize=7)
ax.axvline(100 * r["majority_class_rate"], color="k", ls="--", lw=0.8)
ax.text(100 * r["majority_class_rate"] + 1, 3.45, "classe majoritaire", fontsize=6.5)
ax.set_yticks(y); ax.set_yticklabels([_tr(x) for x in lab]); ax.invert_yaxis(); ax.set_xlim(0, 105)
ax.set_xlabel("Exactitude (%)"); ax.grid(axis="y", visible=False)
save(fig, "fig_label_leak")
