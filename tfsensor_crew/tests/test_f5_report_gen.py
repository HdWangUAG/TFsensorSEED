import pytest
from tfsensor_crew.parser import generate_markdown_report, SyncAnalyzer

# --- Tier 1: Feature Coverage (5 Tests) ---

def test_report_header_present():
    """Verify that report includes the main header."""
    analysis = {
        'matched': [], 'untracked_campaigns': [], 'untracked_jobs': [], 'status_mismatches': [], 'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "# Pipeline Synchronization Report" in report

def test_report_summary_metrics():
    """Verify that executive summary metrics are listed."""
    analysis = {
        'matched': [{'campaign': {'campaign': 'C1', 'state': 'done'}, 'job': {'Task_ID': 'J1', 'Status': 'DONE'}, 'match_type': 'path_overlap'}],
        'untracked_campaigns': [], 'untracked_jobs': [], 'status_mismatches': [], 'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "Total Campaigns Matched to Registry" in report
    assert "Status Mismatches Detected" in report

def test_report_contains_matched_section():
    """Verify that matched campaigns section contains the match data."""
    analysis = {
        'matched': [{'campaign': {'campaign': 'C1', 'state': 'done'}, 'job': {'Task_ID': 'J1', 'Status': 'DONE'}, 'match_type': 'path'}],
        'untracked_campaigns': [], 'untracked_jobs': [], 'status_mismatches': [], 'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "## Matched Campaigns & Jobs" in report
    assert "C1" in report
    assert "J1" in report

def test_report_contains_mismatch_section():
    """Verify that mismatches section displays status disagreements."""
    analysis = {
        'matched': [], 'untracked_campaigns': [], 'untracked_jobs': [],
        'status_mismatches': [{'campaign': {'campaign': 'C1'}, 'job': {'Task_ID': 'J1'}, 'expected': 'done', 'actual': 'PENDING'}],
        'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "## Status Mismatches" in report
    assert "J1" in report
    assert "PENDING" in report

def test_report_contains_untracked_section():
    """Verify that untracked campaigns section lists PROGRESS.md only campaigns."""
    analysis = {
        'matched': [],
        'untracked_campaigns': [{'campaign': 'Estradiol-old', 'stage': 'full', 'state': 'done', 'key_output': 'results/old.json'}],
        'untracked_jobs': [], 'status_mismatches': [], 'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "## Untracked Historical Campaigns" in report
    assert "Estradiol-old" in report


# --- Tier 2: Boundary & Corner Cases (5 Tests) ---

def test_report_empty_analysis():
    """Verify report formatting with completely empty analysis results."""
    analysis = {
        'matched': [], 'untracked_campaigns': [], 'untracked_jobs': [], 'status_mismatches': [], 'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "*No campaigns matched.*" in report
    assert "*No status mismatches detected.*" in report
    assert "*No untracked historical campaigns.*" in report

def test_report_with_mismatches_only():
    """Verify report formatting when only mismatches exist."""
    analysis = {
        'matched': [], 'untracked_campaigns': [], 'untracked_jobs': [],
        'status_mismatches': [{'campaign': {'campaign': 'CampA'}, 'job': {'Task_ID': 'JobA'}, 'expected': 'done', 'actual': 'FAILED'}],
        'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "CampA" in report
    assert "JobA" in report
    assert "FAILED" in report

def test_report_with_untracked_jobs_only():
    """Verify formatting when there are untracked jobs in the registry."""
    analysis = {
        'matched': [], 'untracked_campaigns': [],
        'untracked_jobs': [{'Task_ID': 'job_z', 'Target_Ligand': 'lig_z', 'Status': 'DONE', 'Notes': 'Some notes'}],
        'status_mismatches': [], 'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "## Untracked Jobs in Registry" in report
    assert "job_z" in report
    assert "lig_z" in report

def test_report_table_formatting_valid():
    """Verify markdown table syntax validity."""
    analysis = {
        'matched': [{'campaign': {'campaign': 'C1', 'state': 'done'}, 'job': {'Task_ID': 'J1', 'Status': 'DONE'}, 'match_type': 'path'}],
        'untracked_campaigns': [], 'untracked_jobs': [], 'status_mismatches': [], 'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "| Campaign | Job Task ID | Match Method |" in report
    assert "|---|---|---|---|---|" in report

def test_report_contains_next_actions_section():
    """Verify next actions mapping section in the report."""
    analysis = {
        'matched': [], 'untracked_campaigns': [], 'untracked_jobs': [], 'status_mismatches': [],
        'next_actions_matches': [{'job': {'Task_ID': 'J_act', 'Target_Ligand': 'L_act', 'Status': 'PENDING'}, 'next_action': {'action': 'run FEP', 'node': 'Alpha'}}]
    }
    report = generate_markdown_report(analysis)
    assert "## Next Actions Mapping" in report
    assert "J_act" in report
    assert "run FEP (Alpha)" in report
