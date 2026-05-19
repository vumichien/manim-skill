"""Phase 08 — Valset hash gate.

Recomputes SHA256 over `tests/gepa/valset.yaml` + each
`samples/0N/storyboard.yaml` (in numeric order) and compares against
`tests/gepa/.valset.sha256`. Fails loudly with the override instruction.

This guard catches accidental drift of the regression-guard inputs. To
INTENTIONALLY change the valset:

  1. Run `python -c "exec(open('tests/gepa/.valset_recompute.py').read())"` or
     re-run the inline hash recipe below in a PR.
  2. Update `tests/gepa/.valset.sha256` with the new hash in the same PR.
  3. Apply the GitHub label `samples-valset-update` to the PR. CI then accepts
     the change (workflow checks the label before failing on hash diff).

Hash recipe (copy/paste, no exec):

    import hashlib, pathlib
    h = hashlib.sha256()
    for p in [pathlib.Path('tests/gepa/valset.yaml'),
              *sorted(pathlib.Path('samples').glob('0?-*/storyboard.yaml'))]:
        h.update(p.read_bytes())
    print(h.hexdigest())
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
HASH_FILE = REPO / "tests" / "gepa" / ".valset.sha256"
VALSET_YAML = REPO / "tests" / "gepa" / "valset.yaml"


def _compute_hash() -> str:
    h = hashlib.sha256()
    files = [VALSET_YAML] + sorted((REPO / "samples").glob("0?-*/storyboard.yaml"))
    for p in files:
        h.update(p.read_bytes())
    return h.hexdigest()


def test_valset_hash_matches_pinned() -> None:
    expected = HASH_FILE.read_text(encoding="utf-8").strip()
    actual = _compute_hash()
    assert actual == expected, (
        f"valset hash drift: expected {expected}, got {actual}.\n"
        "If intentional: update tests/gepa/.valset.sha256 AND add the "
        "`samples-valset-update` label to the PR. Otherwise revert the change."
    )
