#!/usr/bin/env bash
# Stage-1d analysis: run all evaluation panels for WT + the two mutants, then build
# the cross-variant benchmark comparison. Safe to re-run; expects predictions present
# (results/stage1d_mutants/PREDICTIONS_DONE for the mutants; WT from stage1_wt_validation).
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTHONPATH=".:$HOME/LC-Seed"
PYR="$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python"
APO=data/AcrR_protein_only.pdb
PANEL=data/steroid_panel.csv
FILT='PyRosetta|Copyright|JHU|LICENSE|retrieved|Created|^│|^┌|^└|NOTE:'

# variant -> boltz_root, protenix_out, results_dir
analyze () {
  local PFX=$1 BROOT=$2 POUT=$3 RDIR=$4
  echo "[$(date +%H:%M:%S)] ===== analyze $PFX ====="
  mkdir -p "$RDIR"
  # binding: Boltz affinity_probability_binary
  $PYR -m tfsensor.replicate_summary boltz \
    --seed_dir 1:$BROOT/seed1 --seed_dir 42:$BROOT/seed42 --seed_dir 2024:$BROOT/seed2024 \
    --pocket data/pocket_residues.json --panel $PANEL \
    --out_json $RDIR/boltz_go_nogo.json > $RDIR/boltz_go_nogo.txt 2>&1 || echo "  [warn] boltz summary failed"
  # binding: Protenix ligand-ipTM
  $PYR -m tfsensor.replicate_summary protenix \
    --out_dir $POUT --panel $PANEL --seeds 1,42,2024 --prefix $PFX \
    --metric ligand_iptm --out_json $RDIR/protenix_go_nogo.json > $RDIR/protenix_go_nogo.txt 2>&1 || echo "  [warn] protenix summary failed"
  # physics: Rosetta interface dG
  $PYR -m tfsensor.physics_panel --panel $PANEL --boltz_root $BROOT --seeds 1,42,2024 \
    --prefix $PFX --work_root $RDIR/physics_work --out_json $RDIR/physics_go_nogo.json \
    > $RDIR/physics.log 2>&1 || echo "  [warn] physics failed"
  # switch: DBD opening
  $PYR -m tfsensor.trigger_panel --panel $PANEL --boltz_root $BROOT --apo $APO \
    --seeds 1,42,2024 --prefix $PFX --out_json $RDIR/trigger_go_nogo.json \
    > $RDIR/trigger.log 2>&1 || echo "  [warn] trigger failed"
  # coupled biosensor score
  $PYR -m tfsensor.biosensor_score --boltz_go_nogo $RDIR/boltz_go_nogo.json \
    --trigger_go_nogo $RDIR/trigger_go_nogo.json --out_json $RDIR/biosensor_score.json \
    > $RDIR/biosensor.log 2>&1 || echo "  [warn] biosensor failed"
  echo "[$(date +%H:%M:%S)] $PFX analysis done -> $RDIR"
}

M=results/stage1d_mutants
analyze wt    results/stage1_wt_validation/boltz       results/stage1_wt_validation/protenix/out $M/wt
analyze f119w $M/f119w/boltz   $M/f119w/protenix/out   $M/f119w
analyze l147r $M/l147r/boltz   $M/l147r/protenix/out   $M/l147r

echo "[$(date +%H:%M:%S)] building cross-variant benchmark..."
$PYR -m tfsensor.benchmark_compare --root $M --mutants data/mutants.json \
  --out_json $M/BENCHMARK.json > $M/BENCHMARK_REPORT.txt 2>&1
echo "[$(date +%H:%M:%S)] DONE -> $M/BENCHMARK_REPORT.txt"
