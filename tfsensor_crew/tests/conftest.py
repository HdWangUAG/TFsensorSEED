import sys
import pytest
from pathlib import Path

# Add src/ directory to python path for testing
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

@pytest.fixture
def mock_progress_content():
    return """# TFsensorSEED — progress ledger

## Established conclusions (trust these)
- WT is a 4-en-3-one sensor.

## Campaign status

| Campaign | Stage | State | Key output | Leads / finding |
|---|---|---|---|---|
| Estradiol | full | done | results/stage3_design/STAGE3_SUMMARY.md | 65 designs; 0/20 pass gate |
| **Testosterone** (D-ring) | gen+screen+gate+validate | done | results/stage3_dring/validate/VALIDATE_SUMMARY.md | des0039, des0044 |
| Testosterone 2-ligand gate | gate (all 71) | **done** (Alpha) | results/stage3_dring/gate2lig/gate2lig.json | 58/71 pass |
| FEP demo (L147R×cortisol) | Tier-2 | done | results/stage3_fep/proto_l147r_cortisol/FEP_DEMO_RESULTS.md | ddG -8.6 kJ/mol |
| E106L specificity FEP | Tier-2 | done | results/stage3_fep/e106l_specificity/SPECIFICITY_RESULTS.md | converged |
| **Progesterone** | gen+screen | **reassigned → Aspartate** | results/stage3_prog/ | design: C20=O bias |
| **Cortisol** | gen+screen | **reassigned → Aspartate** | results/stage3_cort/ | design: R123E anchor |
| **Estradiol** (re-screen) | gen+screen | **assigned → Aspartate** | results/stage3_estradiol/ | phenol clamp |

## Next actions
- [ ] (Alpha) finish testosterone 2-ligand gate → compare vs 1-ligand
- [ ] (Aspartate) prog/cort/estradiol gen+screen
- [ ] (Alpha or Aspartate) prog/cort 2-ligand gate on leads
- [ ] (Beta) build ligand-ligand RBFE executor for the test/prog/cort triad
- [ ] (Beta) consider per-position LigandMPNN bias
"""

@pytest.fixture
def mock_registry_content():
    return """Task_ID,Task_Type,Assigned_Node,Status,Target_Ligand,Batch_File,Start_Time,Completion_Time,Notes
fep_demo_l147r,rbfe,Node-Alpha,DONE,Cortisol,-,2026-06-15,2026-06-15,results/stage3_fep/proto_l147r_cortisol/FEP_DEMO_RESULTS.md
fep_e106l_spec,rbfe,Node-Alpha,DONE,multi,-,2026-06-16,2026-06-16,results/stage3_fep/e106l_specificity/SPECIFICITY_RESULTS.md
gate2lig_testosterone,boltz-2lig-gate,Node-Alpha,DONE,Testosterone,-,2026-06-16,2026-06-16,results/stage3_dring/gate2lig/gate2lig.json
gen_screen_prog,gen+flexddG,Node-Aspartate,REASSIGNED,Progesterone,-,-,-,results/stage3_prog/
gen_screen_cort,gen+flexddG,Node-Aspartate,REASSIGNED,Cortisol,-,-,-,results/stage3_cort/
gen_screen_estradiol,gen+flexddG,Node-Aspartate,PENDING,Estradiol,-,-,-,results/stage3_estradiol/
progcort_2lig_gate,boltz-2lig-gate,Node-Aspartate,PENDING,Progesterone/Cortisol,-,-,-,run on screen leads
ligand_rbfe_triad,ligand-rbfe,Node-Beta,PENDING,test/prog/cort,-,-,-,DEV build dDDG
"""

@pytest.fixture
def temp_progress_file(tmp_path, mock_progress_content):
    p = tmp_path / "PROGRESS.md"
    p.write_text(mock_progress_content, encoding='utf-8')
    return p

@pytest.fixture
def temp_registry_file(tmp_path, mock_registry_content):
    r = tmp_path / "JOBS_REGISTRY.csv"
    r.write_text(mock_registry_content, encoding='utf-8')
    return r

@pytest.fixture
def temp_output_file(tmp_path):
    return tmp_path / "sync_report.md"
