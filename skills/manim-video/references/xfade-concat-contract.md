# xfade Concat Contract

`scripts/concat-xfade.py` is the script the implementer agent calls after all
scenes render. It chains adjacent scene mp4s with ffmpeg's `xfade` (video) and
`acrossfade` (audio) filters, producing one final `video.mp4` with cross-fade
transitions instead of hard cuts.

## Invocation

```bash
python scripts/concat-xfade.py \
  --inputs scene_01.mp4 scene_02.mp4 scene_03.mp4 \
  --durations 8.0 6.0 4.0 \
  --transition-s 0.7 \
  --out out/<run>/video.mp4 \
  [--timeout 120]
```

| Flag | Required | Default | Notes |
|---|---|---|---|
| `--inputs` | yes | — | Per-scene mp4 paths in playback order. |
| `--durations` | yes | — | One float per `--inputs`; storyboard `scene.duration_s`. |
| `--transition-s` | no | 0.7 | Cross-fade duration; range 0.3–1.5. |
| `--out` | yes | — | Final video.mp4 path. Parent dir auto-created. |
| `--timeout` | no | 120 | Subprocess timeout (seconds). |

## Output JSON (stdout)

Exactly one JSON object printed to stdout. Parse it; do not parse stderr.

```json
{
  "ok": true,
  "exit_code": 0,
  "total_duration_s": 16.6,
  "command": ["ffmpeg", "-y", "-hide_banner", ...],
  "fallback_used": false,
  "stderr_tail": ""
}
```

Field semantics:

- `ok` — overall success (xfade or fallback completed).
- `exit_code` — ffmpeg's process exit code (124 on timeout, 127 on missing binary, 1 on filter error).
- `total_duration_s` — predicted total length: `sum(durations) - transition_s × (N - 1)` when xfade succeeded; `sum(durations)` when fallback was used (plain concat does not shrink).
- `command` — the argv ffmpeg was invoked with (or `["copy", ...]` for single-input shortcut).
- `fallback_used` — true when xfade was unavailable or failed and the script fell back to plain `concat` demuxer (no transitions).
- `stderr_tail` — last 50 lines of ffmpeg stderr, useful for debugging.

## Filter graph

For N inputs with durations `d_0, d_1, …, d_{N-1}` and transition `T`, the
script builds a chain:

```
[0:v][1:v]xfade=transition=fade:duration=T:offset=(d_0 - T)[v1];
[v1][2:v]xfade=transition=fade:duration=T:offset=(d_0+d_1 - 2T)[v2];
…
```

Offset for transition between scene `i` and `i+1`:

```
offset_i = sum(d_0 .. d_i) - T × (i + 1)
```

Negative offsets (when a scene is shorter than the transition) are clamped to 0.

For audio (when all inputs have at least one audio stream), an
`acrossfade=duration=T` chain runs in parallel:

```
[0:a][1:a]acrossfade=duration=T[a1];
[a1][2:a]acrossfade=duration=T[a2];
…
```

`acrossfade` is sequential — no offset needed; it consumes `T` seconds from the
end of the previous and the start of the next, mirroring `xfade`'s effect.

## Fallback semantics

The script falls back to `ffmpeg -f concat -safe 0 -i list.txt -c copy …` when:

1. `ffmpeg -filters` does not list `xfade` (older ffmpeg, <4.3).
2. The xfade run fails (filter error, encode error).

Fallback produces a video without cross-fades — hard cuts only. The implementer
agent treats this as a `DONE_WITH_CONCERNS` outcome and surfaces the warning in
`error.md` / `summary.md`.

## Single-input shortcut

When `--inputs` has exactly one entry, the script copies the file to `--out`
without invoking ffmpeg. Returns `ok: true, fallback_used: false`.

## Audio handling

`probe_has_audio(mp4)` runs `ffprobe -select_streams a -show_entries stream=codec_type`.
If any input lacks an audio stream, the script emits a video-only filter chain
(no `acrossfade`, no `-map [aN]`, no `-c:a aac`). This is the path used when
`meta.voice = null` and per-scene mp4s have no audio.

If `ffprobe` is missing from PATH, the script assumes no audio (safe default).

## Performance

Targets:
- ≤15s for a 6-scene video on the reference dev box.
- Subprocess timeout default 120s; raise via `--timeout` for very long videos.

## What this script intentionally does **not** do

- It does not modify the input mp4s.
- It does not generate captions.srt — that is `scripts/emit-captions-srt.py`.
- It does not validate `meta.transition_s` against the storyboard — the caller (implementer agent) reads `transition_s` and passes it via `--transition-s`.
- It does not stream stdout — it emits one JSON object at the end.
