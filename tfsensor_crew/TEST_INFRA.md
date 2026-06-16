# E2E Test Infra: TFsensorSEED Status Crew

## Test Philosophy
- Opaque-box, requirement-driven. Evaluates standard CrewAI structure and sync report logic.
- Methodology: Feature Coverage + Boundary Value Analysis + Pairwise Combination Matrix + Real-World Integration.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| F1 | CrewAI Directory Structure and CLI Lifecycle | R1 | 5 | 5 | ✓ |
| F2 | Progress Ledger Parsing and Extraction | R2 | 5 | 5 | ✓ |
| F3 | Job Registry Parsing and Extraction | R2 | 5 | 5 | ✓ |
| F4 | State Cross-correlation and Sync Analysis | R2 | 5 | 5 | ✓ |
| F5 | Sync Report Compilation & Markdown Gen | R2 | 5 | 5 | ✓ |

## Test Architecture
- **Test Runner**: Pytest framework executed inside local virtual environment.
- **Invocation**: `pytest tfsensor_crew/tests/`
- **Mocking Strategy**: Input files (`PROGRESS.md`, `JOBS_REGISTRY.csv`) mocked using pytest `tmp_path` file fixtures to prevent side effects on live files.
- **Directory Layout**:
  - `tfsensor_crew/tests/`
    - `conftest.py` (fixtures)
    - `test_f1_lifecycle.py`
    - `test_f2_progress_parser.py`
    - `test_f3_csv_parser.py`
    - `test_f4_sync_analysis.py`
    - `test_f5_report_gen.py`
    - `test_pairwise.py`
    - `test_real_world.py`

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | `test_real_testosterone_campaign_sync` | F2, F3, F4, F5 | Medium |
| 2 | `test_real_reassigned_campaigns` | F2, F3, F4, F5 | Medium |
| 3 | `test_real_pending_rescreen` | F2, F3, F4, F5 | Medium |
| 4 | `test_real_untracked_historical_campaigns` | F2, F3, F4, F5 | High |
| 5 | `test_real_next_actions_mapping` | F2, F3, F4, F5 | High |

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: ≥5 per feature (Total 25)
- **Tier 2 (Boundary & Corner Cases)**: ≥5 per feature (Total 25)
- **Tier 3 (Cross-feature Combinations)**: Pairwise coverage of 6 major feature pairs (Total 6)
- **Tier 4 (Real-world scenarios)**: 5 realistic scenarios from live files (Total 5)
- **Total Minimum**: 61 test cases
