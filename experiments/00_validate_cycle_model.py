"""00_validate_cycle_model.py - validates the Cortex-M cycle model.

Rebuilds the 28-algorithm benchmark set of the lwc-finalists library for
Cortex-M3 (-Os), runs it in flora.m4emu and compares the modelled speed ratios
("ChaChaPoly units") with the values measured by the library author on an
Arduino Due (reference_data/due_chachapoly_units.csv).
Output: outputs/results/00_cycle_model_validation.json  (~2 min)
"""
import json, os, sys
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.m4emu import M4Emu
from flora.config import OUT, ROOT

ORDER = ["ChaChaPoly", "Schwaemm128-128", "Xoodyak", "Schwaemm256-128", "Schwaemm192-192", "ASCON-128a",
         "ASCON-128", "ASCON-80pq", "Schwaemm256-256", "TinyJAMBU-128", "GIFT-COFB", "TinyJAMBU-192",
         "TinyJAMBU-256", "Grain-128AEAD", "AES-128-GCM", "AES-192-GCM", "AES-256-GCM", "Romulus-N",
         "Delirium", "PHOTON-Beetle-128", "Romulus-M", "ISAP-A-128A", "Romulus-T", "PHOTON-Beetle-32",
         "ISAP-A-128", "ISAP-K-128A", "Dumbo", "Jumbo", "ISAP-K-128"]


def main():
    emu = M4Emu(os.path.join(ROOT, "firmware/build/val_due_m3_Os.elf"))
    rng = np.random.default_rng(0)
    emu.write("K", rng.bytes(32)); emu.write("N", rng.bytes(32))
    cyc = {}
    for i, name in enumerate(ORDER):
        emu.write_u32("g_alg", i)
        row = {}
        for L in (128, 16):
            emu.write("M", rng.bytes(L)); emu.write_u32("g_mlen", L)
            e = emu.call("bench_enc"); d = emu.call("bench_dec")
            assert d.ret == 0, f"{name}: decryption failed"
            row[f"enc{L}"], row[f"dec{L}"] = e.cycles, d.cycles
        cyc[name] = row
    ref = pd.read_csv(os.path.join(ROOT, "reference_data/due_chachapoly_units.csv")).set_index("algorithm")
    rows = []
    for name in ORDER[1:]:
        for col in ("enc128", "dec128", "enc16", "dec16"):
            model_units = cyc["ChaChaPoly"][col] / cyc[name][col]
            rows.append({"algorithm": name, "case": col, "model": model_units, "measured": ref.loc[name, col]})
    df = pd.DataFrame(rows)
    df["log_ratio"] = np.log(df.model / df.measured)
    rho = stats.spearmanr(df.model, df.measured)
    r_log = stats.pearsonr(np.log(df.model), np.log(df.measured))
    avg = df.groupby("algorithm")[["model", "measured"]].mean()
    rho_avg = stats.spearmanr(avg.model, avg.measured)
    res = {
        "n_points": len(df), "n_algorithms": len(avg),
        "spearman_rho_all": rho.statistic, "spearman_p_all": rho.pvalue,
        "pearson_r_log_all": r_log.statistic,
        "spearman_rho_avg": rho_avg.statistic,
        "median_abs_rel_error": float(np.median(np.abs(df.model / df.measured - 1))),
        "p90_abs_rel_error": float(np.quantile(np.abs(df.model / df.measured - 1), 0.9)),
        "geo_mean_ratio_model_over_measured": float(np.exp(df.log_ratio.mean())),
        "cycles": cyc, "points": df.to_dict(orient="records"),
    }
    os.makedirs(os.path.join(OUT, "results"), exist_ok=True)
    with open(os.path.join(OUT, "results/00_cycle_model_validation.json"), "w") as f:
        json.dump(res, f, indent=1)
    print({k: v for k, v in res.items() if k not in ("cycles", "points")})


if __name__ == "__main__":
    main()
