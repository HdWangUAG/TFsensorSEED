#!/usr/bin/env bash
# ============================================================================
# 2-ligand allosteric gate on ALL 71 D-ring designs (unbiased, homodimer-correct).
# Per design: Boltz fold of apo + 2-ligand testosterone holo (~8 min) -> ~9.5 h total.
# Then design_gate gate (--all) computes DBD opening + PASS/FAIL.
# ============================================================================
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTHONPATH=".:$HOME/LC-Seed"
export PYTORCH_ALLOC_CONF=expandable_segments:True
G=results/stage3_dring/gate2lig
BOLTZ="${TFSENSOR_BOLTZ_BIN:-$HOME/LC-Seed/envs/boltz2/.venv/bin/boltz}"
PYR="${TFSENSOR_PYROSETTA_PY:-$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python}"
LOG="$G/drive.log"
tot=$(ls -d "$G"/inputs/*/ | wc -l); n=0
echo "[$(date '+%F %T')] === 2-ligand gate, ALL $tot designs START ===" | tee -a "$LOG"

for sub in "$G"/inputs/*/; do
  did=$(basename "$sub"); n=$((n+1))
  apo="$G/$did/seed1/boltz_results_$did/predictions/${did}_apo/${did}_apo_model_0.pdb"
  holo="$G/$did/seed1/boltz_results_$did/predictions/${did}_testosterone/${did}_testosterone_model_0.pdb"
  if [ -f "$apo" ] && [ -f "$holo" ]; then
    echo "[$(date '+%T')] ($n/$tot) $did already folded, skip" | tee -a "$LOG"; continue
  fi
  echo "[$(date '+%T')] ($n/$tot) folding $did (apo + 2-ligand holo)" | tee -a "$LOG"
  "$BOLTZ" predict "$sub" --out_dir "$G/$did/seed1" --seed 1 \
    --diffusion_samples 5 --recycling_steps 3 --model boltz2 --output_format pdb \
    --devices 1 --accelerator gpu --use_msa_server >> "$G/boltz.log" 2>&1 \
    || echo "[$(date '+%T')] $did FOLD FAILED" | tee -a "$LOG"
done

echo "[$(date '+%F %T')] folding done -> gate analysis (all designs)" | tee -a "$LOG"
$PYR -m tfsensor.design_gate gate --screen results/stage3_dring/screen.json --all \
  --ligand testosterone --boltz_root "$G" --seeds 1 \
  --out_json "$G/gate2lig.json" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] === COMPLETE -> $G/gate2lig.json ===" | tee -a "$LOG"
touch "$G/GATE2LIG_DONE"
