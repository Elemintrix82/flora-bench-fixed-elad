"""Figure: (a) energy change when FLOOR-E uses another AEAD; (b) BER sensitivity.
(The deadline sensitivity moved to fig_deadline_tradeoff.py.)"""
import json, os
import numpy as np
from figstyle import plt, save, OUT, OKABE
s = json.load(open(os.path.join(OUT, "results/07_summary.json")))
fig, axs = plt.subplots(1, 2, figsize=(6.0, 2.5), gridspec_kw={"width_ratios": [1.35, 1]})
C = ["FLOOR-E/Xoodyak", "FLOOR-E/ChaCha20-Poly1305", "FLOOR-E/GIFT-COFB", "FLOOR-E/AES-GCM", "FLOOR-E/RECTANGLE-CTR+HMAC"]
lbl = [c.split("/")[1] for c in C]
ENV = [("hospital", "Hôpital"), ("home", "Domicile"), ("rural", "Rural")]
w = 0.26
for i, (env, lab) in enumerate(ENV):
    d = s["cipher_ablation"][env]
    m = np.array([100 * d[c]["mean_rel_change"] for c in C])
    lo = np.array([100 * d[c]["ci95"][0] for c in C]); hi = np.array([100 * d[c]["ci95"][1] for c in C])
    x = np.arange(len(C)) + (i - 1) * w
    axs[0].bar(x, m, w, color=OKABE[i + 5 if i < 2 else 3], label=lab)
    axs[0].errorbar(x, m, yerr=[m - lo, hi - m], fmt="none", ecolor="k", elinewidth=0.6, capsize=1.2)
axs[0].set_xticks(np.arange(len(C))); axs[0].set_xticklabels(lbl, rotation=25, ha="right")
axs[0].set_ylabel("Écart d'énergie vs FLOOR-E (%)"); axs[0].legend(frameon=False)
axs[0].set_title("(a)")
for i, (env, lab) in enumerate(ENV):
    sens = s["sensitivity"][env]
    main = s["per_policy"][env]
    xs = [0.1, 1.0, 10.0]
    ys = [100 * sens["0.1"]["FLOOR-E_vs_Elad_rel"], 100 * s["primary"][f"{env}:FLOOR-E_vs_Elad2026"]["mean_rel_change"],
          100 * sens["10.0"]["FLOOR-E_vs_Elad_rel"]]
    axs[1].plot(xs, ys, marker="o", ms=3, color=OKABE[i + 5 if i < 2 else 3], label=lab)
axs[1].set_xscale("log"); axs[1].set_xlabel("Multiplicateur du TEB")
axs[1].set_ylabel("FLOOR-E vs règle Elad 2026 (%)"); axs[1].set_title("(b)")
axs[1].axhline(0, color="k", lw=0.6)
fig.tight_layout(w_pad=0.8)
save(fig, "fig_cipher_sens")
