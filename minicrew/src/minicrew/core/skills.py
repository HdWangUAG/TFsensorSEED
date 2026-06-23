"""Skill framework — registrable, validated, auditable scientific capabilities.

A *skill* is a tool an agent can run (PyMOL, flex-ddG, RDKit, …) that returns a
**standardized SkillResult**, because in a co-scientist a tool output is
*computational evidence*, not chat text — it must be traceable and recallable.

SkillResult (the contract every skill returns):

    {"ok": bool, "skill": str,
     "result": {...},                       # the science (summary + metrics)
     "artifacts": [{"type","uri","caption"}],# files produced (images, json, …)
     "provenance": {"skill_version","run_id","command","conda_env","binary",
                    "runtime_seconds","timestamp","input_files","output_files"},
     "warnings": [...], "stderr_tail": str, "error": str | None}

Security boundary (we run real subprocesses): each skill declares `requires`
(conda_env / binaries / max_runtime_seconds / allow_* / allowed_input_roots /
allowed_output_root). Enforcement here: never `shell=True`; input paths are
normalized + confined to the repo (no `../` escape); a hard timeout; stdout/
stderr captured + truncated; failures return a structured result, never raise
raw text into an agent.

Skills are defined as plain functions wrapped by the ``@skill`` decorator, so the
existing tool functions migrate with almost no churn. `tools.py` stays a thin
compat shim (REGISTRY + openai_schemas) generated from SKILLS, so the CLI + chat
page keep working unchanged; the rich SkillResult is exposed via ``call()``.
"""
from __future__ import annotations

import contextvars
import datetime
import os
import subprocess
import threading
import time

from . import config

# ---------------------------------------------------------------------------
# Skill control (skills/skills.yaml) — timeouts, heavy budget, enable/disable
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(config.MINICREW_DIR, "skills", "skills.yaml")


def _load_config():
    try:
        import yaml
        with open(_CONFIG_PATH) as fh:
            cfg = yaml.safe_load(fh) or {}
    except Exception:
        cfg = {}
    cfg.setdefault("defaults", {})
    cfg.setdefault("skills", {})
    d = cfg["defaults"]
    d.setdefault("heavy_runtime_s", 600)
    d.setdefault("heavy_budget", 4)
    d.setdefault("grace_s", 20)
    d.setdefault("inprocess_default_s", 120)
    return cfg


CONFIG = _load_config()
# the timeout of the skill currently running — subprocess calls inherit it so a
# skill's run_subprocess() without an explicit timeout uses its configured budget.
_CURRENT_TIMEOUT = contextvars.ContextVar("skill_timeout", default=None)


def skill_timeout(name, requires=None):
    """Resolved wall-clock budget (s): skills.yaml > requires.max_runtime_seconds > default."""
    sc = CONFIG["skills"].get(name) or {}
    if sc.get("timeout_s"):
        return int(sc["timeout_s"])
    if requires and requires.get("max_runtime_seconds"):
        return int(requires["max_runtime_seconds"])
    return int(CONFIG["defaults"]["inprocess_default_s"])


def skill_enabled(name):
    return bool((CONFIG["skills"].get(name) or {}).get("enabled", True))


def is_heavy(name):
    s = SKILLS.get(name)
    if not s:
        return False
    return skill_timeout(name, s.requires) >= CONFIG["defaults"]["heavy_runtime_s"]


def heavy_budget():
    return int(CONFIG["defaults"]["heavy_budget"])


# ---------------------------------------------------------------------------
# SkillResult helpers
# ---------------------------------------------------------------------------

def make_result(skill, *, ok=True, result=None, artifacts=None, provenance=None,
                warnings=None, stderr_tail="", error=None):
    """Build a standardized SkillResult dict."""
    return {"ok": bool(ok), "skill": skill, "result": result or {},
            "artifacts": artifacts or [], "provenance": provenance or {},
            "warnings": warnings or [], "stderr_tail": stderr_tail or "",
            "error": error}


def to_legacy(res):
    """Old plain-dict shape for the CLI / chat compat path (zero behavior change).

    Success → the `result` payload verbatim (still carries e.g. an `image` key);
    failure → `{"error": ...}` exactly as the old tools returned.
    """
    if not res.get("ok"):
        return {"error": res.get("error") or "skill failed"}
    return res.get("result") or {}


def compact(res, max_len=600):
    """One-block, transcript-safe summary of a SkillResult (no big JSON/stdout).

    Used when folding a tool run into a crew transcript — the full result lives
    in the artifact, only this digest goes into the prompt.
    """
    head = f"[skill {res['skill']} | {'ok' if res['ok'] else 'FAILED'}]"
    if not res["ok"]:
        return f"{head}\nerror: {res.get('error')}"
    r = res.get("result") or {}
    summary = r.get("summary")
    metrics = r.get("metrics") or {k: v for k, v in r.items()
                                    if isinstance(v, (int, float, str)) and k != "summary"}
    lines = [head]
    if summary:
        lines.append(f"summary: {summary}")
    if metrics:
        kv = ", ".join(f"{k}={v}" for k, v in list(metrics.items())[:8])
        lines.append(f"metrics: {kv}")
    if res.get("warnings"):
        lines.append("warnings: " + "; ".join(res["warnings"][:3]))
    for a in res.get("artifacts", [])[:4]:
        lines.append(f"artifact: {a.get('type')} {a.get('uri')}")
    prov = res.get("provenance") or {}
    if prov.get("run_id"):
        lines.append(f"run_id: {prov['run_id']}  runtime_s: {prov.get('runtime_seconds')}")
    out = "\n".join(lines)
    return out if len(out) <= max_len else out[:max_len] + " …"


# ---------------------------------------------------------------------------
# Security helpers (used by path-taking skills)
# ---------------------------------------------------------------------------

def safe_input_path(path, allowed_roots=None):
    """Resolve a repo-relative-or-absolute input path, confined to the repo.

    Rejects traversal that escapes REPO_ROOT (the key safety win). If
    `allowed_roots` is given, also require the path's top-level dir to be one of
    them. Returns (abspath, None) or (None, error_message).
    """
    if not isinstance(path, str) or not path.strip():
        return None, "empty path"
    p = path if os.path.isabs(path) else os.path.join(config.REPO_ROOT, path)
    rp = os.path.realpath(p)
    root = os.path.realpath(config.REPO_ROOT)
    try:
        if os.path.commonpath([rp, root]) != root:
            return None, f"path escapes repo root: {path}"
    except ValueError:
        return None, f"invalid path: {path}"
    if allowed_roots:
        top = os.path.relpath(rp, root).split(os.sep)[0]
        if top not in allowed_roots:
            return None, f"path not under allowed roots {allowed_roots}: {path}"
    return rp, None


def run_id():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def conda_python(env):
    """Absolute python for a conda env name (or an explicit abs path passed through)."""
    if env and os.path.isabs(env):
        return env
    return os.path.expanduser(f"~/.conda/envs/{env}/bin/python")


def run_subprocess(cmd, *, timeout=None, cwd=None, env_extra=None, stderr_tail=4000):
    """Run a command (list, never shell=True). Returns dict with rc/stdout/
    stderr_tail/runtime. Raises nothing — callers wrap into SkillResult.

    `timeout=None` inherits the running skill's configured budget (the single
    source of truth) so a one-step skill needn't restate it; multi-step skills
    pass explicit per-step sub-budgets."""
    if not isinstance(cmd, (list, tuple)):
        raise ValueError("cmd must be a list (shell=True is forbidden)")
    if timeout is None:
        timeout = _CURRENT_TIMEOUT.get() or 180
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    try:
        proc = subprocess.run(list(cmd), capture_output=True, text=True,
                              timeout=timeout, cwd=cwd, env=env)
        return {"rc": proc.returncode, "stdout": proc.stdout or "",
                "stderr_tail": (proc.stderr or "")[-stderr_tail:],
                "runtime_seconds": round(time.time() - t0, 2), "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"rc": -1, "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr_tail": f"TIMEOUT after {timeout}s",
                "runtime_seconds": round(time.time() - t0, 2), "timed_out": True}


# ---------------------------------------------------------------------------
# Skill base + registry
# ---------------------------------------------------------------------------

SKILLS = {}


class Skill:
    """A registrable capability. Subclass or use the @skill decorator on a fn."""

    name = ""
    description = ""
    parameters = {"type": "object", "properties": {}, "required": []}
    requires = {}            # conda_env, binaries, max_runtime_seconds, allow_*, allowed_*_roots
    version = "0.1.0"

    def _impl(self, **kwargs):
        raise NotImplementedError

    # -- validation / preflight --------------------------------------------
    def validate_args(self, kwargs):
        props = self.parameters.get("properties", {})
        required = self.parameters.get("required", [])
        missing = [r for r in required if r not in kwargs or kwargs[r] in (None, "")]
        if missing:
            return False, f"missing required args: {missing}"
        unknown = [k for k in kwargs if k not in props]
        if unknown:
            return False, f"unknown args: {unknown} (allowed: {list(props)})"
        return True, ""

    def preflight(self):
        """Check declared binaries / conda env exist before running."""
        req = self.requires or {}
        env = req.get("conda_env")
        if env:
            py = conda_python(env)
            if not os.path.exists(py):
                return False, f"conda env {env!r} not found ({py}); set it up or fix MINICREW"
        for b in req.get("binaries", []):
            path = config.get(f"MINICREW_{b.upper()}_BIN", "") or _which_in_env(b, env)
            if not path or not os.path.exists(path):
                return False, f"required binary {b!r} not found (set MINICREW_{b.upper()}_BIN)"
        return True, ""

    # -- run wrapper -------------------------------------------------------
    def run(self, **kwargs):
        if not skill_enabled(self.name):
            return make_result(self.name, ok=False, error="skill disabled in skills/skills.yaml")
        ok, err = self.validate_args(kwargs)
        if not ok:
            return make_result(self.name, ok=False, error=f"invalid args: {err}")
        ok, err = self.preflight()
        if not ok:
            return make_result(self.name, ok=False, error=f"preflight failed: {err}")
        rid = run_id()
        timeout = skill_timeout(self.name, self.requires)
        grace = int(CONFIG["defaults"]["grace_s"])
        t0 = time.time()
        # Run the impl with the skill's timeout in context (subprocess calls inherit
        # it) AND under a wall-clock watchdog thread, so even an in-process skill
        # (RDKit/XGBoost) can't hang the app past its budget.
        _CURRENT_TIMEOUT.set(timeout)
        ctx = contextvars.copy_context()
        box = {}

        def _worker():
            try:
                box["raw"] = self._impl(**kwargs)
            except Exception as exc:
                box["exc"] = exc

        th = threading.Thread(target=lambda: ctx.run(_worker), daemon=True)
        th.start()
        th.join(timeout + grace)
        prov0 = {"skill_version": self.version, "run_id": rid,
                 "runtime_seconds": round(time.time() - t0, 2), "timestamp": _now(),
                 "conda_env": (self.requires or {}).get("conda_env")}
        if th.is_alive():                              # blew the wall budget
            return make_result(self.name, ok=False,
                               error=f"timed out after {timeout}s (wall budget)",
                               provenance=prov0)
        if "exc" in box:                               # never leak a raw traceback
            exc = box["exc"]
            return make_result(self.name, ok=False,
                               error=f"{type(exc).__name__}: {exc}", provenance=prov0)
        raw = box.get("raw")
        prov = dict(prov0)
        if isinstance(raw, dict):
            prov.update(raw.pop("_provenance", {}) or {})
            stderr = raw.pop("_stderr_tail", "")
            warnings = raw.pop("_warnings", []) or []
            if raw.get("error"):
                return make_result(self.name, ok=False, error=raw["error"],
                                   provenance=prov, stderr_tail=stderr or raw.get("stderr", ""))
            artifacts = list(raw.pop("_artifacts", []) or [])
            if raw.get("image"):                       # legacy single-image convention
                artifacts.append({"type": "image", "uri": raw["image"], "caption": self.name})
            return make_result(self.name, ok=True, result=raw, artifacts=artifacts,
                               provenance=prov, warnings=warnings, stderr_tail=stderr)
        return make_result(self.name, ok=True, result={"value": raw}, provenance=prov)

    def to_openai_schema(self):
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.parameters}}


class _FnSkill(Skill):
    def __init__(self, name, description, parameters, requires, version, fn):
        self.name, self.description = name, description
        self.parameters = parameters or {"type": "object", "properties": {}, "required": []}
        self.requires, self.version, self._fn = requires or {}, version, fn

    def _impl(self, **kwargs):
        return self._fn(**kwargs)


def skill(name, description, parameters=None, requires=None, version="0.1.0"):
    """Decorator: register a plain function as a Skill. The function returns the
    legacy plain dict (success payload, possibly with an `image`, or `{"error":}`);
    the framework wraps it into a SkillResult."""
    def deco(fn):
        SKILLS[name] = _FnSkill(name, description, parameters, requires, version, fn)
        return fn
    return deco


def register(skill_obj):
    SKILLS[skill_obj.name] = skill_obj
    return skill_obj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call(name, **kwargs):
    """Run a skill by name → SkillResult (the rich path, for crews)."""
    if name not in SKILLS:
        return make_result(name, ok=False, error=f"unknown skill {name!r}; "
                           f"known: {sorted(SKILLS)}")
    return SKILLS[name].run(**kwargs)


def list_skills():
    return {n: {"description": s.description, "requires": s.requires}
            for n, s in sorted(SKILLS.items())}


def openai_schemas(names=None):
    """Tool list in OpenAI function-calling format (for toolcall.run). Disabled
    skills are excluded so agents can't request them."""
    names = names or list(SKILLS)
    return [SKILLS[n].to_openai_schema() for n in names
            if n in SKILLS and skill_enabled(n)]


# Skills grouped by engine → one folder per group, each with a `<group>_skill.md`
# doc + its processing scripts. (group: (title, [skill names]))
SKILL_GROUPS = {
    "pyrosetta": ("PyRosetta — flex-ddG energetics & mutation threading",
                  ["flexddg_score", "retrodict"]),
    "pymol": ("PyMOL — structural rendering & pocket analysis",
              ["analyze_structure", "pocket_mutation_view"]),
    "boltz": ("Boltz-2 — co-folding pose & binding", ["boltz_compare"]),
    "cheminformatics": ("RDKit / ProLIF — ligand & interaction analysis",
                        ["ligand_descriptors", "ligand_similarity",
                         "interaction_fingerprint"]),
    "ml": ("ML — predictive models", ["train_model"]),
    "literature": ("Literature — web retrieval", ["literature_search"]),
}


def _skill_doc(n):
    s = SKILLS[n]
    req = s.requires or {}
    out = [f"### `{n}`", s.description]
    badges = []
    if req.get("conda_env"):
        badges.append(f"conda env `{req['conda_env']}`")
    if req.get("binaries"):
        badges.append("binaries " + ", ".join(f"`{b}`" for b in req["binaries"]))
    if req.get("allow_network"):
        badges.append("network")
    if req.get("max_runtime_seconds", 0) >= 600:
        badges.append(f"⏳ long-running (≤{req['max_runtime_seconds']}s)")
    if badges:
        out.append("- **requires:** " + " · ".join(badges))
    props = (s.parameters or {}).get("properties", {})
    required = set((s.parameters or {}).get("required", []))
    if props:
        out.append("- **args:**")
        for k, p in props.items():
            tag = "required" if k in required else "optional"
            out.append(f"  - `{k}` ({p.get('type', 'string')}, {tag})"
                       + (f" — {p['description']}" if p.get("description") else ""))
    out.append("")
    return "\n".join(out)


def _group_md(group):
    import glob as _glob
    title, names = SKILL_GROUPS[group]
    names = [n for n in names if n in SKILLS]
    out = [f"# {group} skills", "", title, "",
           "_Auto-generated (`minicrew skills --write`). Skills are defined in "
           "`src/minicrew/core/skills_impl.py`; standalone processing scripts live "
           "in this folder._", ""]
    scripts = sorted(os.path.basename(p) for p in _glob.glob(
        os.path.join(config.MINICREW_DIR, "skills", group, "*.py")))
    if scripts:
        out += ["**Processing scripts in this folder:** "
                + ", ".join(f"`{s}`" for s in scripts), ""]
    for n in names:
        out.append(_skill_doc(n))
    return "\n".join(out)


def catalog_markdown():
    """Top-level skills/ index — links to each per-engine group doc."""
    lines = ["# MiniCrew skills", "",
             f"{len(SKILLS)} runnable skills, grouped by engine. Each group has its "
             "own folder with a `<group>_skill.md` doc + processing scripts. Skills "
             "are defined in `src/minicrew/core/skills_impl.py` (`@skill`); run them "
             "on the **🛠️ Skills** page or via the crew tool-request protocol.", "",
             "_Regenerate: `minicrew skills --write`._", ""]
    grouped = set()
    for g, (title, names) in SKILL_GROUPS.items():
        have = [n for n in names if n in SKILLS]
        if not have:
            continue
        grouped.update(have)
        lines.append(f"- **[`{g}/`]({g}/{g}_skill.md)** — {title}: "
                     + ", ".join(f"`{n}`" for n in have))
    ung = [n for n in sorted(SKILLS) if n not in grouped]
    if ung:
        lines.append("- **(ungrouped)**: " + ", ".join(f"`{n}`" for n in ung))
    lines.append("")
    return "\n".join(lines)


def write_catalog(base=None):
    """Write the top index + one <group>/<group>_skill.md per engine group."""
    base = base or os.path.join(config.MINICREW_DIR, "skills")
    os.makedirs(base, exist_ok=True)
    written = [os.path.join(base, "README.md")]
    open(written[0], "w", encoding="utf-8").write(catalog_markdown())
    for g in SKILL_GROUPS:
        if not [n for n in SKILL_GROUPS[g][1] if n in SKILLS]:
            continue
        d = os.path.join(base, g)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{g}_skill.md")
        open(p, "w", encoding="utf-8").write(_group_md(g))
        written.append(p)
    return written


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _which_in_env(binary, env):
    if env:
        cand = os.path.expanduser(f"~/.conda/envs/{env}/bin/{binary}")
        if os.path.exists(cand):
            return cand
    from shutil import which
    return which(binary) or ""


# Import the skill modules so they self-register on `import skills`.
from . import skills_impl as _impl_pkg  # noqa: E402,F401
