"""Shared pytest fixtures + sys.path bootstrap for the manim-skill suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Ensure scripts/ is importable so tests can use ingest_shared etc.
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def scripts_dir() -> Path:
    return SCRIPTS_DIR


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    return REPO_ROOT / "samples"


@pytest.fixture(scope="session")
def schema_path() -> Path:
    return REPO_ROOT / "schemas" / "storyboard.schema.json"


@pytest.fixture(scope="session")
def example_storyboard(repo_root: Path) -> Path:
    return repo_root / "schemas" / "storyboard.example.yaml"


@pytest.fixture
def tmp_run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "run"
    d.mkdir()
    return d
