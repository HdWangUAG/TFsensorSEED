#!/usr/bin/env bash
# ============================================================================
# Generalized Tier-2 RBFE leg: pmx hybrid-topology + GROMACS non-eq TI.
# Morphs the PROTEIN (WT -> mutant, both chains) in a given ligand-bound complex
# (or apo). dG of that morph; the specificity signal is the difference of
# dG_bound across ligands (the apo leg cancels in the double-difference).
#
# Driven entirely by environment variables (set by drive_specificity.sh):
#   LEG=bound|apo  TAG=<workdir name>  CAMP=<campaign dir>
#   PROT=<protein_only.pdb>  MUT_RES=106 MUT_AA=L  CHAINS="A B"
#   LIGITP=<lig_GMX.itp> LIGGRO=<lig_GMX.gro>            (bound only)
#   NTRANS, EQPS, TRPS                                   (sampling)
# Run inside the 'fep' conda env.
# ============================================================================
set -uo pipefail
: "${LEG:?}"; : "${TAG:?}"; : "${CAMP:?}"; : "${PROT:?}"; : "${MUT_RES:?}"; : "${MUT_AA:?}"
CHAINS="${CHAINS:-A B}"
FE=/home/hdwang/.conda/envs/fep
export GMXLIB=$FE/lib/python3.10/site-packages/pmx/data/mutff
GMX="gmx"; MUTFF=amber99sb-star-ildn-mut
NTRANS=${NTRANS:-30}; EQPS=${EQPS:-500}; TRPS=${TRPS:-80}
W=$CAMP/work/$TAG; rm -rf "$W"; mkdir -p "$W"; cd "$W"

echo "[$(date +%H:%M:%S)] === TAG=$TAG LEG=$LEG mut=${MUT_RES}${MUT_AA} chains='$CHAINS' (NTRANS=$NTRANS EQPS=$EQPS TRPS=$TRPS) ==="

# ---- 1. hybrid topology (protein point mutation, both chains) ----
cp "$PROT" protein_only.pdb
: > mut.txt
for c in $CHAINS; do printf "%s %s %s\n" "$c" "$MUT_RES" "$MUT_AA" >> mut.txt; done
$GMX pdb2gmx -f protein_only.pdb -o wt_h.pdb -p topol.top -ff $MUTFF -water tip3p -ignh >pdb2gmx1.log 2>&1
pmx mutate -f wt_h.pdb -o mutant.pdb -ff $MUTFF --keep_resid --script mut.txt >mutate.log 2>&1
$GMX pdb2gmx -f mutant.pdb -o hybrid.gro -p hybrid.top -ff $MUTFF -water tip3p >pdb2gmx2.log 2>&1
pmx gentop -p hybrid.top -o pmxtop.top -ff $MUTFF >gentop.log 2>&1
[ -f pmxtop.top ] || { echo "[FAIL] hybrid topology build"; tail -15 gentop.log mutate.log; exit 1; }
echo "[$(date +%H:%M:%S)] hybrid topology built"

# ---- 2. assemble system (+ ligand for bound) ----
if [ "$LEG" = "bound" ]; then
  : "${LIGITP:?}"; : "${LIGGRO:?}"
  MOL=$(awk '/\[ moleculetype \]/{f=1;next} f&&/^[[:space:]]*;/{next} f&&NF{print $1; exit}' "$LIGITP")
  sed -i "/forcefield.itp/a #include \"$LIGITP\"" pmxtop.top
  awk -v mol="$MOL" 'BEGIN{m=0} {print} /\[ molecules \]/{m=1} m==1 && /Protein_chain_B/{print mol"           1"; m=2}' pmxtop.top > tmp.top && mv tmp.top pmxtop.top
  python3 - "$LIGGRO" <<'PY'
import sys
prot=open("hybrid.gro").read().splitlines()
lig=open(sys.argv[1]).read().splitlines()
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
printf "integrator=steep\nnsteps=1\n" > ions.mdp
$GMX grompp -f ions.mdp -c solv.gro -p pmxtop.top -o ions.tpr -maxwarn 5 >grompp_ions.log 2>&1
echo SOL | $GMX genion -s ions.tpr -o ions.gro -p pmxtop.top -neutral -conc 0.15 -pname NA -nname CL >genion.log 2>&1
[ -f ions.gro ] || { echo "[FAIL] genion"; tail -15 genion.log grompp_ions.log; exit 1; }
echo "[$(date +%H:%M:%S)] solvated+ionized: $(sed -n '2p' ions.gro) atoms"

# ---- 4. MDP templates ----
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
emhdr(){ printf "integrator=steep\nnsteps=10000\nemtol=100\nemstep=0.005\n%s\ninit-lambda=%s\n" "$common" "$1"; }
nvthdr(){ cat <<EOF
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
trhdr(){ cat <<EOF
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
  emhdr $L > em$L.mdp; nvthdr $L > nvt$L.mdp; eqhdr $L > eq$L.mdp
  $GMX grompp -f em$L.mdp -c ions.gro -p pmxtop.top -o em$L.tpr -maxwarn 5 >grompp_em$L.log 2>&1
  [ -f em$L.tpr ] || { echo "[FAIL] em$L grompp:"; tail -20 grompp_em$L.log; exit 1; }
  GPUMD em$L
  echo "[$(date +%H:%M:%S)] EM state $L: $(grep -A1 'Maximum force' em$L.log | tail -1 2>/dev/null | awk '{print $1,$2,$3,$4}')"
  $GMX grompp -f nvt$L.mdp -c em$L.gro -r em$L.gro -p pmxtop.top -o nvt$L.tpr -maxwarn 5 >grompp_nvt$L.log 2>&1
  [ -f nvt$L.tpr ] || { echo "[FAIL] nvt$L grompp:"; tail -15 grompp_nvt$L.log; exit 1; }
  GPUMD nvt$L
  [ -f nvt$L.gro ] || { echo "[FAIL] nvt$L mdrun crashed:"; tail -15 mdrun_nvt$L.log; exit 1; }
  $GMX grompp -f eq$L.mdp -c nvt$L.gro -t nvt$L.cpt -p pmxtop.top -o eq$L.tpr -maxwarn 5 >grompp_eq$L.log 2>&1
  [ -f eq$L.tpr ] || { echo "[FAIL] eq$L grompp:"; tail -15 grompp_eq$L.log; exit 1; }
  GPUMD eq$L
  [ -f eq$L.gro ] || { echo "[FAIL] eq$L mdrun crashed:"; tail -15 mdrun_eq$L.log; exit 1; }
  echo "[$(date +%H:%M:%S)] equil state $L done"
done

# ---- 7. non-equilibrium transitions ----
DL=$(python3 -c "print(1.0/($TRPS*500))")
mkdir -p tr
echo System | $GMX trjconv -s eq0.tpr -f eq0.xtc -o tr/frA.gro -sep >/dev/null 2>&1
echo System | $GMX trjconv -s eq1.tpr -f eq1.xtc -o tr/frB.gro -sep >/dev/null 2>&1
trhdr 0 $DL  > tiF.mdp
trhdr 1 -$DL > tiR.mdp
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
pmx analyse -fA $fwd -fB $rev -o results_$TAG.dat -w work_$TAG.png -t 298 >analyse_$TAG.log 2>&1 || true
echo "[$(date +%H:%M:%S)] === $TAG analysis ==="; grep -E "BAR: dG|BAR: Std Err \(bootstrap\)|CGI: dG" results_$TAG.dat 2>/dev/null || tail -20 analyse_$TAG.log
touch "$W/LEG_DONE"
