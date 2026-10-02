"""Figure: energy of one frame vs application payload: radio (per PHY, BER of the
link state, ARQ) and AEAD computation (per algorithm, Cortex-M4 model)."""
import os, sys
import numpy as np
from figstyle import plt, save, OUT, OKABE
from flora import energy as en
from flora.traffic import LINK_BER
from flora.policies import REC_HDR   # 2-byte record header, counted as in the simulator
cc = en.CryptoCost()
L = np.unique(np.round(np.logspace(np.log10(8), np.log10(4000), 40)).astype(int))
fig, ax = plt.subplots(figsize=(3.4, 2.7))
for phy, st, col in (("2M", "good", OKABE[5]), ("1M", "fair", OKABE[2]), ("S8", "poor", OKABE[6])):
    e = [en.expected_radio_energy(phy, int(l) + REC_HDR + 5 + 16, LINK_BER[st])[0] * 1e6 for l in L]
    ax.plot(L, e, color=col, label=f"radio {phy}")
for v, lab, ls in (("ascon_armv7m", "Ascon-AEAD128", "--"), ("aesgcm", "AES-128-GCM", "-."),
                   ("rectangle_ctr_hmac", "RECTANGLE-CTR+HMAC", ":")):
    ax.plot(L, [cc.energy(v, int(l) + REC_HDR) * 1e6 for l in L], color="k", ls=ls, label=lab)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Charge utile applicative (octets)"); ax.set_ylabel("Énergie par trame (µJ)")
ax.legend(frameon=False, fontsize=6.2, loc="upper left")
save(fig, "fig_frame_energy")
