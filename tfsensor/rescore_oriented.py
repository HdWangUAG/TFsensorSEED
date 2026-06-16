"""Orientation-aware, 2-ligand re-scoring of the testosterone leads.

No crystal exists and de-novo co-folds flip the steroid inconsistently, so we use the
SAR as the orientation filter: a pose is SAR-consistent only if the A-ring 3-keto sits
nearer the E106/R123 cluster than Q88 (the SAR-derived A-ring end). We fold with TWO
testosterone ligands (homodimer), keep only SAR-consistent holo poses, then apply the
34 A allosteric gate on those + the matched apo. Also reports the orientation-consistent
fraction (a reliability metric for each design).

    python -m tfsensor.rescore_oriented --root results/stage3_dring/rescore \
        --out_json results/stage3_dring/rescore/gate_oriented.json
"""
from __future__ import annotations

import argparse, glob, json, math, os, statistics

APO_MAX, HOLO_MIN = 35.5, 38.0
A_CLUSTER = [(106, ("OE1", "OE2")), (123, ("NH1", "NH2", "NE"))]   # A-ring readers
D_MARKER = [(88, ("NE2", "OE1"))]                                  # D-ring end (Q88)


def _atoms(pdb):
    A = []
    for l in open(pdb):
        if l[:6] in ("ATOM  ", "HETATM"):
            A.append((l[:6].strip(), l[12:16].strip(), l[17:20].strip(), l[21],
                      l[22:26].strip(), (l[76:78].strip() or l[12:16].strip()[:1]),
                      (float(l[30:38]), float(l[38:46]), float(l[46:54]))))
    return A
def _d(a, b): return math.dist(a, b)


def _ligand_chains(A):
    return sorted({a[3] for a in A if a[2] == "LIG"})


def _keto_O(A, ch):
    """testosterone: 3-keto O = the ligand-O on chain `ch` with shortest C-O (~1.23) vs 17-OH (~1.39)."""
    Os = [a for a in A if a[2] == "LIG" and a[3] == ch and a[5] == "O"]
    Cs = [a for a in A if a[2] == "LIG" and a[3] == ch and a[5] == "C"]
    if not Os or not Cs:
        return None
    def co(o): return min(_d(o[6], c[6]) for c in Cs)
    return min(Os, key=co)  # shortest C-O = keto


def _prot_atoms(A, resi, names):
    return [a for a in A if a[0] == "ATOM" and a[4] == str(resi) and a[1] in names]


def _orientation_ok(pdb):
    """SAR-consistent if EVERY ligand's 3-keto is closer to the E106/R123 cluster than to Q88."""
    A = _atoms(pdb)
    ok = []
    for ch in _ligand_chains(A):
        keto = _keto_O(A, ch)
        if keto is None:
            continue
        dA = min((_d(keto[6], p[6]) for r, nm in A_CLUSTER for p in _prot_atoms(A, r, nm)), default=99)
        dD = min((_d(keto[6], p[6]) for r, nm in D_MARKER for p in _prot_atoms(A, r, nm)), default=99)
        ok.append(dA < dD)
    return bool(ok) and all(ok)


def _dbd(pdb, anchors=(37, 40)):
    A = _atoms(pdb)
    ca = {}
    for a in A:
        if a[1] == "CA" and a[0] == "ATOM":
            try:
                ri = int(a[4])
            except ValueError:
                continue
            if ri in anchors:
                ca.setdefault(a[3], {})[ri] = a[6]
    prot = [c for c in ca if all(x in ca[c] for x in anchors)]
    if len(prot) < 2:
        return None
    p, q = prot[:2]
    return statistics.mean(_d(ca[p][x], ca[q][x]) for x in anchors)


def _models(root, design, job):
    return glob.glob(os.path.join(root, design, "out", "boltz_results_inputs",
                                  "predictions", job, f"{job}_model_*.pdb"))


def run(root, out_json, designs=("wt", "des0039", "des0060")):
    rows = []
    for d in designs:
        holo = _models(root, d, f"{d}_testosterone")
        apo = _models(root, d, f"{d}_apo")
        if not holo or not apo:
            rows.append({"design": d, "note": "missing predictions",
                         "n_holo": len(holo), "n_apo": len(apo)})
            continue
        consistent = [h for h in holo if _orientation_ok(h)]
        frac = round(len(consistent) / len(holo), 2)
        apo_dbd = round(statistics.mean([x for x in (_dbd(a) for a in apo) if x]), 2)
        # holo DBD on SAR-consistent poses (fall back to all if none consistent, flagged)
        use = consistent if consistent else holo
        holo_dbd = round(statistics.mean([x for x in (_dbd(h) for h in use) if x]), 2)
        delta = round(holo_dbd - apo_dbd, 2)
        rows.append({"design": d, "n_holo": len(holo), "orient_consistent": len(consistent),
                     "orient_frac": frac, "apo_dbd": apo_dbd, "holo_dbd": holo_dbd,
                     "delta": delta, "scored_on_consistent": bool(consistent),
                     "basal_ok": apo_dbd < APO_MAX, "agonist_ok": holo_dbd > HOLO_MIN,
                     "not_dead_ok": delta > 0,
                     "pass": bool(apo_dbd < APO_MAX and holo_dbd > HOLO_MIN and delta > 0)})
    out = {"apo_max": APO_MAX, "holo_min": HOLO_MIN, "n_ligand": 2,
           "orientation_filter": "A-ring 3-keto nearer E106/R123 than Q88", "rows": rows}
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)
    print("==== 2-LIGAND, ORIENTATION-FILTERED gate (testosterone) ====")
    print(f"{'design':9s} {'orient✓':>9s} {'apo':>6s} {'holo':>6s} {'Δ':>6s}  basal agon dead PASS")
    for r in rows:
        if r.get("apo_dbd") is None:
            print(f"{r['design']:9s}  (missing)"); continue
        print(f"{r['design']:9s} {r['orient_consistent']}/{r['n_holo']:<6d} "
              f"{r['apo_dbd']:6.2f} {r['holo_dbd']:6.2f} {r['delta']:6.2f}   "
              f"{str(r['basal_ok'])[0]}    {str(r['agonist_ok'])[0]}    {str(r['not_dead_ok'])[0]}   "
              f"{'YES' if r['pass'] else 'no'}{'' if r['scored_on_consistent'] else '  (no SAR-consistent pose!)'}")
    print(f"\n[rescore] wrote {out_json}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="results/stage3_dring/rescore")
    ap.add_argument("--out_json", default="results/stage3_dring/rescore/gate_oriented.json")
    args = ap.parse_args()
    run(args.root, args.out_json)


if __name__ == "__main__":
    main()
