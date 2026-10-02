"""Figure: modelled Cortex-M4 cycles vs message length for each AEAD (AD = 16 B)."""
import os
import pandas as pd
from figstyle import plt, save, OUT, OKABE
d = pd.read_csv(os.path.join(OUT, "results/01_crypto_cost.csv"))
order = ["ascon_armv7m", "xoodyak", "chacha20poly1305", "ascon_ref", "giftcofb", "aesgcm", "rectangle_ctr_hmac"]
COLS = ["#E69F00", "#56B4E9", "#009E73", "#000000", "#0072B2", "#D55E00", "#CC79A7"]
fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.8))
for i, v in enumerate(order):
    g = d[d.variant == v].sort_values("msg_len")
    lab = g.label.iloc[0]
    g0 = g[g.msg_len >= 8]
    axs[0].plot(g0.msg_len, g0.enc_cycles, marker="o", ms=2.5, color=COLS[i], label=lab)
    gg = g[g.msg_len >= 16]
    axs[1].plot(gg.msg_len, gg.enc_cycles / gg.msg_len, marker="o", ms=2.5, color=COLS[i], label=lab)
for ax in axs:
    ax.set_xscale("log", base=2); ax.set_xlabel("Taille du message (octets)")
axs[0].set_yscale("log"); axs[0].set_ylabel("Cycles (modèle Cortex-M4)")
axs[1].set_yscale("log"); axs[1].set_ylabel("Cycles par octet")
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.24))
save(fig, "fig_crypto_cost")
