"""MiniCrew — AI co-scientist workbench (multipage Streamlit entry).

Run: scripts/minicrew-app   (or scripts/minicrew-desktop for a native window)
"""
import streamlit as st

from minicrew.core import agents, config, crew, litstore

st.set_page_config(page_title="MiniCrew", page_icon="🔬", layout="wide")


def home():
    st.title("🔬 MiniCrew — AI co-scientist workbench")
    st.caption("Local, model-agnostic agents that read your papers and data, "
               "discuss by role, and help you do research.")

    personas = agents.list_agents("persona")
    tools = agents.list_agents("tool")
    notes = litstore.list_notes()
    crews = crew.list_crews()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🤖 Knowledge agents", len(personas))
    c2.metric("🛠️ Tool agents", len(tools))
    c3.metric("📚 Literature notes", len(notes))
    c4.metric("👥 Crews", len(crews))

    st.divider()
    a, b = st.columns(2)
    with a:
        st.subheader("Sections")
        st.markdown(
            "- **🔬 Discussion room** — run a crew, watch agents discover live\n"
            "- **💬 Chat** — talk 1:1 with an agent, grounded in your knowledge\n"
            "- **🤖 Agents** — create / edit / delete knowledge & tool agents\n"
            "- **📚 Literature** — ingest papers (PDF/SI/figures), distil, search\n"
            "- **🧭 Pipeline** — workflow + project status\n"
            "- **🗂️ History** — browse past discussions (with each agent's prompt)")
    with b:
        st.subheader("Your agents")
        for ag in personas + tools:
            tag = "🛠️" if ag["kind"] == "tool" else "🤖"
            st.caption(f"{tag} **{ag['name']}**"
                       + (f" · {ag['model']}" if ag.get("model") else "")
                       + (f" — {ag['description']}" if ag.get("description") else ""))


nav = [
    st.Page(home, title="Home", icon="🏠", default=True),
    st.Page("pages/discussion.py", title="Discussion room", icon="🔬"),
    st.Page("pages/chat.py", title="Chat", icon="💬"),
    st.Page("pages/agents.py", title="Agents", icon="🤖"),
    st.Page("pages/literature.py", title="Literature", icon="📚"),
    st.Page("pages/pipeline.py", title="Pipeline", icon="🧭"),
    st.Page("pages/history.py", title="History", icon="🗂️"),
]
st.navigation(nav).run()
