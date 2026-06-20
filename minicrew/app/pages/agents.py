"""Agents page — create / edit / delete knowledge & tool agents."""
import streamlit as st

from minicrew.core import agents, config

st.title("🤖 Agents")
st.caption("Knowledge agents (viewpoints, used today) and tool agents "
           "(capabilities, for tool-calling). Edited here, used by Chat & crews.")

aliases = sorted(config.MODELS)
existing = agents.list_agents()
labels = {f"{'🛠️' if a['kind'] == 'tool' else '🤖'} {a['name']}  ·  {a['kind']}/{a['file']}": a
          for a in existing}

choice = st.sidebar.radio("Edit", ["➕ New agent"] + list(labels))
editing = None if choice == "➕ New agent" else labels[choice]

if editing and st.sidebar.button("🗑️ Delete this agent"):
    agents.delete(editing["kind"], editing["file"])
    st.sidebar.success(f"Deleted {editing['file']}")
    st.rerun()

st.subheader("New agent" if not editing else f"Editing · {editing['name']}")

col1, col2 = st.columns(2)
kind = col1.selectbox(
    "Type", ["persona", "tool"],
    index=0 if (not editing or editing["kind"] == "persona") else 1,
    help="persona = a viewpoint (works today); tool = persona + real tool-calling (roadmap)")
file = col2.text_input("File name", value=editing["file"] if editing else "",
                       placeholder="e.g. structural_biologist.md",
                       disabled=bool(editing))

name = col1.text_input("Display name", value=editing["name"] if editing else "")
_models = ["(none)"] + aliases
_cur = (editing or {}).get("model")
model = col2.selectbox("Default model", _models,
                       index=_models.index(_cur) if _cur in _models else 0)
description = st.text_input("Description (one line)",
                           value=editing["description"] if editing else "")
body = st.text_area("System prompt (the agent's role / instructions)",
                    value=editing["body"] if editing else "", height=380,
                    placeholder="You are a rigorous … expert. You do NOT cheerlead …")

if st.button("💾 Save agent", type="primary"):
    if not name.strip() or not file.strip() or not body.strip():
        st.warning("Name, file name and system prompt are all required.")
    else:
        m = None if model == "(none)" else model
        path = agents.save(kind, file, name, body, model=m, description=description)
        st.success(f"Saved → {path}")
        st.rerun()
