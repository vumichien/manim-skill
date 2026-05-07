# Voiceover text style guide (schema 0.2.0)

`voiceover_text` is **required** on every scene since 0.2.0. It drives both the
TTS narration (when `meta.voice ≠ null`) and the auto-chunked on-screen captions
(always). Get it wrong and viewers see captions that don't match the action.

## Length math

Aim for ≤2.5 words per second of `duration_s`. So:

| `duration_s` | target words | hard ceiling |
|---|---|---|
| 4 | 8–10 | 12 |
| 6 | 12–15 | 18 |
| 8 | 16–20 | 24 |
| 12 | 25–30 | 36 |

Validator floor is 5 words. Below that, captions feel empty.

## Tone

- **Educational, present tense, declarative.** "A right triangle appears." Not
  "We will see a triangle that we are going to use."
- **No jargon without immediate definition.** "The Hessian — the matrix of second
  derivatives — measures curvature."
- **Active subject, simple verb.** "The vector rotates." Not "Rotation is applied
  to the vector by a transformation."

## Structure

A scene's narration usually has three beats, even if you write it as one
sentence:

1. **What appears** (matches the first animation)
2. **What it means** (the key insight for this beat)
3. **What it sets up** (callback to the next scene)

Example for a 6s scene introducing a sine wave:

> "A sine wave appears on the axes. Its amplitude is the height of each peak.
> The next scene varies that amplitude with a slider."

## Captions field — when to populate

`scene.captions[]` is **almost always empty**. The implementer auto-chunks the
voiceover_text into on-screen captions at runtime. Only populate `captions[]`
when:

- A specific word must coincide with a specific animation (e.g. "**rotates**" must
  appear exactly when the rotation animation plays).
- Auto-chunking would split on a critical word ("the **derivative** of x squared"
  — keep "derivative" intact).

Format:

```yaml
captions:
  - { text: "A right triangle appears", start_s: 0.0, duration_s: 2.0 }
  - { text: "Legs labeled a and b",    start_s: 2.0, duration_s: 2.0 }
```

If you populate captions, their cumulative end time should not exceed
`scene.duration_s` (validator emits a warning, not error).

## Good / bad examples

| Bad | Why | Good |
|---|---|---|
| "Stuff happens." | < 5 words; meaningless | "A right triangle appears with sides a, b, c labeled." |
| "We are now going to draw the right triangle that we will use throughout this video to demonstrate the theorem." | Too long, future tense | "Draw the right triangle. Legs a and b sit at right angles; c is the hypotenuse." |
| "MathTex displays a^2 + b^2 = c^2 on the axes." | Names the API, not the meaning | "The squared sum of the legs equals the squared hypotenuse." |

## Common pitfalls

- **Past tense** (e.g. "the triangle appeared") — captions trail the animation.
  Use present.
- **Pronoun without antecedent** ("**It** rotates clockwise") — captions appear
  out of context when chunked. Repeat the noun.
- **Reading the formula symbol-by-symbol** ("a squared plus b squared equals c
  squared") — fine sparingly; tedious if every scene does it.
