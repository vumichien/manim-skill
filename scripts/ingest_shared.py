#!/usr/bin/env python3
"""Shared helpers for ingest-{arxiv,pdf,url,router}.py.

Imported as a module by sibling scripts; not meant to be run directly.
File name uses kebab-case to match the rest of the scripts/ folder; we expose
underscore-named symbols for Python imports.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar

T = TypeVar("T")
SourceKind = Literal["arxiv", "pdf", "url"]

ARXIV_ID_RE = re.compile(r"^(?:arxiv:)?([\d]{4}\.[\d]{4,5}(v\d+)?|[a-z\-]+/\d{7}(v\d+)?)$", re.I)
PDF_SUFFIX_RE = re.compile(r"\.pdf(\?.*)?$", re.I)


def detect_source_kind(s: str) -> SourceKind:
    """Classify input as arxiv-id | pdf | url.

    Priority:
      1. arxiv URLs (abs/ or pdf/) — even if ending .pdf, we want metadata enrichment
      2. arxiv id pattern
      3. .pdf suffix
      4. http(s) URL
    """
    s = s.strip()
    if "arxiv.org/abs/" in s or "arxiv.org/pdf/" in s:
        return "arxiv"
    if ARXIV_ID_RE.match(s):
        return "arxiv"
    if PDF_SUFFIX_RE.search(s) or (Path(s).suffix.lower() == ".pdf"):
        return "pdf"
    if s.startswith(("http://", "https://")):
        return "url"
    raise ValueError(f"Cannot classify source: {s!r}")


def normalize_arxiv_id(raw: str) -> str:
    """Strip `arxiv:` prefix, trailing version, URL wrappers, etc."""
    raw = raw.strip()
    raw = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", raw, flags=re.I)
    raw = re.sub(r"\.pdf$", "", raw, flags=re.I)
    raw = re.sub(r"^arxiv:", "", raw, flags=re.I)
    return raw


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id(slug: str) -> str:
    ts = _dt.datetime.now().strftime("%y%m%d-%H%M")
    safe = re.sub(r"[^\w\-]", "-", slug.lower())[:40].strip("-") or "run"
    return f"{ts}-{safe}"


def retry(fn: Callable[[], T], attempts: int = 3, base_delay: float = 1.0) -> T:
    """Call fn() with exponential backoff on Exception."""
    last: Exception | None = None
    for n in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — retry on any exception
            last = exc
            if n < attempts - 1:
                time.sleep(base_delay * (2 ** n))
    assert last is not None
    raise last


def write_source_md(out_dir: Path, body_md: str, meta: dict[str, Any]) -> Path:
    """Write `source.md` (frontmatter + body) and `source.meta.json` (full meta)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "source.md"
    json_path = out_dir / "source.meta.json"

    fm_lines = ["---"]
    for key in ("source_type", "source_ref", "title", "authors", "fetched_at"):
        if key not in meta:
            continue
        val = meta[key]
        if isinstance(val, list):
            fm_lines.append(f"{key}: {json.dumps(val, ensure_ascii=False)}")
        else:
            fm_lines.append(f"{key}: {json.dumps(str(val), ensure_ascii=False)}")
    fm_lines.append("---\n")
    md_path.write_text("\n".join(fm_lines) + body_md, encoding="utf-8")
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path


def safe_filename(s: str, max_len: int = 60) -> str:
    return re.sub(r"[^\w\-]+", "_", s).strip("_")[:max_len] or "untitled"
