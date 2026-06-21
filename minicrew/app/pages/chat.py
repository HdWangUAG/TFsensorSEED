"""Chat page — talk 1:1 with a single agent, grounded in project knowledge."""
import os

import streamlit as st

from minicrew.core import agents, chat, config, crew, toolcall

st.title("💬 Chat with an agent")


def _answer(agent, hist, msg, ground, use_tools):
    if use_tools:
        prov = config.resolve_model(agent["model"]).get("provider")
        tmodel = agent["model"] if prov == "openai" else "openai"
        convo = "\n".join(f"{h['role']}: {h['content']}" for h in hist)
        user = (convo + "\n\n" if convo else "") + msg
        try:
            ans, trace = toolcall.run(agent.get("body", "You are a helpful expert."),
                                      user, model=tmodel)
            if trace:
                with st.expander("🛠️ tool calls (real computations)", expanded=True):
                    for t in trace:
                        st.write(f"`{t['tool']}({t['args']})` → {t['result']}")
            return ans or "(no answer)"
        except Exception as exc:
            return f"⚠️ {exc}"
    try:
        return chat.reply(agent, hist, msg, ground=ground)
    except Exception as exc:
        return f"⚠️ {exc}"

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
use_tools = st.sidebar.checkbox("🛠️ Tools (RDKit)", value=False,
                                help="agent computes real descriptors/similarity; "
                                     "uses an OpenAI model for tool-calling")
key = f"chat_{sel}"
if st.sidebar.button("💾 Save chat"):
    _hist = st.session_state.get(key, [])
    if _hist:
        md_path, json_path = chat.save_session(agent, _hist)
        st.sidebar.success(f"saved → {os.path.relpath(md_path, config.REPO_ROOT)}")
        st.sidebar.caption("sediment-ready: " +
                           os.path.relpath(json_path, config.REPO_ROOT))
    else:
        st.sidebar.info("nothing to save yet")
if st.sidebar.button("🧹 Clear conversation"):
    st.session_state.pop(key, None)
    st.rerun()

# --- escalate this chat to a multi-expert discussion ----------------------
st.sidebar.divider()
st.sidebar.caption("⤴ Hit a technical-route fork? Convene a panel on it.")
_crews = crew.list_crews()
if _crews:
    esc_crew = st.sidebar.selectbox("Escalate to crew", _crews)
    if st.sidebar.button("⤴ Escalate to Discussion"):
        _hist = st.session_state.get(key, [])
        if len(_hist) < 2:
            st.sidebar.info("chat a bit first, then escalate")
        else:
            with st.spinner("distilling the fork + convening the panel… "
                            "(real multi-model calls, ~1–2 min)"):
                brief, question, transcript = chat.escalate_to_discussion(
                    agent, _hist, esc_crew)
            st.success(f"Panel convened on: {question}")
            with st.expander("⤴ escalation brief + panel verdict", expanded=True):
                st.markdown("### Brief\n" + brief)
                st.markdown("### Panel")
                for t in transcript:
                    st.markdown(f"**{t['role']}** ({t['alias']})\n\n{t['content']}")
            st.caption("Saved to conversations/ + runs/. Sediment it to "
                       "`decisions` on the **History** page.")

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
            ans = _answer(agent, hist, msg, ground, use_tools)
        st.markdown(ans)
    hist.append({"role": "user", "content": msg})
    hist.append({"role": "assistant", "content": ans})
