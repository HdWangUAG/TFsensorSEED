"""Discussion history — browse, visualize, verify, report on, and sediment runs."""
import glob
import json
import os

import pandas as pd
import streamlit as st

from minicrew.core import config, report, scribe, verify

st.title("🗂️ Discussion history")

files = sorted(glob.glob(os.path.join(config.RUNS_DIR, "*.json")), reverse=True)
if not files:
    st.info("No past discussions yet — run one in the Discussion room.")
    st.stop()

labels = {}
for f in files:
    try:
        dd = json.load(open(f, encoding="utf-8"))
        labels[f"{dd.get('timestamp', '?')} · {dd.get('crew', '?')} "
               f"({dd.get('topology', '?')})"] = dd
    except (OSError, json.JSONDecodeError):
        continue

sel = st.sidebar.selectbox("Run", list(labels))
d = labels[sel]
outputs = [o for o in d.get("outputs", []) if o.get("ok", True)]

st.markdown(f"**{d.get('crew')}** · {d.get('topology')} · {d.get('timestamp')}")
if d.get("task"):
    st.caption(d["task"])

# --- visualization: who contributed how much --------------------------------
contrib = {o["agent"]: len(o.get("reply", "")) for o in outputs}
if contrib:
    st.bar_chart(pd.DataFrame({"chars contributed": contrib}))

# --- actions ----------------------------------------------------------------
vmodel = st.sidebar.selectbox("Verifier / report model", sorted(config.MODELS),
                              index=sorted(config.MODELS).index("openai")
                              if "openai" in config.MODELS else 0)
c1, c2, c3 = st.columns(3)

if c1.button("🔍 Verify claims"):
    moderator = [o for o in outputs if o.get("kind") == "moderator"]
    src = (moderator[-1] if moderator else outputs[-1])["reply"]
    claims = verify.claims_from_text(src)
    with st.spinner(f"fact-checking {len(claims)} claims vs project evidence…"):
        try:
            text, counts = verify.verify_claims(claims, model=vmodel)
            st.bar_chart(pd.DataFrame({"claims": counts}))
            st.markdown(text)
        except Exception as exc:
            st.error(f"Failed: {exc}")

fact_check = c2.checkbox("fact-check first", value=True)
if c2.button("📌 Sediment to knowledge"):
    with st.spinner("scribe extracting durable knowledge…"):
        try:
            path, note = scribe.sediment_run(
                d, verify_model=vmodel if fact_check else None)
            st.success(f"Saved → {os.path.relpath(path, config.REPO_ROOT)}")
            with st.expander("📝 what was sedimented", expanded=True):
                st.markdown(note)
        except Exception as exc:
            st.error(f"Failed: {exc}")

if c3.button("📄 Build report"):
    with st.spinner("building cited report…"):
        try:
            md = report.build_report(d)
            st.session_state["report_md"] = md
        except Exception as exc:
            st.error(f"Failed: {exc}")
if st.session_state.get("report_md"):
    st.download_button("⬇️ Download report (.md)", st.session_state["report_md"],
                       file_name=f"{d.get('timestamp','run')}_{d.get('crew','')}_report.md")

st.divider()
for o in outputs:
    moderator = o.get("kind") == "moderator"
    icon = "🟦" if moderator else "🔹"
    st.markdown(f"### {icon} {o.get('agent')}  ·  `{o.get('alias')}:{o.get('model')}`")
    st.markdown(o.get("reply", ""))
    with st.expander("🔬 prompt this agent saw"):
        st.code(o.get("prompt_seen", ""))
    st.divider()
