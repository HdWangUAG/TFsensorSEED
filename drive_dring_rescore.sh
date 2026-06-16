#!/usr/bin/env bash
# Corrected re-scoring of the testosterone leads:
#   * TWO testosterone ligands (homodimer, one per pocket)
#   * many diffusion samples, then ORIENTATION-FILTER to SAR-consistent poses
#     (A-ring 3-keto near the E106/R123 cluster, not Q88) before gating.
# Designs: WT, des0039 (I61L,L85I,L122F,L143I,L146I,L147F), des0060 (I61L,L85I,L146I).
set -uo pipefail
cd "$HOME/TFsensorSEED"
export PYTHONPATH=".:$HOME/LC-Seed"; export PYTORCH_ALLOC_CONF=expandable_segments:True
PYR="$HOME/LC-Seed/envs/pyrosetta/.venv/bin/python"; BOLTZ="$HOME/LC-Seed/envs/boltz2/.venv/bin/boltz"
R=results/stage3_dring/rescore; mkdir -p "$R"
printf "name,smiles,role\ntestosterone,%s,target\n" "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O" > "$R/panel.csv"

declare -A MUT=( [wt]="" [des0039]="61:L,85:I,122:F,143:I,146:I,147:F" [des0060]="61:L,85:I,146:I" )
for d in wt des0039 des0060; do
  IN="$R/$d/inputs"; mkdir -p "$IN"
  MA=""; [ -n "${MUT[$d]}" ] && MA="--mutate ${MUT[$d]}"
  # 2-ligand holo (boltz_holo_inputs writes one ligand block per protein chain for a dimer)
  $PYR -m tfsensor.boltz_holo_inputs --seq_fasta data/AcrR_dimer.fasta --panel_csv "$R/panel.csv" \
    --out_dir "$IN" --prefix "$d" $MA >> "$R/build.log" 2>&1
  # matched apo (2 protein chains, no ligand)
  $PYR -m tfsensor.boltz_holo_inputs --seq_fasta data/AcrR_dimer.fasta --out_dir "$IN" \
    --prefix "$d" --apo $MA >> "$R/build.log" 2>&1
done
echo "[$(date +%H:%M:%S)] inputs built (2-ligand holo + apo)"

for d in wt des0039 des0060; do
  echo "[$(date +%H:%M:%S)] Boltz fold $d (10 samples)"
  $BOLTZ predict "$R/$d/inputs" --out_dir "$R/$d/out" --seed 1 \
    --diffusion_samples 10 --recycling_steps 3 --model boltz2 \
    --output_format pdb --devices 1 --accelerator gpu --use_msa_server >> "$R/boltz.log" 2>&1
done
touch "$R/RESCORE_FOLD_DONE"
echo "[$(date +%H:%M:%S)] re-fold done -> $R"
