#!/usr/bin/env bash
# run_all.sh - full FLOOR campaign.  Options: --quick (short runs), --skip-build
set -euo pipefail
cd "$(dirname "$0")"
QUICK=0; BUILD=1
for a in "$@"; do
  case $a in --quick) QUICK=1 ;; --skip-build) BUILD=0 ;; *) echo "unknown option $a"; exit 1 ;; esac
done
export FLORA_QUICK=$QUICK
export FLORA_OUT=${FLORA_OUT:-$PWD/outputs}
mkdir -p "$FLORA_OUT/logs" "$FLORA_OUT/results" "$FLORA_OUT/figures"
if [ $BUILD = 1 ]; then
  make -C firmware CPU=cortex-m4 OPT=-O2
  L=firmware/third_party/lwc_full
  arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -mfloat-abi=soft -Os -ffunction-sections -fdata-sections \
    -Ifirmware/src -I$L firmware/src/val_harness.c $(ls $L/*.c $L/*armv7m.S | grep -v masked) \
    -T firmware/link.ld -nostartfiles --specs=nano.specs -Wl,--gc-sections -Wl,--no-warn-rwx-segments \
    -o firmware/build/val_due_m3_Os.elf
fi
for s in 00_validate_cycle_model 01_crypto_cost 03_policy_simulation 03b_deadline_sensitivity 03c_profiles 03d_guard_sensitivity 04_leakage 04b_leakage_prior 04c_strong_attacker 05_downgrade 05b_replay 06_label_leak_2026 07_summarise; do
  echo "== $s"; python3 experiments/$s.py 2>&1 | tee "$FLORA_OUT/logs/$s.log"
done
cd experiments/figures
for f in fig_*.py; do for L in fr en; do FIGLANG=$L python3 $f; done; done
cd ../..
python3 scripts/check_against_reference.py || true
echo "done: results in $FLORA_OUT"
