"""Crews — assemble agents into a team for a topic (create / edit / delete)."""
import os

import streamlit as st

from minicrew.core import agents, config, crews

st.title("👥 Crews — build an agent team")
st.caption("Assemble agents into a team for a research topic. Saved crews appear "
           "in the 🔬 Discussion room. New topic? Make agents first (🤖 Agents), "
           "then assemble them here.")

personas = agents.list_agents("persona")
if not personas:
    st.info("No knowledge agents yet — create some on the **Agents** page first.")
    st.stop()

by_name = {a["name"]: a for a in personas}
file_to_name = {a["file"]: a["name"] for a in personas}
aliases = sorted(config.MODELS)

existing = crews.list_crews()
choice = st.sidebar.radio("Edit", ["➕ New crew"] + list(existing))
editing = None
if choice != "➕ New crew":
    try:
        editing = crews.get(choice)
    except Exception as exc:
        st.error(exc)

if editing and st.sidebar.button("🗑️ Delete this crew"):
    crews.delete(choice)
    st.sidebar.success(f"Deleted {choice}")
    st.rerun()

ed = editing or {}
c1, c2 = st.columns(2)
name = c1.text_input("Crew file name", value=(choice if editing else ""),
                     disabled=bool(editing),
                     placeholder="e.g. kinase_inhibitor_review")
project = c2.text_input("Project / topic", value=ed.get("project", ""))
task = st.text_area("Task — what should the team review or do?",
                    value=ed.get("task", ""), height=120,
                    placeholder="Critically review … stress-test … propose …")

c3, c4 = st.columns(2)
topo_opts = ["parallel_blind", "round_robin"]
topology = c3.selectbox(
    "Topology", topo_opts,
    index=topo_opts.index(ed.get("topology")) if ed.get("topology") in topo_opts else 0,
    help="parallel_blind = independent reviews + moderator; "
         "round_robin = a debate over N rounds")
rounds = c4.number_input("Rounds (round_robin only)", 1, 5,
                         int(ed.get("rounds", 1)))

knowledge = st.multiselect(
    "Knowledge layers to ground on",
    ["pitfalls", "computational", "experimental", "literature"],
    default=ed.get("knowledge", []))

c5, c6 = st.columns(2)
ctx = c5.text_area("Context files (one per line, repo-relative)",
                   value="\n".join(ed.get("context_files", []) or []), height=90,
                   placeholder="PIPELINE.md\nPROGRESS.md")
evid = c6.text_area("Evidence files (one per line)",
                    value="\n".join(ed.get("evidence_files", []) or []), height=90,
                    placeholder="DEV_STATUS.md")

st.divider()
st.subheader("Reviewers")
default_rev, role_model = [], {}
for r in ed.get("roles", []):
    nm = file_to_name.get(os.path.basename(r.get("persona_file", "")))
    if nm:
        default_rev.append(nm)
        role_model[nm] = r.get("model")
picked = st.multiselect("Reviewer agents", list(by_name), default=default_rev)
reviewers = []
for nm in picked:
    ag = by_name[nm]
    dflt = role_model.get(nm) or ag.get("model") or "claude_cli"
    m = st.selectbox(f"model for · {nm}", aliases,
                     index=aliases.index(dflt) if dflt in aliases else 0,
                     key=f"rev_{nm}")
    reviewers.append({"name": nm, "model": m,
                      "persona_file": f"personas/{ag['file']}"})

st.subheader("Moderator (optional)")
mod_names = ["(none)"] + list(by_name)
cur_mod = None
if ed.get("synthesizer"):
    cur_mod = file_to_name.get(os.path.basename(ed["synthesizer"].get("persona_file", "")))
mod_sel = st.selectbox("Moderator agent", mod_names,
                       index=mod_names.index(cur_mod) if cur_mod in mod_names else 0)
moderator = None
if mod_sel != "(none)":
    ag = by_name[mod_sel]
    dflt = ed.get("synthesizer", {}).get("model") or ag.get("model") or "claude_cli"
    mm = st.selectbox("moderator model", aliases,
                      index=aliases.index(dflt) if dflt in aliases else 0,
                      key="mod_model")
    moderator = {"name": mod_sel, "model": mm,
                 "persona_file": f"personas/{ag['file']}"}

if st.button("💾 Save crew", type="primary"):
    if not name.strip() or not task.strip() or not reviewers:
        st.warning("Need a file name, a task, and at least one reviewer.")
    else:
        spec = crews.build_spec(
            name, project, task, topology, rounds, knowledge,
            [x.strip() for x in ctx.splitlines() if x.strip()],
            [x.strip() for x in evid.splitlines() if x.strip()],
            reviewers, moderator)
        path = crews.save(name, spec)
        st.success(f"Saved → {os.path.relpath(path, config.REPO_ROOT)} — "
                   "now available in the Discussion room.")
        st.rerun()
