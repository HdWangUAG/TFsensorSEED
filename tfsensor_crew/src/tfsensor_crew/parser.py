import os
import re
import pandas as pd
from pathlib import Path
from io import StringIO


def _looks_like_path(arg):
    """True only for a Path, or a str that is a single-line, existing file path.
    A multi-line string (raw file *content*) is treated as content, not a path —
    the parse functions accept either a path OR inline content."""
    if isinstance(arg, Path):
        return True
    if isinstance(arg, str):
        return "\n" not in arg and len(arg) < 4096 and os.path.isfile(arg)
    return False


def normalize_campaign_name(name):
    # Remove markdown bolding and strip whitespace
    name = name.replace("**", "").strip()
    # Normalize spaces
    name = re.sub(r'\s+', ' ', name)
    return name

def parse_progress_markdown(filepath_or_content):
    """
    Parses PROGRESS.md to extract campaign status and next actions.
    """
    if _looks_like_path(filepath_or_content):
        with open(filepath_or_content, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = filepath_or_content

    campaigns = []
    next_actions = []
    
    # Parse Campaign status table
    table_started = False
    in_campaign_status_section = False
    for line in content.splitlines():
        line_stripped = line.strip()
        if line_stripped.startswith('#'):
            header_name = line_stripped.lstrip('#').strip().lower()
            if header_name == 'campaign status':
                in_campaign_status_section = True
            else:
                in_campaign_status_section = False
                table_started = False
            continue
        if not line_stripped.startswith('|'):
            table_started = False
            continue
        line_replaced = line_stripped.replace('\\|', '__PIPE__')
        cols = [c.replace('__PIPE__', '|').strip() for c in line_replaced.split('|')[1:-1]]
        if len(cols) != 5:
            continue
        # A "Campaign | Stage | State | ..." header row starts the campaign table — works
        # whether or not a "## Campaign status" section header preceded it (robust to bare
        # tables). The "## ..." branch above still resets table_started at the next section,
        # so tables in other sections are not captured.
        if cols[0].lower() == 'campaign':
            table_started = True
            in_campaign_status_section = True
            continue
        if '---' in cols[0]:
            continue
        if table_started:
            # It is a data row
            campaigns.append({
                'campaign_raw': cols[0],
                'campaign': normalize_campaign_name(cols[0]),
                'stage': cols[1],
                'state_raw': cols[2],
                'state': cols[2].replace("**", "").strip(),
                'key_output': cols[3],
                'leads_finding': cols[4]
            })

    # Parse Next actions list
    next_actions_started = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('## Next actions'):
            next_actions_started = True
            continue
        elif line.startswith('##') and next_actions_started:
            next_actions_started = False
        if next_actions_started and line.startswith('-'):
            match = re.match(r'-\s*\[\s*([ xX]?)\s*\]\s*(?:\(([^)]+)\))?\s*(.*)', line)
            if match:
                checked = match.group(1).strip() != ''
                node = match.group(2) or ''
                action_text = match.group(3) or ''
                next_actions.append({
                    'raw': line,
                    'completed': checked,
                    'node': node.strip(),
                    'action': action_text.strip()
                })
                
    return campaigns, next_actions

def parse_jobs_registry_csv(filepath_or_content):
    """
    Parses JOBS_REGISTRY.csv and returns a list of dictionaries representing jobs.
    """
    if _looks_like_path(filepath_or_content):
        df = pd.read_csv(filepath_or_content)
    else:
        df = pd.read_csv(StringIO(filepath_or_content))
        
    df = df.fillna('')
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()
            
    return df.to_dict(orient='records')

class SyncAnalyzer:
    def __init__(self, campaigns, next_actions, jobs):
        self.campaigns = campaigns
        self.next_actions = next_actions
        self.jobs = jobs

    def analyze(self):
        """
        Cross-reference the progress ledger and jobs registry.
        """
        analysis_results = {
            'matched': [],
            'untracked_campaigns': [],
            'untracked_jobs': [],
            'status_mismatches': [],
            'next_actions_matches': []
        }

        # Step 1: Match campaigns to jobs
        # We match using path overlaps in key_output / job Notes, or ligand names.
        matched_job_ids = set()
        matched_campaign_indices = set()

        # Two-pass matching: PATH matches (strong, unambiguous) take priority over
        # ligand-name matches (weak, greedy). A single job can only be claimed once, and a
        # path-matched job cannot then be stolen by a name match on a different campaign
        # (e.g. the historical "Estradiol" must not claim gen_screen_estradiol once the
        # "Estradiol (re-screen)" campaign has path-matched it).
        # --- Pass A: path overlap, across all campaigns ---
        for idx, camp in enumerate(self.campaigns):
            # Exclude markdown backticks from the path token, otherwise a key_output written
            # as `results/stage3_cort/` captures the trailing ` and the substring test fails.
            camp_output_paths = re.findall(r'results/[^\s+,;|`]+', camp['key_output'])
            found_match = False
            for job in self.jobs:
                job_id = job.get('Task_ID')
                if job_id in matched_job_ids:
                    continue
                job_notes = job.get('Notes', '')
                for path in camp_output_paths:
                    path_clean = path.strip('`').rstrip('.').rstrip('/')
                    # Avoid generic path matches
                    components = [c for c in path_clean.split('/') if c]
                    if len(components) < 2 or path_clean.lower() in {'results', 'data', 'results/', 'data/', ''}:
                        continue
                    if path_clean and path_clean in job_notes:
                        analysis_results['matched'].append({
                            'campaign': camp, 'job': job,
                            'match_type': 'path_overlap', 'path': path_clean})
                        matched_job_ids.add(job_id)
                        matched_campaign_indices.add(idx)
                        found_match = True
                        break
                if found_match:
                    break

        # --- Pass B: ligand-name fallback, only unmatched campaigns vs unmatched jobs ---
        for idx, camp in enumerate(self.campaigns):
            if idx in matched_campaign_indices:
                continue
            for job in self.jobs:
                job_id = job.get('Task_ID')
                if job_id in matched_job_ids:
                    continue
                target_ligand = job.get('Target_Ligand', '')
                if not target_ligand or target_ligand == '-':
                    continue
                if target_ligand.lower() in camp['campaign'].lower():
                    analysis_results['matched'].append({
                        'campaign': camp, 'job': job, 'match_type': 'ligand_name'})
                    matched_job_ids.add(job_id)
                    matched_campaign_indices.add(idx)
                    break

        # Identify Untracked/Historical Campaigns
        for idx, camp in enumerate(self.campaigns):
            if idx not in matched_campaign_indices:
                analysis_results['untracked_campaigns'].append(camp)

        # Identify Untracked Jobs in Registry
        for job in self.jobs:
            job_id = job.get('Task_ID')
            if job_id not in matched_job_ids:
                # Map the job to its best-fitting planned next action. Score EVERY action and
                # pick the highest (not the first hit), requiring both a ligand and a task-type
                # signal. Token-level matching avoids substring traps: 'test' (a token in
                # "test/prog/cort") must not silently match "testosterone".
                job_ligand = job.get('Target_Ligand', '').lower()
                job_type = job.get('Task_Type', '').lower()
                ligand_parts = [p for p in re.split(r'[/ ]', job_ligand) if len(p) >= 3]
                type_parts = [p for p in re.split(r'[/ -]', job_type) if len(p) >= 3]

                def _overlap(parts, tokens):
                    n = 0
                    for p in parts:
                        if p in tokens or any(t.startswith(p[:4]) for t in tokens):
                            n += 1
                    return n

                best_action, best_score = None, 0
                for act in self.next_actions:
                    tokens = {t for t in re.split(r'[^a-z0-9]+', act['action'].lower()) if t}
                    lig = _overlap(ligand_parts, tokens)
                    typ = _overlap(type_parts, tokens)
                    if lig >= 1 and typ >= 1:
                        score = lig * 2 + typ          # weight ligand specificity higher
                        if score > best_score:
                            best_action, best_score = act, score

                if best_action:
                    analysis_results['next_actions_matches'].append({
                        'job': job, 'next_action': best_action})
                else:
                    analysis_results['untracked_jobs'].append(job)

        # Step 2: Check for status mismatches among matched items
        for match in analysis_results['matched']:
            camp = match['campaign']
            job = match['job']
            
            camp_state = camp['state'].lower()
            job_status = (job.get('Status') or 'PENDING').lower()

            # Normalize statuses for comparison
            # done, done (alpha) -> done
            # reassigned, reassigned -> aspartate -> reassigned
            # assigned -> aspartate, pending -> pending/assigned
            norm_camp = camp_state
            if 'done' in camp_state:
                norm_camp = 'done'
            elif 'reassigned' in camp_state:
                norm_camp = 'reassigned'
            elif 'assigned' in camp_state or 'pending' in camp_state:
                norm_camp = 'pending'

            norm_job = job_status
            if 'done' in job_status:
                norm_job = 'done'
            elif 'reassigned' in job_status:
                norm_job = 'reassigned'
            elif 'pending' in job_status or 'assigned' in job_status:
                norm_job = 'pending'

            if norm_camp != norm_job:
                analysis_results['status_mismatches'].append({
                    'campaign': camp,
                    'job': job,
                    'expected': camp['state'],
                    'actual': job.get('Status') or 'PENDING'
                })

        return analysis_results

def generate_markdown_report(analysis):
    """
    Generates a markdown report summarizing the synchronization status.
    """
    report = []
    report.append("# Pipeline Synchronization Report")
    report.append("")
    report.append("## Executive Summary")
    total_matched = len(analysis['matched'])
    total_mismatches = len(analysis['status_mismatches'])
    total_untracked_c = len(analysis['untracked_campaigns'])
    total_untracked_j = len(analysis['untracked_jobs'])
    total_next_actions = len(analysis['next_actions_matches'])
    
    report.append(f"- **Total Campaigns Matched to Registry**: {total_matched}")
    report.append(f"- **Status Mismatches Detected**: {total_mismatches}")
    report.append(f"- **Untracked Historical Campaigns (PROGRESS.md only)**: {total_untracked_c}")
    report.append(f"- **Registry Jobs Matching Next Actions (Pending/Planned)**: {total_next_actions}")
    report.append(f"- **Untracked Jobs (Registry only, no relation to campaigns or next actions)**: {total_untracked_j}")
    report.append("")

    report.append("## Matched Campaigns & Jobs")
    if total_matched == 0:
        report.append("*No campaigns matched.*")
    else:
        report.append("| Campaign | Job Task ID | Match Method | Campaign State | Job Status |")
        report.append("|---|---|---|---|---|")
        for match in analysis['matched']:
            camp = match['campaign']
            job = match['job']
            match_type = match['match_type']
            report.append(f"| {camp['campaign']} | {job.get('Task_ID', '')} | {match_type} | {camp['state']} | {job.get('Status') or 'PENDING'} |")
    report.append("")

    report.append("## Status Mismatches")
    if total_mismatches == 0:
        report.append("*No status mismatches detected.*")
    else:
        report.append("| Campaign | Job Task ID | Campaign State | Job Status |")
        report.append("|---|---|---|---|")
        for mis in analysis['status_mismatches']:
            camp = mis['campaign']
            job = mis['job']
            report.append(f"| {camp['campaign']} | {job.get('Task_ID', '')} | {mis['expected']} | {mis['actual']} |")
    report.append("")

    report.append("## Untracked Historical Campaigns")
    if total_untracked_c == 0:
        report.append("*No untracked historical campaigns.*")
    else:
        report.append("| Campaign | Stage | State | Key Output |")
        report.append("|---|---|---|---|")
        for camp in analysis['untracked_campaigns']:
            report.append(f"| {camp['campaign']} | {camp['stage']} | {camp['state']} | {camp['key_output']} |")
    report.append("")

    report.append("## Next Actions Mapping")
    if total_next_actions == 0:
        report.append("*No next action mapping found.*")
    else:
        report.append("| Job Task ID | Target Ligand | Status | Matched Next Action |")
        report.append("|---|---|---|---|")
        for match in analysis['next_actions_matches']:
            job = match['job']
            act = match['next_action']
            report.append(f"| {job.get('Task_ID', '')} | {job.get('Target_Ligand', '')} | {job.get('Status') or 'PENDING'} | {act['action']} ({act['node']}) |")
    report.append("")

    report.append("## Untracked Jobs in Registry")
    if total_untracked_j == 0:
        report.append("*No untracked jobs.*")
    else:
        report.append("| Job Task ID | Target Ligand | Status | Notes |")
        report.append("|---|---|---|---|")
        for job in analysis['untracked_jobs']:
            report.append(f"| {job.get('Task_ID', '')} | {job.get('Target_Ligand', '')} | {job.get('Status') or 'PENDING'} | {job.get('Notes', '')} |")
    report.append("")

    return "\n".join(report)
