---
title: Decisions — debate
type: decisions
source_run: 20260623_195430_debate
crew: debate
date: 20260623_195455
trust: MEDIUM
---

_Sedimented from discussion run `20260623_195430_debate`._

## Consensus / findings
- [HIGH] Computational selectivity prediction has failed: the P1 GP surrogate scores Spearman ≤0 (beaten by a trivial additive baseline; evi_1054c72b) and #4 flex-ddG mis-signs all three validated singles (evi_ccbfe393). cla_8dcc8869 holds — these tools are dead for *ranking* selectivity.
- [HIGH] flex-ddG resolves binding but not selectivity: it recovers WT steroid order (cla_f4e015f1) yet not selectivity shifts. Both sides accept it only as a coarse dead-binder gate (dec_724644ec), never a selectivity gate (pit_f84276d6).
- [HIGH] The computational failures refute *predictability*, not *reachability* — "we can't predict it" does not imply "it isn't there." Both sides leave this distinction standing.
- [HIGH] Epistasis is unobserved: cla_1cfd144b is explicitly open; no data exists on singles→multi behavior.
- [HIGH] The dead-binder gate never ran (`data/holo_testosterone.pdb` not found), so "the lead I61L/L85I double still binds testosterone" is currently unsupported.
- [MEDIUM] The crux dividing the panel is whether the test/prog ratio gain in each single comes from a *testosterone-signal gain* or a *progesterone-signal loss* (denominator collapse). This is load-bearing for both the headroom and the saturation arguments and is unobservable from the ratio alone.

## Decisions
- [HIGH] Decompose the three singles using existing round-0 GFP data before building anything — owner: computational/data analyst — next step: plot *absolute* testosterone and *absolute* progesterone dose-response for I61L, L85I, E106L separately; if all three gain selectivity via prog-signal loss → predict negative epistasis and do not build the triple; if ≥one shows genuine absolute testosterone gain → headroom is live.
- [MEDIUM] Treat flex-ddG strictly as a coarse dead-binder viability filter, never as a selectivity gate — owner: tool-runner — next step: locate the orientation-corrected holo PDB (respect pit_d2bfb9d3: never gate on a single Boltz pose), fix the missing input path, rerun on I61L/L85I.
- [MEDIUM] Make the wet-lab double/triple build conditional on the decomposition result — owner: wet-lab — next step: build validated-single doubles + triple only if Item #1 shows real absolute testosterone gain; measure dose-response selectivity looking for a value *exceeding the best single*; hold otherwise.
- [LOW] Set the gating threshold and confirm slot budget — owner: human/PI — next step: define what absolute-progesterone floor counts as "denominator collapse" and approve wet-lab slots before any build commits.

## Open questions
- Does each single raise test/prog selectivity by gaining testosterone reading or by suppressing progesterone toward the noise floor? (decisive, unresolved)
- Does the lead I61L/L85I double still bind testosterone at all? (gate never ran)
- Sign and magnitude of epistasis when validated singles are combined (cla_1cfd144b open).
- Could the D-ring bump-and-hole clash with I61L/L85I repacking? (raised by Proponent as an unproven weakness)

## Candidate pitfalls (for human review — not yet a hard rule)
- Do not read a high test/prog ratio as evidence of testosterone discrimination — a ratio can rise purely from denominator (progesterone-signal) collapse, which mimics k=2 saturation / negative epistasis.
- Do not use a model that resolves binding but not selectivity (flex-ddG) as a selectivity gate (reinforces pit_f84276d6).
- Do not spend wet-lab slots on combinatorial builds before exhausting the free, prior analysis on existing round-0 data.
- Do not gate viability on a single Boltz pose / unverified holo structure (pit_d2bfb9d3); confirm the input PDB exists and is orientation-corrected before trusting the gate.

## Typed records emitted (14: 14 new, 0 updated/deduped)
- `claim` cla_92b41bf5 (status=open, confidence=high) → knowledge/claims/cla_92b41bf5.md
- `claim` cla_cf1989f2 (status=open, confidence=high) → knowledge/claims/cla_cf1989f2.md
- `claim` cla_2f9fc080 (status=open, confidence=high) → knowledge/claims/cla_2f9fc080.md
- `claim` cla_5bd24eed (status=open, confidence=high) → knowledge/claims/cla_5bd24eed.md
- `claim` cla_2b1a3ae6 (status=open, confidence=high) → knowledge/claims/cla_2b1a3ae6.md
- `claim` cla_89787154 (status=open, confidence=medium) → knowledge/claims/cla_89787154.md
- `decision` dec_4ede33ee (status=active, confidence=high) → knowledge/decisions/dec_4ede33ee.md
- `decision` dec_811dc59a (status=active, confidence=medium) → knowledge/decisions/dec_811dc59a.md
- `decision` dec_e45cdbe9 (status=active, confidence=medium) → knowledge/decisions/dec_e45cdbe9.md
- `decision` dec_9767c3a5 (status=active, confidence=low) → knowledge/decisions/dec_9767c3a5.md
- `pitfall` pit_7deb8ea1 (status=active, confidence=medium) → knowledge/pitfalls/pit_7deb8ea1.md
- `pitfall` pit_f3bdfff6 (status=active, confidence=medium) → knowledge/pitfalls/pit_f3bdfff6.md
- `pitfall` pit_f1143030 (status=active, confidence=medium) → knowledge/pitfalls/pit_f1143030.md
- `pitfall` pit_7c8d7573 (status=active, confidence=medium) → knowledge/pitfalls/pit_7c8d7573.md
