"""Context pack — retrieve a compact, relevant, role-specific briefing.

Replaces "dump every knowledge file truncated" with "retrieve what THIS task and
THIS role need, within a budget". Built on the typed memory (kdb) + literature
RAG. Properties the reviewer required:
  - query-aware: pulls only records relevant to the task (semantic when the DB is
    up, keyword+metadata otherwise);
  - status-filtered: HIDES superseded decisions by default (a reversed call must
    not resurface as if live); marks low-confidence;
  - role-specific: each role gets a different slice + emphasis (the Tool-Runner
    gets almost nothing; the Skeptic also sees superseded + low-confidence);
  - budgeted: per-section caps so a flood of records can't blow the window.

Used by crew.py when a crew sets `context_pack: true` (flag-gated → the old flat
behavior stays A/B-comparable via the logged `prompt_seen`).
"""
from __future__ import annotations

from . import kdb, knowledge

# per-role retrieval emphasis: how many of each record type to pull, plus flags.
# Matched by substring against the role name (lowercased). `_DEFAULT` otherwise.
_DEFAULT = {"decision": 4, "claim": 4, "evidence": 4, "pitfall": 4, "literature": 3}
ROLE_FOCUS = {
    "moderator": {"decision": 5, "claim": 4, "evidence": 4, "pitfall": 3, "literature": 2},
    "pi":        {"decision": 5, "claim": 4, "evidence": 3, "pitfall": 3, "literature": 2},
    "structural": {"decision": 2, "claim": 3, "evidence": 5, "pitfall": 4, "literature": 3},
    "skeptic":   {"decision": 3, "claim": 4, "evidence": 4, "pitfall": 5, "literature": 2,
                  "include_superseded": True},          # the skeptic SHOULD see reversals
    "ml":        {"decision": 3, "claim": 5, "evidence": 4, "pitfall": 3, "literature": 2},
    "tool":      {"decision": 0, "claim": 0, "evidence": 0, "pitfall": 1, "literature": 0},
}
_SECTION_ORDER = ["pitfall", "decision", "evidence", "claim", "literature"]
_SECTION_TITLE = {"pitfall": "Relevant pitfalls (HARD CONSTRAINTS — do not repeat)",
                  "decision": "Active decisions",
                  "evidence": "Relevant evidence",
                  "claim": "Relevant claims",
                  "literature": "Relevant literature"}


def _focus(role_name):
    name = (role_name or "").lower()
    for key, f in ROLE_FOCUS.items():
        if key in name:
            return f
    return _DEFAULT


def _fmt_record(r):
    bits = [f"[{r['id']}] (status={r.get('status')}, conf={r.get('confidence')}"]
    if r.get("relation"):
        bits.append(f", relation={r['relation']}")
    if r.get("superseded_by"):
        bits.append(f", ⤳{r['superseded_by']}")
    head = "".join(bits) + ")"
    tags = (" {" + ", ".join(map(str, r.get("tags") or [])) + "}") if r.get("tags") else ""
    return f"- {head}{tags}\n  {(r.get('text','') or '').strip()[:400]}"


def build_pack(question, role=None, budget_chars=12000):
    """Assemble the role-specific context pack. Returns (text, stats)."""
    focus = _focus(role)
    incl_sup = focus.get("include_superseded", False)
    retrieved = {}
    for rtype in ("decision", "claim", "evidence", "pitfall"):
        k = focus.get(rtype, _DEFAULT[rtype])
        if k <= 0:
            continue
        recs = kdb.search(question, types=[rtype], include_superseded=incl_sup, top_k=k)
        if recs:
            retrieved[rtype] = recs

    sections, used, dropped = [], 0, []
    for rtype in _SECTION_ORDER:
        if rtype == "literature":
            if focus.get("literature", 0) <= 0:
                continue
            lit = knowledge._literature_retrieved(question) if question else None
            if not lit:
                continue
            block = lit
        else:
            recs = retrieved.get(rtype)
            if not recs:
                continue
            block = (f"### {_SECTION_TITLE[rtype]}\n"
                     + "\n".join(_fmt_record(r) for r in recs))
        if used + len(block) > budget_chars:
            dropped.append(rtype)
            continue
        sections.append(block)
        used += len(block)

    focus_line = _role_instruction(role)
    header = "## Project context pack (retrieved for this task" + (
        f" · role: {role}" if role else "") + ")"
    body = "\n\n".join([header, focus_line] + sections) if sections else (
        header + "\n" + focus_line + "\n(no relevant prior records retrieved)")
    if dropped:
        body += f"\n\n_(sections trimmed for budget: {', '.join(dropped)})_"
    stats = {"chars": len(body), "sections": [s for s in _SECTION_ORDER
                                              if s in retrieved or s == "literature"],
             "counts": {k: len(v) for k, v in retrieved.items()},
             "include_superseded": incl_sup}
    return body, stats


def _role_instruction(role):
    name = (role or "").lower()
    if "skeptic" in name:
        return ("_As the Skeptic: weigh contradictory evidence and superseded "
                "decisions; name the artefact most likely to fool the panel._")
    if "moderator" in name or "pi" in name:
        return ("_As the PI/Moderator: synthesise against ACTIVE decisions + the "
                "evidence map; flag the least-verifiable claim._")
    if "tool" in name:
        return "_As the Tool-Runner: you need only the skill + args; ignore the rest._"
    if "structural" in name:
        return ("_As the Structural Biologist: focus on pose/contact evidence and "
                "structural pitfalls; request analyze_structure if a real pose check helps._")
    return ("_Weigh each record by its status + confidence; computational evidence "
            "is coarse (see COMPUTATIONAL_BOUNDARY.md), wet-lab overrides it._")
