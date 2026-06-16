#!/usr/bin/env bash
# Fold the matched APO (no ligand) for WT / L147R / F119W with Boltz-2, 3 seeds,
# SAME settings as the holo runs so apo↔holo DBD is comparable. The apo gives the
# matched two-state reference: DBD opening = mean(holo DBD) − mean(apo DBD).
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTORCH_ALLOC_CONF=expandable_segments:True
BOLTZ="$HOME/LC-Seed/envs/boltz2/.venv/bin/boltz"
A=results/stage3_apo

echo "[$(date +%H:%M:%S)] drive_apo start"
for PFX in wt l147r f119w; do
  IN="$A/$PFX/inputs"
  for S in 1 42 2024; do
    echo "[$(date +%H:%M:%S)] [apo:$PFX] seed $S"
    $BOLTZ predict "$IN" --out_dir "$A/$PFX/seed${S}" \
      --seed $S --diffusion_samples 5 --recycling_steps 3 --model boltz2 \
      --output_format pdb --devices 1 --accelerator gpu --use_msa_server \
      >> "$A/$PFX/apo.log" 2>&1
  done
  echo "[$(date +%H:%M:%S)] [apo:$PFX] done"
done
touch "$A/APO_DONE"
echo "[$(date +%H:%M:%S)] drive_apo DONE -> $A/APO_DONE"
