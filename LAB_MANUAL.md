# Biosensor Engineering Lab Manual & Design Principles

This manual serves as the absolute source of truth for the TFsensorSEED project, integrating experimental observations, first-principles structural biology, and computational design rules.

## 1. Experimental Ground Truths

| Variant | Operating Range | Max Signal (a.u.) | Target Specificity | Notes on Basal Leakiness / Dynamics |
|---------|-----------------|-------------------|--------------------|-------------------------------------|
| **WT** | 1 - 100 µM | ~150,000 | Test = Prog > Cort/Est | Tight DNA binder. No basal leakiness. High ligand concentration required to push open. |
| **L147R** | 1 - 5 µM | ~25,000 | Cort > Prog > Test | Hyper-sensitive. ~10% basal leakiness without ligand. Testosterone acts as an antagonist (binds but ~0 signal). |
| **F119W** | 1 - 100 µM | ~150,000 | Test = Prog > Cort | Sensitivity amplifier (overall binding boost via pi-packing). No basal leakiness. |
| **A66M** (A57M model) | N/A | 130,097 (Basal) | N/A | Catastrophic leaky. Basal spikes to 130,097 (~200x WT). Bulky Methionine destroys the Apo closed state entirely. True negative. |
| **A66L** (A57L model) | N/A | N/A | N/A | Tolerable. Basal 1361 (~2x WT). Functional, induction up to 4.4x for Testosterone. |
| **I70L** (I61L model) | N/A | N/A | N/A | Tolerable. Basal 1865 (~2.8x WT). Excellent Testosterone screening site. |

## 2. Structural Binding Codes (First-Principles)

Nature uses strict "lock-and-key" motifs to recognize steroids based on hydrogen bond polarity and steric volume.

### A-Ring Recognition (Specificity Switch)
- **4-en-3-one Steroids (Testosterone, Progesterone, Cortisol):** The A-ring C3 position is a **Keto (C=O)**, which is exclusively a Hydrogen Bond **Acceptor**. In nature (and in WT AcrR), this is recognized by an **Arginine (Arg)** or Glutamine donor.
- **Aromatic Steroids (Estradiol):** The A-ring C3 position is a **Phenol (-OH)**, which is a strong Hydrogen Bond **Donor**. Nature recognizes this using a **Carboxylate Clamp (Glu or Asp)**.
- **Design Rule 1:** To create an Estradiol-specific biosensor, the Arg123 position must be mutated to **Glu/Asp** (accepts the estradiol phenol; repels the 4-en-3-one 3-keto).
  > **⚠️ Wet-lab correction (empirical scan):** the single mutation **R123E does NOT yield estradiol response** — estradiol stays dead (~0.8), and R123E instead becomes **cortisol-selective** (cortisol 31 = top; test/prog/DHT killed). The carboxylate is hijacked by cortisol's polyol. **Estradiol is unreachable by any single/double mutation** in the 85-variant scan → it needs the **full Glu + Arg + His triad** (multi-residue pocket redesign), and even then estradiol is a weak agonist. Treat R123E as the validated **cortisol** anchor (see Rule 3), not the estradiol route.

### D-Ring Recognition (Testosterone vs. Progesterone)
- **Testosterone:** D-ring C17 has a small -OH (Donor/Acceptor).
- **Progesterone:** D-ring C17 has a bulky 20-acetyl group (-C(=O)CH3).
- **Design Rule 2 (Testosterone, Space Inhibition):** Keep A-ring anchors (Arg123/Glu106), introduce **bulky hydrophobic residues (Trp/Phe/Ile)** at the D-ring to clash with Progesterone's acetyl while fitting Testosterone's small -OH.
  > **Empirical support:** the scan validates D-ring positions **I61L and L85I** as testosterone-over-progesterone (L85I: test 120/prog 14; I61L: test 21/prog 3), and **E106L** as a clean testosterone switch (test 26 / prog 5.6 / cort 1.8 / estr 0.6). Leads carrying I61L+L85I: **des0039/des0044/des0060** (see `deliverables/AcrR_testosterone_sensor_designs.md`).

- **Design Rule 2b (Progesterone — inverse of Rule 2):** To select Progesterone, *accommodate* the bulky 17-acetyl: **enlarge** the D-ring pocket and add **one H-bond donor (Ser/Thr/Asn/Gln) for the C20 carbonyl**; keep A-ring anchors; deny the cortisol polyol. (Campaign `results/stage3_prog/`.)

### Core Recognition (Cortisol)
- **Cortisol:** Highly polar polyol core (11-OH, 17-OH, 21-OH).
- **Design Rule 3:** Requires a polar pocket. **Validated anchor: R123E** (empirical scan — R123E makes cortisol the top responder, 31). Combine with a **polar D-ring redesign (Ser/Thr/Asn/Gln)** to wrap the polyol. (L147R also rescues cortisol by introducing a polar Arg into the core while penalizing hydrophobic Testosterone.) Campaign `results/stage3_cort/`.

## 3. Allosteric Gating Principles (The 34 Å Rule)

Binding affinity ($\Delta\Delta G$) alone does not guarantee allosteric efficacy (fluorescence). The sensor must physically disengage from DNA upon ligand binding. The DNA Major Groove spacing dictates absolute geometric requirements for the DNA-Binding Domains (DBD).

### Basal Stability (Apo State)
- The absolute distance between the DBDs in the Apo state MUST be **~34.0 - 35.0 Å** (matching the DNA major groove). 
- If a mutation (like the bulky L147R) pre-opens the Apo pocket to **> 36.0 Å**, the sensor will bind DNA weakly, resulting in basal leakiness (constitutive activity) and a shifted sensitivity threshold (e.g., operating at 1-5 µM instead of 1-100 µM).

### Agonist Activation (Holo State)
- To achieve maximum fluorescence signal (complete DNA release), the Holo state DBD distance must widen significantly (e.g., **> 38.0 Å**).
- A ligand that binds but fails to open the DBD (Holo distance ≈ Apo distance) is a **Dead Binder / Antagonist**.

> **Caveat (2026-06-16) — the gate is a soft, single-predictor proxy.** (1) The homodimer must be
> folded with **2 ligands** (one per protomer); the 1-ligand fold under-opens, while 2 ligands open
> the holo much wider (~44 Å). (2) **Boltz and Protenix disagree** on the opening magnitude. So a
> "passes the gate" result is *Boltz-specific and stoichiometry-sensitive*. Use the gate to reject
> clearly dead/leaky designs, but **measure amplitude in the lab** — do not trust the predicted Δ as
> a quantitative agonist score.

## 4. Computational Pipeline Standard Operating Procedure (SOP)

Future Stage-3 designs must pass through this funnel before wet-lab synthesis:

*   **Tier 0 (Generation):** Motif-Anchored LigandMPNN. Hardcode the catalytic anchor (e.g., `Arg123Glu`) and allow MPNN to repack the 1st/2nd shell residues to stabilize the motif. No blind sampling.
*   **Tier 1 (Affinity Filter):** PyRosetta `flex-ddG`. Evaluate sequences using local backbone flexibility (±2 residues) and ligand tethering. Discard false-negative clashes. Rank by relative specificity (target $\Delta\Delta G$ must be highly negative, decoys positive).
*   **Tier 1.5 (Gating Filter):** Boltz-2 Two-State Absolute Geometry.
    *   **Check 1:** Mutant Apo DBD distance must be < 35.5 Å (No severe leakiness).
    *   **Check 2:** Mutant Holo DBD distance must be > 38.0 Å (Strong agonist).
    *   **Check 3:** Holo - Apo Delta must be positive for the target ligand.
*   **Tier 2 (Ultimate Arbiter):** Free Energy Perturbation. **BUILT & VALIDATED (2026-06-16):**
    RBFE via **pmx hybrid-topology + GROMACS (CUDA) non-equilibrium TI** (Crooks/BAR/Jarzynski) — *not*
    drMD. Validated on L147R×cortisol (sign-correct). **Critical lesson:** FEP is GIGO — it only
    resolves ~1 kcal/mol specificity if run on a **validated/restrained pose with a first-shell
    target** (the E106L run failed because E106 is second-shell and the pose was unstable). Prefer
    **ligand-ligand RBFE** across the test/prog/cort triad (identical A-ring; estradiol excluded) to
    compute ΔΔΔG selectivity directly. Executors: `scripts/fep/`; env: `HANDOFF.md §2`.

> **Note on this SOP:** Tiers 1 and 1.5 are computational *filters/ranks*, not ground truth. The
> binding-ΔΔG cannot robustly resolve ~1 kcal/mol selectivity, and the Tier-1.5 gate is a
> single-predictor proxy (see §3 caveat). Final calls = gate ∩ empirical-scan convergence + wet-lab.
