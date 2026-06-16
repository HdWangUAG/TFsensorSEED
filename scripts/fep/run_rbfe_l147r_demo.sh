#!/usr/bin/env bash
# ============================================================================
# Tier-2 RBFE: pmx + GROMACS non-equilibrium TI for L147R (chain A) with cortisol.
#   ddG_bind = dG_bound(WT->mut) - dG_apo(WT->mut)
# DEMO scale (short equil + few fast transitions) — prototype, not production-converged.
# Usage:  run_rbfe.sh <bound|apo>
# Run inside the 'fep' conda env (gmx, pmx, acpype on PATH).
# ============================================================================
set -uo pipefail
LEG="${1:?usage: run_rbfe.sh <bound|apo>}"
P=/home/hdwang/TFsensorSEED/results/stage3_fep/proto_l147r_cortisol
FE=/home/hdwang/.conda/envs/fep
export GMXLIB=$FE/lib/python3.10/site-packages/pmx/data/mutff
GMX="gmx"
MUTFF=amber99sb-star-ildn-mut
NTRANS=${NTRANS:-8}          # non-eq transitions per direction
EQPS=${EQPS:-100}            # equilibration ps per end-state
TRPS=${TRPS:-50}             # transition length ps
W=$P/work/$LEG; rm -rf "$W"; mkdir -p "$W"; cd "$W"

echo "[$(date +%H:%M:%S)] === LEG=$LEG  (NTRANS=$NTRANS EQPS=$EQPS TRPS=$TRPS) ==="

# ---- 1. hybrid topology (protein L147R chain A) ----
cp "$P/protein_only.pdb" .
printf "A 147 R\n" > mut.txt
$GMX pdb2gmx -f protein_only.pdb -o wt_h.pdb -p topol.top -ff $MUTFF -water tip3p -ignh >/dev/null 2>&1
pmx mutate -f wt_h.pdb -o mutant.pdb -ff $MUTFF --keep_resid --script mut.txt >/dev/null 2>&1
$GMX pdb2gmx -f mutant.pdb -o hybrid.gro -p hybrid.top -ff $MUTFF -water tip3p >/dev/null 2>&1
pmx gentop -p hybrid.top -o pmxtop.top -ff $MUTFF >/dev/null 2>&1
echo "[$(date +%H:%M:%S)] hybrid topology built"

# ---- 2. assemble system (+ cortisol for bound) ----
if [ "$LEG" = "bound" ]; then
  # insert cortisol atomtypes+moleculetype after the FF include, and add to [molecules]
  sed -i "/forcefield.itp/a #include \"$P/cortisol.acpype/cortisol_GMX.itp\"" pmxtop.top
  awk 'BEGIN{m=0} {print} /\[ molecules \]/{m=1} m==1 && /Protein_chain_B/{print "cortisol           1"; m=2}' pmxtop.top > tmp.top && mv tmp.top pmxtop.top
  # merge protein + cortisol coords (same frame; just concatenate, fix count)
  python3 - <<PY
prot=open("hybrid.gro").read().splitlines()
lig=open("$P/cortisol.acpype/cortisol_GMX.gro").read().splitlines()
np=int(prot[1]); nl=int(lig[1])
body=prot[2:2+np]+lig[2:2+nl]
open("complex.gro","w").write(prot[0]+"\n"+str(np+nl)+"\n"+"\n".join(body)+"\n"+prot[-1]+"\n")
PY
  START=complex.gro
else
  START=hybrid.gro
fi
echo "[$(date +%H:%M:%S)] system assembled ($START)"

# ---- 3. box, solvate, ions ----
$GMX editconf -f $START -o box.gro -bt dodecahedron -d 1.0 >/dev/null 2>&1
$GMX solvate -cp box.gro -cs spc216.gro -p pmxtop.top -o solv.gro >/dev/null 2>&1
cat > ions.mdp <<EOF
integrator=steep
nsteps=1
EOF
$GMX grompp -f ions.mdp -c solv.gro -p pmxtop.top -o ions.tpr -maxwarn 5 >grompp_ions.log 2>&1
echo SOL | $GMX genion -s ions.tpr -o ions.gro -p pmxtop.top -neutral -conc 0.15 -pname NA -nname CL >genion.log 2>&1
echo "[$(date +%H:%M:%S)] solvated+ionized: $(sed -n '2p' ions.gro) atoms"

# ---- 4. MDP files ----
common="cutoff-scheme=Verlet
nstlist=20
coulombtype=PME
rcoulomb=1.0
rvdw=1.0
constraints=h-bonds
constraint-algorithm=lincs
free-energy=yes
sc-alpha=0.3
sc-coul=yes
sc-power=1
sc-sigma=0.25
nstcalcenergy=100"
emhdr(){ cat <<EOF
integrator=steep
nsteps=10000
emtol=100
emstep=0.005
$common
init-lambda=$1
EOF
}
nvthdr(){ # restrained warm-up at dt=1fs to relax hybrid dummies/solvent
cat <<EOF
integrator=md
dt=0.001
nsteps=20000
define=-DPOSRES
continuation=no
gen-vel=yes
gen-temp=298
tcoupl=v-rescale
tc-grps=System
tau-t=0.5
ref-t=298
pcoupl=no
lincs-order=8
lincs-iter=2
$common
init-lambda=$1
EOF
}
eqhdr(){ cat <<EOF
integrator=md
dt=0.002
nsteps=$((EQPS*500))
continuation=yes
tcoupl=v-rescale
tc-grps=System
tau-t=0.5
ref-t=298
pcoupl=C-rescale
pcoupltype=isotropic
tau-p=2.0
ref-p=1.0
compressibility=4.5e-5
lincs-order=8
nstxout-compressed=$((EQPS*500/NTRANS))
compressed-x-grps=System
$common
init-lambda=$1
EOF
}
trhdr(){ # $1=init-lambda(0/1) $2=delta-lambda
cat <<EOF
integrator=sd
dt=0.002
nsteps=$((TRPS*500))
gen-vel=yes
gen-temp=298
continuation=no
lincs-order=8
tc-grps=System
tau-t=1.0
ref-t=298
pcoupl=C-rescale
tau-p=2.0
ref-p=1.0
compressibility=4.5e-5
$common
init-lambda=$1
delta-lambda=$2
nstdhdl=50
dhdl-derivatives=yes
separate-dhdl-file=yes
EOF
}

# ---- 5+6. per end-state: EM -> restrained NVT warm-up -> NPT equilibration ----
GPUMD(){ $GMX mdrun -deffnm $1 -ntmpi 1 -nb gpu "${@:2}" >mdrun_$1.log 2>&1 || $GMX mdrun -deffnm $1 "${@:2}" >mdrun_$1.log 2>&1; }
for L in 0 1; do
  emhdr  $L > em$L.mdp;  nvthdr $L > nvt$L.mdp;  eqhdr $L > eq$L.mdp
  # EM
  $GMX grompp -f em$L.mdp -c ions.gro -p pmxtop.top -o em$L.tpr -maxwarn 5 >grompp_em$L.log 2>&1
  [ -f em$L.tpr ] || { echo "[FAIL] em$L grompp:"; tail -20 grompp_em$L.log; exit 1; }
  GPUMD em$L
  echo "[$(date +%H:%M:%S)] EM state $L: $(grep -A1 'Maximum force' em$L.log | tail -1 2>/dev/null | awk '{print $1,$2,$3,$4}')"
  # NVT warm-up (posres, dt=1fs)
  $GMX grompp -f nvt$L.mdp -c em$L.gro -r em$L.gro -p pmxtop.top -o nvt$L.tpr -maxwarn 5 >grompp_nvt$L.log 2>&1
  [ -f nvt$L.tpr ] || { echo "[FAIL] nvt$L grompp:"; tail -15 grompp_nvt$L.log; exit 1; }
  GPUMD nvt$L
  [ -f nvt$L.gro ] || { echo "[FAIL] nvt$L mdrun crashed:"; tail -15 mdrun_nvt$L.log; exit 1; }
  # NPT equilibration (dt=2fs, produces eq$L.xtc for transition seeding)
  $GMX grompp -f eq$L.mdp -c nvt$L.gro -t nvt$L.cpt -p pmxtop.top -o eq$L.tpr -maxwarn 5 >grompp_eq$L.log 2>&1
  [ -f eq$L.tpr ] || { echo "[FAIL] eq$L grompp:"; tail -15 grompp_eq$L.log; exit 1; }
  GPUMD eq$L
  [ -f eq$L.gro ] || { echo "[FAIL] eq$L mdrun crashed:"; tail -15 mdrun_eq$L.log; exit 1; }
  echo "[$(date +%H:%M:%S)] equil state $L done"
done

# ---- 7. non-equilibrium transitions: A->B (from eq0) and B->A (from eq1) ----
DL=$(python3 -c "print(1.0/($TRPS*500))")
mkdir -p tr
# dump frames from each equilibrium trajectory
echo System | $GMX trjconv -s eq0.tpr -f eq0.xtc -o tr/frA.gro -sep >/dev/null 2>&1
echo System | $GMX trjconv -s eq1.tpr -f eq1.xtc -o tr/frB.gro -sep >/dev/null 2>&1
trhdr 0 $DL  > tiF.mdp     # forward A->B
trhdr 1 -$DL > tiR.mdp     # reverse B->A
fwd=""; rev=""
for i in $(seq 0 $((NTRANS-1))); do
  if [ -f tr/frA$i.gro ]; then
    $GMX grompp -f tiF.mdp -c tr/frA$i.gro -p pmxtop.top -o tr/f$i.tpr -maxwarn 5 >/dev/null 2>&1
    $GMX mdrun -deffnm tr/f$i -dhdl tr/f$i.dhdl.xvg -ntmpi 1 -nb gpu >/dev/null 2>&1 || $GMX mdrun -deffnm tr/f$i -dhdl tr/f$i.dhdl.xvg >/dev/null 2>&1
    [ -f tr/f$i.dhdl.xvg ] && fwd="$fwd tr/f$i.dhdl.xvg"
  fi
  if [ -f tr/frB$i.gro ]; then
    $GMX grompp -f tiR.mdp -c tr/frB$i.gro -p pmxtop.top -o tr/r$i.tpr -maxwarn 5 >/dev/null 2>&1
    $GMX mdrun -deffnm tr/r$i -dhdl tr/r$i.dhdl.xvg -ntmpi 1 -nb gpu >/dev/null 2>&1 || $GMX mdrun -deffnm tr/r$i -dhdl tr/r$i.dhdl.xvg >/dev/null 2>&1
    [ -f tr/r$i.dhdl.xvg ] && rev="$rev tr/r$i.dhdl.xvg"
  fi
done
echo "[$(date +%H:%M:%S)] transitions done (fwd=$(echo $fwd|wc -w) rev=$(echo $rev|wc -w))"

# ---- 8. analyse (BAR/Crooks via pmx) ----
pmx analyse -fA $fwd -fB $rev -o results_$LEG.dat -w work_$LEG.png -t 298 >analyse_$LEG.log 2>&1 || true
echo "[$(date +%H:%M:%S)] === LEG $LEG analysis ==="; cat results_$LEG.dat 2>/dev/null || tail -20 analyse_$LEG.log
touch "$W/LEG_DONE"
