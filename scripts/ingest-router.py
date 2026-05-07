#!/usr/bin/env python3
"""Dispatch <source> to the right ingestor (arxiv | pdf | url).

Usage:
  python scripts/ingest-router.py <source> [--out OUT_DIR]

Source detection (priority order):
  1. Ends in `.pdf` (or has `.pdf` in URL path)  → ingest-pdf.py
  2. Matches arXiv id pattern OR arxiv.org URL    → ingest-arxiv.py
  3. http(s)://...                                → ingest-url.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ingest_shared import detect_source_kind  # noqa: E402

# Re-import sibling ingestors as functions so we stay in-process (single venv).
import importlib.util  # noqa: E402


def _load_module(filename: str, alias: str):
    """Load a kebab-named sibling script as an importable module."""
    path = Path(__file__).parent / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", help="arXiv id, PDF path/URL, or HTML URL.")
    ap.add_argument("--out", type=Path, default=Path("out/run"))
    args = ap.parse_args()

    try:
        kind = detect_source_kind(args.source)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"==> source kind: {kind}", file=sys.stderr)
    try:
        if kind == "arxiv":
            mod = _load_module("ingest-arxiv.py", "ingest_arxiv")
            md_path = mod.fetch_arxiv(args.source, args.out)
        elif kind == "pdf":
            mod = _load_module("ingest-pdf.py", "ingest_pdf")
            md_path = mod.fetch_pdf(args.source, args.out)
        else:  # url
            mod = _load_module("ingest-url.py", "ingest_url")
            md_path = mod.fetch_url(args.source, args.out)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {kind} ingest failed: {exc}", file=sys.stderr)
        return 1

    print(md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
