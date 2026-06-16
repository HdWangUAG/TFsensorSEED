---
name: tfsensor-pyrosetta-init-once-per-process
description: "PyRosetta init is one-shot per process — loop ligand dG scoring via subprocess, not in-process"
metadata: 
  node_type: memory
  type: reference
  originSessionId: a8b6a708-ed73-43fe-b948-ff262bc39f09
---

In the LC-Seed pyrosetta venv (`~/LC-Seed/envs/pyrosetta/.venv`, PyRosetta 2026.21), `pyrosetta.init()` takes effect only **once per process**. Calling it again to register a different ligand's `-extra_res_fa` params is silently ignored, so every ligand after the first becomes an "Unrecognized residue" error.

**How to apply:** when scoring multiple ligands (e.g. a steroid panel through `tfsensor.physics_score.interface_dg`), run each ligand in a **fresh subprocess** rather than looping in one process. `tfsensor/physics_panel.py` does this via `_dg_subprocess` calling `python -m tfsensor.physics_score ... --out_json`. Also: `molfile_to_params` runs with `cwd=work_dir` and resolves the `.mol` path against it, so pass **absolute** work dirs. And `AddConstraintsToCurrentConformationMover.use_distance_cst` is now a read-only getter (default False = CA coordinate constraints) — don't call it as a setter. Related: [[tfsensor-stage1-triple-nogo]].
