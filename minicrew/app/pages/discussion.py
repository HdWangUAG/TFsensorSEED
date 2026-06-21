"""Discussion room — run a crew and watch the agents discover, live."""
import os
import subprocess
import tempfile

import streamlit as st

from minicrew.core import crew

st.title("🔬 Discussion room")
st.caption("Your agents review a task by role (blind or in turns), then a "
           "moderator synthesises — streamed live as each one finishes.")

crews = crew.list_crews()
if not crews:
    st.info("No crews in minicrew/configs/. Add one (copy steroid_plan_review.yaml).")
    st.stop()

name = st.sidebar.selectbox("Crew", list(crews))
topo = st.sidebar.selectbox("Topology", ["(crew default)", "parallel_blind", "round_robin"])
rounds = st.sidebar.number_input("Rounds (round_robin)", 1, 5, 1)
mock = st.sidebar.checkbox("Mock (no API calls / free)", value=False)
upload = st.sidebar.file_uploader("Extra material (optional)", type=["md", "txt", "pdf"])

try:
    c = crew.load_crew(name)
except Exception as exc:
    st.error(exc)
    st.stop()

st.markdown(f"**Task** — {c.get('task', c.get('description', ''))}")
st.caption("Reviewers: "
           + ", ".join(f"{r['name']} ({r.get('model', '?')})" for r in c["roles"])
           + (f"  ·  Moderator: {c['synthesizer'].get('name', 'Moderator')}"
              f" ({c['synthesizer'].get('model', '?')})" if c.get("synthesizer") else "")
           + f"  ·  knowledge: {', '.join(c.get('knowledge') or []) or 'none'}")


def _render_turn(ev):
    moderator = ev["kind"] == "moderator"
    icon = "🟦" if moderator else "🔹"
    with st.chat_message("assistant", avatar="🧑‍⚖️" if moderator else "🧑‍🔬"):
        rnd = f" · round {ev['round']}" if ev.get("round") else ""
        st.markdown(f"{icon} **{ev['role']}**  ·  `{ev['alias']}:{ev['model']}`{rnd}")
        st.markdown(ev.get("content", ""))


# persist the most recent discussion across reruns (also saved to History)
prev = st.session_state.get("last_discussion")
if prev and st.session_state.get("last_crew") == name:
    st.caption("Most recent run (also in 🗂️ History):")
    for ev in prev:
        _render_turn(ev)

if st.button("▶ Run discussion", type="primary"):
    extra = []
    if upload is not None:
        suffix = os.path.splitext(upload.name)[1].lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
            tf.write(upload.getvalue())
            path = tf.name
        if suffix == ".pdf":
            txt = subprocess.run(["pdftotext", "-layout", path, "-"],
                                 capture_output=True, text=True).stdout
            path = path + ".txt"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(txt)
        extra = [path]

    turns, holder = [], st.container()

    def on_event(ev):
        if ev["type"] == "turn":
            turns.append(ev)
            with holder:
                _render_turn(ev)
        elif ev["type"] == "done":
            with holder:
                st.success(f"Done — saved as run `{ev['run_id']}`.")

    ok = False
    with st.spinner("agents are discussing… (a real run takes 1–3 min)"):
        try:
            crew.run_crew(
                name, extra_files=extra,
                topology=None if topo == "(crew default)" else topo,
                rounds=int(rounds), mock=mock, on_event=on_event)
            ok = True
        except Exception as exc:
            st.error(f"Run failed: {exc}")
    if ok:                                   # rerun OUTSIDE try (it raises to control flow)
        st.session_state["last_discussion"] = turns
        st.session_state["last_crew"] = name
        st.rerun()
