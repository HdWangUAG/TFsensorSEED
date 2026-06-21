"""Chat page — talk 1:1 with a single agent, grounded in project knowledge."""
import os

import streamlit as st

from minicrew.core import agents, chat, config, crew, toolcall

st.title("💬 Chat with an agent")

# Pin the toolbar so it stays visible while the chat scrolls (a "floating" bar).
# The selector is scoped to the one container that holds the anchor below, so it
# does not also stick the page's other vertical blocks. (`:has` needs a Chromium/
# Edge/Firefox-recent browser.)
st.markdown(
    """
    <style>
    /* Stick the container WRAPPER (its parent is the full-height content block,
       so there is scroll travel). Sticking the inner block fails — its parent is
       only as tall as the toolbar, so it scrolls away. */
    div[data-testid="stVerticalBlock"] > div:has(.mc-toolbar-anchor),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.mc-toolbar-anchor){
        position: sticky;
        top: 3.25rem;
        z-index: 1000;
        /* Frosted glass — theme-agnostic: shows a blurred version of whatever is
           behind, so it darkens in dark mode and lightens in light mode without
           needing to know the theme. Text keeps the theme's colour and stays
           readable in both. */
        background-color: rgba(127,127,127,0.08);
        backdrop-filter: blur(16px) saturate(180%);
        -webkit-backdrop-filter: blur(16px) saturate(180%);
        padding: 0.5rem 0.25rem 0.35rem;
        border-bottom: 1px solid rgba(128,128,128,0.25);
        box-shadow: 0 6px 12px -8px rgba(0,0,0,0.5);
    }
    </style>
    """,
    unsafe_allow_html=True)


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
# Apply a deferred "resume" agent switch BEFORE the selectbox is instantiated —
# Streamlit forbids modifying a widget-keyed session value after the widget exists.
_resume_to = st.session_state.pop("_resume_agent", None)
if _resume_to and _resume_to in names:
    st.session_state["chat_agent"] = _resume_to

# === floating toolbar (sticky) ============================================
toolbar = st.container()
with toolbar:
    st.markdown('<span class="mc-toolbar-anchor"></span>', unsafe_allow_html=True)

    # identity row: agent / model / toggles. `key=` keeps selections across nav.
    c_agent, c_model, c_ground, c_tools = st.columns([3, 2, 1.6, 1.6])
    sel = c_agent.selectbox("Agent", list(names), key="chat_agent")
    agent = dict(names[sel])
    aliases = sorted(config.MODELS)
    default_model = agent.get("model") or "claude_cli"
    agent["model"] = c_model.selectbox(
        "Model", aliases, key=f"chat_model_{sel}",
        index=aliases.index(default_model) if default_model in aliases else 0)
    ground = c_ground.toggle("📚 Ground", value=True, key="chat_ground",
                             help="inject relevant pitfalls + top-k literature")
    use_tools = c_tools.toggle("🛠️ Tools", value=False, key="chat_tools",
                               help="agent computes real descriptors/similarity "
                                    "(uses an OpenAI model for tool-calling)")

    key = f"chat_{sel}"

    # action row: save / clear / resume
    _saved = chat.list_saved_chats()
    _labels = ["—"] + [s[0] for s in _saved]
    b_save, b_clear, b_pick, b_resume = st.columns([1, 1, 3.5, 1])
    if b_save.button("💾 Save", use_container_width=True):
        _hist = st.session_state.get(key, [])
        if _hist:
            md_path, _ = chat.save_session(agent, _hist)
            st.toast(f"💾 saved → {os.path.relpath(md_path, config.REPO_ROOT)}")
        else:
            st.toast("nothing to save yet")
    if b_clear.button("🧹 Clear", use_container_width=True):
        st.session_state.pop(key, None)
        st.rerun()
    _pick = b_pick.selectbox("Resume a saved chat", _labels,
                             key="chat_resume_pick", label_visibility="collapsed")
    if b_resume.button("📂 Resume", use_container_width=True) and _pick != "—":
        _, _path, _ag = _saved[_labels.index(_pick) - 1]
        _hist_loaded, _ = chat.load_history(_path)
        if _ag in names:
            st.session_state[f"chat_{_ag}"] = _hist_loaded
            st.session_state["_resume_agent"] = _ag   # applied at top of next run
        else:
            st.session_state[key] = _hist_loaded
        st.rerun()

# === escalate to a discussion (folded, below the sticky bar) ==============
with st.expander("⤴ Hit a technical-route fork? Convene a panel on it."):
    _crews = crew.list_crews()
    if _crews:
        e_crew, e_btn = st.columns([3, 1])
        esc_crew = e_crew.selectbox("Escalate to crew", _crews,
                                    key="chat_escalate_crew")
        if e_btn.button("⤴ Escalate", use_container_width=True):
            _hist = st.session_state.get(key, [])
            if len(_hist) < 2:
                st.info("chat a bit first, then escalate")
            else:
                with st.spinner("distilling the fork + convening the panel… "
                                "(real multi-model calls, ~1–2 min)"):
                    brief, question, transcript = chat.escalate_to_discussion(
                        agent, _hist, esc_crew)
                st.success(f"Panel convened on: {question}")
                st.markdown("### Brief\n" + brief)
                st.markdown("### Panel")
                for t in transcript:
                    st.markdown(f"**{t['role']}** ({t['alias']})\n\n{t['content']}")
                st.caption("Saved to conversations/ + runs/. Sediment it to "
                           "`decisions` on the **History** page.")

if agent.get("description"):
    st.caption(agent["description"])

# Keep the sidebar populated so it stays expanded and the page-navigation icons
# remain visible (an empty page-sidebar gets collapsed by Streamlit). The actual
# controls live in the floating toolbar above.
with st.sidebar:
    st.markdown("### 💬 Chat")
    st.caption(f"with **{sel}**"
               + (f" · `{agent['model']}`" if agent.get("model") else ""))
    if agent.get("description"):
        st.caption(agent["description"])
    if agent.get("capabilities") or agent.get("limitations"):
        with st.expander("ℹ️ capabilities & limits"):
            if agent.get("capabilities"):
                st.caption("**✓ Can:** " + agent["capabilities"])
            if agent.get("limitations"):
                st.caption("**✗ Can't:** " + agent["limitations"])
            st.caption("Full reference: `minicrew/docs/AGENTS.md`")
    st.caption("Controls are in the floating bar at the top ↑")

# === chat room ============================================================
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
