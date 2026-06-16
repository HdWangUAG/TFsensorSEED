#!/usr/bin/env bash
# Stage-1d mutant benchmark driver (detach-safe). For each mutant (F119W=our F119W,
# L147R=our L147R) runs the Boltz panel (3 seeds) then the Protenix panel, using the
# SAME settings as the WT Stage-1 run so the comparison is apples-to-apples:
#   Boltz:    --diffusion_samples 5 --recycling_steps 3 --model boltz2  seeds {1,42,2024}
#   Protenix: -s 1,42,2024 -e 3 --use_msa True
# Inputs must already be built (tfsensor.boltz_holo_inputs / protenix_runner --mutate).
set -uo pipefail
cd "$HOME/TFsensorSEED"

BOLTZ="$HOME/LC-Seed/envs/boltz2/.venv/bin/boltz"
PROTENIX="$HOME/.conda/envs/protenix2/bin/protenix"
M=results/stage1d_mutants
export PYTORCH_ALLOC_CONF=expandable_segments:True
VARIANTS="f119w l147r"

echo "[$(date +%H:%M:%S)] drive_mutants start (variants: $VARIANTS)"

for PFX in $VARIANTS; do
  IN="$M/$PFX/boltz/inputs"
  echo "[$(date +%H:%M:%S)] ===== BOLTZ $PFX ====="
  for S in 1 42 2024; do
    echo "[$(date +%H:%M:%S)] [boltz:$PFX] seed $S"
    $BOLTZ predict "$IN" \
      --out_dir "$M/$PFX/boltz/seed${S}" \
      --seed $S --diffusion_samples 5 --recycling_steps 3 --model boltz2 \
      --output_format pdb --devices 1 --accelerator gpu --use_msa_server \
      >> "$M/$PFX/boltz/panel.log" 2>&1
  done
  echo "[$(date +%H:%M:%S)] [boltz:$PFX] ALL SEEDS DONE"
done

for PFX in $VARIANTS; do
  echo "[$(date +%H:%M:%S)] ===== PROTENIX $PFX ====="
  $PROTENIX pred -i "$M/$PFX/protenix/inputs" -o "$M/$PFX/protenix/out" \
    -s 1,42,2024 -e 3 --use_msa True \
    >> "$M/$PFX/protenix/panel.log" 2>&1
  echo "[$(date +%H:%M:%S)] [protenix:$PFX] DONE"
done

touch "$M/PREDICTIONS_DONE"
echo "[$(date +%H:%M:%S)] drive_mutants DONE -> $M/PREDICTIONS_DONE"
