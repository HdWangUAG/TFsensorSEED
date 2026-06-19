"""`minicrew` command-line entry point.

    minicrew run <crew> [--file plan.md ...] [--rounds N] [--dry-run] [--out PATH]
    minicrew list
    minicrew models
"""
from __future__ import annotations

import argparse
import shutil
import sys

from .core import config, crew, distill


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


def _cmd_distill(args):
    if args.input == "-":
        text = sys.stdin.read()
    else:
        if args.input.lower().endswith(".pdf"):
            print("error: distill takes text, not PDF. Convert first, e.g. "
                  "`pdftotext paper.pdf paper.txt`", file=sys.stderr)
            return
        with open(args.input, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    if not text.strip():
        print("error: empty input", file=sys.stderr)
        return

    note = distill.distill(text, model=args.model, mock=args.mock)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(note)
        print(f"[draft saved → {args.out}]  — verify the numbers + DOI before use")
    else:
        print(note)

    if args.verify:
        print("\n" + "=" * 60 + "\nFACT-CHECK (" + args.check_model + ")\n" + "=" * 60)
        print(distill.verify(text, note, model=args.check_model, mock=args.mock))


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
    d.add_argument("input", help="paper text file, or '-' for stdin "
                   "(convert PDFs first: pdftotext paper.pdf paper.txt)")
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
