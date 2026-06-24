> **STATUS: COMPLETED (2026-06-24).** This migration has been carried out —
> `prompts/tools/` is removed, the UI/docs reference persona agents + skills, and
> the checks below pass. Kept as a historical record of the change.

Goal: cleanly remove MiniCrew's legacy `prompts/tools/` concept and make `skills/` the single source of truth for runnable tools.

  Important context:
  - MiniCrew is moving away from "tool agents as prompt files".
  - Real computational capabilities should be managed by:
    - `minicrew/src/minicrew/core/skills.py`
    - `minicrew/src/minicrew/core/skills_impl.py`
    - `minicrew/skills/skills.yaml`
    - `minicrew/skills/<group>/<group>_skill.md`
  - Persona prompts should stay in:
    - `minicrew/prompts/personas/`
  - `prompts/tools/` is legacy roadmap material and should be removed.
  - Do not remove or weaken the existing `skills` framework.
  - Do not rewrite MiniCrew broadly. Make a focused cleanup.

  Before editing:
  1. Run:
     ```bash
     git status --short
     git diff -- minicrew
     rg -n "prompts/tools|tool agent|tool agents|pyrosetta_runner|pymol_structural|TOOL AGENT" minicrew README.md docs scripts

  2. Note that there may already be partial local edits. Preserve unrelated work.

  Required changes:

  1. Remove the legacy directory:

     minicrew/prompts/tools/
     Specifically delete:

     minicrew/prompts/tools/README.md
     minicrew/prompts/tools/pymol_structural.md
     minicrew/prompts/tools/pyrosetta_runner.md
     minicrew/prompts/tools/pyrosetta_runner.md

  2. Update minicrew/src/minicrew/core/agents.py
      - It should only manage persona agents from prompts/personas/.
      - Remove "tool": os.path.join(config.PROMPTS_DIR, "tools") from DIRS.
      - Update the module docstring to say:
          - agents are persona/viewpoint prompt files;
          - runnable tools are managed as skills, not prompt files;
          - see core/skills.py, core/skills_impl.py, and minicrew/skills/.

      - Keep existing functions compatible for persona agents:
          - split_frontmatter
          - list_agents
          - get
          - save
          - delete

      - It is acceptable for get/save/delete(kind="tool", ...) to stop being a supported path, but avoid confusing KeyErrors in the UI by removing UI access to tool
        kind.

  3. Update minicrew/app/pages/agents.py
      - Change the page from "knowledge & tool agents" to "persona agents".
      - Remove the "Type" selector with ["persona", "tool"].
      - Always save as kind = "persona".
      - List only agents.list_agents("persona").
      - Update help text/caption to say computational capabilities are managed in the Skills page.
      - Keep create/edit/delete behavior for persona prompts working.

  4. Update minicrew/app/Home.py
      - Stop counting agents.list_agents("tool").
      - Replace "Tool agents" metric with "Skills", using len(skills.SKILLS).
      - Import skills if needed.
      - Update section text:
          - Agents = create/edit/delete persona agents.
          - Skills = browse/run computational skills.

      - In "Your agents", list only personas.

  5. Update documentation references:
      - minicrew/README.md
          - Remove prompts/tools/ from the layout.
          - Add or keep skills/ as the place for runnable tools.
          - Change "knowledge & tool agents" wording to "persona agents".

      - minicrew/docs/MINICREW_STRUCTURE.md
          - Ensure it clearly says:

            prompts/personas/ = scientific viewpoints
            skills/ = runnable tools and capability docs
            prompts/tools/ has been removed

      - Do not spend time rewriting agent_updating_plan.md unless it is actively misleading and tracked. If it is an old planning artifact, a small note saying it
        predates the skills migration is enough.

  6. Validate references:
     After edits, this should return no active-code references to the removed directory:

     rg -n "prompts/tools|pyrosetta_runner|pymol_structural|TOOL AGENT" minicrew README.md docs scripts

     If old planning docs still mention it, either update them or explicitly mark those sections as historical.

  7. Run checks:

     minicrew/.venv/bin/python -m compileall -q minicrew/src minicrew/app minicrew/tests
     minicrew/.venv/bin/python -m unittest discover -s minicrew/tests
     scripts/minicrew list
     scripts/minicrew skills

     If sandboxing blocks venv Python, explain that and rerun outside sandbox if available.

  Acceptance criteria:

  - minicrew/prompts/tools/ no longer exists.
  - MiniCrew UI no longer exposes "tool agents" as editable prompt files.
  - Persona agents still load from minicrew/prompts/personas/.
  - Skills remain visible through the Skills page and scripts/minicrew skills.
  - No code path depends on prompts/tools/.
  - Docs reflect the new boundary:
      - persona prompt = role/viewpoint;
      - skill = real runnable tool capability.

  - Tests/compile checks pass, or any failure is clearly reported with cause.

  Also check for the small existing CLI issue if you touch nearby code:

  - PromptBudgetError currently may print an error but still return exit code 0 from CLI.
  - If easy, make prompt-budget abort return nonzero.
  - Do not let this distract from the main prompts/tools cleanup.