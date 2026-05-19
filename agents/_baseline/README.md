# Baseline agents — DO NOT EDIT

Frozen pre-GEPA originals of `agents/manim-{researcher,planner,implementer}.md`.

These files exist so that:

- `scripts/optimize-prompts.py` can use them as the **seed candidate** for GEPA.
- Maintainers can `diff agents/<name>.md agents/_baseline/<name>.md` to review
  every optimization-induced change before merging.
- A bad optimization run can be rolled back with `cp agents/_baseline/* agents/`.

Refresh policy: only update these files in a separate, explicit commit when
the upstream pipeline itself materially changes (e.g. schema bump, new
storyboard contract). Never let an optimization run overwrite them.
