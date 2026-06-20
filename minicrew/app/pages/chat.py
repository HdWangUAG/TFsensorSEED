"""Chat page — talk 1:1 with a single agent, grounded in project knowledge."""
import streamlit as st

from minicrew.core import agents, chat, config

st.title("💬 Chat with an agent")

personas = agents.list_agents("persona")
if not personas:
    st.info("No knowledge agents yet — create one on the **Agents** page.")
    st.stop()

names = {a["name"]: a for a in personas}
sel = st.sidebar.selectbox("Agent", list(names))
agent = dict(names[sel])

aliases = sorted(config.MODELS)
default_model = agent.get("model") or "claude_cli"
agent["model"] = st.sidebar.selectbox(
    "Model", aliases,
    index=aliases.index(default_model) if default_model in aliases else 0)
ground = st.sidebar.checkbox("Ground in project knowledge", value=True,
                             help="inject relevant pitfalls + top-k literature")
if st.sidebar.button("🧹 Clear conversation"):
    st.session_state.pop(f"chat_{sel}", None)
    st.rerun()

if agent.get("description"):
    st.caption(agent["description"])

key = f"chat_{sel}"
hist = st.session_state.setdefault(key, [])
for h in hist:
    st.chat_message(h["role"]).markdown(h["content"])

msg = st.chat_input(f"Message {sel}…")
if msg:
    st.chat_message("user").markdown(msg)
    with st.chat_message("assistant"):
        with st.spinner(f"{sel} is thinking…"):
            try:
                ans = chat.reply(agent, hist, msg, ground=ground)
            except Exception as exc:
                ans = f"⚠️ {exc}"
        st.markdown(ans)
    hist.append({"role": "user", "content": msg})
    hist.append({"role": "assistant", "content": ans})
