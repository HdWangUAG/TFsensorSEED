# TFsensorSEED — progress ledger

Single source of truth for campaign state across nodes. Each node updates its section;
merge = text merge. See `HANDOFF.md` for env/sync/merge mechanics, `docs/agent_memory/`
for the agent's accumulated reasoning. **Numbering = MODEL index everywhere (exp = model + 9).**

_Last updated: 2026-06-17 (Node-Aspartate results merged)_

## Established conclusions (trust these)
- **WT is a 4-en-3-one sensor**: testosterone > cortisol > progesterone; **estradiol = non-responder**.
- **Recognition code** (`results/stage1e_pdbmine/`): A-ring 3-keto ↔ R123/E106/D116 cluster; D-ring/C17 = the selectivity lever among test/prog/cort; estradiol phenol needs a Glu/Arg clamp.
- **DL pose caveat**: no crystal exists; Boltz/Protenix poses are unreliable for orientation/amplitude (testosterone flips — quantified: only **1/15** WT-holo poses are A-ring-correct, #4). Use SAR as a *qualitative* hypothesis; treat allosteric opening + specificity as **wet-lab** readouts.
- **Specificity ≠ resolvable by computation at the mutation level** — three independent methods fail: supervised ranker ≈ chance; P1 GP Spearman ≤0; **#4 flex-ddG on orientation-corrected poses gets the test/prog selectivity shift WRONG-SIGNED for all 3 validated singles** (I61L/L85I/E106L). Computation is reliable only for **coarse binder/order/dead-binder** questions. **→ See `docs/COMPUTATIONAL_BOUNDARY.md` for the full CAN/CANNOT boundary + evidence + when-to-use guide. The trusted specificity signal is the wet-lab scan / round-1 dose-response.**
- **Empirical leads** (`results/stage1f_empirical/`): testosterone-selective = **E106L, L85I, I61L**; **R123E → cortisol** (validated); estradiol unreachable by point mutation.

## Pipeline (4-tier)
Tier-0 LigandMPNN gen → Tier-1 flex-ddG specificity screen → Tier-1.5 Boltz 2-state gate (now **2-ligand**) → Tier-2 FEP/ligand-RBFE. Drivers: `drive_stage3.sh`, `drive_dring.sh`, `drive_prog_cort.sh`. Code refactor: paths via `tfsensor/config.py` + `.env`.

## Campaign status

| Campaign | Stage | State | Key output | Leads / finding |
|---|---|---|---|---|
| Estradiol | full | done | `results/stage3_design/STAGE3_SUMMARY.md` | 65 designs; **0/20 pass gate** (bind ≠ activate) |
| **Testosterone** (D-ring) | gen+screen+gate+validate | done | `results/stage3_dring/validate/VALIDATE_SUMMARY.md` | **des0039, des0044, des0060** (I61L+L85I core); gate 7/12 (1-ligand) |
| Testosterone 2-ligand gate | gate (all 71) | **done** (Alpha) | `results/stage3_dring/gate2lig/gate2lig.json` | **58/71 pass**. At 2 ligands holo opens wide for ALL 71 (38–49 Å) → agonist criterion non-discriminating (Boltz over-opens; Protenix disagreed) → real filter = **apo/basal-leak** (13 leaky fails). apo identical 1-vs-2-lig. Leads des0039/44/60 pass (tight apo + wide holo). |
| FEP demo (L147R×cortisol) | Tier-2 | done | `results/stage3_fep/proto_l147r_cortisol/FEP_DEMO_RESULTS.md` + `FEP_demo_figure.png` | ΔΔG_bind −8.6 kJ/mol (BAR), sign-correct; pipeline validated |
| E106L specificity FEP | Tier-2 | done | `results/stage3_fep/e106l_specificity/SPECIFICITY_RESULTS.md` | converged but **fails vs assay** — GIGO (E106 second-shell, unstable pose). Lesson: restrain pose + first-shell target |
| **Progesterone** | gen+screen+gate | **done** (Aspartate) | `results/stage3_prog/PROG_CORT_SCREEN_SUMMARY.md` | leads **des0002** (I61L, Q88T), **des0000** (I61L, Q88L); both pass 2-lig gate |
| **Cortisol** | gen+screen+gate | **done** (Aspartate) | `results/stage3_prog/GATE2LIG_SUMMARY.md` | lead **des0001** (I61V, Q88L, R123E) passes gate. All selective converge on R123E. Top ddG (des0007) is leaky |
| **Estradiol** (re-screen) | gen+screen | **assigned → Aspartate** | `results/stage3_estradiol/` | Glu/Arg/His phenol clamp; prior single-anchor run failed gate (`results/stage3_design/`) |

## Wet-lab panel (current best, build-and-test)
Testosterone: **des0039 / des0060 / des0044** (I61L+L85I) + single **E106L**.
Progesterone: **des0002** (I61L+Q88T) / **des0000** (I61L+Q88L).
Cortisol: **des0001** (I61V+Q88L+R123E) + single **R123E** (validated).
Judge by gate + FEP + wet-lab, NOT the ΔΔG margin.
**Bench deliverable (FASTA + mutations + caveats):** `deliverables/AcrR_testosterone_sensor_designs.{md,csv}` (regenerate after the 2-ligand gate finishes to refresh the gate Å values).

## Next actions (claim by node, then check off)
- [x] (Alpha) finish testosterone 2-ligand gate → compare vs 1-ligand; pick survivors.
- [x] (Aspartate) prog/cort gen+screen → ranked leads + 2-ligand gate on leads.
- [ ] (Aspartate) estradiol gen+screen (Glu/Arg/His clamp).
- [ ] (Beta) build **ligand-ligand RBFE executor** for the test/prog/cort triad → ΔΔΔG specificity (identical A-ring, C17 perturbation maps cleanly; estradiol excluded). This is the rigorous "explain the ΔΔΔG" tool and avoids the E106L second-shell pitfall.
- [ ] (Beta) consider per-position LigandMPNN bias (current `--favor` is uniform across design positions).

## ML track (`tfsensor/ml/`) — general steroid–protein binding/specificity predictor
New subpackage; goal = a reusable steroid-binding model focused on **relative binding preference ranking** and **interpretability** (affinity / binder / preference ranking / structural attribution), AcrR as the headline test case. Plan: `~/.claude/plans/composed-puzzling-church.md`.
Strategy: **evaluate pretrained scorers first**, bespoke EGNN only if they fail preference ranking. 
*Key Insight*: Natural proteins are promiscuous, and pure allosteric activation is hard to predict. Thus, the model targets *relative binding affinity differences* (preference ranking) rather than absolute functional readouts. **Interpretability** (mapping preference to specific residue-ligand interactions) is mandatory to justify the score. Local GPU.

- **Phase 0 (data) — DONE.** Backbone = **LC-SEED** (`~/LC-Seed/static/dataset/`): mined **324 steroid
  ligand codes → 8,742 steroid–protein complexes / 2,564 PDBs** (`data/ml/lcseed_steroid_complexes.csv`)
  via `ccd_smiles.py` (RCSB CCD, 50,469 codes) + `steroid_filter.py` (gonane ring perception) +
  `lcseed_mining.py`. Affinity labels = ChEMBL NR loader (`nr_datasets.py`, 6 receptors). Unified
  manifest + **CATH-family leakage-safe splits** (`build_dataset.py`, `splits.py`; no-leak verified,
  ΔG in all splits). 8 Å pockets via `pocket_extract.py`. _LC-SEED = structures/pockets/sequences/
  contacts/splits; ChEMBL/PDBbind/NR-DBIND = affinity labels; they join on PDB id / ligand code._
- **PIVOT (2026-06-18):** target = **relative binding-preference ranking / ΔΔΔG preference SHIFTS**
  (which ligand a mutation favors in a pocket), NOT allosteric activation (proteins are promiscuous;
  activation is unpredictable). **Interpretability mandatory** — every score maps to specific
  residue↔ligand contacts. **Boltz-2 = negative control only** (AF3 insensitive to point mutations).
- **Phase 1 (baselines) — done for now.** `gnina` run on the panel: ranks prog>test>estr>cort (binding,
  not activation) — `results/ml_phase1/baseline_gnina.md`. Now framed as the expected binding-vs-activation
  gap. `baselines/boltz_head.py` = Boltz-2 **negative-control** scaffold (parse path tested; GPU run deferred).
- **Data-quality (seq redundancy) — fixed.** Same protein under many PDB IDs: 2,564 steroid PDBs →
  **1,577 unique sequences**. `data/protein_seq.py` assigns a `seq_hash`; `build_dataset.py` dedups
  identical (sequence, ligand) complexes (8,742 → **1,892** structural rows) and uses `seq_hash` as the
  split group_key so identical sequences can't leak across train/val/test (exact-match; MMseqs2 near-id
  clustering is the planned tightening). Manifest = 2,259 rows (1,892 struct + 367 ChEMBL); splits leak-free.
- **Phase 2 (preference ranking) — foundation built & tested.** `data/preference_pairs.py` (within-
  (receptor,split) ΔpKd pairs → 7,901 pairs); `eval/acrr_specificity_test.py` reframed around **ΔΔΔG
  preference shifts** vs flex-ddG (R123E & L147R both favor cortisol — validated); `features/
  contacts_fingerprint.py` = **interpretable (residue-type × interaction-type) fingerprint** (so feature
  attribution == atom-residue interpretability). All `tfsensor/ml/tests/` green.
- **Contact bridge — NO blind docking** (user mandate: rigid steroids dock upside-down → GIGO).
  `features/template_pose.py` places a query steroid by superposing its **rigid 17-carbon gonane nucleus**
  onto a reference steroid's known pose (rdMolAlign over nucleus atoms only; CompareAny bonds so aromatic-A
  estradiol matches enone-A); QC-filters on core size + RMSD (validated: prog 0.01 Å, estr 0.37, cort 0.44;
  non-steroid rejected). `test_template_pose.py` green.
- **Agonist references — built.** `data/reference_structures.py` auto-picks the highest-res crystal of each
  NR bound to its **natural (agonist) ligand** (antagonists distort the pocket via H12): AR/7ztz/DHT 1.4Å,
  ESR1/7nel & ESR2/3oll/estradiol, GR/4p6x/cortisol, PR/1a28/progesterone, MR/2aa2/aldosterone. Reference
  ligand poses rebuilt (crystal coords + bond orders from CCD template); 8 Å pockets extracted.
- **Contact bridge — built & validated.** `features/pose_contacts.py` poses each ChEMBL ligand by rigid-core
  superposition onto its receptor's agonist reference, then classifies residue contacts (hbond/hydrophobic/
  pistacking/saltbridge) → `contacts_fingerprint`. Recovers known AR biology (testosterone/DHT → ARG+ASN+THR
  H-bonds at the 3-keto/17-OH anchors + hydrophobic Met/Leu/Phe). `test_pose_contacts.py` green.
- **Interpretable ranker — `model/preference_ranker.py`** (numpy pairwise logistic on contact-difference
  features; weights ARE the explanation). Trained: 290/367 ligands featurized (77 dropped on core-pose QC/
  timeout), 10,152 train pairs, **train pairwise_acc 0.748** (> gnina's failed specificity). Weights are
  biochemically sensible: polar H-bond/saltbridge anchoring (His/Thr/Asn/Asp) + Phe π-stacking RAISE
  preference. **CAVEATS:** val/test tiny (10/2 pairs — capped ChEMBL pull → generalization UNPROVEN);
  pooled pan-receptor linear model conflates pockets; 77 dropped need 2D (Morgan+ESM) fallback.
- **Next:** expand affinity labels (full ChEMBL + NR-DBIND negatives → real val/test pairs); 2D fallback
  (Morgan+ESM) for ligands failing core-pose QC; bespoke GNN + Integrated Gradients (Phase 3, `~/LC-Seed/envs/ml` GPU venv).
- gnina at `/usr/local/bin/gnina` (v1.3.1). Generated ML data under `data/ml/` git-ignored. Not committed.
