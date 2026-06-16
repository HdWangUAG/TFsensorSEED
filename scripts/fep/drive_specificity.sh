#!/usr/bin/env bash
# ============================================================================
# E106L testosterone-specificity FEP validation (overnight, 1 GPU).
# Protein mutation WT->E106L (both chains) morphed in each ligand-bound complex
# + apo. Per-ligand dG_bound; specificity = dG_bound(testosterone) - dG_bound(comp).
# Sequential legs (GPU-bound). Each leg ~1.5 h at decent sampling -> ~8 h total.
# ============================================================================
set -uo pipefail
CAMP=/home/hdwang/TFsensorSEED/results/stage3_fep/e106l_specificity
export CAMP
export MUT_RES=106 MUT_AA=L CHAINS="A B"
export NTRANS=${NTRANS:-30} EQPS=${EQPS:-400} TRPS=${TRPS:-80}
RUN="$CAMP/run_rbfe_general.sh"
LOG="$CAMP/drive.log"
LIGANDS="testosterone progesterone cortisol estradiol"
APO_PROT="$CAMP/prep/testosterone/protein_only.pdb"   # ligand-free reference protein

echo "[$(date '+%F %T')] === E106L specificity campaign START (NTRANS=$NTRANS EQPS=$EQPS TRPS=$TRPS) ===" | tee -a "$LOG"

run_leg(){  # $1=TAG $2=LEG ; ligand-specific env already exported
  echo "[$(date '+%F %T')] >>> LEG $1 ($2) starting" | tee -a "$LOG"
  if conda run -n fep --no-capture-output bash "$RUN" >>"$CAMP/leg_$1.log" 2>&1; then
    echo "[$(date '+%F %T')] <<< LEG $1 done" | tee -a "$LOG"
  else
    echo "[$(date '+%F %T')] !!! LEG $1 FAILED (see leg_$1.log)" | tee -a "$LOG"
  fi
}

# --- 4 bound legs ---
for lig in $LIGANDS; do
  ACP="$CAMP/prep/$lig/$lig.acpype"
  export LEG=bound TAG="$lig" PROT="$CAMP/prep/$lig/protein_only.pdb"
  export LIGITP="$ACP/${lig}_GMX.itp" LIGGRO="$ACP/${lig}_GMX.gro"
  run_leg "$lig" bound
done

# --- apo leg (no ligand) ---
unset LIGITP LIGGRO
export LEG=apo TAG="apo" PROT="$APO_PROT"
run_leg "apo" apo

echo "[$(date '+%F %T')] === campaign COMPLETE ===" | tee -a "$LOG"
touch "$CAMP/CAMPAIGN_DONE"
