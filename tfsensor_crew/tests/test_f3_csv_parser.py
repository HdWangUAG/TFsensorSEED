import pytest
from tfsensor_crew.parser import parse_jobs_registry_csv

# --- Tier 1: Feature Coverage (5 Tests) ---

def test_parse_valid_csv_records_count(mock_registry_content):
    """Verify correct count of jobs is parsed from registry CSV."""
    jobs = parse_jobs_registry_csv(mock_registry_content)
    assert len(jobs) == 8

def test_parse_valid_csv_record_keys(mock_registry_content):
    """Verify parsed job dictionary keys match headers."""
    jobs = parse_jobs_registry_csv(mock_registry_content)
    first_job = jobs[0]
    expected_keys = {
        'Task_ID', 'Task_Type', 'Assigned_Node', 'Status',
        'Target_Ligand', 'Batch_File', 'Start_Time', 'Completion_Time', 'Notes'
    }
    assert expected_keys.issubset(first_job.keys())
    assert first_job['Task_ID'] == 'fep_demo_l147r'

def test_parse_csv_whitespace_stripping():
    """Verify column headers and values are stripped of whitespace."""
    content = "  Task_ID  , Status \n job1 ,  PENDING "
    jobs = parse_jobs_registry_csv(content)
    assert len(jobs) == 1
    assert 'Task_ID' in jobs[0]
    assert 'Status' in jobs[0]
    assert jobs[0]['Task_ID'] == 'job1'
    assert jobs[0]['Status'] == 'PENDING'

def test_parse_csv_status_mapping(mock_registry_content):
    """Verify various status values are parsed correctly."""
    jobs = parse_jobs_registry_csv(mock_registry_content)
    statuses = [j['Status'] for j in jobs]
    assert 'DONE' in statuses
    assert 'REASSIGNED' in statuses
    assert 'PENDING' in statuses

def test_parse_csv_ligand_mapping(mock_registry_content):
    """Verify Target_Ligand values are correctly parsed."""
    jobs = parse_jobs_registry_csv(mock_registry_content)
    ligands = [j['Target_Ligand'] for j in jobs]
    assert 'Cortisol' in ligands
    assert 'Testosterone' in ligands
    assert 'Progesterone' in ligands
    assert 'Estradiol' in ligands
    assert 'Progesterone/Cortisol' in ligands


# --- Tier 2: Boundary & Corner Cases (5 Tests) ---

def test_parse_csv_empty_file():
    """Verify parser behaves correctly on empty input (empty list or raises)."""
    # Using pandas, empty input raises EmptyDataError, but we handle or let it raise
    import pandas as pd
    with pytest.raises(pd.errors.EmptyDataError):
        parse_jobs_registry_csv("")

def test_parse_csv_headers_only():
    """Verify parser returns empty list when CSV contains only headers."""
    content = "Task_ID,Task_Type,Assigned_Node,Status,Target_Ligand,Batch_File,Start_Time,Completion_Time,Notes"
    jobs = parse_jobs_registry_csv(content)
    assert jobs == []

def test_parse_csv_missing_optional_columns():
    """Verify parser accepts CSV with subset of columns."""
    content = "Task_ID,Status\njob1,DONE"
    jobs = parse_jobs_registry_csv(content)
    assert len(jobs) == 1
    assert jobs[0]['Task_ID'] == 'job1'
    assert jobs[0]['Status'] == 'DONE'

def test_parse_csv_extra_columns():
    """Verify parser preserves extra columns in output dictionaries."""
    content = "Task_ID,Status,ExtraCol\njob1,DONE,ExtraValue"
    jobs = parse_jobs_registry_csv(content)
    assert len(jobs) == 1
    assert jobs[0]['ExtraCol'] == 'ExtraValue'

def test_parse_csv_special_characters():
    """Verify notes containing commas and quotes are parsed correctly."""
    content = 'Task_ID,Status,Notes\njob1,DONE,"Note with a comma, inside quotes"\n'
    jobs = parse_jobs_registry_csv(content)
    assert len(jobs) == 1
    assert jobs[0]['Notes'] == 'Note with a comma, inside quotes'
