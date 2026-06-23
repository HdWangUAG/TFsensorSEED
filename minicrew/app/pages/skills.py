"""Skills — browse and run the lab's computational skills (PyMOL, flex-ddG, RDKit, …)."""
import os

import streamlit as st

from minicrew.core import skills

st.title("🛠️ Skills — runnable scientific tools")
st.caption("Capabilities agents can run inside a crew (via the tool-request "
           "protocol) — or that you can run ad-hoc here. Each returns a "
           "standardized, provenanced result (result + artifacts + provenance).")

SK = skills.SKILLS
names = sorted(SK)

st.subheader(f"{len(names)} registered skills")
for n in names:
    s = SK[n]
    req = s.requires or {}
    badges = []
    if req.get("conda_env"):
        badges.append(f"env:{req['conda_env']}")
    if req.get("binaries"):
        badges.append("bin:" + ",".join(req["binaries"]))
    if req.get("allow_network"):
        badges.append("network")
    if req.get("max_runtime_seconds", 0) and req["max_runtime_seconds"] >= 600:
        badges.append("⏳ long-running")
    ok_pre, msg = s.preflight()
    status = "✅" if ok_pre else "⚠️"
    with st.expander(f"{status} **{n}** — {s.description[:90]}…"):
        st.markdown(s.description)
        if badges:
            st.caption("requires: " + "  ·  ".join(badges))
        if not ok_pre:
            st.warning(f"preflight: {msg}")
        props = (s.parameters or {}).get("properties", {})
        required = set((s.parameters or {}).get("required", []))
        if props:
            st.markdown("**Args:**")
            for k, p in props.items():
                tag = "required" if k in required else "optional"
                st.caption(f"- `{k}` ({p.get('type', 'string')}, {tag})"
                           + (f" — {p['description']}" if p.get("description") else ""))

st.divider()
st.subheader("Run a skill")
sel = st.selectbox("Skill", names)
s = SK[sel]
props = (s.parameters or {}).get("properties", {})
required = set((s.parameters or {}).get("required", []))

args, arg_err = {}, False
for k, p in props.items():
    label = f"{k}{' *' if k in required else ''}"
    help_ = p.get("description", "")
    raw = st.text_input(label, key=f"arg_{sel}_{k}", help=help_,
                        placeholder=help_[:60])
    if raw.strip():
        if p.get("type") == "number":
            try:
                args[k] = float(raw)
            except ValueError:
                st.error(f"`{k}` must be a number")
                arg_err = True
        else:
            args[k] = raw.strip()

if st.button("▶ Run skill", type="primary", disabled=arg_err):
    with st.spinner(f"running {sel} …"):
        res = skills.call(sel, **args)
    if res.get("ok"):
        prov = res.get("provenance", {})
        st.success(f"{sel} ok · {prov.get('runtime_seconds', '?')}s · run {prov.get('run_id', '')}")
        result = res.get("result") or {}
        st.json(result)
        shown = False
        for a in res.get("artifacts", []):
            if a.get("type") == "image" and a.get("uri") and os.path.exists(a["uri"]):
                st.image(a["uri"], caption=a.get("caption", ""))
                shown = True
        img = result.get("image") if isinstance(result, dict) else None
        if img and not shown and os.path.exists(img):
            st.image(img)
        if res.get("warnings"):
            st.warning("⚠️ " + "  ·  ".join(res["warnings"]))
        with st.expander("provenance + raw SkillResult"):
            st.json({k: v for k, v in res.items() if k != "result"})
    else:
        st.error(res.get("error", "skill failed"))
        if res.get("stderr_tail"):
            st.code(res["stderr_tail"][-1000:])
