#!/usr/bin/env bash
# Stage-3a fixed-backbone ΔΔG driver (detach-safe). Runs the ΔΔG panel
# (R123E/R123D/F119W/L147R × 4 steroids × 3 seeds × N replicates, threaded into the
# WT Boltz holo backbones) then writes the calibration/positive-control report.
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTHONPATH=".:$HOME/LC-Seed"
PY="$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python"
OUT=results/stage3_ddg
mkdir -p "$OUT"

echo "[$(date +%H:%M:%S)] ddg panel start"
$PY -m tfsensor.ddg_panel \
  --panel data/steroid_panel.csv \
  --boltz_root results/stage1_wt_validation/boltz \
  --seeds 1,42,2024 \
  --mutations R123E,R123D,F119W,L147R \
  --n_ensemble 8 --jobs 12 \
  --work_root "$OUT/work" \
  --out_json "$OUT/ddg_results.json"
echo "[$(date +%H:%M:%S)] ddg panel done"

$PY -m tfsensor.ddg_report \
  --results "$OUT/ddg_results.json" \
  --out_json "$OUT/BENCHMARK.json" > "$OUT/BENCHMARK.txt" 2>&1
echo "[$(date +%H:%M:%S)] ddg report -> $OUT/BENCHMARK.txt"
cat "$OUT/BENCHMARK.txt"
