#!/usr/bin/env python3
"""Extract a PDF (local path or URL) into unified `source.md`.

Usage:
  python scripts/ingest-pdf.py <path-or-url> [--out OUT_DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ingest_shared import retry, utc_now_iso, write_source_md  # noqa: E402

REQUEST_TIMEOUT_S = 30


def fetch_pdf(source: str, out_dir: Path) -> Path:
    import pymupdf4llm

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "source.pdf"

    if source.startswith(("http://", "https://")):
        if not pdf_path.exists():
            import requests

            def _download() -> None:
                resp = requests.get(source, timeout=REQUEST_TIMEOUT_S, stream=True)
                resp.raise_for_status()
                with open(pdf_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)

            retry(_download)
    else:
        local = Path(source).expanduser().resolve()
        if not local.exists():
            raise FileNotFoundError(local)
        if local != pdf_path:
            pdf_path.write_bytes(local.read_bytes())

    body_md = pymupdf4llm.to_markdown(str(pdf_path))
    meta = {
        "source_type": "pdf",
        "source_ref": source,
        "title": _guess_title(body_md),
        "authors": [],
        "fetched_at": utc_now_iso(),
        "byte_size": pdf_path.stat().st_size,
    }
    return write_source_md(out_dir, body_md, meta)


def _guess_title(md: str, fallback: str = "Untitled PDF") -> str:
    """First non-empty line of extracted markdown is usually the title."""
    for line in md.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:200]
    return fallback


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", help="Local path or http(s) URL to a PDF.")
    ap.add_argument("--out", type=Path, default=Path("out/run"))
    args = ap.parse_args()

    try:
        md_path = fetch_pdf(args.source, args.out)
    except Exception as exc:  # noqa: BLE001
        print(f"error: pdf ingest failed: {exc}", file=sys.stderr)
        return 1
    print(md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
