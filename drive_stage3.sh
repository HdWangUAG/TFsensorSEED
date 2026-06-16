#!/usr/bin/env bash
# ============================================================================
# Stage-3 end-to-end estradiol-biosensor design pipeline (see LAB_MANUAL.md).
#   Phase 1  Tier-0   Motif-anchored LigandMPNN generation (Arg123->Glu/Asp)
#   Phase 2  Tier-1   flex-ddG specificity screen  -> Top N
#   Phase 3  Tier-1.5 Boltz two-state ABSOLUTE GEOMETRY gate (34 Å rule)
#   Phase 4  Tier-2   RBFE/FEP arbiter (scaffold + prototype)
# Usage: ./drive_stage3.sh [phases...]   e.g. ./drive_stage3.sh 1 2   (default: 1 2 3 4)
# ============================================================================
set -uo pipefail
REPO="${TFSENSOR_REPO_ROOT:-$HOME/TFsensorSEED}"
cd "$REPO"

# --- config: .env (KEY=VALUE) > environment > built-in default ---------------
# Load .env so paths aren't hardcoded (mirrors tfsensor/config.py for Python side).
if [[ -f "$REPO/.env" ]]; then
  set -a; source "$REPO/.env"; set +a
fi
LC_SEED="${TFSENSOR_LC_SEED:-$HOME/LC-Seed}"
PYR="${TFSENSOR_PYROSETTA_PY:-$LC_SEED/envs/pyrosetta/.venv/bin/python}"
BOLTZ="${TFSENSOR_BOLTZ_BIN:-$LC_SEED/envs/boltz2/.venv/bin/boltz}"
export PYTHONPATH=".:$LC_SEED"
export PYTORCH_ALLOC_CONF=expandable_segments:True
S3=results/stage3_design
SCAF=results/stage1_wt_validation/boltz/seed1/boltz_results_inputs/predictions/wt_estradiol/wt_estradiol_model_0.pdb

N_SEQS=${N_SEQS:-1000}
TOP=${TOP:-20}
SEEDS="${SEEDS:-1}"                                   # Boltz seeds per design
NUM_GPUS="${NUM_GPUS:-$(nvidia-smi -L 2>/dev/null | wc -l)}"; NUM_GPUS=${NUM_GPUS:-1}
[[ "$NUM_GPUS" -lt 1 ]] && NUM_GPUS=1
PHASES="${*:-1 2 3 4}"
echo "[$(date +%H:%M:%S)] drive_stage3 phases: $PHASES (N_SEQS=$N_SEQS TOP=$TOP NUM_GPUS=$NUM_GPUS SEEDS=$SEEDS)"
mkdir -p "$S3"

run_phase () { [[ " $PHASES " == *" $1 "* ]]; }

# ---- Phase 1: generation ----
if run_phase 1; then
  echo "[$(date +%H:%M:%S)] PHASE 1 — motif-anchored LigandMPNN ($N_SEQS seqs)"
  $PYR -m tfsensor.ligandmpnn_gen --scaffold "$SCAF" --out_dir "$S3/gen" \
    --n_seqs "$N_SEQS" --temperatures 0.1,0.2,0.3 --seed 1 >> "$S3/phase1.log" 2>&1
  echo "[$(date +%H:%M:%S)] PHASE 1 done -> $S3/library.json"
fi

# ---- Phase 2: flex-ddG specificity screen ----
if run_phase 2; then
  echo "[$(date +%H:%M:%S)] PHASE 2 — Tier-1 flex-ddG specificity screen"
  $PYR -m tfsensor.design_score panel --library "$S3/library.json" \
    --seeds 1 --jobs 32 --shards 16 --top "$TOP" \
    --work_root "$S3/screen" --out_json "$S3/screen.json" >> "$S3/phase2.log" 2>&1
  echo "[$(date +%H:%M:%S)] PHASE 2 done -> $S3/screen.json (top $TOP)"
fi

# ---- Phase 3: Boltz two-state absolute-geometry gate ----
if run_phase 3; then
  echo "[$(date +%H:%M:%S)] PHASE 3 — Tier-1.5 allosteric gate (build inputs)"
  G=results/stage3_gate
  $PYR -m tfsensor.design_gate build --screen "$S3/screen.json" --top "$TOP" \
    --out_dir "$G/inputs" >> "$G/phase3.log" 2>&1
  echo "[$(date +%H:%M:%S)] PHASE 3 — folding apo+estradiol-holo for top $TOP designs"
  # Boltz is GPU-bound. Build the (design x seed) job list, then fan it out across
  # NUM_GPUS lanes: each lane is pinned to one GPU (CUDA_VISIBLE_DEVICES) and drains
  # its share sequentially, so exactly one Boltz job runs per GPU at a time.
  mapfile -t JOBS < <(for sub in "$G/inputs"/*/; do for S in $SEEDS; do echo "$sub|$S"; done; done)
  echo "[$(date +%H:%M:%S)] PHASE 3 — ${#JOBS[@]} Boltz jobs across $NUM_GPUS GPU lane(s)"
  for ((g=0; g<NUM_GPUS; g++)); do
    (
      for ((j=g; j<${#JOBS[@]}; j+=NUM_GPUS)); do
        IFS='|' read -r sub S <<< "${JOBS[$j]}"
        did=$(basename "$sub")
        CUDA_VISIBLE_DEVICES="$g" "$BOLTZ" predict "$sub" --out_dir "$G/$did/seed${S}" --seed "$S" \
          --diffusion_samples 5 --recycling_steps 3 --model boltz2 \
          --output_format pdb --devices 1 --accelerator gpu --use_msa_server \
          >> "$G/phase3.log" 2>&1
      done
    ) &
  done
  wait
  $PYR -m tfsensor.design_gate gate --screen "$S3/screen.json" --top "$TOP" \
    --boltz_root "$G" --seeds "${SEEDS// /,}" --out_json "$G/gate.json" >> "$G/phase3.log" 2>&1
  echo "[$(date +%H:%M:%S)] PHASE 3 done -> $G/gate.json"
fi

# ---- Phase 4: FEP arbiter (scaffold + prototype prep) ----
if run_phase 4; then
  echo "[$(date +%H:%M:%S)] PHASE 4 — Tier-2 RBFE/FEP scaffold + prototype"
  $PYR -m tfsensor.fep_rbfe prepare --variant l147r --ligand cortisol \
    --out_dir results/stage3_fep/proto_l147r_cortisol >> results/stage3_fep/phase4.log 2>&1
  echo "[$(date +%H:%M:%S)] PHASE 4 done -> results/stage3_fep/ (see SETUP_FEP.md)"
fi

touch "$S3/STAGE3_DONE"
echo "[$(date +%H:%M:%S)] drive_stage3 COMPLETE"
