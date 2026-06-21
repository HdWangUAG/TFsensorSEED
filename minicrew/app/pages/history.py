"""Discussion history — browse past runs, with the prompt each agent saw."""
import glob
import json
import os

import streamlit as st

from minicrew.core import config, scribe

st.title("🗂️ Discussion history")

files = sorted(glob.glob(os.path.join(config.RUNS_DIR, "*.json")), reverse=True)
if not files:
    st.info("No past discussions yet — run one in the Discussion room.")
    st.stop()

labels = {}
for f in files:
    try:
        d = json.load(open(f, encoding="utf-8"))
        labels[f"{d.get('timestamp', '?')} · {d.get('crew', '?')} "
               f"({d.get('topology', '?')})"] = d
    except (OSError, json.JSONDecodeError):
        continue

sel = st.sidebar.selectbox("Run", list(labels))
d = labels[sel]

st.markdown(f"**{d.get('crew')}** · {d.get('topology')} · {d.get('timestamp')}")
if d.get("task"):
    st.caption(d["task"])

if st.button("📌 Sediment to knowledge",
             help="Extract consensus / decisions / open questions into "
                  "knowledge/decisions/ so future discussions build on them."):
    with st.spinner("scribe is extracting durable knowledge…"):
        try:
            path, note = scribe.sediment_run(d)
            st.success(f"Saved → {os.path.relpath(path, config.REPO_ROOT)}")
            with st.expander("📝 what was sedimented", expanded=True):
                st.markdown(note)
        except Exception as exc:
            st.error(f"Failed: {exc}")
st.divider()

for o in d.get("outputs", []):
    moderator = o.get("kind") == "moderator"
    icon = "🟦" if moderator else "🔹"
    ok = "" if o.get("ok", True) else " ⚠️ (skipped)"
    st.markdown(f"### {icon} {o.get('agent')}  ·  "
                f"`{o.get('alias')}:{o.get('model')}`{ok}")
    st.markdown(o.get("reply", ""))
    with st.expander("🔬 prompt this agent saw"):
        st.code(o.get("prompt_seen", ""))
    st.divider()
