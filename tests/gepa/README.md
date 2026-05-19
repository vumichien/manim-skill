# GEPA trainset & valset

Inputs for `scripts/optimize-prompts.py` (phase 06).

## Files

- `trainset.yaml` — 30 hand-curated topics GEPA reflects against.
- `valset.yaml` — pointers to `samples/01-06` storyboards (untouched).
- `.valset.sha256` — hash gate from phase 08 (added by that phase).

## Curation rules

- **No overlap with valset.** Trainset must not duplicate any concept covered
  by `samples/01-06` (Pythagoras, rotating cube, Fourier series, quadratic
  plot, text morph, sine-wave tracker). Overlap = leak between train and val.
- **Diversity targets:**
  - Mode mix: ~40% `--idea`, 30% `--math`, 30% `--paper`.
  - Difficulty: ~40% easy, 40% medium, 20% hard.
  - Domain: ≥ 8 math, ≥ 5 cs, ≥ 5 physics, plus at least 3 in other domains
    (bio, finance, statistics, etc.).
- **No PII, no copyrighted prose.** Topics are paraphrased common-knowledge
  references. Paper IDs are public arXiv, and we ship only the ID — never
  the full text.
- **Refresh cadence:** rotate quarterly. Each refresh, swap 5-8 entries so
  candidates can't memorize the trainset across runs.

## Entry shape

```yaml
- id: 07-eigenvectors
  mode: math                       # idea | math | paper
  input: "..."                     # the topic string sent to the pipeline
  difficulty: medium               # easy | medium | hard
  domain: math                     # math | cs | physics | bio | finance | stats | other
  expected_traits: "..."           # free-text reviewer notes, NOT scored
```

`expected_traits` is intentionally not part of the metric — it's a hint for
the human reviewer eyeballing a Pareto candidate.

## Current stats

30 entries — see `trainset.yaml` and `valset.yaml` for the canonical
breakdown. Curator: vumichien.
