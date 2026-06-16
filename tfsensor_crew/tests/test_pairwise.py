import pytest
from pathlib import Path
from tfsensor_crew.parser import parse_progress_markdown, parse_jobs_registry_csv, SyncAnalyzer, generate_markdown_report
from tfsensor_crew.crew import TfsensorCrew

# --- Tier 3: Cross-Feature Combinations (6 Tests) ---

def test_pairwise_f2_f3_parsers_integration(temp_progress_file, temp_registry_file):
    """Pair 1: Verify F2 Progress Parser & F3 CSV Parser integration."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    jobs = parse_jobs_registry_csv(temp_registry_file)
    
    assert len(campaigns) > 0
    assert len(jobs) > 0
    # Basic schema alignment check: ensure we extracted target ligands from both
    camp_ligands = {c['campaign'].lower() for c in campaigns}
    job_ligands = {j['Target_Ligand'].lower() for j in jobs}
    # Check that they have some intersection (e.g. testosterone, progesterone, cortisol, estradiol)
    assert len(camp_ligands.intersection(job_ligands)) > 0

def test_pairwise_f2_f4_progress_sync(temp_progress_file):
    """Pair 2: Verify F2 Progress Parser & F4 Sync Analysis integration."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    # Give it an empty job list to ensure everything in campaigns becomes untracked or handles it
    analyzer = SyncAnalyzer(campaigns, next_actions, [])
    analysis = analyzer.analyze()
    
    assert len(analysis['untracked_campaigns']) == len(campaigns)
    assert len(analysis['matched']) == 0

def test_pairwise_f3_f4_csv_sync(temp_registry_file):
    """Pair 3: Verify F3 CSV Parser & F4 Sync Analysis integration."""
    jobs = parse_jobs_registry_csv(temp_registry_file)
    # Give it empty campaigns list to ensure everything in jobs becomes untracked
    analyzer = SyncAnalyzer([], [], jobs)
    analysis = analyzer.analyze()
    
    # All jobs are untracked since there are no campaigns or next actions
    assert len(analysis['untracked_jobs']) + len(analysis['next_actions_matches']) == len(jobs)
    assert len(analysis['matched']) == 0

def test_pairwise_f2_f5_progress_report(temp_progress_file):
    """Pair 4: Verify F2 Progress Parser & F5 Report Gen integration."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    # Build a fake analysis containing only these campaigns as untracked
    analysis = {
        'matched': [],
        'untracked_campaigns': campaigns,
        'untracked_jobs': [],
        'status_mismatches': [],
        'next_actions_matches': []
    }
    report = generate_markdown_report(analysis)
    assert "## Untracked Historical Campaigns" in report
    for camp in campaigns:
        assert camp['campaign'] in report

def test_pairwise_f4_f5_sync_report(temp_progress_file, temp_registry_file):
    """Pair 5: Verify F4 Sync Analysis & F5 Report Gen integration."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    jobs = parse_jobs_registry_csv(temp_registry_file)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    report = generate_markdown_report(analysis)
    
    assert "# Pipeline Synchronization Report" in report
    assert "Total Campaigns Matched to Registry" in report
    assert "Status Mismatches Detected" in report

def test_pairwise_f1_f5_lifecycle_report(temp_progress_file, temp_registry_file, temp_output_file):
    """Pair 6: Verify F1 CLI Lifecycle & F5 Report Gen integration."""
    crew_instance = TfsensorCrew()
    inputs = {
        'progress_path': str(temp_progress_file),
        'registry_path': str(temp_registry_file),
        'output_path': str(temp_output_file)
    }
    report = crew_instance.kickoff(inputs=inputs)
    
    assert temp_output_file.exists()
    file_content = temp_output_file.read_text(encoding='utf-8')
    assert "# Pipeline Synchronization Report" in file_content
    assert report == file_content
