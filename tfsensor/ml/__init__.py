"""Machine-learning track for general steroid–protein binding & specificity.

A new subpackage (plan: ~/.claude/plans/composed-puzzling-church.md) that reuses the
existing tfsensor cheminformatics / PDB-parsing / pose-parsing machinery and adds a
data-curation, baseline-scoring, and (conditional) bespoke-model layer.

Layout:
    data/      dataset curation (steroid filtering, PDBbind/NR parsing, pockets, splits)
    features/  ligand/pocket graphs, ESM-2 embeddings, tabular features
    baselines/ pretrained scorers (Boltz-2/gnina/GEMS) + leakage sanity baselines
    eval/      metrics + the AcrR specificity acceptance test
    tests/     unit/sanity tests
"""
