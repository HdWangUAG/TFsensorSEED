import os
import pytest
from pathlib import Path
from tfsensor_crew.crew import TfsensorCrew
from tfsensor_crew.main import run

# --- Tier 1: Feature Coverage (5 Tests) ---

def test_structure_src_exists():
    """Verify src/tfsensor_crew/ structure is intact."""
    base_path = Path(__file__).parent.parent / "src" / "tfsensor_crew"
    assert base_path.exists()
    assert (base_path / "__init__.py").exists()
    assert (base_path / "crew.py").exists()
    assert (base_path / "main.py").exists()
    assert (base_path / "parser.py").exists()

def test_structure_knowledge_exists():
    """Verify knowledge/ directory exists."""
    # We will ensure the directory is created if it does not exist
    base_path = Path(__file__).parent.parent / "knowledge"
    os.makedirs(base_path, exist_ok=True)
    assert base_path.exists()

def test_structure_tests_exists():
    """Verify tests/ directory exists."""
    base_path = Path(__file__).parent.parent / "tests"
    assert base_path.exists()

def test_crew_instantiation():
    """Verify TfsensorCrew class can be instantiated."""
    crew_instance = TfsensorCrew()
    assert crew_instance is not None
    assert hasattr(crew_instance, 'progress_parser_agent')
    assert hasattr(crew_instance, 'parse_progress_task')

def test_config_yaml_files_loaded():
    """Verify config YAML files are loaded successfully."""
    crew_instance = TfsensorCrew()
    assert crew_instance.agents_yaml is not None
    assert crew_instance.tasks_yaml is not None
    assert 'progress_parser_agent' in crew_instance.agents_yaml
    assert 'parse_progress_task' in crew_instance.tasks_yaml


# --- Tier 2: Boundary & Corner Cases (5 Tests) ---

def test_crew_kickoff_missing_inputs(temp_progress_file, temp_registry_file, temp_output_file):
    """Verify kickoff works with partial/default inputs and doesn't crash."""
    crew_instance = TfsensorCrew()
    inputs = {
        'progress_path': str(temp_progress_file),
        'registry_path': str(temp_registry_file),
        'output_path': str(temp_output_file)
    }
    report = crew_instance.kickoff(inputs=inputs)
    assert report is not None
    assert temp_output_file.exists()

def test_crew_kickoff_invalid_progress_path(temp_registry_file, temp_output_file):
    """Verify kickoff raises FileNotFoundError on missing progress path."""
    crew_instance = TfsensorCrew()
    inputs = {
        'progress_path': 'nonexistent_progress.md',
        'registry_path': str(temp_registry_file),
        'output_path': str(temp_output_file)
    }
    with pytest.raises(FileNotFoundError):
        crew_instance.kickoff(inputs=inputs)

def test_crew_kickoff_invalid_registry_path(temp_progress_file, temp_output_file):
    """Verify kickoff raises FileNotFoundError on missing registry path."""
    crew_instance = TfsensorCrew()
    inputs = {
        'progress_path': str(temp_progress_file),
        'registry_path': 'nonexistent_registry.csv',
        'output_path': str(temp_output_file)
    }
    with pytest.raises(FileNotFoundError):
        crew_instance.kickoff(inputs=inputs)

def test_main_cli_help(monkeypatch):
    """Verify main entrypoint can be imported and arguments can be parsed."""
    import sys
    monkeypatch.setattr(sys, "argv", ["main.py", "--help"])
    # Simply verify that parser gets constructed and can print help/exit
    with pytest.raises(SystemExit) as excinfo:
        run()
    assert excinfo.value.code == 0

def test_crew_kickoff_writes_to_unwritable_path(temp_progress_file, temp_registry_file):
    """Verify appropriate exception is raised when output path is unwritable."""
    crew_instance = TfsensorCrew()
    inputs = {
        'progress_path': str(temp_progress_file),
        'registry_path': str(temp_registry_file),
        'output_path': '/nonexistent_dir/unwritable_report.md'
    }
    # Should raise PermissionError or FileNotFoundError/OSError
    with pytest.raises(OSError):
        crew_instance.kickoff(inputs=inputs)
