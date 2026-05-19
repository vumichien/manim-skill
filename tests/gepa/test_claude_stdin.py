"""Verify claude CLI calls use stdin (not args) for prompt payloads.

Regression for a previous run that wasted ~75 min: GEPA's reflection prompt
grew past Windows' 32K-arg-length limit, so `subprocess.run(cmd_with_prompt)`
returned exit 1 with empty stderr. Passing the prompt via stdin sidesteps
the limit entirely. We assert by mocking subprocess.run and inspecting the
kwargs each call site uses.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def adapter_mod():
    _load("gepa_metrics")
    _load("gepa_invoke_agents")
    _load("gepa_pipeline_runner")
    return _load("gepa_adapter")


@pytest.fixture
def transport_mod():
    return _load("gepa_invoke_agents")


def _fake_completed(stdout: str = "ok"):
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = stdout
    fake.stderr = ""
    return fake


def test_reflection_lm_pipes_prompt_via_stdin(adapter_mod):
    """ClaudeCliReflectionLM must pass prompt as input=, not as a CLI arg."""
    lm = adapter_mod.ClaudeCliReflectionLM(claude_bin="claude")
    big = "x" * 50_000  # past Windows' 32K arg limit
    with patch("gepa_adapter.subprocess.run", return_value=_fake_completed("ok")) as m:
        out = lm(big)
    assert out == "ok"
    args, kwargs = m.call_args
    cmd = args[0]
    assert big not in cmd, "prompt must NOT be in argv"
    assert kwargs.get("input") == big, "prompt must be piped via stdin"
    assert "--print" in cmd and "--model" in cmd


def test_reflection_lm_flattens_message_list(adapter_mod):
    """GEPA may pass list-of-messages — adapter should flatten and stdin it."""
    lm = adapter_mod.ClaudeCliReflectionLM(claude_bin="claude")
    msgs = [{"role": "user", "content": "hello"}, {"role": "user", "content": "world"}]
    with patch("gepa_adapter.subprocess.run", return_value=_fake_completed("ok")) as m:
        lm(msgs)
    kwargs = m.call_args.kwargs
    sent = kwargs.get("input")
    assert "hello" in sent and "world" in sent
    assert all("hello" not in str(a) and "world" not in str(a) for a in m.call_args.args[0])


def test_reflection_lm_surfaces_diagnostics_on_failure(adapter_mod):
    lm = adapter_mod.ClaudeCliReflectionLM(claude_bin="claude")
    fail = MagicMock(returncode=1, stdout="some output", stderr="boom")
    with patch("gepa_adapter.subprocess.run", return_value=fail):
        with pytest.raises(RuntimeError, match="boom"):
            lm("anything")


def test_transport_claude_print_combines_into_stdin(transport_mod):
    """_claude_print pipes system+user via stdin; CLI args stay small."""
    with patch("gepa_invoke_agents.subprocess.run", return_value=_fake_completed("ok")) as m:
        out = transport_mod._claude_print("claude", system="SYS", user="USR", model="m")
    assert out == "ok"
    kwargs = m.call_args.kwargs
    assert kwargs.get("input") == "SYS\n\n---\n\nUSR"
    cmd = m.call_args.args[0]
    assert "SYS" not in cmd and "USR" not in cmd, "neither prompt may land in argv"
    assert "--append-system-prompt" not in cmd, "system goes via stdin, not arg"


def test_transport_claude_print_user_only_when_no_system(transport_mod):
    with patch("gepa_invoke_agents.subprocess.run", return_value=_fake_completed("ok")) as m:
        transport_mod._claude_print("claude", system="", user="just-user", model="m")
    assert m.call_args.kwargs.get("input") == "just-user"


def test_transport_handles_huge_combined_prompt(transport_mod):
    """40KB combined payload would crash if passed as arg on Windows."""
    big_sys = "a" * 20_000
    big_user = "b" * 20_000
    with patch("gepa_invoke_agents.subprocess.run", return_value=_fake_completed("ok")) as m:
        transport_mod._claude_print("claude", system=big_sys, user=big_user, model="m")
    assert len(m.call_args.kwargs["input"]) > 40_000
