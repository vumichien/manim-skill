#!/usr/bin/env python3
"""Post-install verification: import every required dep and report.

Exit 0 if all imports succeed, 1 if any fails. Output one line per dep
so install scripts can grep for FAIL.
"""
from __future__ import annotations

import importlib
import io
import shutil
import subprocess
import sys

# Force UTF-8 stdout so we can print non-ASCII safely on cp932 (Japanese)
# and other narrow locales used by Windows users.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation):
        pass

# Module name → human label. Some PyPI distributions install under a different
# importable name (e.g. PyYAML → yaml), so we list the *import* name here.
DEPS: list[tuple[str, str]] = [
    ("manim", "Manim Community"),
    ("manim_voiceover", "manim-voiceover"),
    ("arxiv", "arxiv"),
    ("pymupdf4llm", "pymupdf4llm"),
    ("trafilatura", "trafilatura"),
    ("requests", "requests"),
    ("yaml", "PyYAML"),
    ("jsonschema", "jsonschema"),
]


def check_imports() -> list[str]:
    failed: list[str] = []
    for mod, label in DEPS:
        try:
            importlib.import_module(mod)
            print(f"OK    {label}")
        except ImportError as exc:
            print(f"FAIL  {label}: {exc}")
            failed.append(label)
    return failed


def check_xelatex() -> None:
    """Optional check: xelatex is required only for MathTex/Tex."""
    if shutil.which("xelatex") is None:
        print("WARN  xelatex not on PATH -- MathTex/Tex will render empty.")
        return
    try:
        out = subprocess.check_output(
            ["xelatex", "--version"], text=True, stderr=subprocess.STDOUT, timeout=5
        ).splitlines()[0]
        print(f"OK    LaTeX: {out}")
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"WARN  xelatex present but errored: {exc}")


def main() -> int:
    failed = check_imports()
    check_xelatex()
    if failed:
        print(f"\n{len(failed)} module(s) failed to import: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("\nAll required modules imported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
