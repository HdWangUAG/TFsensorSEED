#!/usr/bin/env bash
# ============================================================================
# Progesterone + Cortisol specificity campaigns — generation + flex-ddG screen.
# Waits for the testosterone 2-ligand gate to free the GPU, then:
#   1. LigandMPNN generation (GPU, ~min each)
#   2. flex-ddG specificity screen (CPU, hours each), ranked dG(target) - best decoy
# Design strategy (recognition code; A-ring kept for all 4-en-3-ones):
#   progesterone: ligand-aware D-ring {61,85,88,122,143,146,147}, mild S/T/N/Q (C20=O) bias
#   cortisol:     anchor R123E (wet-lab-validated) + polar D-ring {..,123,..}, S/T/N/Q bias
# Gate (2-ligand) + FEP/RBFE handled separately after leads are picked.
# ============================================================================
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTHONPATH=".:$HOME/LC-Seed"
export PYTORCH_ALLOC_CONF=expandable_segments:True
PYR="${TFSENSOR_PYROSETTA_PY:-$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python}"
PRED=results/stage1_wt_validation/boltz/seed1/boltz_results_inputs/predictions
GATE_DONE=results/stage3_dring/gate2lig/GATE2LIG_DONE
LOG=results/stage3_prog_cort.log

echo "[$(date '+%F %T')] waiting for GPU (testosterone gate)..." | tee -a "$LOG"
while [ ! -f "$GATE_DONE" ]; do sleep 300; done
echo "[$(date '+%F %T')] GPU free -> starting prog/cort campaigns" | tee -a "$LOG"

gen () {  # $1=name $2=scaffold $3=design_res $4=anchor $5=favor
  echo "[$(date '+%T')] GEN $1 (anchor=$4 favor=$5)" | tee -a "$LOG"
  $PYR -m tfsensor.ligandmpnn_gen --scaffold "$2" --out_dir "results/stage3_$1/gen" \
    --design_residues "$3" --anchor "$4" --favor "$5" \
    --n_seqs 1200 --temperatures 0.2,0.3,0.4 --seed 1 >> "results/stage3_$1/gen.log" 2>&1 \
    && echo "[$(date '+%T')] GEN $1 done -> results/stage3_$1/library.json" | tee -a "$LOG" \
    || echo "[$(date '+%T')] GEN $1 FAILED" | tee -a "$LOG"
}

screen () {  # $1=name $2=target
  echo "[$(date '+%T')] SCREEN $1 (target=$2)" | tee -a "$LOG"
  $PYR -m tfsensor.design_score panel --library "results/stage3_$1/library.json" \
    --target "$2" --seeds 1 --jobs 32 --shards 16 --top 20 \
    --work_root "results/stage3_$1/screen" --out_json "results/stage3_$1/screen.json" \
    >> "results/stage3_$1/screen.log" 2>&1 \
    && echo "[$(date '+%T')] SCREEN $1 done -> results/stage3_$1/screen.json" | tee -a "$LOG" \
    || echo "[$(date '+%T')] SCREEN $1 FAILED" | tee -a "$LOG"
}

# --- generation (GPU, quick, sequential) ---
gen prog "$PRED/wt_progesterone/wt_progesterone_model_0.pdb" "61 85 88 122 143 146 147" "none"    "STNQ:1.2"
gen cort "$PRED/wt_cortisol/wt_cortisol_model_0.pdb"         "61 85 88 122 123 143 146 147" "123:E" "STNQ:1.5"

# --- screen (CPU, hours, sequential to avoid core oversubscription) ---
screen prog progesterone
screen cort cortisol

echo "[$(date '+%F %T')] === prog+cort gen+screen COMPLETE ===" | tee -a "$LOG"
touch results/stage3_prog_cort_DONE
