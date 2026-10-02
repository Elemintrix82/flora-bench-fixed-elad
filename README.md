# FLOOR bench: fixed vs context-adaptive record protection for medical IoT

Reproducible benchmark for the article
*"Fixed versus context-adaptive lightweight encryption for medical IoT devices"*
(Elad, Fotso Tekam, Mengata Mengounou, Nneme Nneme). Bench version **1.2**.

The bench asks one question: on a battery-powered wearable (nRF52840-class SoC, BLE link)
that sends medical telemetry, does choosing the cipher per record from the radio context
save energy, and what does it cost in security? It compares the context-adaptive rule of
Elad et al. (2026) with static AEADs and with **FLOOR**, a policy that adapts batching and framing
but never goes below a per-class security floor.

> **FLORA** (the Python package name) stands for *Floor-constrained, Leakage-aware,
> Online-learned Radio-and-crypto Adaptation*.

---

## Contents
- [How it works](#how-it-works)
- [Policies compared](#policies-compared)
- [Headline results](#headline-results-frozen-reference)
- [Install and run](#install-and-run)
- [Experiments](#experiments)
- [Reproduce each table and figure](#reproduce-each-table-and-figure)
- [Configuration](#configuration)
- [Check your results](#check-your-results)
- [Repository layout](#repository-layout)
- [Real hardware](#real-hardware)
- [Limits](#limits)
- [Changelog](#changelog)
- [Licences of third-party code](#licences-of-third-party-code)

---

## How it works

```
 firmware/ (C, arm-none-eabi-gcc)          flora/ (Python)
 ┌─────────────────────────────┐   ELF   ┌──────────────────────────────────────────┐
 │ harness.c + wrap_<aead>.c   │ ──────▶ │ m4emu.py   Unicorn + Capstone,           │
 │ one bare-metal ELF per AEAD │         │            Cortex-M4 TRM cycle model     │
 └─────────────────────────────┘         │ refs.py    host KAT / cross-checks       │
                                         │ energy.py  nRF52840 + BLE energy model   │
                                         │ traffic.py GATT-grounded records,        │
                                         │            link-state Markov chain       │
                                         │ policies.py, sim.py  node-day simulation │
                                         │ adversary.py passive traffic analysis    │
                                         │ stats.py   paired bootstrap / Wilcoxon   │
                                         └──────────────────────────────────────────┘
```

1. **Crypto cost.** Each AEAD is compiled bare-metal for Cortex-M4 and executed in an
   instruction-level emulator. A cycle cost is assigned per instruction from the ARM Cortex-M4 TRM timing
   rules. Every build is checked against known-answer vectors and independent host implementations.
2. **Model validation.** The same emulator, run on a Cortex-M3 build of 28 AEADs from
   `lwc-finalists`, is compared with published Arduino Due measurements.
3. **Node-day simulation.** Synthetic but standard-grounded telemetry (Heart Rate, PLX, CGM
   GATT formats, 250 Hz ECG) is labelled with HL7 confidentiality classes **N / R / V**.
   It is sent over a BLE link whose state (good / fair / poor → 2M / 1M / Coded S8 PHY) follows a
   Markov chain. Three environments are simulated: `hospital`, `home` and `rural`.
4. **Security analyses.** These cover a passive traffic-analysis attacker (gradient boosting on
   frame length and time), jamming that forces a context downgrade, header tampering and replay, and label leakage in the 2026 protocol.

## Policies compared

| Policy | Idea |
|---|---|
| `Static-Ascon`, `Static-AES-GCM` | One approved AEAD, every record sent immediately |
| `Elad2026-rule` | Context-adaptive cipher choice from RSSI (Elad et al. 2026) |
| `Q-learning (no floor / with floor)` | Learned adaptation, with and without the security floor |
| `FLOOR-E` | Energy-oriented: approved AEAD only, tag ≥ floor (N: 64 bit, R/V: 128 bit), deadline-aware batching, implicit nonce |
| `FLOOR-L(pow2 / q16 / q64 / q128)` | Leakage-aware FLOOR with length padding |
| `FLOOR-C` | Constant-rate FLOOR (traffic-shape hiding) |
| `Elad2026-rule+FLOOR-framing` | The 2026 rule with FLOOR batching, to separate the two effects |
| `FLOOR-E/...` ablations | No batching, explicit nonce, single 128-bit tag, other ciphers (AES-GCM, ChaCha20-Poly1305, Xoodyak, GIFT-COFB, RECTANGLE-CTR+HMAC) |

The approved set is Ascon-AEAD128 (SP 800-232), AES-GCM (SP 800-38D) and ChaCha20-Poly1305 (RFC 8439).

## Headline results (frozen reference)

The values below are taken from `reference_results/07_summary.json`: 20 seeds per environment, with paired relative energy change and 95 % bootstrap CI.

| Environment | Static-Ascon (J/day) | Elad2026-rule (J/day) | FLOOR-E (J/day) | FLOOR-E vs Elad2026 |
|---|---|---|---|---|
| hospital | 1.70 | 1.89 | 0.89 | −53.5 % [−55.1, −51.7] |
| home | 2.69 | 2.86 | 1.50 | −48.0 % [−49.6, −46.6] |
| rural | 9.04 | 9.89 | 5.43 | −45.1 % [−45.8, −44.2] |

- In every environment, the 2026 adaptive rule uses **more** energy than static Ascon (+6 % to +11 %). It also sends R and V records with non-approved protection in 55–100 % of cases.
- FLOOR-E never goes below the floor and misses no deadline. Most of its saving comes from framing and batching, not from the cipher choice. Applying FLOOR framing to the 2026 rule recovers most of the gain.
- Cycle model validation: Spearman ρ = 0.994 over 112 published measurements (28 AEADs), with a median relative error of 19 % on speed ratios.

See the article for the leakage, downgrade and label-leak results.

## Install and run

**Linux** (or WSL / Docker on Windows):
```bash
sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi make python3-pip
pip install -r requirements.txt
./run_all.sh            # full campaign (~1.5 h on 2 cores)
./run_all.sh --quick    # short runs (~15 min); numbers differ from the article
./run_all.sh --skip-build   # reuse existing firmware/build ELFs
```

**Docker:**
```bash
docker build -t floor-bench .
docker run --rm -v $PWD/outputs:/bench/outputs floor-bench
```

Python dependencies are pinned in `requirements.txt` (Unicorn 2.1.4, Capstone 5.0.7, NumPy, SciPy, pandas, scikit-learn, matplotlib, cryptography).
The outputs go to `outputs/results`, `outputs/figures` and `outputs/logs`.

## Experiments

| Step | Script | Output | Time (2 cores) |
|---|---|---|---|
| E0 cycle-model validation vs published Arduino Due results (28 AEADs) | `experiments/00_validate_cycle_model.py` | `00_cycle_model_validation.json` | 1 min |
| E1 AEAD cost on emulated Cortex-M4 + KAT / cross checks | `experiments/01_crypto_cost.py` | `01_crypto_cost.csv`, `01_crypto_meta.json` | 2 min |
| E2 node-day simulation, 3 environments × 20 seeds × 17 policies + BER sensitivity; 03b deadline slack; 03c device profiles; 03d guard sensitivity | `experiments/03_policy_simulation.py` (+ `03b`, `03c`, `03d`) | `03_policy_sim.csv`, … | 25 min |
| E3 traffic-analysis attacker (120 node-days); 04b hour-of-day prior; 04c strong attacker | `experiments/04_leakage.py` (+ `04b`, `04c`) | `04_leakage.json`, `04_leakage_oof.csv` | 50 min |
| E4 jamming (context manipulation), header tampering; 05b replay | `experiments/05_downgrade.py` (+ `05b`) | `05_downgrade.json`, `05b_replay.json` | 6 min |
| E5 label leakage in the 2026 protocol | `experiments/06_label_leak_2026.py` | `06_label_leak.json` | 5 min |
| Statistics (paired bootstrap, Wilcoxon, Holm) | `experiments/07_summarise.py` | `07_summary.json` | <1 min |
| Figures FR + EN | `experiments/figures/fig_*.py` | `outputs/figures/*.pdf` | 1 min |

Additional checks are in `scripts/`:
- `check_adversary_regularised.py` compares the regularised attacker with alternative classifiers on the frozen out-of-fold data.
- `leakage_padding_q64_q128.py` runs the leakage experiment for the q64 and q128 padding variants. Its 60-day result is in `reference_results/leakage_padding_regularised_60days.txt`.

## Reproduce each table and figure

The numbering follows the English version of the article.

Every script reads and writes `outputs/` (override with `FLORA_OUT`). `run_all.sh` runs everything in order.
You can regenerate a single item as shown below, but the simulation scripts must have run before `07_summarise.py` and the figures.

| Article item | Command |
|---|---|
| Fig. 2 (cycle-model validation) | `python3 experiments/00_validate_cycle_model.py` then `experiments/figures/fig_validation.py` |
| Table 6, Fig. 3 (AEAD cost) | `python3 experiments/01_crypto_cost.py` then `fig_crypto_cost.py` |
| Fig. 4 (energy of a frame) | `experiments/figures/fig_frame_energy.py` |
| Table 7, Fig. 5, Fig. 6 (node-day energy, ablations, BER) | `python3 experiments/03_policy_simulation.py`, `07_summarise.py`, then `fig_energy.py`, `fig_cipher_sens.py` |
| Fig. 7, Table 8 (deadlines, guard and T_CI sensitivity) | `03b_deadline_sensitivity.py`, `03d_guard_sensitivity.py`, then `fig_deadline_tradeoff.py` |
| Table 9 (device profiles) | `03c_profiles.py` |
| Fig. 8, Table 10 (traffic analysis) | `04_leakage.py`, `04b_leakage_prior.py`, `04c_strong_attacker.py`, then `fig_leakage.py` |
| Fig. 9, Table 10 (jamming, header rewriting, replay) | `05_downgrade.py`, `05b_replay.py`, then `fig_downgrade.py` |
| Fig. 10 (2026 protocol) | `06_label_leak_2026.py`, then `fig_label_leak.py` |

Figures are produced in French and English: run the figure scripts with `FIGLANG=fr` or `FIGLANG=en`.

## Configuration

All tunable parameters live in `flora/config.py` and can be overridden by environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `FLORA_OUT` | `./outputs` | Output directory |
| `FLORA_SEED` | `2026` | Master random seed |
| `FLORA_QUICK` | `0` | `1` = short runs |
| `FLORA_THREADS` | CPU count | Worker processes |
| `FLORA_ONLY` | all | Comma-separated policy subset for 03 / 04 |
| `FIGLANG` | — | `fr` or `en` for figures |

The physical constants (nRF52840 currents, BLE timing) are in `flora/energy.py`. The link states, BER and traffic are in `flora/traffic.py`. Values not taken from a datasheet or standard are marked `ASSUMPTION` in the source.

## Check your results

```bash
python3 scripts/check_against_reference.py
```
This script compares `outputs/results` with the frozen article results in `reference_results/`.
Cycle counts and KAT checks must be **identical**. Simulation summaries must match to 1e-9 relative when you use the same seeds and package versions.

## Repository layout

```
.
├── run_all.sh, Dockerfile, requirements.txt
├── firmware/
│   ├── Makefile, link.ld        one ELF per AEAD variant (CPU=cortex-m4, OPT=-O2)
│   ├── src/                     harness.c, val_harness.c, aead_iface.h, wrap_<aead>.c, rectangle.c
│   └── third_party/             unmodified upstream sources + KAT files
├── flora/                       Python library (see "How it works")
├── experiments/                 00 … 07 experiment scripts, figures/ (fig_*.py, figstyle, figlang)
├── scripts/                     reference check and additional analyses
├── reference_data/              published Arduino Due benchmark (validation only)
└── reference_results/           raw results used in the article
```

The firmware variants are `ascon_armv7m`, `ascon_ref`, `aesgcm`, `chacha20poly1305`, `giftcofb`, `xoodyak`, `rectangle_ctr_hmac` and `lwcchachapoly`.

## Real hardware

The ELF files in `firmware/build/` are plain Cortex-M4 code. To measure real cycles on an nRF52840 or STM32L4 board, link `harness.c` with the vendor startup code and read `DWT->CYCCNT` around `bench_enc()`.
Energy per cycle and radio currents are set in `flora/energy.py`.

## Limits

See the "Validity" section of the article.

- **Cycle counts** come from a model. It is validated to a rank correlation of 0.994 against 112 published hardware measurements, with a median relative error of 19 % on speed ratios. Zero flash wait states are assumed; instruction counts are exact.
- **Radio energy** is modelled from datasheet currents and BLE timing.
- **Link states and traffic periods** are scenario assumptions. BER sensitivity is explored from ×0.1 to ×10.

## Changelog

**1.2** (changes from 1.1):
- L2CAP credit-based transport for frames larger than 244 B (`energy.py`).
- Retransmission latency (`sim.py`).
- In `05`, BER ×10 applies only inside the jamming window, and the tag-downgrade test is done in-table.
- Regularised passive adversary (`flora/adversary.py`, used by 04, 04b and 04c). The 1.1 model over-fitted the frame-length feature.
- New padding variants `q64` and `q128`.

## Licences of third-party code

| Component | Source | Licence |
|---|---|---|
| `third_party/ascon_armv7m`, `ascon_ref` | ascon-c (NIST SP 800-232) | CC0 |
| `third_party/lwc`, `lwc_full` | rweather/lwc-finalists | MIT |
| `third_party/monocypher` | Monocypher 4 | BSD-2 / CC0 |
| `src/rectangle.c` | derived from FELICS | GPLv3 |
| `flora/pyascon_ref.py` | pyascon reference implementation | see file header |

## Citation

If you use this bench, please cite the article:

> Elad, Fotso Tekam, Mengata Mengounou, Nneme Nneme. *Fixed versus context-adaptive lightweight
> encryption for medical IoT devices.*
