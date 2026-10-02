"""Common matplotlib style: serif, 7-8 pt, Okabe-Ito palette, vector PDF + PNG preview."""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from flora.config import OUT
from figlang import translate_figure, LANG

OKABE = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]
POLICY_COLORS = {
    "Static-Ascon": "#56B4E9", "Static-AES-GCM": "#0072B2", "Elad2026-rule": "#D55E00",
    "Q-learning (no floor)": "#CC79A7", "FLOOR-E": "#009E73", "FLOOR-L(q16)": "#E69F00",
    "FLOOR-L(pow2)": "#F0E442", "FLOOR-E/no-batch": "#999999", "FLOOR-E/explicit-nonce": "#666666",
    "FLOOR-L(q64)": "#b07a00", "FLOOR-L(q128)": "#7a5200", "FLOOR-C": "#8c564b",
}
plt.rcParams.update({
    "font.family": "serif", "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
    "legend.fontsize": 6.8, "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.grid": True,
    "grid.alpha": 0.25, "grid.linewidth": 0.5, "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "lines.linewidth": 1.2,
})
FIG_DIR = os.path.join(OUT, "figures")
os.makedirs(FIG_DIR, exist_ok=True)


def save(fig, name):
    translate_figure(fig)
    suffix = "" if LANG == "fr" else "_en"
    fig.savefig(os.path.join(FIG_DIR, f"{name}{suffix}.pdf"))
    fig.savefig(os.path.join(FIG_DIR, f"{name}{suffix}.png"), dpi=200)
    plt.close(fig)
