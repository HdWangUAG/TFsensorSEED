# Steroid Sensor Design — plan (example fixture)

Goal: engineer an AcrR-family transcription factor into a β-estradiol-specific
biosensor, selective against progesterone, cortisol, and testosterone.

Approach:
1. Tier-0 — hypothesis-driven pocket design (Glu/Asp carboxylate clamp for the
   estradiol 3-OH phenol; aromatic π-stack on the planar A-ring).
2. Tier-1 — flex-ddG (PyRosetta, CPU) to rank affinity / specificity.
3. Tier-1.5 — Boltz-2 apo/holo gate (GPU) to check the DBD actually opens.
4. Tier-2 — FEP/RBFE only to arbitrate the closest survivors.

Open questions this plan does not yet answer:
- How is the ~1 kcal flex-ddG margin distinguished from noise before gating?
- Is the carboxylate clamp actually selective, or does it reward cortisol's
  polyol just as much as estradiol's 3-OH?
- Where does the allosteric (binding → activation) coupling enter the funnel?
