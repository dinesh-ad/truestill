# The design system - what every screen is built against

**Written 2026-09-04 (P219).** `.scratch/organize-preview/` is the **style** reference - the
maintainer's words, *"just a style of design, how it looks, that's it"* - and its source is kept
at [`research/organize-preview/`](research/organize-preview/). **This document is the
specification.** Where the two differ, this wins, and section 6 is the one place they differ.

⚠ **The look is translucency, a hairline and a shadow over a gradient. It does NOT depend on
`backdrop-filter`**, which WebKit reports as supported and does not paint - `(ake)`. Read that
entry before adding blur to anything.

## 1. The canvas is a prerequisite, not decoration

Glass is invisible on flat white and `--bg` is `#faf8f5`, so the canvas gains tonal range for a
translucent surface to be translucent *against*. It stays in the warm family
`test_palette_and_resting_panel.py` pins - *"the neutrals are WARM"* - and adds **no second
accent**: the third stop is the existing `--accent` hue at whisper saturation.

```css
--canvas-from: #faf8f5;   /* today's --bg unchanged, so the top-left is the app people know */
--canvas-mid:  #f1ebe1;   /* warm sand */
--canvas-to:   #e8e9f3;   /* the accent hue, desaturated to a whisper */
--canvas: linear-gradient(135deg, var(--canvas-from), var(--canvas-mid) 45%, var(--canvas-to));
```

Every text token clears AA against the **worst** stop, computed rather than assumed:

| token | worst stop | ratio |
|---|---|---|
| `--fg` | `--canvas-to` | 14.37:1 |
| `--accent-strong` | `--canvas-to` | 8.27:1 |
| `--fg-secondary` | `--canvas-to` | 5.88:1 |
| `--fg-muted` | `--canvas-to` | **4.68:1** |

## 2. Glass tokens

```css
--glass-bg:     rgba(255, 255, 255, 0.62);
--glass-border: rgba(255, 255, 255, 0.72);
--glass-shadow: 0 8px 32px rgba(28, 26, 23, 0.08);
--glass-blur:   14px;     /* enhancement only - section 5 */
```

**Contrast is computed against the COMPOSITE, never against the glass colour.** White at 0.62 over
`--canvas-to` composites to `#f6f6fb`, against which the weakest text token `--fg-muted` measures
**5.30:1**. Every alpha from 0.45 to 0.80 clears 4.5:1; **0.45 is the floor**, 0.62 is chosen.

## 3. The surface table

The production rule is *glass on overlays, navigation and highlight areas; solid for extended
reading or forms* - and these screens are mostly forms. **Two columns, because the look and the
blur are separable and only one of them is risky.**

| surface | glass look | `backdrop-filter` | why |
|---|---|---|---|
| the rail | no | no | opaque dark, theme-independent, on the window edge - nothing behind it to show through |
| resting panel | **yes** | **yes** | a highlight area, not a form; over the canvas; nothing is typed into it |
| modal scrim (picker) | **yes** | **yes** | an overlay, the canonical case |
| main content card | **yes** | **no** | it holds the form - section 6 |
| mode option cards | **yes** | no | controls, read while choosing |
| Browse / secondary buttons | **yes** | no | the preview's `bg-white/80` |
| form fields, inputs, selects | no | no | solid `--surface`, always |
| tables | no | no | extended reading, dense rows |
| notices, banners, rail alert | no | no | they carry warnings; legibility is the entire job |

**At most two blurred layers exist by construction** - the panel and the scrim - and they are
never nested, because the scrim covers the panel rather than containing it.

## 4. Hard limits, and what enforces each

| limit | enforced by |
|---|---|
| at most two blurred layers, never nested | the table above is the whole permitted set |
| text >= 4.5:1, large >= 3:1, against the **composite** | the tokens in section 2, computed above |
| glass only over a **known** backdrop | glass is permitted over `--canvas` only; contrast cannot be computed against arbitrary content, so glass over content is refused |
| a fallback that actually fires | **not `@supports`** - section 5 |

## 5. Solid-first, and why the fallback is not `@supports`

⚠ **`@supports (backdrop-filter: blur(1px))` cannot be the fallback: WebKit answers `true` and
paints nothing** (`(ake)`). A design leaning on that guard ships a surface that vanishes for Linux
users while every check reports success.

> **Every glass surface must be complete, legible and correct with `backdrop-filter` doing
> nothing.** The blur is added on top and changes nothing that matters.

This is testable on the engine with the gap: **the WebKit half of the browser lane renders the
solid-first design, so a screenshot assertion there is asserting the fallback.** That is the only
arrangement where the fallback is not taken on trust.

## 6. ⚠ Where glass is refused even if asked - and the one departure from the preview

**Never behind a form field, and never behind text a person reads while typing.**

🔑 **The reason, and it is the strongest rule in this document: a path is checked character by
character, and a wrong one moves the wrong files.** A blurred, moving backdrop under an input
while someone is reading back `/home/you/Pictures/Truestill` is the case this project would regret
most, on the two screens - Organize and Settings - where that text decides where someone's
photographs go.

**The preview puts `backdrop-blur-2xl` on the form card.** This is the one place the
specification departs from it, and the departure is narrow: **the card keeps the look -
`--glass-bg`, the hairline, the shadow - and drops the blur.** Over this canvas that is a measured
difference of nearly nothing, and it removes the only case where a moving backdrop sits under a
path being typed.

**Also refused**: glass on notices - a warning that is harder to read is a worse warning - glass
over tables, and any nested glass.

## 7. What this does not cover

The preview designs **one** screen; the other six are `PlaceholderMain`. This document fixes the
**canvas, the surfaces and the floors**. **Per-screen composition is not covered**, and that is
where a specification quietly becomes a reference again. What Organize establishes for the others,
and what each still needs decided, is in [`react-migration-plan.md`](react-migration-plan.md).
