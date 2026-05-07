"""Source-detection regex + arxiv id normalization."""
from __future__ import annotations

import pytest
from ingest_shared import detect_source_kind, normalize_arxiv_id


@pytest.mark.parametrize(
    "src,expected",
    [
        ("1706.03762", "arxiv"),
        ("arxiv:1706.03762v1", "arxiv"),
        ("https://arxiv.org/abs/1706.03762", "arxiv"),
        ("https://arxiv.org/pdf/1706.03762.pdf", "arxiv"),
        ("hep-ex/0307015", "arxiv"),
        ("./local.pdf", "pdf"),
        ("https://example.com/paper.pdf", "pdf"),
        ("https://example.com/paper.pdf?token=abc", "pdf"),
        ("https://en.wikipedia.org/wiki/Pythagorean_theorem", "url"),
    ],
)
def test_detect_source_kind(src: str, expected: str) -> None:
    assert detect_source_kind(src) == expected


def test_detect_unrecognized_raises() -> None:
    with pytest.raises(ValueError):
        detect_source_kind("not a url or arxiv id")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1706.03762",                          "1706.03762"),
        ("arxiv:1706.03762",                    "1706.03762"),
        ("https://arxiv.org/abs/1706.03762v3",  "1706.03762v3"),
        ("https://arxiv.org/pdf/1706.03762v2.pdf", "1706.03762v2"),
    ],
)
def test_normalize_arxiv_id(raw: str, expected: str) -> None:
    assert normalize_arxiv_id(raw) == expected
