# Changelog

All notable changes documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-05-07

### Added
- Initial public release.
- 4-role agent pipeline: `manim-researcher`, `manim-planner` (skeleton + final modes), `manim-implementer`. Agents shipped as documents under `agents/`; the skill body spawns generic Task subagents with the doc contents as system prompts.
- Slash command `/manim-video` with mode flags (`--idea`, `--paper`, `--math`), output flags (`--out`, `--quality`, `--storyboard-only`), and `--voice [gtts|openai|elevenlabs]`.
- Storyboard YAML schema (Draft 2020-12) at `schemas/storyboard.schema.json` and validator at `scripts/validate-storyboard.py`. Cross-checks: target/name resolution, duration sum, contiguous scene IDs.
- Source-aware ingest: `arxiv` (id or URL), `pymupdf4llm` (local + remote PDF), `trafilatura` (HTML pages with readability-lxml fallback).
- Render runner `scripts/render.py` — single-shot subprocess wrapper around `python -m manim render`, returning structured JSON with `error_class` heuristics (`latex` / `import` / `name` / `type` / `timeout` / `other`).
- Install bootstrap: `scripts/install.ps1` (Windows-first) and `scripts/install.sh` (POSIX). Detects pycairo native-build failure and prints two-path remediation (MSVC Build Tools or Conda).
- Five reference samples covering 2D, 3D, math (LaTeX), plot, and text-morph patterns. Each with `storyboard.yaml`, hand-coded `scene.py`, README, and a build script (`samples/build-samples.{ps1,sh}`) to populate `out.mp4` + `thumb.png` after install.
- Hand-crafted SVG logo + dark-mode variant in `assets/`.
- Test suite (40 tests, ~2s) covering: storyboard validation (positive + 3 broken fixtures), source-detection regex, plugin manifest schema/reserved-name guard, render-runner JSON contract + error classifier, sample integrity (every storyboard validates, every scene compiles).
- GitHub Actions CI on Ubuntu (`ruff` + `pytest -m "not requires_manim and not slow"` + manim-installed dry-run smoke).
- Documentation: README (with hero, badges, Mermaid pipeline diagram, samples grid), tech-stack, design-guidelines, contributing, release procedure.

### Known limitations
- LaTeX (xelatex) is optional. Without it, `MathTex` renders empty silently — sample 03 (Fourier math) is the only sample that requires it.
- `--paper` accepts a single source per invocation; multi-source is deferred to v0.2.
- Windows CI is not part of the matrix yet — Ubuntu only. Windows installs are tested manually.
- The implementer agent retry budget is fixed at 5 per scene; it is not user-tunable in v0.1.

### Security
- All HTTP fetches use explicit `timeout=30`. HTTPS enforced for URLs.
- `.env` ignored at repo level; install scripts never persist API keys.
- `subprocess.run` calls use explicit arg lists; no shell.

[Unreleased]: https://github.com/vumichien/manim-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vumichien/manim-skill/releases/tag/v0.1.0
