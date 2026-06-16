import pytest
import pandas as pd
from tfsensor_crew.parser import (
    parse_progress_markdown,
    parse_jobs_registry_csv,
    SyncAnalyzer
)

def test_multiple_tables_leak():
    """
    BUG: If a table with 5 columns exists before the Campaign status table in PROGRESS.md,
    its rows are incorrectly parsed as campaigns.
    """
    progress_content = """# PROGRESS
## Miscellaneous Data
| Col1 | Col2 | Col3 | Col4 | Col5 |
|---|---|---|---|---|
| Val1 | Val2 | Val3 | Val4 | Val5 |

## Campaign status
| Campaign | Stage | State | Key output | Leads / finding |
|---|---|---|---|---|
| Cortisol | gen+screen | reassigned | results/stage3_cort/ | R123E |
"""
    campaigns, next_actions = parse_progress_markdown(progress_content)
    # The parser should only parse the 'Campaign status' table.
    assert len(campaigns) == 1
    assert campaigns[0]['campaign'] == 'Cortisol'

def test_jobs_registry_nan_status():
    """
    BUG: If a status column has NaN/empty values, SyncAnalyzer raises AttributeError: 'float' object has no attribute 'lower'.
    """
    csv_content = "Task_ID,Task_Type,Assigned_Node,Status,Target_Ligand,Notes\njob1,rbfe,Node-Alpha,,Cortisol,results/stage3_cort/\n"
    campaigns = [{'campaign': 'Cortisol', 'stage': 'gen', 'state': 'reassigned', 'key_output': 'results/stage3_cort/', 'leads_finding': ''}]
    jobs = parse_jobs_registry_csv(csv_content)
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    try:
        analysis = analyzer.analyze()
    except AttributeError as e:
        pytest.fail(f"SyncAnalyzer raised AttributeError due to NaN Status: {e}")

def test_jobs_registry_nan_notes():
    """
    BUG: If Notes column contains NaN/empty values, SyncAnalyzer raises TypeError: argument of type 'float' is not iterable.
    """
    csv_content = "Task_ID,Task_Type,Assigned_Node,Status,Target_Ligand,Notes\njob1,rbfe,Node-Alpha,DONE,Cortisol,\n"
    campaigns = [{'campaign': 'Cortisol', 'stage': 'gen', 'state': 'done', 'key_output': 'results/stage3_cort/', 'leads_finding': ''}]
    jobs = parse_jobs_registry_csv(csv_content)
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    try:
        analysis = analyzer.analyze()
    except TypeError as e:
        pytest.fail(f"SyncAnalyzer raised TypeError due to NaN Notes: {e}")

def test_jobs_registry_missing_status():
    """
    BUG: If the Status column is completely missing from the CSV, SyncAnalyzer raises KeyError.
    """
    csv_content = "Task_ID,Task_Type,Assigned_Node,Target_Ligand,Notes\njob1,rbfe,Node-Alpha,Cortisol,results/stage3_cort/\n"
    campaigns = [{'campaign': 'Cortisol', 'stage': 'gen', 'state': 'reassigned', 'key_output': 'results/stage3_cort/', 'leads_finding': ''}]
    jobs = parse_jobs_registry_csv(csv_content)
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    try:
        analysis = analyzer.analyze()
    except KeyError as e:
        pytest.fail(f"SyncAnalyzer raised KeyError due to missing Status column: {e}")

def test_greedy_path_matching():
    """
    BUG: A generic key_output like 'results/' matching any job with 'results/' in notes.
    """
    campaigns = [
        {'campaign': 'Prog', 'stage': 'gen', 'state': 'done', 'key_output': 'results/', 'leads_finding': ''}
    ]
    jobs = [
        {'Task_ID': 'job_cort', 'Target_Ligand': 'Cortisol', 'Status': 'DONE', 'Notes': 'results/stage3_cort/'}
    ]
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    analysis = analyzer.analyze()
    # The Prog campaign should NOT match job_cort because 'results/' is too generic.
    assert len(analysis['matched']) == 0

def test_escaped_pipes():
    """
    BUG: Escaped pipes in markdown table columns are split, leading to invalid parsing.
    """
    progress_content = """# PROGRESS
## Campaign status
| Campaign | Stage | State | Key output | Leads / finding |
|---|---|---|---|---|
| Cortisol | gen+screen | reassigned | results/stage3_cort/ | R123E \\| anchor |
"""
    campaigns, next_actions = parse_progress_markdown(progress_content)
    assert len(campaigns) == 1
    assert campaigns[0]['leads_finding'] == "R123E | anchor"
