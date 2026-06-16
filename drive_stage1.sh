#!/usr/bin/env bash
# Self-contained Stage-1 driver (detach-safe under nohup): waits for the Boltz
# panel, aggregates the Boltz GO/NO-GO, runs the full Protenix panel, aggregates
# the Protenix GO/NO-GO, and writes a combined Stage-1 report. Safe to re-run.
set -uo pipefail
cd "$HOME/TFsensorSEED"

PYR="$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python"   # has rdkit (parsers)
PROTENIX="$HOME/.conda/envs/protenix2/bin/protenix"
S1=results/stage1_wt_validation
export PYTHONPATH=".:$HOME/LC-Seed"

echo "[$(date +%H:%M:%S)] drive_stage1 start"

# 1. wait for the Boltz panel to finish (it is launched separately)
echo "[$(date +%H:%M:%S)] waiting for Boltz panel (ALL SEEDS DONE)..."
while ! grep -q 'ALL SEEDS DONE' "$S1/boltz/panel.log" 2>/dev/null; do sleep 30; done
echo "[$(date +%H:%M:%S)] Boltz panel done."

# 2. Boltz GO/NO-GO across seeds
$PYR -m tfsensor.replicate_summary boltz \
  --seed_dir 1:$S1/boltz/seed1 --seed_dir 42:$S1/boltz/seed42 --seed_dir 2024:$S1/boltz/seed2024 \
  --pocket data/pocket_residues.json --panel data/steroid_panel.csv \
  --out_json $S1/boltz/go_nogo.json > $S1/boltz/go_nogo.txt 2>&1
echo "[$(date +%H:%M:%S)] Boltz GO/NO-GO written."

# 3. full Protenix panel (4 steroids x 3 seeds); wait for any smoke to clear first
while pgrep -f 'protenix.*_smoke' >/dev/null; do sleep 30; done
echo "[$(date +%H:%M:%S)] launching Protenix panel..."
$PROTENIX pred -i $S1/protenix/inputs -o $S1/protenix/out \
  -s 1,42,2024 -e 3 --use_msa True > $S1/protenix/panel.log 2>&1
echo "[$(date +%H:%M:%S)] Protenix panel done."

# 4. Protenix GO/NO-GO (ligand-ipTM)
$PYR -m tfsensor.replicate_summary protenix \
  --out_dir $S1/protenix/out --panel data/steroid_panel.csv --seeds 1,42,2024 \
  --metric ligand_iptm --out_json $S1/protenix/go_nogo.json > $S1/protenix/go_nogo.txt 2>&1
echo "[$(date +%H:%M:%S)] Protenix GO/NO-GO written."

# 5. combined report
{
  echo "==================== STAGE 1 WT VALIDATION REPORT ===================="
  echo "generated: $(date)"
  echo; echo "----- BOLTZ-2 (affinity_probability_binary) -----"
  cat $S1/boltz/go_nogo.txt
  echo; echo "----- PROTENIX (ligand_iptm, orthogonal) -----"
  cat $S1/protenix/go_nogo.txt
  echo; echo "Consensus GO requires BOTH models to reproduce the WT testosterone preference."
} > $S1/STAGE1_REPORT.txt 2>&1
echo "[$(date +%H:%M:%S)] drive_stage1 DONE -> $S1/STAGE1_REPORT.txt"
