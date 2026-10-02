"""07_summarise.py - statistics and tables from the raw results of experiments 00-06.
Primary comparisons (defined before running): FLOOR-E vs Elad2026-rule and
FLOOR-L(q16) vs Elad2026-rule, total energy per node-day, per environment,
Wilcoxon signed-rank on 20 paired seeds, Holm correction over the 6 tests.
Other comparisons are descriptive.
Output: outputs/results/07_summary.json"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.config import OUT
from flora.stats import paired_saving, holm, boot_ci

R = os.path.join(OUT, "results")


def main():
    df = pd.read_csv(os.path.join(R, "03_policy_sim.csv"))
    main_ = df[df.ber_mult == 1.0]
    out = {"per_policy": {}, "vs_static_ascon": {}, "primary": {}, "cipher_ablation": {}, "sensitivity": {}}
    for (env, pol), g in main_.groupby(["env", "policy"]):
        d = out["per_policy"].setdefault(env, {})
        n = {c: g[f"n_{c}"].sum() for c in "NRV"}
        d[pol] = {
            "E_total_J_mean": g.E_total_J.mean(), "E_total_J_ci95": boot_ci(g.E_total_J),
            "E_crypto_J_mean": g.E_crypto_J.mean(), "E_radio_J_mean": g.E_radio_J.mean(),
            "crypto_share_mean": g.crypto_share.mean(),
            "frames_mean": g.frames.mean(), "air_bytes_mean": g.air_bytes.mean(),
            "miss_rate": {c: g[f"miss_{c}"].sum() / n[c] for c in "NRV"},
            "below_floor_rate": {c: g[f"viol_tag_{c}"].sum() / n[c] for c in "NRV"},
            "nonstd_rate": {c: g[f"nonstd_{c}"].sum() / n[c] for c in "RV"},
            "lat_p95_median": {c: g[f"lat_p95_{c}"].median() for c in "NRV"},
            "n_runs": int(len(g)),
        }
    pv = {}
    for env, g in main_.groupby("env"):
        w = g.pivot(index="seed", columns="policy", values="E_total_J")
        out["vs_static_ascon"][env] = {p: paired_saving(w[p], w["Static-Ascon"]) for p in w.columns if p != "Static-Ascon"}
        for p in ("FLOOR-E", "FLOOR-L(q16)"):
            r = paired_saving(w[p], w["Elad2026-rule"])
            out["primary"][f"{env}:{p}_vs_Elad2026"] = r
            pv[f"{env}:{p}_vs_Elad2026"] = r["wilcoxon_p"]
        out["primary"][f"{env}:Elad2026_vs_Static-Ascon"] = paired_saving(w["Elad2026-rule"], w["Static-Ascon"])
        if "Elad2026-rule+FLOOR-framing" in w:
            out["primary"][f"{env}:EladBatched_vs_FLOOR-E"] = paired_saving(w["Elad2026-rule+FLOOR-framing"], w["FLOOR-E"])
            out["primary"][f"{env}:FLOOR-E_vs_EladBatched"] = paired_saving(w["FLOOR-E"], w["Elad2026-rule+FLOOR-framing"])
        out["cipher_ablation"][env] = {p: paired_saving(w[p], w["FLOOR-E"]) for p in w.columns if p.startswith("FLOOR-E/") and p not in ("FLOOR-E/no-batch", "FLOOR-E/explicit-nonce", "FLOOR-E/tag128-single-key")}
        if "FLOOR-E/tag128-single-key" in w.columns:   # SP 800-232: one tag length per key
            out.setdefault("tag_ablation", {})[env] = {
                "vs_FLOOR-E": paired_saving(w["FLOOR-E/tag128-single-key"], w["FLOOR-E"]),
                "vs_Elad2026": paired_saving(w["FLOOR-E/tag128-single-key"], w["Elad2026-rule"]),
                "vs_Static-Ascon": paired_saving(w["FLOOR-E/tag128-single-key"], w["Static-Ascon"])}
    for k, v in holm(pv).items():
        out["primary"][k]["p_holm"] = v
    sens = df[df.ber_mult != 1.0]
    for (env, ber, pol), g in sens.groupby(["env", "ber_mult", "policy"]):
        out["sensitivity"].setdefault(env, {}).setdefault(str(ber), {})[pol] = {
            "E_total_J_mean": g.E_total_J.mean(), "crypto_share_mean": g.crypto_share.mean(),
            "miss_rate_all": (g.miss_N.sum() + g.miss_R.sum() + g.miss_V.sum()) / (g.n_N.sum() + g.n_R.sum() + g.n_V.sum())}
    for env in out["sensitivity"]:
        for ber in out["sensitivity"][env]:
            s = out["sensitivity"][env][ber]
            # same estimator as the primary comparisons: mean of the paired per-seed relative changes
            g = sens[(sens.env == env) & (sens.ber_mult == float(ber))].pivot(index="seed", columns="policy", values="E_total_J")
            s["FLOOR-E_vs_Elad_rel"] = float((g["FLOOR-E"] / g["Elad2026-rule"] - 1).mean())
            s["FLOOR-E_vs_Elad_ratio_of_means"] = s["FLOOR-E"]["E_total_J_mean"] / s["Elad2026-rule"]["E_total_J_mean"] - 1
    # leakage: average precision recomputed from out-of-fold scores (V detection)
    from sklearn.metrics import average_precision_score
    oof_path = os.path.join(R, "04_leakage_oof.csv")
    if os.path.exists(oof_path):
        oof = pd.read_csv(oof_path)
        leak = json.load(open(os.path.join(R, "04_leakage.json")))
        for pol, g in oof.groupby("policy"):
            ap = average_precision_score(g.has_V, g.score)
            leak[pol]["V_detection"]["ap"] = float(ap)
            leak[pol]["V_detection"]["prevalence_in_sample"] = float(g.has_V.mean())
            leak[pol]["V_detection"]["ap_lift"] = float(ap / g.has_V.mean())
            # expected number of V-free frames of the same node-day ranked above a V frame
            fpd = out["per_policy"]["home"].get(pol, {}).get("frames_mean", float("nan"))
            leak[pol]["V_detection"]["expected_frames_ranked_above_V"] = float((1 - leak[pol]["V_detection"]["auc"]) * fpd)
        out["leakage"] = leak
    dl = os.path.join(R, "03b_deadline_sensitivity.csv")
    if os.path.exists(dl):
        d = pd.read_csv(dl)
        out["deadline_sensitivity"] = {}
        for (env, pol, f), g in d.groupby(["env", "policy", "deadline_factor"]):
            out["deadline_sensitivity"].setdefault(env, {}).setdefault(pol, {})[str(f)] = {
                "rel_vs_static_mean": g.rel_vs_static.mean(), "rel_vs_static_ci95": boot_ci(g.rel_vs_static),
                "rel_vs_elad_mean": g.rel_vs_elad.mean(), "frames_mean": g.frames.mean(),
                "miss_rate_all": (g.miss_N.sum() + g.miss_R.sum() + g.miss_V.sum()) / (g.n_N.sum() + g.n_R.sum() + g.n_V.sum())}
    pf = os.path.join(R, "03c_profiles.csv")
    if os.path.exists(pf):
        d = pd.read_csv(pf)
        out["profiles"] = {}
        for (prof, env), g in d.groupby(["profile", "env"]):
            w = g.pivot(index="seed", columns="policy", values="E_total_J")
            o = out["profiles"].setdefault(prof, {}).setdefault(env, {})
            for p in w.columns:
                o[p] = {"E_mean": w[p].mean(),
                        "rel_vs_static": paired_saving(w[p], w["Static-Ascon"]) if p != "Static-Ascon" else None,
                        "rel_vs_FLOOR-E": paired_saving(w[p], w["FLOOR-E"]) if p != "FLOOR-E" else None}
            gg = g.groupby("policy")
            for p, x in gg:
                n = x.n_N.sum() + x.n_R.sum() + x.n_V.sum()
                o[p]["miss_rate_all"] = (x.miss_N.sum() + x.miss_R.sum() + x.miss_V.sum()) / n
                o[p]["below_floor_all"] = (x.viol_tag_N.sum() + x.viol_tag_R.sum() + x.viol_tag_V.sum()) / n
                o[p]["crypto_share"] = x.crypto_share.mean()
    for f in ("04b_leakage_prior.json", "04c_strong_attacker.json", "05_downgrade.json", "06_label_leak.json", "00_cycle_model_validation.json", "01_crypto_meta.json"):
        fp = os.path.join(R, f)
        if os.path.exists(fp):
            d = json.load(open(fp))
            if f.startswith("00"):
                d = {k: v for k, v in d.items() if k not in ("cycles", "points")}
            out[f.split(".")[0]] = d
    json.dump(out, open(os.path.join(R, "07_summary.json"), "w"), indent=1, default=float)
    for env in ("hospital", "home", "rural"):
        print(env, {k: round(v["E_total_J_mean"], 3) for k, v in out["per_policy"][env].items()})
    print(json.dumps(out["primary"], indent=1, default=float))


if __name__ == "__main__":
    main()
