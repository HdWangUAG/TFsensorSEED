"""`minicrew` command-line entry point.

    minicrew run <crew> [--file plan.md ...] [--rounds N] [--dry-run] [--out PATH]
    minicrew list
    minicrew models
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

from .core import config, crew, distill, embed, litdb, scribe, vision


def _cmd_run(args):
    crew.run_crew(
        args.crew,
        extra_files=args.file,
        rounds=args.rounds,
        topology=args.topology,
        dry_run=args.dry_run,
        mock=args.mock,
        out_path=args.out,
    )


def _read_doc(path):
    """Read a paper source. PDFs are converted with `pdftotext -layout` (keeps
    table columns); '-' reads stdin; everything else is read as text."""
    if path == "-":
        return sys.stdin.read()
    if path.lower().endswith(".pdf"):
        out = subprocess.run(["pdftotext", "-layout", path, "-"],
                             capture_output=True, text=True, timeout=180)
        if out.returncode != 0:
            raise RuntimeError(out.stderr[:300] or "pdftotext failed")
        return out.stdout
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _cmd_distill(args):
    try:
        text = _read_doc(args.input)
        si_text = _read_doc(args.si) if args.si else ""
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return
    if not text.strip():
        print("error: empty input", file=sys.stderr)
        return

    source = distill.compose(text, si_text)
    note = distill.distill(source, model=args.model, mock=args.mock)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(note)
        print(f"[draft saved → {args.out}]  — verify the numbers + DOI before use")
    else:
        print(note)

    if args.verify:
        print("\n" + "=" * 60 + "\nFACT-CHECK (" + args.check_model + ")\n" + "=" * 60)
        print(distill.verify(source, note, model=args.check_model, mock=args.mock))


def _cmd_figures(args):
    try:
        out = vision.extract(args.pdf, pages=args.pages, model=args.model)
    except Exception as exc:  # render or vision error
        print(f"error: {exc}", file=sys.stderr)
        return
    if not out.strip():
        print("no data extracted (no pages rendered?)")
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"[saved → {args.out}]  — CONFIRM any plot-read numbers")
    else:
        print(out)


def _cmd_sediment(args):
    runs = sorted(glob.glob(os.path.join(config.RUNS_DIR, "*.json")), reverse=True)
    if not runs:
        print("no discussion runs to sediment", file=sys.stderr)
        return
    if args.run_id:
        match = [r for r in runs if args.run_id in os.path.basename(r)]
        if not match:
            print(f"run {args.run_id!r} not found", file=sys.stderr)
            return
        path = match[0]
    else:
        path = runs[0]
    record = json.load(open(path, encoding="utf-8"))
    vmodel = (args.verify if isinstance(args.verify, str) else "openai") if args.verify else None
    out, _ = scribe.sediment_run(record, model=args.model, verify_model=vmodel)
    print(f"sedimented run {record.get('run_id')} → "
          f"{os.path.relpath(out, config.REPO_ROOT)}"
          + (f"  (fact-checked by {vmodel})" if vmodel else ""))
    print("crews that list `decisions` will build on it next discussion.")


def _cmd_index(_args):
    ok, msg = litdb.status()
    if not ok:
        print(f"error: literature DB not reachable ({msg})\n"
              "start it with: cd minicrew && docker compose up -d", file=sys.stderr)
        return
    n = litdb.index_all()
    print(f"indexed {n} literature note(s) with {embed.info()} → "
          f"Qdrant '{config.QDRANT_COLLECTION}' + Mongo ({msg})")


def _cmd_search(args):
    ok, msg = litdb.status()
    if not ok:
        print(f"error: literature DB not reachable ({msg})\n"
              "start it with: cd minicrew && docker compose up -d", file=sys.stderr)
        return
    hits = litdb.search(args.query, k=args.k, tags=args.tag or None)
    if not hits:
        print("no matches (did you run `minicrew index`?)")
        return
    for h in hits:
        tags = ", ".join(map(str, h.get("tags") or []))
        print(f"\n[{h['score']:.3f}] {h['title']}  ({h['name']})")
        if tags:
            print(f"        tags: {tags}")
        body = h["body"]
        if body.startswith("---"):                 # skip frontmatter in the snippet
            end = body.find("\n---", 3)
            if end != -1:
                body = body[end + 4:]
        snippet = " ".join(body.split())[:240]
        print(f"        {snippet}…")
    scores = [h["score"] for h in hits]
    if scores:
        mean = sum(scores) / len(scores)
        print(f"\nsimilarity: min={min(scores):.3f} max={max(scores):.3f} "
              f"mean={mean:.3f}  ·  embedder {embed.info()}")


def _cmd_list(_args):
    crews = crew.list_crews()
    if not crews:
        print("no crews found in:", ", ".join(config.CREW_DIRS))
        return
    print("available crews:")
    for name, path in crews.items():
        print(f"  {name:24s} {path}")


def _cmd_models(_args):
    print("model aliases (✓ = ready to call):")
    for alias in sorted(config.MODELS):
        spec = config.resolve_model(alias)
        if spec["provider"] == "claude_cli":
            binary = spec.get("bin") or "claude"
            path = shutil.which(binary)
            mark = "✓" if path else "✗"
            model = spec.get("model") or "(subscription default)"
            print(f"  {mark} {alias:12s} {spec['provider']:10s} "
                  f"{model:24s} {path or binary + ' not found'}")
            continue
        mark = "✓" if spec["api_key"] else "✗"
        base = spec.get("base_url") or "(default)"
        print(f"  {mark} {alias:12s} {spec['provider']:10s} "
              f"{spec['model']:24s} {base}")


def build_parser():
    p = argparse.ArgumentParser(prog="minicrew",
                                description="Local, config-driven multi-agent "
                                            "discussion for research projects.")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a crew discussion")
    r.add_argument("crew", help="crew name (see `minicrew list`)")
    r.add_argument("--file", "-f", action="append", default=[],
                   help="extra context file (repeatable)")
    r.add_argument("--rounds", "-n", type=int, default=None,
                   help="override discussion rounds (round_robin only)")
    r.add_argument("--topology", "-t", default=None,
                   choices=["round_robin", "parallel_blind"],
                   help="override the crew's topology")
    r.add_argument("--dry-run", action="store_true",
                   help="assemble prompts and print them; make no API calls")
    r.add_argument("--mock", action="store_true",
                   help="run the full pipeline with deterministic fake replies "
                        "(no keys, no tokens) — proves the wiring")
    r.add_argument("--out", "-o", default=None, help="transcript output path")
    r.set_defaults(func=_cmd_run)

    d = sub.add_parser("distill", help="distil a paper's text into a "
                       "knowledge/literature note (verify the numbers before use)")
    d.add_argument("input", help="paper file (.pdf auto-converted) or '-' for stdin")
    d.add_argument("--si", default=None,
                   help="supplementary-information file (.pdf/.txt) to mine for "
                        "data tables")
    d.add_argument("--out", "-o", default=None,
                   help="write the note here (default: print to stdout)")
    d.add_argument("--model", "-m", default="claude_cli",
                   help="model alias for the librarian (default: claude_cli)")
    d.add_argument("--verify", action="store_true",
                   help="cross-check the draft's numbers with a second model")
    d.add_argument("--check-model", default="openai",
                   help="model alias for the fact-checker (default: openai)")
    d.add_argument("--mock", action="store_true", help="no API calls")
    d.set_defaults(func=_cmd_distill)

    g = sub.add_parser("figures", help="vision-extract figure/table data from a "
                       "PDF (needs a multimodal model; confirm plot-read numbers)")
    g.add_argument("pdf", help="PDF path")
    g.add_argument("--pages", default=None, help="page or range, e.g. 3 or 2-4")
    g.add_argument("--model", "-m", default="openai", help="vision model alias")
    g.add_argument("--out", "-o", default=None, help="write extracted data here")
    g.set_defaults(func=_cmd_figures)

    sed = sub.add_parser("sediment", help="extract a discussion's decisions into "
                         "knowledge/decisions/ (closes the loop)")
    sed.add_argument("run_id", nargs="?", default=None,
                     help="run id substring (default: latest run)")
    sed.add_argument("--model", "-m", default="claude_cli", help="scribe model")
    sed.add_argument("--verify", nargs="?", const="openai", default=None,
                     help="fact-check claims vs evidence before sedimenting "
                          "(optional model alias; default openai)")
    sed.set_defaults(func=_cmd_sediment)

    sub.add_parser("index", help="(re)index literature notes into Mongo + Qdrant"
                   ).set_defaults(func=_cmd_index)

    s = sub.add_parser("search", help="semantic-search the literature index")
    s.add_argument("query", help="natural-language query")
    s.add_argument("-k", type=int, default=5, help="number of results")
    s.add_argument("--tag", action="append", default=[],
                   help="filter by tag (repeatable)")
    s.set_defaults(func=_cmd_search)

    sub.add_parser("list", help="list available crews").set_defaults(func=_cmd_list)
    sub.add_parser("models", help="show model aliases + key status").set_defaults(
        func=_cmd_models)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
