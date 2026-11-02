"""Tests for the checkpoint / --fresh / resume detection in optimize-prompts.py.

The script exposes its checkpoint behaviour via:
  - always-on `run_dir = RUNS_DIR / run_id`
  - `--fresh` deletes `<run_dir>/gepa_state.bin` before optimize runs
  - dry-run prints `RESUME from ...` if `gepa_state.bin` exists, else `fresh run`

We exercise the script end-to-end with `--dry-run` (no LM calls) so the test is
fast and free.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"


def _load_optimize_module():
    spec = importlib.util.spec_from_file_location(
        "optimize_prompts", SCRIPTS / "optimize-prompts.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["optimize_prompts"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_dry(monkeypatch, tmp_path: Path, run_id: str, *extra: str) -> str:
    """Run main() in dry-run mode against an isolated RUNS_DIR. Return stdout."""
    mod = _load_optimize_module()
    monkeypatch.setattr(mod, "RUNS_DIR", tmp_path)
    argv = [
        "--transport", "claude",
        "--reflection-lm", "claude",
        "--claude-model", "claude-sonnet-4-6",
        "--budget", "1",
        "--yes",
        "--dry-run",
        "--run-id", run_id,
        *extra,
    ]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.main(argv)
    assert rc == 0, buf.getvalue()
    return buf.getvalue()


def test_fresh_run_reports_no_checkpoint(monkeypatch, tmp_path):
    out = _run_dry(monkeypatch, tmp_path, "fresh-detect")
    assert "checkpoint       : fresh run" in out
    # dry-run still creates archive dir, but no gepa_state.bin
    assert not (tmp_path / "fresh-detect" / "gepa_state.bin").exists()


def test_existing_checkpoint_triggers_resume_mode(monkeypatch, tmp_path):
    run_dir = tmp_path / "resume-detect"
    run_dir.mkdir(parents=True)
    (run_dir / "gepa_state.bin").write_bytes(b"stub-checkpoint")
    # dry-run path doesn't enter GEPA, so detection prints from the header
    out = _run_dry(monkeypatch, tmp_path, "resume-detect")
    # dry-run skips real GEPA, so resume_mode flips only outside dry-run, but
    # the header line should still reflect the detected checkpoint
    assert "gepa_state.bin" in out and "fresh run" not in out.split("checkpoint")[-1].split("\n")[0]
    # checkpoint still on disk (no --fresh)
    assert (run_dir / "gepa_state.bin").read_bytes() == b"stub-checkpoint"


def test_fresh_flag_removes_existing_checkpoint(monkeypatch, tmp_path):
    run_dir = tmp_path / "fresh-wipe"
    run_dir.mkdir(parents=True)
    (run_dir / "gepa_state.bin").write_bytes(b"stale")
    out = _run_dry(monkeypatch, tmp_path, "fresh-wipe", "--fresh")
    assert "[fresh] removed" in out
    assert "checkpoint       : fresh run" in out
    assert not (run_dir / "gepa_state.bin").exists()


def test_fresh_flag_no_op_when_no_checkpoint(monkeypatch, tmp_path):
    """--fresh on a never-run dir should not error."""
    out = _run_dry(monkeypatch, tmp_path, "fresh-noop", "--fresh")
    assert "[fresh] removed" not in out
    assert "checkpoint       : fresh run" in out
