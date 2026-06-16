import pytest
from tfsensor_crew.parser import parse_progress_markdown, parse_jobs_registry_csv, SyncAnalyzer

# --- Tier 4: Real-World Application Scenarios (5 Tests) ---

def test_real_testosterone_campaign_sync(temp_progress_file, temp_registry_file):
    """Scenario 1: Verify sync status of Testosterone campaigns."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    jobs = parse_jobs_registry_csv(temp_registry_file)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    # Verify that Testosterone 2-ligand gate is matched to gate2lig_testosterone
    testosterone_matches = [
        m for m in analysis['matched'] 
        if "testosterone" in m['campaign']['campaign'].lower()
    ]
    assert len(testosterone_matches) >= 1
    
    # Check that gate2lig_testosterone is indeed matched and status is DONE
    gate2lig_match = next(m for m in testosterone_matches if m['job']['Task_ID'] == 'gate2lig_testosterone')
    assert gate2lig_match['job']['Status'] == 'DONE'
    assert 'done' in gate2lig_match['campaign']['state'].lower()

def test_real_reassigned_campaigns(temp_progress_file, temp_registry_file):
    """Scenario 2: Verify that reassigned campaigns (Progesterone & Cortisol) are mapped correctly."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    jobs = parse_jobs_registry_csv(temp_registry_file)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    # Check Progesterone and Cortisol screen tasks
    reassigned_matches = [
        m for m in analysis['matched']
        if m['job']['Status'] == 'REASSIGNED'
    ]
    assert len(reassigned_matches) == 2
    
    task_ids = {m['job']['Task_ID'] for m in reassigned_matches}
    assert 'gen_screen_prog' in task_ids
    assert 'gen_screen_cort' in task_ids
    
    for match in reassigned_matches:
        assert 'reassigned' in match['campaign']['state'].lower()

def test_real_pending_rescreen(temp_progress_file, temp_registry_file):
    """Scenario 3: Verify the Estradiol re-screen campaign mapping."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    jobs = parse_jobs_registry_csv(temp_registry_file)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    # Find match for Estradiol re-screen
    rescreen_match = next(
        m for m in analysis['matched']
        if m['campaign']['campaign'] == 'Estradiol (re-screen)'
    )
    assert rescreen_match['job']['Task_ID'] == 'gen_screen_estradiol'
    assert rescreen_match['job']['Status'] == 'PENDING'
    assert 'assigned' in rescreen_match['campaign']['state'].lower()

def test_real_untracked_historical_campaigns(temp_progress_file, temp_registry_file):
    """Scenario 4: Verify that the historical Estradiol campaign is flagged as untracked."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    jobs = parse_jobs_registry_csv(temp_registry_file)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    # We expect the historical "Estradiol" campaign (state = done, output = results/stage3_design/STAGE3_SUMMARY.md)
    # to be flagged as untracked in the registry.
    untracked_names = [c['campaign'] for c in analysis['untracked_campaigns']]
    assert 'Estradiol' in untracked_names
    
    # Ensure it's the done one, not the re-screen one
    hist_camp = next(c for c in analysis['untracked_campaigns'] if c['campaign'] == 'Estradiol')
    assert hist_camp['stage'] == 'full'
    assert hist_camp['state'] == 'done'

def test_real_next_actions_mapping(temp_progress_file, temp_registry_file):
    """Scenario 5: Verify that registry jobs mapping to next actions are identified."""
    campaigns, next_actions = parse_progress_markdown(temp_progress_file)
    jobs = parse_jobs_registry_csv(temp_registry_file)
    
    analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
    analysis = analyzer.analyze()
    
    # We expect progcort_2lig_gate and ligand_rbfe_triad to match next actions
    matched_job_ids = [m['job']['Task_ID'] for m in analysis['next_actions_matches']]
    assert 'progcort_2lig_gate' in matched_job_ids
    assert 'ligand_rbfe_triad' in matched_job_ids
    
    # Verify their mapped actions contain correct details
    triad_match = next(m for m in analysis['next_actions_matches'] if m['job']['Task_ID'] == 'ligand_rbfe_triad')
    assert 'build ligand-ligand rbfe executor' in triad_match['next_action']['action'].lower()
    assert triad_match['next_action']['node'] == 'Beta'
