"""Storyboard validator: positive case, three negative fixtures."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate-storyboard.py"
FIXTURES = REPO / "tests" / "fixtures"


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        capture_output=True,
        text=True,
    )


def test_example_storyboard_passes() -> None:
    res = _run(REPO / "schemas" / "storyboard.example.yaml")
    assert res.returncode == 0, f"example must pass, stderr:\n{res.stderr}"


@pytest.mark.parametrize(
    "fixture,expected_substring",
    [
        ("broken-no-duration.yaml",   "duration_s"),
        ("broken-bad-target.yaml",    "ghost_circle"),
        ("broken-duration-sum.yaml",  "total_duration_s"),
    ],
)
def test_broken_fixture_fails(fixture: str, expected_substring: str) -> None:
    res = _run(FIXTURES / fixture)
    assert res.returncode != 0, f"{fixture} should fail validation"
    assert expected_substring in res.stderr, (
        f"expected '{expected_substring}' in stderr, got:\n{res.stderr}"
    )
