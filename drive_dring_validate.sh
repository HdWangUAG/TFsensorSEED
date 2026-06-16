#!/usr/bin/env bash
# Validate the D-ring testosterone-specificity leads:
#   1. re-score Top-20 with 3 backbones (seed-average de-noises the 1-seed screen)
#   2. Tier-1.5 gate the Top-10: fold apo + TESTOSTERONE-holo, apply the 34 A rule
#      (basal apo<35.5; agonist testosterone-holo>38; holo-apo>0).
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTHONPATH=".:$HOME/LC-Seed"
export PYTORCH_ALLOC_CONF=expandable_segments:True
PYR="$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python"
BOLTZ="$HOME/LC-Seed/envs/boltz2/.venv/bin/boltz"
D=results/stage3_dring; V=$D/validate; G=$V/gate
mkdir -p "$V" "$G"

echo "[$(date +%H:%M:%S)] build Top-20 library from screen"
$PYR -c "import json; s=json.load(open('$D/screen.json')); json.dump(s['ranked'][:20], open('$V/top20.json','w'), indent=2)"

echo "[$(date +%H:%M:%S)] STEP 1 — re-score Top-20 with 3 seeds (seed-averaged test-vs-prog)"
$PYR -m tfsensor.design_score panel --library "$V/top20.json" \
  --target testosterone --rival progesterone --seeds 1,42,2024 \
  --jobs 32 --shards 4 --top 20 \
  --work_root "$V/screen" --out_json "$V/screen_verified.json" >> "$V/step1.log" 2>&1
echo "[$(date +%H:%M:%S)] STEP 1 done -> $V/screen_verified.json"

echo "[$(date +%H:%M:%S)] STEP 2 — Tier-1.5 gate (build apo + testosterone-holo for Top-10)"
$PYR -m tfsensor.design_gate build --screen "$V/screen_verified.json" --top 10 \
  --ligand testosterone --out_dir "$G/inputs" >> "$V/step2.log" 2>&1
for sub in "$G/inputs"/*/; do
  did=$(basename "$sub")
  $BOLTZ predict "$sub" --out_dir "$G/$did/seed1" --seed 1 \
    --diffusion_samples 5 --recycling_steps 3 --model boltz2 \
    --output_format pdb --devices 1 --accelerator gpu --use_msa_server \
    >> "$V/step2.log" 2>&1
done
$PYR -m tfsensor.design_gate gate --screen "$V/screen_verified.json" --top 10 \
  --ligand testosterone --boltz_root "$G" --seeds 1 \
  --out_json "$G/gate.json" >> "$V/step2.log" 2>&1
echo "[$(date +%H:%M:%S)] STEP 2 done -> $G/gate.json"
touch "$V/VALIDATE_DONE"
echo "[$(date +%H:%M:%S)] drive_dring_validate COMPLETE"
