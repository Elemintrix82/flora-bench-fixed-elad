"""Figure: energy-latency-deadline trade-off of FLOOR (03b, 10 paired seeds per environment).
(a) energy per node-day (home) vs deadline factor; (b) 95th-percentile latency of N and R
records (FLOOR-E); (c) deadline miss rate of FLOOR-E (all records)."""
import os
import numpy as np, pandas as pd
from figstyle import plt, save, OUT, OKABE, POLICY_COLORS
d = pd.read_csv(os.path.join(OUT, "results/03b_deadline_sensitivity.csv"))
d["miss"] = 100 * (d.miss_N + d.miss_R + d.miss_V) / (d.n_N + d.n_R + d.n_V)
g = d.groupby(["policy", "env", "deadline_factor"]).mean(numeric_only=True).reset_index()
F = [0.2, 0.5, 1.0]
ENV = [("hospital", "Hôpital"), ("home", "Domicile"), ("rural", "Rural")]
COL = {e: OKABE[i + 5 if i < 2 else 3] for i, (e, _) in enumerate(ENV)}
fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.4))
h = g[g.env == "home"]
fe = h[h.policy == "FLOOR-E"].sort_values("deadline_factor")
fl = h[h.policy == "FLOOR-L(q16)"].sort_values("deadline_factor")
axs[0].plot(F, fe.E_static, ls=":", marker="o", ms=3, color=POLICY_COLORS["Static-Ascon"], label="Static-Ascon")
axs[0].plot(F, fe.E_elad, ls=":", marker="o", ms=3, color=POLICY_COLORS["Elad2026-rule"], label="Règle Elad 2026")
axs[0].plot(F, fl.E_total_J, ls="--", marker="s", ms=3, mfc="white", color=POLICY_COLORS["FLOOR-L(q16)"], label="FLOOR-L(q16)")
axs[0].plot(F, fe.E_total_J, marker="o", ms=3, color=POLICY_COLORS["FLOOR-E"], label="FLOOR-E")
axs[0].set_xlabel("Facteur d'échéance"); axs[0].set_ylabel("Énergie par nœud-jour, domicile (J)")
axs[0].set_ylim(0, None); axs[0].legend(frameon=False, loc="lower left"); axs[0].set_title("(a)")
for env, lab in ENV:
    e = g[(g.env == env) & (g.policy == "FLOOR-E")].sort_values("deadline_factor")
    axs[1].plot(F, e.lat_p95_N, marker="o", ms=3, color=COL[env], label=lab)
    axs[1].plot(F, e.lat_p95_R, marker="s", ms=3, ls="--", mfc="white", color=COL[env])
axs[1].plot(F, [5 * f for f in F], color="k", lw=0.7, ls=":", label="échéance N")
axs[1].set_xlabel("Facteur d'échéance"); axs[1].set_ylabel("Latence P95, FLOOR-E (s)")
axs[1].legend(frameon=False, loc="upper left"); axs[1].set_title("(b)")
axs[1].text(0.55, 0.4, "plein : N ; tirets : R", fontsize=6)
for env, lab in ENV:
    e = g[(g.env == env) & (g.policy == "FLOOR-E")].sort_values("deadline_factor")
    axs[2].plot(F, 1000 * e.miss, marker="o", ms=3, color=COL[env], label=lab)
axs[2].set_xlabel("Facteur d'échéance"); axs[2].set_ylabel("Échéances manquées, FLOOR-E (10$^{-3}$ %)")
axs[2].set_ylim(0, None); axs[2].set_title("(c)")
fig.tight_layout(w_pad=0.8)
save(fig, "fig_deadline_tradeoff")
