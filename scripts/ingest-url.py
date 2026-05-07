#!/usr/bin/env python3
"""Extract main content of an HTML page into unified `source.md`.

Primary: trafilatura (markdown output).
Fallback: readability-lxml when trafilatura returns <500 chars.

Usage:
  python scripts/ingest-url.py <url> [--out OUT_DIR]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ingest_shared import retry, utc_now_iso, write_source_md  # noqa: E402

MIN_BODY_CHARS = 500
REQUEST_TIMEOUT_S = 30


def fetch_url(url: str, out_dir: Path) -> Path:
    import trafilatura

    out_dir.mkdir(parents=True, exist_ok=True)

    def _fetch() -> str | None:
        return trafilatura.fetch_url(url)

    raw = retry(_fetch)
    if not raw:
        raise RuntimeError(f"trafilatura.fetch_url returned empty for {url}")

    body_md = trafilatura.extract(
        raw, output_format="markdown", include_links=True, with_metadata=False
    ) or ""
    title = _extract_title(raw) or "Untitled page"

    if len(body_md) < MIN_BODY_CHARS:
        body_md = _readability_fallback(raw, body_md)

    meta = {
        "source_type": "url",
        "source_ref": url,
        "title": title,
        "authors": [],
        "fetched_at": utc_now_iso(),
        "extracted_chars": len(body_md),
    }
    return write_source_md(out_dir, body_md, meta)


def _extract_title(html: str) -> str | None:
    # Prefer <title>, then og:title.
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return _strip(m.group(1))[:200]
    m = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE
    )
    if m:
        return _strip(m.group(1))[:200]
    return None


def _readability_fallback(html: str, prior: str) -> str:
    try:
        from readability import Document  # readability-lxml
    except ImportError:
        return prior  # extra not installed; keep prior
    try:
        summary_html = Document(html).summary()
        return _html_to_text(summary_html)
    except Exception:  # noqa: BLE001
        return prior


def _html_to_text(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return _strip(text)


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("--out", type=Path, default=Path("out/run"))
    args = ap.parse_args()

    if not args.url.startswith(("http://", "https://")):
        print("error: url must start with http:// or https://", file=sys.stderr)
        return 1

    try:
        md_path = fetch_url(args.url, args.out)
    except Exception as exc:  # noqa: BLE001
        print(f"error: url ingest failed: {exc}", file=sys.stderr)
        return 1
    print(md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
