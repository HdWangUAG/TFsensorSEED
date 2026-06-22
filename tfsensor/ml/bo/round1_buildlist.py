"""Order-ready build-list for the round-1 testosterone>progesterone diagnostic.

Turns the round-1 variant set (tfsensor.ml.bo.round1_design) into wet-lab-ready
artifacts: full-length mutant protein sequences (FASTA), a construct table in BOTH
numbering schemes (MODEL = seq index; EXPERIMENTAL = model + 9, the lab spreadsheet
convention), a stated build method per construct, and a per-well plate layout for
the dose-response assay.

Numbering: the WT AcrR chain (data/AcrR_dimer.fasta) is indexed in MODEL numbering
(seq position == model residue number). Mutation tokens in round1_design are MODEL
numbering; the lab's empirical sheet uses EXPERIMENTAL = MODEL + 9 (confirmed:
F119W=F128W, R123=R132, I61L=I70L). Both are emitted so nothing is ambiguous; the
amino-acid sequence is the unambiguous source of truth for synthesis.

Pure-stdlib. Writes under results/stage4_bo/round1_build/.

    PYTHONPATH=. python -m tfsensor.ml.bo.round1_buildlist
"""
from __future__ import annotations

import csv
import os

from tfsensor import config
from tfsensor.ml.bo import round1_design as r1
from tfsensor.ml.bo.seed import parse_mutation
from tfsensor.ml.features.esm_embed import wt_seq

OUT_DIR = os.path.join(config.REPO_ROOT, "results/stage4_bo/round1_build")
EXP_OFFSET = 9   # experimental = model + 9

# leads carry extra distal mutations beyond the I61L+L85I core (MODEL numbering)
LEAD_MUTATIONS = {
    "des0039": ["I61L", "L85I", "L122F", "L143I", "L146I", "L147F"],
    "des0044": ["I61L", "L85I", "L122F", "L143I", "L146I"],
    "des0060": ["I61L", "L85I", "L146I"],
}


def to_exp(token):
    """Model-numbering token 'I61L' -> experimental 'I70L'."""
    wt, pos, aa = parse_mutation(token)
    return f"{wt}{pos + EXP_OFFSET}{aa}"


def thread(seq, tokens):
    """Apply MODEL-numbering mutation tokens; return (mutant_seq, mismatches)."""
    s = list(seq)
    bad = []
    for t in tokens:
        wt, pos, aa = parse_mutation(t)
        if not (1 <= pos <= len(s)) or s[pos - 1] != wt:
            bad.append(f"{t}(seq has {s[pos-1] if 1 <= pos <= len(s) else '?'})")
            continue
        s[pos - 1] = aa
    return "".join(s), bad


def _build_method(n_mut, is_lead):
    if n_mut == 0:
        return "WT control (no mutagenesis)"
    if is_lead or n_mut >= 3:
        return "gene synthesis (~$80-200, 1-2 wk lead)"
    return "site-directed mutagenesis (point/overlap primers)"


def constructs():
    """All round-1 constructs with threaded sequences + both numbering schemes."""
    wt = wt_seq()
    rows = []
    # WT + singles + doubles from the round-1 design
    items = [(label, toks, why, False) for (label, toks, why) in r1.VARIANTS]
    # + the existing build-and-test leads
    for lead, toks in LEAD_MUTATIONS.items():
        items.append((lead, toks, "existing lead (I61L+L85I core + distal)", True))

    for label, toks, why, is_lead in items:
        seq, bad = thread(wt, toks)
        rows.append({
            "construct": label,
            "n_mut": len(toks),
            "mut_model": "; ".join(toks) if toks else "(WT)",
            "mut_exp": "; ".join(to_exp(t) for t in toks) if toks else "(WT)",
            "build_method": _build_method(len(toks), is_lead),
            "rationale": why,
            "seq_len": len(seq),
            "mismatch": "; ".join(bad),
            "sequence": seq,
        })
    return rows


def plate_layout(constructs_list):
    """Per-well dose-response layout. 1 replicate == 1 plate (384-well): the
    n_construct x n_steroid x n_dose conditions fill one plate; replicates are
    separate plates. Returns rows: replicate/plate, well, construct, steroid, dose."""
    steroids = r1.STEROIDS
    doses = r1.DOSES_UM
    rep = r1.N_REPLICATES
    conds = [(c["construct"], s, d) for c in constructs_list for s in steroids for d in doses]
    per_plate = 384
    rows_letters = "ABCDEFGHIJKLMNOP"   # 16 rows
    cols = 24                            # x 24 = 384
    out = []
    for r_i in range(rep):
        for idx, (cons, ster, dose) in enumerate(conds):
            plate = r_i + 1
            row = rows_letters[idx // cols]
            col = idx % cols + 1
            out.append({"replicate": r_i + 1, "plate": plate, "well": f"{row}{col:02d}",
                        "construct": cons, "steroid": ster, "dose_uM": dose,
                        "is_basal": int(dose == 0)})
    return out, len(conds), per_plate


def write(out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    cons = constructs()
    bad = [c for c in cons if c["mismatch"]]

    # 1) FASTA (synthesis source of truth)
    fasta = os.path.join(out_dir, "build.fasta")
    with open(fasta, "w") as fh:
        for c in cons:
            fh.write(f">{c['construct']} | model:{c['mut_model']} | exp:{c['mut_exp']} "
                     f"| n_mut={c['n_mut']} | {c['build_method']}\n{c['sequence']}\n")

    # 2) construct table
    csvp = os.path.join(out_dir, "build_list.csv")
    cols = ["construct", "n_mut", "mut_model", "mut_exp", "build_method",
            "rationale", "seq_len", "mismatch", "sequence"]
    with open(csvp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for c in cons:
            w.writerow(c)

    # 3) plate layout
    layout, n_cond, per_plate = plate_layout(cons)
    platep = os.path.join(out_dir, "plate_layout.csv")
    with open(platep, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["replicate", "plate", "well", "construct",
                                           "steroid", "dose_uM", "is_basal"])
        w.writeheader(); w.writerows(layout)

    # 4) human-readable summary
    mdp = os.path.join(out_dir, "BUILD_LIST.md")
    lines = ["# Round-1 build-list — testosterone>progesterone diagnostic (order-ready)",
             "",
             f"**{len(cons)} constructs** · numbering: MODEL (seq index) + EXPERIMENTAL "
             f"(= model + {EXP_OFFSET}, lab sheet). Sequence is the synthesis source of truth.",
             "",
             "| construct | n | mutations (model) | mutations (exp) | build method | rationale |",
             "|---|---|---|---|---|---|"]
    for c in cons:
        lines.append(f"| {c['construct']} | {c['n_mut']} | {c['mut_model']} | {c['mut_exp']} "
                     f"| {c['build_method']} | {c['rationale']} |")
    lines += ["",
              f"- **Synthesis:** `build.fasta` ({len(cons)} full-length records) · "
              f"table `build_list.csv`.",
              f"- **Assay:** {len(cons)} constructs × {len(r1.STEROIDS)} steroids "
              f"({', '.join(r1.STEROIDS)}) × {len(r1.DOSES_UM)} doses "
              f"({r1.DOSES_UM} µM, 0 = no-ligand basal) × {r1.N_REPLICATES} reps "
              f"= **{len(layout)} wells** = {r1.N_REPLICATES} × 384-well plates "
              f"(1 replicate/plate, {n_cond} conditions each). Map: `plate_layout.csv`.",
              "- **Controls (built in):** WT (anchor), no-ligand basal per construct (dose 0), "
              "validated responder (I61L/L85I/E106L), estradiol = dead-ligand negative.",
              "- **Readout → analysis:** GFP per well → 4-param Hill fit "
              "(`tfsensor.ml.bo.doseresponse`) → basal/amplitude/EC50; selectivity y1 = "
              "amplitude ratio (basal-subtracted); replicate variance → assay-noise estimate.",
              "",
              ("⚠️ **Sequence mismatches:** " + "; ".join(f"{c['construct']}: {c['mismatch']}"
               for c in bad)) if bad else "✅ All mutations thread cleanly onto WT (no WT-letter mismatch)."]
    open(mdp, "w").write("\n".join(lines))
    return cons, layout, bad, (fasta, csvp, platep, mdp)


if __name__ == "__main__":
    cons, layout, bad, paths = write()
    print(f"constructs={len(cons)}  wells={len(layout)}  mismatches={len(bad)}")
    for p in paths:
        print("  wrote", p)
    if bad:
        print("  ⚠️ mismatches:", [(c["construct"], c["mismatch"]) for c in bad])
