"""MiniCrew — Literature library (Streamlit, v1, files backend).

Upload a paper PDF (or paste text) → distil into a structured note with every
number anchored to its source sentence → cross-check with a second model → edit
→ save into knowledge/literature/. No terminal, no YAML.

Launch:  scripts/minicrew-app
"""
import os
import subprocess
import tempfile

import streamlit as st

from minicrew.core import config, distill, litstore

st.set_page_config(page_title="MiniCrew · Literature", page_icon="📚", layout="wide")


def _extract_text(upload, pasted):
    if pasted and pasted.strip():
        return pasted
    if upload is None:
        return ""
    data = upload.getvalue()
    if upload.name.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(data)
            tmp = tf.name
        try:
            out = subprocess.run(["pdftotext", tmp, "-"], capture_output=True,
                                 text=True, timeout=120)
        except FileNotFoundError:
            st.error("`pdftotext` not found — install poppler-utils, or paste text.")
            return ""
        finally:
            os.unlink(tmp)
        return out.stdout
    return data.decode("utf-8", "replace")


def _suggest_name(upload):
    if upload and upload.name:
        stem = os.path.splitext(os.path.basename(upload.name))[0]
        return stem.replace(" ", "_")[:60] + ".md"
    return "new_paper.md"


# --- sidebar: models + library ----------------------------------------------
aliases = sorted(config.MODELS)


def _default(alias):
    return aliases.index(alias) if alias in aliases else 0


with st.sidebar:
    st.header("⚙️ Settings")
    librarian = st.selectbox("Librarian (extracts)", aliases, _default("claude_cli"))
    checker = st.selectbox("Checker (verifies)", aliases, _default("openai"))
    do_verify = st.checkbox("Cross-check the numbers", value=True)
    st.divider()
    notes = litstore.list_notes()
    st.subheader(f"📚 In library ({len(notes)})")
    for n in notes:
        st.caption(f"• {n.get('title', n['name'])}")

st.title("📚 Literature Library")
st.caption("PDF → distilled note (numbers anchored to source) → cross-checked → "
           "saved to knowledge/literature/. Always confirm the numbers + DOI.")

tab_add, tab_browse = st.tabs(["➕ Add a paper", "📖 Browse"])

with tab_add:
    col1, col2 = st.columns(2)
    upload = col1.file_uploader("Upload PDF / txt", type=["pdf", "txt"])
    pasted = col2.text_area("…or paste paper text", height=130,
                            placeholder="Paste the paper's text here")

    if st.button("🧪 Distill", type="primary"):
        text = _extract_text(upload, pasted)
        if not text.strip():
            st.warning("Give me a PDF or some text first.")
        else:
            st.session_state["src_text"] = text
            st.session_state["save_name"] = _suggest_name(upload)
            try:
                with st.spinner(f"Distilling with {librarian}…"):
                    st.session_state["draft"] = distill.distill(text, model=librarian)
                st.session_state["verify"] = None
                if do_verify:
                    with st.spinner(f"Fact-checking with {checker}…"):
                        st.session_state["verify"] = distill.verify(
                            text, st.session_state["draft"], model=checker)
            except Exception as exc:  # surface provider errors in the UI
                st.error(f"Failed: {exc}")

    if st.session_state.get("draft"):
        st.divider()
        left, right = st.columns([3, 2])
        with left:
            st.subheader("Draft note — edit before saving")
            edited = st.text_area("note", value=st.session_state["draft"],
                                  height=460, label_visibility="collapsed")
        with right:
            if st.session_state.get("verify"):
                st.subheader("🔎 Fact-check")
                st.markdown(st.session_state["verify"])
            else:
                st.info("Verify was off — confirm the numbers yourself.")
        name = st.text_input("Save as", value=st.session_state.get("save_name",
                                                                   "new_paper.md"))
        if st.button("💾 Save to library"):
            path = litstore.save(name, edited)
            st.success(f"Saved → {os.path.relpath(path, config.REPO_ROOT)}")
            for k in ("draft", "verify", "src_text"):
                st.session_state.pop(k, None)
            st.rerun()

with tab_browse:
    notes = litstore.list_notes()
    if not notes:
        st.info("No notes yet — add one in the other tab.")
    for n in notes:
        with st.expander(f"{n.get('title', n['name'])}  ·  {n['name']}"):
            tags = n.get("tags")
            if tags:
                st.caption("tags: " + ", ".join(map(str, tags)))
            st.markdown(litstore.read(n["path"]))
