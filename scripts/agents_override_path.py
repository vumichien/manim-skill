"""Platform-aware override path for user-optimized agent prompts.

`scripts/optimize-prompts.py --output ...` (and the slash-command's
`--optimize` flag) write optimized agent files into a per-user override dir.
Agent resolution prefers that override over the plugin-shipped `agents/` dir.

Layout:
  Windows : %USERPROFILE%\\.manim-skill\\agents-override\\manim-*.md
  POSIX   : $XDG_CONFIG_HOME/manim-skill/agents-override/manim-*.md
            ($XDG_CONFIG_HOME defaults to $HOME/.config)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_AGENTS_DIR = REPO_ROOT / "agents"


def get_override_dir() -> Path:
    """Return the per-user override dir. Creates parents as needed."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".manim-skill"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) / "manim-skill" if xdg else Path.home() / ".config" / "manim-skill"
    return base / "agents-override"


def resolve_agent(name: str) -> Path:
    """Resolve an agent file by short name (e.g. 'manim-researcher').

    Override dir wins; plugin baseline is the fallback. Returns the plugin
    baseline path even if it does not exist (the caller surfaces that error).
    """
    if not name.endswith(".md"):
        name = name + ".md"
    override = get_override_dir() / name
    if override.exists():
        return override
    return PLUGIN_AGENTS_DIR / name


def ensure_override_dir() -> Path:
    """Create the override dir (mode 0700 on POSIX) and return it."""
    d = get_override_dir()
    d.mkdir(parents=True, exist_ok=True)
    if not sys.platform.startswith("win"):
        try:
            d.chmod(0o700)
        except OSError:
            pass  # best-effort; caller can tighten later
    return d
