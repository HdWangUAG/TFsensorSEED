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
- **Design Rule 1:** To create an Estradiol-specific biosensor, the Arg123 position must be mutated to **Glu/Asp**. This accepts the estradiol phenol while simultaneously exerting catastrophic O-O electrostatic repulsion against Testosterone, Progesterone, and Cortisol.

### D-Ring Recognition (Testosterone vs. Progesterone)
- **Testosterone:** D-ring C17 has a small -OH (Donor/Acceptor).
- **Progesterone:** D-ring C17 has a bulky 20-acetyl group (-C(=O)CH3).
- **Design Rule 2 (Space Inhibition):** To strictly select for Testosterone and exclude Progesterone, maintain the A-ring anchors (Arg123/Glu106) and introduce **bulky hydrophobic residues (Trp, Phe, Ile)** at the D-ring pocket region. This creates severe steric clash with Progesterone's large acetyl group, physically "bumping" it out, while leaving just enough room for Testosterone's small -OH.

### Core Recognition (Cortisol)
- **Cortisol:** Highly polar polyol core (11-OH, 17-OH, 21-OH).
- **Design Rule 3:** Requires a polar pocket (e.g., L147R introduces a polar Arg into the hydrophobic core, rescuing Cortisol binding while penalizing the hydrophobic Testosterone).

## 3. Allosteric Gating Principles (The 34 Å Rule)

Binding affinity ($\Delta\Delta G$) alone does not guarantee allosteric efficacy (fluorescence). The sensor must physically disengage from DNA upon ligand binding. The DNA Major Groove spacing dictates absolute geometric requirements for the DNA-Binding Domains (DBD).

### Basal Stability (Apo State)
- The absolute distance between the DBDs in the Apo state MUST be **~34.0 - 35.0 Å** (matching the DNA major groove). 
- If a mutation (like the bulky L147R) pre-opens the Apo pocket to **> 36.0 Å**, the sensor will bind DNA weakly, resulting in basal leakiness (constitutive activity) and a shifted sensitivity threshold (e.g., operating at 1-5 µM instead of 1-100 µM).

### Agonist Activation (Holo State)
- To achieve maximum fluorescence signal (complete DNA release), the Holo state DBD distance must widen significantly (e.g., **> 38.0 Å**).
- A ligand that binds but fails to open the DBD (Holo distance ≈ Apo distance) is a **Dead Binder / Antagonist**.

## 4. Computational Pipeline Standard Operating Procedure (SOP)

Future Stage-3 designs must pass through this funnel before wet-lab synthesis:

*   **Tier 0 (Generation):** Motif-Anchored LigandMPNN. Hardcode the catalytic anchor (e.g., `Arg123Glu`) and allow MPNN to repack the 1st/2nd shell residues to stabilize the motif. No blind sampling.
*   **Tier 1 (Affinity Filter):** PyRosetta `flex-ddG`. Evaluate sequences using local backbone flexibility (±2 residues) and ligand tethering. Discard false-negative clashes. Rank by relative specificity (target $\Delta\Delta G$ must be highly negative, decoys positive).
*   **Tier 1.5 (Gating Filter):** Boltz-2 Two-State Absolute Geometry.
    *   **Check 1:** Mutant Apo DBD distance must be < 35.5 Å (No severe leakiness).
    *   **Check 2:** Mutant Holo DBD distance must be > 38.0 Å (Strong agonist).
    *   **Check 3:** Holo - Apo Delta must be positive for the target ligand.
*   **Tier 2 (Ultimate Arbiter):** Free Energy Perturbation (FEP). Run RBFE (Relative Binding Free Energy) via drMD and alchemical transformation for the Top ~10 elite sequences to obtain mathematically rigorous binding free energies prior to ordering DNA.
