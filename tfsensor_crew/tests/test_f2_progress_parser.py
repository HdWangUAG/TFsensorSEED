import pytest
from tfsensor_crew.parser import parse_progress_markdown, normalize_campaign_name

# --- Tier 1: Feature Coverage (5 Tests) ---

def test_parse_valid_progress_markdown_campaigns_count(mock_progress_content):
    """Verify correct count of campaigns is parsed."""
    campaigns, _ = parse_progress_markdown(mock_progress_content)
    assert len(campaigns) == 8

def test_parse_valid_progress_markdown_campaign_keys(mock_progress_content):
    """Verify parsed campaign dict contains all required fields."""
    campaigns, _ = parse_progress_markdown(mock_progress_content)
    first_camp = campaigns[0]
    expected_keys = {'campaign_raw', 'campaign', 'stage', 'state_raw', 'state', 'key_output', 'leads_finding'}
    assert expected_keys.issubset(first_camp.keys())
    assert first_camp['campaign'] == "Estradiol"
    assert first_camp['state'] == "done"

def test_parse_valid_progress_markdown_next_actions_count(mock_progress_content):
    """Verify next actions count is correct."""
    _, next_actions = parse_progress_markdown(mock_progress_content)
    assert len(next_actions) == 5

def test_parse_valid_progress_markdown_next_action_keys(mock_progress_content):
    """Verify next action dict has correct keys and fields."""
    _, next_actions = parse_progress_markdown(mock_progress_content)
    action = next_actions[0]
    assert 'completed' in action
    assert 'node' in action
    assert 'action' in action
    assert action['completed'] is False
    assert action['node'] == "Alpha"
    assert "finish testosterone 2-ligand gate" in action['action']

def test_parse_campaign_normalization():
    """Verify campaign names are properly normalized."""
    assert normalize_campaign_name("**Testosterone** (D-ring)") == "Testosterone (D-ring)"
    assert normalize_campaign_name("  Estradiol   ") == "Estradiol"
    assert normalize_campaign_name("**Progesterone**") == "Progesterone"


# --- Tier 2: Boundary & Corner Cases (5 Tests) ---

def test_parse_progress_empty_content():
    """Verify parser returns empty lists for empty markdown content."""
    campaigns, next_actions = parse_progress_markdown("")
    assert campaigns == []
    assert next_actions == []

def test_parse_progress_no_campaigns_table():
    """Verify parser returns empty list of campaigns if no table header matches."""
    content = """
    # Progress
    Some details here.
    No table at all.
    """
    campaigns, next_actions = parse_progress_markdown(content)
    assert campaigns == []
    assert next_actions == []

def test_parse_progress_malformed_table_columns():
    """Verify parser ignores lines in table with incorrect columns count."""
    content = """
    | Campaign | Stage | State | Key output | Leads / finding |
    |---|---|---|---|---|
    | Camp1 | full | done | output | finding |
    | Malformed Row | only three | columns |
    | Camp2 | gen | reassigned | out2 | find2 |
    """
    campaigns, _ = parse_progress_markdown(content)
    assert len(campaigns) == 2
    assert campaigns[0]['campaign'] == "Camp1"
    assert campaigns[1]['campaign'] == "Camp2"

def test_parse_progress_no_next_actions():
    """Verify parser handles missing Next Actions section gracefully."""
    content = """
    | Campaign | Stage | State | Key output | Leads / finding |
    |---|---|---|---|---|
    | Camp1 | full | done | output | finding |
    """
    campaigns, next_actions = parse_progress_markdown(content)
    assert len(campaigns) == 1
    assert next_actions == []

def test_parse_progress_next_actions_different_checkbox_formats():
    """Verify parser handles different checkbox formats (checked/unchecked)."""
    content = """
    ## Next actions
    - [ ] (Alpha) Uncompleted action
    - [x] (Beta) Completed action lowercase x
    - [X] (Gamma) Completed action uppercase X
    - [  ] (Delta) Uncompleted with spaces
    """
    _, next_actions = parse_progress_markdown(content)
    assert len(next_actions) == 4
    assert next_actions[0]['completed'] is False
    assert next_actions[0]['node'] == "Alpha"
    assert next_actions[0]['action'] == "Uncompleted action"
    
    assert next_actions[1]['completed'] is True
    assert next_actions[1]['node'] == "Beta"
    
    assert next_actions[2]['completed'] is True
    assert next_actions[2]['node'] == "Gamma"
    
    assert next_actions[3]['completed'] is False
    assert next_actions[3]['node'] == "Delta"
