#!/usr/bin/env bash
# Stage-3 "D-ring steric clash" campaign: testosterone-over-progesterone specificity.
#   Strategy (LAB_MANUAL D-ring rule): preserve the A-ring recognition (Arg123/Glu106 = WT,
#   NOT designed) and install BULKY hydrophobics (Trp/Phe/Ile) at the C17/D-ring shell to
#   clash with progesterone's 20-acetyl while leaving room for testosterone's 17beta-OH.
#   Tier-1 screen ranks by dG(testosterone) - dG(progesterone) (margin < 0 = test-specific).
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTHONPATH=".:$HOME/LC-Seed"
export PYTORCH_ALLOC_CONF=expandable_segments:True
PYR="$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python"
D=results/stage3_dring
# scaffold = WT TESTOSTERONE holo (design for the ligand we want to keep)
SCAF=results/stage1_wt_validation/boltz/seed1/boltz_results_inputs/predictions/wt_testosterone/wt_testosterone_model_0.pdb
DRING="61 85 122 143 146 147"           # D-ring proximal shell (model numbering)
N_SEQS=${N_SEQS:-1000}; TOP=${TOP:-20}
mkdir -p "$D"

echo "[$(date +%H:%M:%S)] D-RING PHASE 1 — bulky-biased generation (A-ring Arg123/Glu106 fixed)"
$PYR -m tfsensor.ligandmpnn_gen --scaffold "$SCAF" --out_dir "$D/gen" \
  --design_residues "$DRING" --anchor none --favor "WFI:4.0" \
  --n_seqs "$N_SEQS" --temperatures 0.2,0.3,0.4 --seed 1 >> "$D/phase1.log" 2>&1
echo "[$(date +%H:%M:%S)] PHASE 1 done -> $D/library.json"

echo "[$(date +%H:%M:%S)] D-RING PHASE 2 — Tier-1 flex-ddG, rank by dG(test)-dG(prog)"
$PYR -m tfsensor.design_score panel --library "$D/library.json" \
  --target testosterone --rival progesterone \
  --seeds 1 --jobs 32 --shards 16 --top "$TOP" \
  --work_root "$D/screen" --out_json "$D/screen.json" >> "$D/phase2.log" 2>&1
echo "[$(date +%H:%M:%S)] PHASE 2 done -> $D/screen.json"
touch "$D/DRING_DONE"
echo "[$(date +%H:%M:%S)] drive_dring COMPLETE"
