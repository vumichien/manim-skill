"""Transport layer for GEPA pipeline runner.

Three implementations:
  - LitellmTransport (v1 default): one LLM call per agent role via `litellm`.
  - ClaudeCliTransport (recommended for users with a Claude subscription):
    three sequential `claude --print` calls (researcher / planner /
    implementer), each receiving the candidate prompt as system message.
  - ClaudeSubprocessTransport (opt-in): shells out to the slash command
    `claude --bare --print /manim-skill:manim-video ...`. Requires the plugin
    to be installed in the same Claude Code session.

Each transport accepts a candidate prompt dict and a topic, writes the
storyboard YAML + per-scene Python files into a working directory, and returns
their paths. The orchestrator (gepa_pipeline_runner.run) handles render.

See plans/260519-1521-gepa-prompt-optimization/spike-subprocess.md for the
spike result that picked Path B as the v1 default.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

DEFAULT_LITELLM_MODEL = "openai/gpt-4.1-mini"
# Sonnet 4.6 is the balanced default — keeps GEPA optimization accessible to
# users on standard Claude plans, no Opus flagship required. Override with
# the --claude-model CLI flag if you want Opus or a future model.
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
SCENE_BLOCK_RE = re.compile(r"```python\s*(.+?)```", re.DOTALL)
YAML_BLOCK_RE = re.compile(r"```yaml\s*(.+?)```", re.DOTALL)
CLAUDE_CLI_TIMEOUT_S = 600


@dataclass(frozen=True)
class TransportResult:
    storyboard_path: Path | None
    scene_files: tuple[Path, ...]
    transport_error: str | None = None


class Transport(Protocol):
    def run(self, candidate: dict[str, str], topic: str, work_dir: Path) -> TransportResult: ...


def _extract_first_code_block(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text or "")
    return m.group(1).strip() if m else None


def _litellm_complete(model: str, system: str, user: str) -> str:
    """Single LLM call. Caller owns provider env (`OPENAI_API_KEY` etc.)."""
    import litellm  # imported lazily — dev-extra only
    resp = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return resp["choices"][0]["message"]["content"]


class LitellmTransport:
    """Default v1 transport: one litellm call per agent prompt."""

    def __init__(self, model: str = DEFAULT_LITELLM_MODEL, *, completer=None) -> None:
        self.model = model
        # Hook for tests to mock the LLM. Same signature as _litellm_complete.
        self._complete = completer or _litellm_complete

    def run(self, candidate: dict[str, str], topic: str, work_dir: Path) -> TransportResult:
        try:
            outline = self._complete(self.model, candidate["researcher"], f"Topic: {topic}")
            (work_dir / "outline.md").write_text(outline, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return TransportResult(None, (), f"researcher failed: {exc!s}")

        planner_input = (
            f"Topic: {topic}\n\n"
            f"Researcher outline:\n{outline}\n\n"
            "Produce the complete storyboard YAML inside one ```yaml ... ``` fence."
        )
        try:
            planner_out = self._complete(self.model, candidate["planner"], planner_input)
        except Exception as exc:  # noqa: BLE001
            return TransportResult(None, (), f"planner failed: {exc!s}")

        yaml_text = _extract_first_code_block(planner_out, YAML_BLOCK_RE)
        if not yaml_text:
            return TransportResult(None, (), "planner produced no ```yaml``` fence")
        storyboard_path = work_dir / "storyboard.yaml"
        storyboard_path.write_text(yaml_text, encoding="utf-8")

        implementer_input = (
            f"Storyboard:\n```yaml\n{yaml_text}\n```\n\n"
            "Emit one ```python``` fence per scene, in scene_NN order. "
            "Each block must be a self-contained Manim Scene subclass named Scene01, Scene02, ..."
        )
        try:
            impl_out = self._complete(self.model, candidate["implementer"], implementer_input)
        except Exception as exc:  # noqa: BLE001
            return TransportResult(storyboard_path, (), f"implementer failed: {exc!s}")

        scenes: list[Path] = []
        for idx, m in enumerate(SCENE_BLOCK_RE.finditer(impl_out), start=1):
            scene_path = work_dir / f"scene_{idx:02d}.py"
            scene_path.write_text(m.group(1).strip() + "\n", encoding="utf-8")
            scenes.append(scene_path)
        return TransportResult(storyboard_path, tuple(scenes))


def _claude_print(claude_bin: str, system: str, user: str, *, model: str = DEFAULT_CLAUDE_MODEL) -> str:
    """Single claude --print call with system + user content. Returns stdout.

    Deliberately does NOT pass --bare so Claude Code's keychain login is used.
    `--bare` requires ANTHROPIC_API_KEY which most local users don't set.

    The `model` parameter is forwarded as `claude --model <model>`. Default is
    `sonnet` so the GEPA workflow is accessible without a flagship plan.
    """
    if shutil.which(claude_bin) is None:
        raise RuntimeError(f"`{claude_bin}` not on PATH")
    # Windows CreateProcess arg-length limit is ~32K chars. The implementer
    # role's system prompt (~13KB) + a long storyboard (~10KB) easily blows
    # past it. Combine system + user and pipe via stdin so the limit never
    # bites. We lose the system/user role distinction at the LM boundary,
    # but agents already format their .md as instructions, so the effect is
    # negligible.
    cmd = [
        claude_bin,
        "--print",
        "--dangerously-skip-permissions",
        "--model", model,
    ]
    combined = f"{system}\n\n---\n\n{user}" if system else user
    proc = subprocess.run(  # noqa: S603 — explicit arg list, no shell
        cmd, input=combined, capture_output=True, text=True,
        timeout=CLAUDE_CLI_TIMEOUT_S, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude --print exit {proc.returncode}: "
            f"stderr={proc.stderr[:500]!r} stdout_tail={proc.stdout[-200:]!r}"
        )
    return proc.stdout


class ClaudeCliTransport:
    """Three `claude --print` calls per pipeline run (researcher → planner → implementer).

    Recommended for users with a Claude Code subscription — no API key required.
    The agent prompts go through `--append-system-prompt`; topic / outline /
    storyboard go in as the user message.
    """

    def __init__(self, claude_bin: str = "claude", *, model: str = DEFAULT_CLAUDE_MODEL) -> None:
        self.claude_bin = claude_bin
        self.model = model

    def _call(self, system: str, user: str) -> str:
        return _claude_print(self.claude_bin, system, user, model=self.model)

    @staticmethod
    def _run_args(run_id: str, out_dir: Path, source: str, topic: str) -> str:
        return (
            "RUN ARGS:\n"
            f"  run_id: {run_id}\n"
            f"  out_dir: {out_dir.as_posix()}\n"
            f"  source: {source}\n"
            f'  topic: "{topic}"\n'
        )

    def run(self, candidate: dict[str, str], topic: str, work_dir: Path) -> TransportResult:
        run_args = self._run_args(work_dir.name, work_dir, "idea", topic)

        researcher_user = (
            run_args
            + "\nWrite the outline body to stdout as plain markdown. Do NOT "
            "use file tools — return the outline inline; the orchestrator "
            "captures stdout and writes outline.md.\n"
        )
        try:
            outline = self._call(candidate["researcher"], researcher_user)
            (work_dir / "outline.md").write_text(outline, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return TransportResult(None, (), f"researcher (claude cli) failed: {exc!s}")

        planner_user = (
            run_args
            + "\nOutline from researcher:\n```markdown\n" + outline + "\n```\n\n"
            "Produce the complete storyboard YAML inside exactly one "
            "```yaml ... ``` fenced block. Do NOT use file tools — return "
            "the yaml inline; the orchestrator writes storyboard.yaml. "
            "Conform to schemas/storyboard.schema.json v0.2.0.\n"
        )
        try:
            planner_out = self._call(candidate["planner"], planner_user)
        except Exception as exc:  # noqa: BLE001
            return TransportResult(None, (), f"planner (claude cli) failed: {exc!s}")

        yaml_text = _extract_first_code_block(planner_out, YAML_BLOCK_RE)
        if not yaml_text:
            return TransportResult(None, (), "planner produced no ```yaml``` fence")
        storyboard_path = work_dir / "storyboard.yaml"
        storyboard_path.write_text(yaml_text, encoding="utf-8")

        implementer_user = (
            run_args
            + "\nStoryboard (canonical, validated against schema):\n"
            "```yaml\n" + yaml_text + "\n```\n\n"
            "Emit one ```python``` fenced block per scene, in scene_NN order. "
            "Each block must be a self-contained Manim Scene subclass named "
            "Scene01, Scene02, ... (one per fenced block). Do NOT use file "
            "tools — return code inline; the orchestrator writes scene_NN.py.\n"
        )
        try:
            impl_out = self._call(candidate["implementer"], implementer_user)
        except Exception as exc:  # noqa: BLE001
            return TransportResult(storyboard_path, (), f"implementer (claude cli) failed: {exc!s}")

        scenes: list[Path] = []
        for idx, m in enumerate(SCENE_BLOCK_RE.finditer(impl_out), start=1):
            scene_path = work_dir / f"scene_{idx:02d}.py"
            scene_path.write_text(m.group(1).strip() + "\n", encoding="utf-8")
            scenes.append(scene_path)
        return TransportResult(storyboard_path, tuple(scenes))


class ClaudeSubprocessTransport:
    """Path A transport — shells out to `claude --bare --print`.

    Not exercised in v1 CI. See spike-subprocess.md.
    """

    def __init__(self, *, claude_bin: str = "claude", max_budget_usd: float = 0.50) -> None:
        self.claude_bin = claude_bin
        self.max_budget_usd = max_budget_usd

    def run(self, candidate: dict[str, str], topic: str, work_dir: Path) -> TransportResult:
        agents_dir = work_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        for key in ("researcher", "planner", "implementer"):
            (agents_dir / f"manim-{key}.md").write_text(candidate[key], encoding="utf-8")
        cmd = [
            self.claude_bin, "--bare", "--print", "--dangerously-skip-permissions",
            "--max-budget-usd", f"{self.max_budget_usd:.2f}",
            "--add-dir", str(work_dir),
            "--output-format", "json",
            f"/manim-skill:manim-video --idea \"{topic}\" --out {work_dir / 'out'}",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # noqa: S603
        except (OSError, subprocess.SubprocessError) as exc:
            return TransportResult(None, (), f"claude subprocess failed: {exc!s}")
        if proc.returncode != 0:
            try:
                err = json.loads(proc.stdout or "{}").get("error", proc.stderr[:500])
            except json.JSONDecodeError:
                err = proc.stderr[:500] or "non-zero exit"
            return TransportResult(None, (), f"claude exit {proc.returncode}: {err}")
        out_dir = work_dir / "out"
        storyboard_candidates = sorted(out_dir.rglob("storyboard.yaml"))
        storyboard_path = storyboard_candidates[0] if storyboard_candidates else None
        scenes = tuple(sorted(out_dir.rglob("scene_*.py")))
        return TransportResult(storyboard_path, scenes)
