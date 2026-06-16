---
name: tfsensor-stage1-triple-nogo
description: "TFsensorSEED Stage-1 — WT responds to testosterone not estradiol; binding-only fails, the bind×switch method validates"
metadata: 
  node_type: memory
  type: project
  originSessionId: a8b6a708-ed73-43fe-b948-ff262bc39f09
---

TFsensorSEED (~/TFsensorSEED) engineers AcrR into an estradiol-specific allosteric biosensor (GFP/fluorescence readout = derepression). **Corrected ground truth (user, 2026-06-14): WT AcrR responds to TESTOSTERONE, not estradiol.** Testosterone (+ other 4-en-3-one steroids) are the natural responders; estradiol is a WT non-responder and the eventual *engineering* target. Panel roles in `data/steroid_panel.csv`: testosterone=target, estradiol/progesterone/cortisol=decoys.

**Key reframing (user):** signal requires BIND *and* TRIGGER the apo→holo DBD switch (37/40 anchors → TF detaches from DNA). Binding energy alone is the wrong axis. Built the two-axis "NO-GO method": `tfsensor/trigger_panel.py` (DBD-opening axis over all Boltz diffusion samples), `tfsensor/biosensor_score.py` (`P(bound)_boltz × max(DBD_opening,0)`), `tfsensor/physics_panel.py` (Rosetta InterfaceAnalyzer dG, 3rd binding axis). Results in `results/stage1b_physics/` and `results/stage1c_trigger/`.

**Findings:** Binding axis does NOT single out the responder — all four steroids bind (estradiol binds fine: Boltz bp 0.578), so a binding-only screen would wrongly pass estradiol. The **switch axis is decisive**: testosterone/progesterone/cortisol open the DBD +4.9/+5.1/+5.6 Å; **estradiol stays closed (+0.32 Å, robust low-variance) = dark**. Coupled biosensor score: testosterone 2.49, progesterone 3.10, cortisol 2.44, **estradiol 0.19 (~13× lower)**. So the method reproduces corrected biology (4-en-3-one respond, estradiol doesn't) → VALIDATED. WT estradiol = near-antagonist (binds, no trigger).

**How to apply (design objective, Stage 3+):** specificity-SWITCH problem — redesign pocket so estradiol BINDING couples to DBD opening (install the trigger; estradiol already binds), while testosterone-class decoys are rejected on ≥1 axis. Score designs by coupled biosensor score, switch axis first-class (not ddG). Next hardening: confirm switch axis with Protenix apo+holo consensus + Boltz-predicted apo reference (plan Stage 5). Stage-2 trigger residues done (`results/stage2_trigger/trigger_residues.json`, candidate levers A96/B96/A106/B106). See [[tfsensor-pyrosetta-init-once-per-process]].
