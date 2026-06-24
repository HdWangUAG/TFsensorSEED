"""Agents page — create / edit / delete persona agents."""
import streamlit as st

from minicrew.core import agents, config

st.title("🤖 Agents")
st.caption("Persona agents = scientific viewpoints/roles, used by Chat & crews. "
           "Runnable computational capabilities live on the **Skills** page, not here.")

aliases = sorted(config.MODELS)
existing = agents.list_agents("persona")
labels = {f"🤖 {a['name']}  ·  {a['file']}": a for a in existing}

choice = st.sidebar.radio("Edit", ["➕ New agent"] + list(labels))
editing = None if choice == "➕ New agent" else labels[choice]

if editing and st.sidebar.button("🗑️ Delete this agent"):
    agents.delete("persona", editing["file"])
    st.sidebar.success(f"Deleted {editing['file']}")
    st.rerun()

st.subheader("New agent" if not editing else f"Editing · {editing['name']}")

col1, col2 = st.columns(2)
file = col1.text_input("File name", value=editing["file"] if editing else "",
                       placeholder="e.g. structural_biologist.md",
                       disabled=bool(editing))
name = col2.text_input("Display name", value=editing["name"] if editing else "")

_models = ["(none)"] + aliases
_cur = (editing or {}).get("model")
model = col1.selectbox("Default model", _models,
                       index=_models.index(_cur) if _cur in _models else 0)
description = col2.text_input("Description (one line)",
                             value=editing["description"] if editing else "")
body = st.text_area("System prompt (the agent's role / instructions)",
                    value=editing["body"] if editing else "", height=380,
                    placeholder="You are a rigorous … expert. You do NOT cheerlead …")

if st.button("💾 Save agent", type="primary"):
    if not name.strip() or not file.strip() or not body.strip():
        st.warning("Name, file name and system prompt are all required.")
    else:
        m = None if model == "(none)" else model
        path = agents.save("persona", file, name, body, model=m,
                           description=description)
        st.success(f"Saved → {path}")
        st.rerun()
