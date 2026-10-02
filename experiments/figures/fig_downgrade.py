"""Figure: protection applied to R and V records without and under jamming (06:00-22:00)."""
import json, os
import numpy as np
from figstyle import plt, save, OUT
from figlang import _tr
d = json.load(open(os.path.join(OUT, "results/05_downgrade.json")))
POL = ["Elad2026-rule", "Q-learning (no floor)", "FLOOR-E", "FLOOR-L(q16)"]
FLOOR_BITS = {"R": 128, "V": 128}
APPROVED = {"ascon_armv7m", "aesgcm", "chacha20poly1305"}
def split(prot, cls):
    tot = sum(prot.values()) or 1
    below = sum(v for k, v in prot.items() if int(k.split("/")[1]) < FLOOR_BITS[cls])
    nonstd = sum(v for k, v in prot.items() if int(k.split("/")[1]) >= FLOOR_BITS[cls] and k.split("/")[0] not in APPROVED)
    return 100 * below / tot, 100 * nonstd / tot, 100 * (tot - below - nonstd) / tot
fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.5), sharey=True)
for ax, cls in zip(axs, ("R", "V")):
    labels, B, N, C = [], [], [], []
    for p in POL:
        for cond, cl in (("clean", "sans attaque"), ("attack", "sous brouillage")):
            b, n, c = split(d[p][cond][f"protection_{cls}"], cls)
            labels.append(f"{p}\n{_tr(cl)}"); B.append(b); N.append(n); C.append(c)
    x = np.arange(len(labels))
    ax.bar(x, C, color="#009E73", label=_tr("conforme"))
    ax.bar(x, N, bottom=C, color="#E69F00", label=_tr("algorithme hors ensemble autorisé"))
    ax.bar(x, B, bottom=np.array(C) + np.array(N), color="#D55E00", label=_tr("sous le plancher"))
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=90, fontsize=5.8)
    ax.set_title(_tr("Enregistrements R") if cls == "R" else _tr("Enregistrements V"))
    ax.grid(axis="x", visible=False)
axs[0].set_ylabel("Part des enregistrements (%)")
h, l = axs[1].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.08))
save(fig, "fig_downgrade")
