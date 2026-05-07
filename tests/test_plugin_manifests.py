"""marketplace.json + plugin.json: parseable, name kebab-case, owner present."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_marketplace_json_parseable() -> None:
    mkt = _load(REPO / ".claude-plugin" / "marketplace.json")
    assert "name" in mkt and "owner" in mkt and "plugins" in mkt
    assert KEBAB_RE.match(mkt["name"]), f"marketplace name not kebab-case: {mkt['name']}"
    assert mkt["plugins"], "plugins array must not be empty"
    plugin = mkt["plugins"][0]
    assert plugin["name"] == "manim-skill"
    assert plugin["source"] in (".", "./")


def test_marketplace_name_not_reserved() -> None:
    mkt = _load(REPO / ".claude-plugin" / "marketplace.json")
    reserved = {
        "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
        "anthropic-marketplace", "anthropic-plugins", "agent-skills",
        "knowledge-work-plugins", "life-sciences",
    }
    assert mkt["name"] not in reserved


def test_plugin_json_parseable() -> None:
    plg = _load(REPO / ".claude-plugin" / "plugin.json")
    assert plg["name"] == "manim-skill"
    assert KEBAB_RE.match(plg["name"])
    assert plg["license"] == "Apache-2.0"
    assert plg["version"]


def test_plugin_keywords_present() -> None:
    plg = _load(REPO / ".claude-plugin" / "plugin.json")
    kws = plg.get("keywords", [])
    assert "manim" in kws and "animation" in kws
