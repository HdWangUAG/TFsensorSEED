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

from minicrew.core import config, distill, litstore, vision

st.set_page_config(page_title="MiniCrew · Literature", page_icon="📚", layout="wide")


def _file_text(upload):
    """Text from an uploaded file; PDFs via `pdftotext -layout` (keeps tables)."""
    if upload is None:
        return ""
    data = upload.getvalue()
    if upload.name.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(data)
            tmp = tf.name
        try:
            out = subprocess.run(["pdftotext", "-layout", tmp, "-"],
                                 capture_output=True, text=True, timeout=120)
        except FileNotFoundError:
            st.error("`pdftotext` not found — install poppler-utils, or paste text.")
            return ""
        finally:
            os.unlink(tmp)
        return out.stdout
    return data.decode("utf-8", "replace")


def _main_text(upload, pasted):
    return pasted if (pasted and pasted.strip()) else _file_text(upload)


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
    vision_model = st.selectbox("Vision (reads figures)", aliases, _default("openai"),
                                help="must be multimodal — openai/gemini/claude, "
                                     "not claude_cli")
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
    upload = col1.file_uploader("Main paper (PDF / txt)", type=["pdf", "txt"])
    si_upload = col1.file_uploader("Supplementary info (optional, PDF / txt)",
                                   type=["pdf", "txt"])
    pasted = col2.text_area("…or paste paper text", height=110,
                            placeholder="Paste the paper's text here")
    tables = col2.text_area("Paste data tables (optional)", height=110,
                            placeholder="Paste a mangled SI table here and it'll "
                                        "be transcribed into the note")

    if st.button("🧪 Distill", type="primary"):
        text = _main_text(upload, pasted)
        si_text = _file_text(si_upload)
        if not text.strip():
            st.warning("Give me a main paper (PDF or text) first.")
        else:
            source = distill.compose(text, si_text, tables)
            st.session_state["source"] = source
            st.session_state["save_name"] = _suggest_name(upload)
            try:
                with st.spinner(f"Distilling with {librarian}…"):
                    st.session_state["draft"] = distill.distill(source, model=librarian)
                st.session_state["verify"] = None
                if do_verify:
                    with st.spinner(f"Fact-checking with {checker}…"):
                        st.session_state["verify"] = distill.verify(
                            source, st.session_state["draft"], model=checker)
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
            st.subheader("💬 Refine by chat")
            st.caption("Tell the librarian what to change — it re-reads the "
                       "source (main + SI + tables), never invents.")
            with st.form("refine", clear_on_submit=True):
                instruction = st.text_input(
                    "instruction", label_visibility="collapsed",
                    placeholder="e.g. add the dose-response from SI Table 3; "
                                "fix the space group; pull the full mutant panel")
                apply = st.form_submit_button("Apply ✦")
            if apply and instruction.strip():
                try:
                    with st.spinner(f"Revising with {librarian}…"):
                        st.session_state["draft"] = distill.refine(
                            st.session_state["source"], edited, instruction,
                            model=librarian)
                    st.session_state.setdefault("history", []).append(instruction)
                    st.session_state["verify"] = None
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed: {exc}")
            if st.session_state.get("history"):
                st.caption("✓ applied: " + " · ".join(st.session_state["history"]))

            with st.expander("📊 Figure / table data (vision)"):
                if upload and upload.name.lower().endswith(".pdf"):
                    pg = st.text_input("pages (e.g. 3 or 2-4)", value="",
                                       key="fig_pages")
                    if st.button(f"Extract with {vision_model}"):
                        try:
                            with tempfile.NamedTemporaryFile(suffix=".pdf",
                                                             delete=False) as tf:
                                tf.write(upload.getvalue())
                                tmp = tf.name
                            with st.spinner("Reading figures/tables…"):
                                data = vision.extract(tmp, pages=pg or None,
                                                      model=vision_model)
                            os.unlink(tmp)
                            st.session_state["draft"] = edited + "\n\n" + data
                            st.session_state["verify"] = None
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed: {exc}")
                    st.caption("Appends vision-extracted data to the note — "
                               "plot-read numbers are flagged APPROXIMATE.")
                else:
                    st.caption("Upload a PDF as the main paper to enable vision.")

            st.divider()
            if st.session_state.get("verify"):
                st.markdown("**🔎 Fact-check**")
                st.markdown(st.session_state["verify"])

        name = st.text_input("Save as", value=st.session_state.get("save_name",
                                                                   "new_paper.md"))
        c1, c2 = st.columns(2)
        if c1.button("💾 Save to library"):
            path = litstore.save(name, edited)
            st.success(f"Saved → {os.path.relpath(path, config.REPO_ROOT)}")
            for k in ("draft", "verify", "source", "history"):
                st.session_state.pop(k, None)
            st.rerun()
        if c2.button("🔎 Re-verify numbers"):
            try:
                with st.spinner(f"Fact-checking with {checker}…"):
                    st.session_state["verify"] = distill.verify(
                        st.session_state["source"], edited, model=checker)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed: {exc}")

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
