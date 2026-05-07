#!/usr/bin/env python3
"""Fetch an arXiv paper and emit a unified `source.md`.

Usage:
  python scripts/ingest-arxiv.py <id-or-url> [--out OUT_DIR]

Exits 0 on success (prints path to source.md), 1 on failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Sibling import — scripts/ is added to sys.path explicitly to avoid relying on cwd.
sys.path.insert(0, str(Path(__file__).parent))
from ingest_shared import (  # noqa: E402
    normalize_arxiv_id,
    retry,
    utc_now_iso,
    write_source_md,
)


def fetch_arxiv(arxiv_id: str, out_dir: Path) -> Path:
    import arxiv  # imported lazily so --help works without deps installed
    import pymupdf4llm

    out_dir.mkdir(parents=True, exist_ok=True)
    norm_id = normalize_arxiv_id(arxiv_id)

    client = arxiv.Client(delay_seconds=3.0, num_retries=3, page_size=1)
    search = arxiv.Search(id_list=[norm_id])
    paper = retry(lambda: next(client.results(search)))

    pdf_path = out_dir / "source.pdf"
    if not pdf_path.exists():
        retry(lambda: paper.download_pdf(dirpath=str(out_dir), filename="source.pdf"))

    body_md = pymupdf4llm.to_markdown(str(pdf_path))
    meta = {
        "source_type": "arxiv",
        "source_ref": arxiv_id,
        "arxiv_id": norm_id,
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "abstract": paper.summary,
        "primary_category": paper.primary_category,
        "published": paper.published.isoformat() if paper.published else None,
        "fetched_at": utc_now_iso(),
    }
    return write_source_md(out_dir, body_md, meta)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("arxiv", help="arXiv id (e.g. 1706.03762) or URL.")
    ap.add_argument("--out", type=Path, default=Path("out/run"))
    args = ap.parse_args()

    try:
        md_path = fetch_arxiv(args.arxiv, args.out)
    except Exception as exc:  # noqa: BLE001
        print(f"error: arxiv ingest failed: {exc}", file=sys.stderr)
        return 1
    print(md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
