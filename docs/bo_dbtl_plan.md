# Plan: Multi-objective Bayesian-optimization DBTL loop for AcrR steroid biosensors (`tfsensor/ml/bo/`)

## Context

The supervised steroid-binding **ranker failed to generalize** (held-out test pairwise-acc ≈ 0.50 = chance;
`tfsensor/ml/model/preference_ranker.py`). Lesson: a globally-accurate predictor isn't achievable from the
available data, and flex-ddG specificity sits at the ~1 kcal/mol noise floor. The **trusted** signal is the
**wet-lab GFP fold-induction** screen.

That motivates a different tool: **Bayesian optimization (BO) with a Gaussian-process (GP) surrogate**. BO
doesn't need a globally-accurate model — it uses a cheap surrogate *with calibrated uncertainty* to decide
which few **expensive** evaluations (wet-lab builds/assays) to spend next, seeded by data we already have.

**Decisions (confirmed):**
- **Objective = multi-objective**: (1) *selectivity* for a chosen target steroid, (2) *sensor quality*
  (dynamic range / low basal leak). Optimize the Pareto front of both.
- **Loop = wet-lab-in-the-loop** (DBTL): BO proposes each next **batch** of designs for the GFP screen;
  the existing **84-variant single-mutant scan = round 0**; assay results feed back (active learning).
- **Scope = multi-mutation designs** (combinatorial pocket redesign, not just singles).
- **Stack = BoTorch** (multi-objective qNEHVI + batch q-proposals + outcome constraints).
- **Features = ESM-2 pocket-seq embedding ⊕ physicochemical mutation encoding** (concatenated).
- BO math runs on **CPU**; **GPU only** for the one-time ESM-2 embedding precompute.

**Central risk (state it honestly):** the seed is **single-mutant** but we optimize **multi-mutant** designs —
epistasis is unobserved, so multi-mutant predictions are extrapolation. De-risked (not removed) by: additive-
leaning physchem prior + ESM context; biasing early rounds to low k; and a **cheap in-silico pre-filter**
(flex-ddG + Boltz gate) that drops obvious losers before any wet-lab spend.

## Review outcome — minicrew panel, 2026-06-22 (`conversations/20260622_132256_bo_plan_review.md`)

ML/Statistics + Structural Biologist + High-Throughput Screening, synthesized by PI/Moderator. The revisions
below are folded into this plan. Unanimous points:
- **Singles→multi extrapolation is the central, unproven risk** — measure epistasis *directly* in round-1 before any BO-combinatorial design.
- **Objective granularity is wrong**: single-dose fold misranks (variants differ in operating range, e.g. WT 1–100 µM vs L147R 1–5 µM) and conflates basal leak with induction (A66M basal 130k = fake signal). Need **dose-response (EC50 + amplitude)** and **replicate variance fed as heteroscedastic GP noise**; `λ`/`EPS` are provisional.
- **y2 "sensor quality" may not be learnable** from a binding-feature surrogate (allostery ≠ binding; ~0.5 Å opening vs several-Å noise). → either add an explicit, separately-measured activation descriptor, or **drop y2 as a predicted objective and treat amplitude as wet-lab-only**. The P1 benchmark decides this.
- **In-silico pre-filter inherits flipped poses** (~8/12 WT holo are A-ring-flipped); GP/flex-ddG/Boltz/ESM share one structural prior, so stacking may *amplify* shared error. SAR-restrain orientation; defer FEP until controlled.
- **A cheap retrospective gate must precede any spend** (see P1, now sharpened).

> ✅ **DECISION (2026-06-22): stay target-agnostic; validate the method first.** Run P0/P1 with the code
> parameterized by target (default **testosterone>progesterone** for concrete pass criteria, since it has
> validated first-shell singles), but **don't commit a target until the P1 grouped-CV gate passes**. The benchmark
> is inherently multi-target (it checks rediscovery of E106L/L85I/I61L *and* R123E→cortisol), so it validates the
> surrogate across axes regardless. Commit the campaign target (test>prog / cortisol / estradiol-moonshot) only
> after P1 passes and the feature ablation is in. estradiol remains gated on *also* adding an explicit
> DBD-activation objective (no single/double reaches it; 0/20 prior leads activated).

## Environment
New venv `~/LC-Seed/envs/ml/.venv` (path already wired as `config.ML_PY`): `torch` (CPU ok for GP),
`gpytorch`, `botorch`, `fair-esm`, `scikit-learn`, `numpy`, `pandas`. ESM precompute can reuse the existing
`~/.conda/envs/pyrosetta` (torch+cu130+fair-esm) writing to the shared `config.ESM_CACHE_DIR`. Add config keys
`TFSENSOR_BO_DIR` (default `results/stage4_bo`) + `TFSENSOR_ESM_MODEL` (default `esm2_t33_650M_UR50D`).

## Module layout — `tfsensor/ml/bo/` (pure-numpy modules importable in any env; BoTorch/ESM need the ml venv)
- `seed.py` — parse `results/stage1f_empirical/scan_model_numbering.csv` → objective vectors per (variant, target). Pure numpy.
- `physchem.py` — 14-position × 5-property mutation-delta encoding (70-dim). Pure numpy.
- `../features/esm_embed.py` — thread mutations onto WT chain → ESM-2 → mean-pool over the 14 pocket residues; cache by mutation-set hash under `ESM_CACHE_DIR`. (GPU.)
- `featurize.py` — `featurize(mutations) -> vec` = ESM ⊕ physchem (+ cache orchestration).
- `candidates.py` — per-round constrained multi-mutation pool (LigandMPNN lib ∪ combos of good singles ∪ GP-guided local search); constraints: symmetric (implicit), optional R123∈{D,E} anchor, `max_k`.
- `surrogate.py` — BoTorch `ModelListGP` (one Matérn-ARD GP per objective; optional 3rd for a leak/constraint outcome). `fit_gpytorch_mll`, CPU/double.
- `acquisition.py` — `qNoisyExpectedHypervolumeImprovement` (qNEHVI), WT-anchored reference point, optional outcome constraints; `optimize_acqf_discrete` over the candidate pool → q designs.
- `loop.py` — DBTL CLI: `fit` / `propose` / `build` / `ingest` (round orchestrator).
- `eval.py` — retrospective LOO + qNEHVI rediscovery (reuse `tfsensor/ml/eval/metrics.py`).
- `tests/test_bo_{seed,featurize,loop}.py` — golden objective values, featurization determinism, mock round (no wet-lab/GPU).

## Reuse (do not reinvent)
- `tfsensor/ligandmpnn_gen.py` — `_wt_seq`, `POCKET`, `ANCHOR_*`, `_collect` (the `library.json` build-list schema), `run` (regenerate a constrained multi-mutant library per round).
- `tfsensor/design_score.py::cmd_panel` (+ `_thread`/`ONE2THREE`) — **the arbitrary-mutation flex-ddG pre-screen**. ⚠️ Use THIS, **not** `ddg_mutation.run_backbone` (its mutation set is hardcoded to 4 entries and asserts WT identity — cannot score arbitrary BO designs).
- `tfsensor/design_gate.py` (`cmd_build`/`cmd_gate`/`_muts_to_boltz`) — two-state Boltz functional-sensor gate for the pre-filter (apo<35.5, holo>38, Δ>0).
- `tfsensor/boltz_holo_inputs.py::_apply_mutations` — full-length mutant FASTA for the build-list.
- `tfsensor/ml/eval/metrics.py` — `pairwise_ranking_accuracy`, `within_group_spearman`, `regression_metrics` (retrospective eval).
- Numbering: MODEL index 1..182 = sequence index (`docs/agent_memory/tfsensor-numbering-convention.md`, `data/resmap.json`); the CSV `model_mut` column is already in model numbering.

## Objectives (`seed.py`) — GFP readout (post-review)
Round-0 uses the existing **single-dose** scan to *seed* and to run the P1 benchmark, with `EPS=1.0` floor
and `y1 = log10(max(f_t,EPS)/max(f_off_max,EPS))` (selectivity). **But the panel showed single-dose folds
misrank and conflate basal leak with induction**, so:
- **From round-1, the trusted objective is dose-response**: per (variant, steroid) fit **EC50 + max amplitude**;
  selectivity `y1` uses amplitude ratios and an EC50/operating-range check; **basal (no-ligand) is measured and
  subtracted** (kills fake "signal" like A66M's huge basal).
- **`y2` (sensor quality / amplitude) is NOT trusted as a *predicted* objective** until P1 proves it's learnable
  from the features. Default: optimize **`y1` (selectivity)** as the predicted objective; treat **amplitude/
  activation as a wet-lab-measured outcome** (and a hard constraint: must be a functional sensor), not a GP target.
  If P1 shows amplitude IS learnable (or an explicit activation descriptor is added), promote it to a 2nd GP objective.
- **Replicate variance → heteroscedastic GP noise** (`Yvar` per point), so the surrogate distrusts noise-floor margins.
- `λ`/`EPS`/operating-range thresholds are **provisional** — set them from the round-0 replicate/dose data, not by hand.
WT row anchors the qNEHVI reference point. Target + off-target panel are config.

## Featurization
- **ESM-2** (`esm2_t33_650M`): thread mutations (index `pos-1`, assert WT letter), embed one protomer, mean-pool the 14 pocket residues (~1280-dim), cache by `md5(sorted(mutations)+model+pool)`.
- **Physchem** (`physchem.py`): per-position `prop(mut)−prop(wt)` for {hydrophobicity, volume, charge, H-bond donors, acceptors} over the 14 positions (70-dim) + a few aggregates (n_mut, |Δcharge|, |Δvolume|).
- Concatenate → ~1350-dim; standardize inside the surrogate (input `Normalize`, outcome `Standardize`).

## BO loop (BoTorch, CPU)
`ModelListGP` (independent GP per objective — robust on ≤~150 pts, per-objective noise). **qNEHVI** batch
acquisition, WT-anchored reference point, optional outcome constraint (3rd GP predicting basal leak / gate-pass).
`optimize_acqf_discrete` over the candidate pool → `q` designs (default 48, set to assay capacity; `sequential=True`
for diversity). Early rounds bias `max_k≤2` to interpolate near the singles manifold before high-order extrapolation.

## DBTL round protocol — artifacts under `results/stage4_bo/round_<NN>/`
0. `loop fit --target cortisol --csv …stage1f_empirical/scan_model_numbering.csv` → ESM precompute (first time, GPU) + fit ModelListGP → `surrogate.pt`, `seed_objectives.json`.
1. `loop propose --round N --q 48 --max_k 4 [--anchor_DE]` → candidate pool → qNEHVI → `proposals.json` (mutations + acq + predicted y mean/var).
2. **Cheap in-silico pre-filter** (low-trust, drops losers): emit proposals as `library.json`; run `tfsensor.design_score panel` (arbitrary-mutation ΔΔΔG margin) and `tfsensor.design_gate build/gate` (Boltz two-state). ⚠️ **SAR-restrain the A-ring to the one correct (progesterone-style) orientation + add an orientation filter** (≈8/12 WT holo poses are flipped — never gate on a flipped pose); report per-seed **median + spread**, drop on margin/gate only with that uncertainty in view.
3. `loop build --round N` → wet-lab **build-list**: `build_list.json` (mirrors the LigandMPNN deliverable schema) + `build.fasta` (full-length mutants via `_apply_mutations`). **State the build method** (point-mutagenesis vs Golden Gate vs synthesis) and keep **q≈24–32**.
4. *User builds + runs the GFP screen — full control set + dose-response (see round-1 below).*
5. `loop ingest --round N --results <gfp.csv>` → append assayed designs to `results/stage4_bo/observations.csv` (seed 84 + all BO designs), recompute objectives **with replicate variance as `Yvar`**, refit → next round.

**Round-1 is a DIAGNOSTIC, not a BO-combinatorial round** (panel must-fix #6): assay **validated-singles doubles**
(I61L+L85I, I61L+Q88T, …) **plus the singles themselves**, all four steroids, **dose-response**, with the
**full control set** — WT anchor, no-ligand basal, a known responder (E106L/L85I/I61L/R123E) + a non-responder
(estradiol), **≥3 biological replicates**, and a few random/exploration wells. This *measures epistasis and assay
noise directly* — the two quantities the whole GP extrapolation depends on — before any BO-proposed combos.

## Verification — the P1 kill-switch (sharpened by the panel)
- **Grouped-CV retrospective benchmark** on the 84 singles (not plain LOO): **leave-one-POSITION-out** AND
  **leave-one-chemical-class-out**. PASS requires ALL of:
  - **rediscovery** of the known leads under the honest split — E106L/L85I/I61L→testosterone, R123E→cortisol;
  - **top-k enrichment** beating BOTH an **additive baseline** and a **random baseline**;
  - **calibration**: predicted 80/95% intervals actually cover held-out outcomes.
  - ⛔ **If it fails, STOP — do not rank multi-mutants.** This is the cheapest exposure of the load-bearing
    assumption (that GFP fold is learnable from a binding-feature surrogate at all).
- **Mandatory feature ablation** in the same harness: **additive vs one-hot vs physchem-only vs ESM-only vs
  concat**. Keep ESM **only if it beats additive** (tests the "mean-pooling destroys H-bond directionality" objection).
- **qNEHVI rediscovery**: seed on a subset, candidate pool includes held-out known-good singles → qNEHVI surfaces them in top-q.
- **Unit tests**: golden objective values; featurization determinism (order-invariant, R123E Δcharge=−2); **mock round** (propose→fake-assay→ingest→refit, no wet-lab/GPU).

## Sequencing & gates
- **P0**: env (`ml` venv) + `seed.py` + `physchem.py` + objective math + unit tests (CPU). Gate: golden objectives.
- **P1 — the decisive gate**: `esm_embed.py` + `featurize.py` + the **grouped-CV benchmark + ablation** above (CPU/days, zero wet-lab). **Pass ⇒ continue; fail ⇒ stop and fix features/objective.** Also decides whether amplitude/`y2` is a learnable objective or stays wet-lab-only.
- **P2**: `surrogate.py` (heteroscedastic `Yvar`) + `acquisition.py` + `candidates.py` + qNEHVI rediscovery gate → `loop propose/build`, sized to ≤3 rounds / q≈24–32.
- **P3**: in-silico pre-filter with **orientation restraint** → **round-1 DIAGNOSTIC** (dose-response on validated doubles+singles, full controls) — measures epistasis & assay noise before any BO-combinatorial designs.
- **P4**: `ingest` (with replicate variance) + iterate. **Defer Tier-2 FEP** until poses/protonation/restraints/≥3 replicates are in place (the controls the E106L FEP lacked).

> The whole loop hinges on the **P1 grouped-CV gate**: if the surrogate can't reproduce *known* phenotypes under an
> honest position/class split — beating an additive baseline, with calibrated intervals — the features/objective are
> wrong and **no wet-lab round is justified**. Cheap, honest, and the direct answer to the ranker's generalization failure.

## Target decision — deferred to after P1 (resolved 2026-06-22)
Stay **target-agnostic** through P0/P1; default to **testosterone>progesterone** for concrete benchmark pass
criteria. **Commit the campaign target only after the P1 grouped-CV gate + ablation pass.** estradiol ⇒ also
build an explicit DBD-activation objective + multi-residue clamp; test>prog ⇒ round-1 doubles (I61L+L85I) are the
natural start. Pick before P2 candidate generation / round-1 build.
