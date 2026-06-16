import pytest
from tfsensor_crew.parser import SyncAnalyzer

# --- Tier 1: Feature Coverage (5 Tests) ---

def test_sync_matched_count(mock_progress_content, mock_registry_content):
    """Verify correct matches between progress campaigns and registry jobs."""
    from tfsensor_crew.parser import parse_progress_markdown, parse_jobs_registry_csv
    campaigns, next_actions = parse_progress_markdown(mock_progress_content)
    jobs = parse_jobs_registry_csv(mock_registry_content)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    # We expect several matched items
    assert len(analysis['matched']) > 0

def test_sync_untracked_campaigns(mock_progress_content, mock_registry_content):
    """Verify historical campaigns in PROGRESS.md with no registry jobs are flagged."""
    from tfsensor_crew.parser import parse_progress_markdown, parse_jobs_registry_csv
    campaigns, next_actions = parse_progress_markdown(mock_progress_content)
    jobs = parse_jobs_registry_csv(mock_registry_content)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    untracked_campaign_names = [c['campaign'] for c in analysis['untracked_campaigns']]
    assert "Estradiol" in untracked_campaign_names

def test_sync_status_mismatch_detection():
    """Verify that status mismatches (e.g. done in progress vs pending in registry) are caught."""
    campaigns = [
        {'campaign': 'Testosterone', 'stage': 'gen', 'state': 'done', 'key_output': 'results/test.json', 'leads_finding': ''}
    ]
    jobs = [
        {'Task_ID': 'job1', 'Target_Ligand': 'Testosterone', 'Status': 'PENDING', 'Notes': 'results/test.json'}
    ]
    
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    analysis = analyzer.analyze()
    
    assert len(analysis['status_mismatches']) == 1
    assert analysis['status_mismatches'][0]['job']['Task_ID'] == 'job1'

def test_sync_next_actions_mapping(mock_progress_content, mock_registry_content):
    """Verify pending jobs map to next actions."""
    from tfsensor_crew.parser import parse_progress_markdown, parse_jobs_registry_csv
    campaigns, next_actions = parse_progress_markdown(mock_progress_content)
    jobs = parse_jobs_registry_csv(mock_registry_content)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    next_action_jobs = [match['job']['Task_ID'] for match in analysis['next_actions_matches']]
    assert 'progcort_2lig_gate' in next_action_jobs
    assert 'ligand_rbfe_triad' in next_action_jobs

def test_sync_untracked_jobs():
    """Verify jobs in registry with no corresponding campaign or next action are caught."""
    campaigns = []
    jobs = [
        {'Task_ID': 'unrelated_job', 'Target_Ligand': 'unrelated', 'Status': 'PENDING', 'Notes': ''}
    ]
    
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    analysis = analyzer.analyze()
    
    assert len(analysis['untracked_jobs']) == 1
    assert analysis['untracked_jobs'][0]['Task_ID'] == 'unrelated_job'


# --- Tier 2: Boundary & Corner Cases (5 Tests) ---

def test_sync_no_data():
    """Verify analyzer handles empty campaign and job lists cleanly."""
    analyzer = SyncAnalyzer([], [], [])
    analysis = analyzer.analyze()
    assert analysis['matched'] == []
    assert analysis['untracked_campaigns'] == []
    assert analysis['untracked_jobs'] == []
    assert analysis['status_mismatches'] == []
    assert analysis['next_actions_matches'] == []

def test_sync_perfect_alignment():
    """Verify perfect alignment leads to zero mismatches or untracked items."""
    campaigns = [
        {'campaign': 'Testosterone', 'stage': 'gen', 'state': 'done', 'key_output': 'results/t1.json', 'leads_finding': ''}
    ]
    jobs = [
        {'Task_ID': 'job1', 'Target_Ligand': 'Testosterone', 'Status': 'DONE', 'Notes': 'results/t1.json'}
    ]
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    analysis = analyzer.analyze()
    
    assert len(analysis['matched']) == 1
    assert len(analysis['untracked_campaigns']) == 0
    assert len(analysis['untracked_jobs']) == 0
    assert len(analysis['status_mismatches']) == 0

def test_sync_all_mismatched():
    """Verify all statuses are mismatched if progress says done and jobs say REASSIGNED."""
    campaigns = [
        {'campaign': 'Testosterone', 'stage': 'gen', 'state': 'done', 'key_output': 'results/t1.json', 'leads_finding': ''}
    ]
    jobs = [
        {'Task_ID': 'job1', 'Target_Ligand': 'Testosterone', 'Status': 'REASSIGNED', 'Notes': 'results/t1.json'}
    ]
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    analysis = analyzer.analyze()
    
    assert len(analysis['status_mismatches']) == 1

def test_sync_duplicate_campaigns_or_jobs():
    """Verify handling when multiple jobs exist for the same target ligand."""
    campaigns = [
        {'campaign': 'Cortisol', 'stage': 'gen', 'state': 'done', 'key_output': 'results/c1.json', 'leads_finding': ''}
    ]
    # two jobs matching Cortisol
    jobs = [
        {'Task_ID': 'job_c1', 'Target_Ligand': 'Cortisol', 'Status': 'DONE', 'Notes': 'results/c1.json'},
        {'Task_ID': 'job_c2', 'Target_Ligand': 'Cortisol', 'Status': 'DONE', 'Notes': 'other'}
    ]
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    analysis = analyzer.analyze()
    
    # Matches job_c1 by path, and job_c2 remains untracked or matched by ligand
    assert len(analysis['matched']) >= 1

def test_sync_case_insensitivity():
    """Verify matching works with different case configurations."""
    campaigns = [
        {'campaign': 'TESTOSTERONE', 'stage': 'gen', 'state': 'done', 'key_output': 'results/t1.json', 'leads_finding': ''}
    ]
    jobs = [
        {'Task_ID': 'job1', 'Target_Ligand': 'testosterone', 'Status': 'DONE', 'Notes': 'results/t1.json'}
    ]
    analyzer = SyncAnalyzer(campaigns, [], jobs)
    analysis = analyzer.analyze()
    assert len(analysis['matched']) == 1
