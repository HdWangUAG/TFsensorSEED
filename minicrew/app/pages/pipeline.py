"""Pipeline — the MiniCrew research workflow + this project's live status."""
import glob
import os

import streamlit as st

from minicrew.core import agents, config, crew, litdb, litstore

st.title("🧭 Pipeline")
st.caption("How a paper becomes a discovery — and where your project stands.")

notes = litstore.list_notes()
personas = agents.list_agents("persona")
tools = agents.list_agents("tool")
crews = crew.list_crews()
runs = glob.glob(os.path.join(config.RUNS_DIR, "*.json"))
db_ok, _ = litdb.status()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📚 Notes", len(notes))
c2.metric("🗄️ Vector DB", "up" if db_ok else "down")
c3.metric("🤖 Agents", len(personas) + len(tools))
c4.metric("👥 Crews", len(crews))
c5.metric("🗂️ Discussions", len(runs))


def _node(nid, label, ok):
    color = "#2e7d32" if ok else "#9e9e9e"
    return (f'{nid} [label="{label}", style="filled,rounded", fillcolor="{color}", '
            f'fontcolor=white, shape=box, margin=0.25];\n')


dot = 'digraph { rankdir=LR; bgcolor="transparent"; node [fontname="sans-serif"];\n'
dot += _node("ingest", "① Ingest\\nPDF · SI · figures", True)
dot += _node("distill", "② Distill\\n+ cross-check", True)
dot += _node("index", "③ Index\\nSPECTER2 → Qdrant", db_ok)
dot += _node("discuss", "④ Discuss\\nmulti-agent room", len(crews) > 0)
dot += _node("discover", "⑤ Discover\\nsynthesis + history", len(runs) > 0)
dot += "ingest -> distill -> index -> discuss -> discover;\n}"
st.graphviz_chart(dot, use_container_width=True)
st.caption("Green = ready / has data · grey = not set up yet.")

st.divider()
st.subheader("Knowledge layers (trust-tiered)")
for cat, tier in config.KNOWLEDGE_TRUST.items():
    srcs = config.KNOWLEDGE_SOURCES.get(cat, [])
    n = 0
    for s in srcs:
        n += len(glob.glob(os.path.join(s, "*.md"))) + len(glob.glob(os.path.join(s, "*.txt")))
    st.markdown(f"- **{cat}** · {n} file(s) — _{tier}_")

pipe_md = os.path.join(config.REPO_ROOT, "PIPELINE.md")
if os.path.isfile(pipe_md):
    st.divider()
    with st.expander("📄 Research pipeline (PIPELINE.md)"):
        with open(pipe_md, encoding="utf-8") as fh:
            st.markdown(fh.read())
