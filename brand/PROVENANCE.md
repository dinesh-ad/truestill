# Brand artwork - provenance

Not a licence file. Nothing here is legally required; it is recorded so a future maintainer can
see what the artwork derives from.

## Source face

- **Libre Caslon Text**, version 1.100, `Copyright 2012 The Libre Caslon Text Project Authors`
- **SIL Open Font License 1.1** - <https://openfontlicense.org>
- Upstream: <https://github.com/impallari/Libre-Caslon-Text>, mirrored in `google/fonts`
- The font file itself is **not** in this repo. The product ships no font.

## Why no licence file is required

The SVGs are outlined glyphs - artwork, not Font Software. Two clauses settle it:

- **OFL 1.1, condition 5:** *"The requirement for fonts to remain under this license does not
  apply to any document created using the Font Software."*
- **OFL-FAQ 1.13:** *"creating any kind of graphic using a font under OFL does not make the
  resulting artwork subject to the OFL."*

So the artwork is Apache-2.0 with the rest of the repo, and may be used commercially.
**Reserved Font Names do not apply** - condition 3 binds *"No Modified Version of the Font
Software"* and *"only the primary font name as presented to the users"*. Separately, Libre Caslon
Text declares no Reserved Font Name at all.

**Contrast with DejaVu:** Bitstream Vera has **no** equivalent carve-out, so its notice genuinely
had to ship with the outlines derived from it. That obligation ended when those outlines left
(`8b31b03`) and **returned on 2026-08-05 for a stronger reason** - the app now bundles the DejaVu
**font files** themselves. The notice lives with them, at
`packages/truestill-app/src/truestill_app/static/fonts/LICENSE-DejaVu.txt`, because Vera binds it
to copies of the typefaces and `brand/` is not packaged. Nothing in *this* directory derives from
DejaVu.

**Not used, and deliberately:** Georgia, from the original brand sheet. It cannot be
redistributed in any format, and outlining does not end a font EULA.

## Files

- `wordmark-{light,dark}.svg` - "Truestill". **No consumer as of 2026-08-05**: the rail
  wordmark reverted to monospace text (`docs/brand.md`). Kept for a possible website header,
  not deleted, because a serif at display size is a different question from one at 18px.
- `monogram-{light,dark}.svg` - "TS", the 64px collapsed rail
- `pillar-t-{light,dark}.svg` - the T alone, for 16px where TS closes up. **Libre Caslon**, and
  still the pair the favicon's 16/24 entries are built from
- `pillar-t-geometric{,-solid}.svg` - **a different mark with a different origin.** See below
- `master-1024.png`, `icons/truestill-*.png`, `favicon.ico`

**Light and dark are authored, not filtered.** The dark variant is a different gradient chosen
for a dark ground, not a CSS filter on the light one:

- light ground: `#4C63C4` to `#2A3B8C` (the brand sheet's own)
- dark ground: `#A9B6F0` to `#7D90E6` (authored - the sheet's low stop measures **1.81:1** on the
  dark rail and is unusable there)

## The geometric pillar T - ORIGINAL ARTWORK, no font involved

`pillar-t-geometric*.svg` are **drawn, not outlined.** Every point comes from named constants in
`scripts/make_pillar_t.py`; no typeface was traced or referenced. **No font licence attaches, and
no attribution is required.**

Four files, two flags: gradient or solid paint, flute or no flute.

Stated explicitly because every other mark in this directory *is* Libre Caslon derived, and a
reader who assumes one provenance covers the folder would be wrong about this one. Asserted, not
just documented: `test_pillar_t_is_deterministic.py` fails if these files ever claim a font
origin.

**Regenerate:** `python scripts/make_pillar_t.py`. Output is pinned byte-for-byte by that same
test, so a constant cannot drift from the committed SVG. `TOP_BAR_EXTRA` is a deliberate knob -
the test pins its current value (`0`), it does not forbid changing it.

**What it supersedes: NOTHING YET.** It is an added candidate, not a replacement.

- The favicon is **unchanged**, and nothing reads these files.
  `scripts/build_brand_assets.py` *writes* `pillar-t-{light,dark}.svg` from the font and
  rasterises the ICO's small entries from the same font glyph. The geometric T is not in the
  favicon path until that script is taught to consume an SVG.
- The collapsed rail is **unchanged**; it still shows the Libre Caslon `TS` monogram.
- So the product currently carries **two different T letterforms from two different origins**.
  That is a real inconsistency and a decision the maintainer has not yet taken.

**Two measured limits, before it can replace anything:**

1. **It is a light-ground mark only.** Its ramp is `#35558F` to `#121E3F`, which is not the brand
   indigo and has no dark variant. On the dark rail `#14161b` the stops measure **2.45:1** and
   **1.11:1** - the foot is effectively invisible. Compare the Libre Caslon dark pair, authored
   for that ground at 9.17:1 and 6.04:1.

   A dark-rail variant needs **both** stops at relative luminance >= 0.124 (3:1 on the rail,
   the non-text threshold); `#5B6FCB` is the darkest usable stop at 3.95:1. Not built - the
   ramp is a design choice, not a computation.
2. **The flute needs 128px.** It is 12% of the stem, so it is sub-pixel below ~61px and only
   reaches paper white at 128. Measured as the lightest interior pixel against the darkest ink
   across the stem:

   | size | flute px | reads as |
   |---|---|---|
   | 16-28 | 0.26-0.46 | invisible |
   | 32-80 | 0.52-1.31 | grey smudge |
   | 96-128 | 1.57-2.09 | hairline |

   **Rule: use `-noflute` at 64px and below, the fluted form at 128 and above.** The cut sits
   there rather than at the measured 96 because the generated ladder is
   16/24/32/48/64/128/256/512/1024 - nothing is emitted in the ambiguous 80-112 band, so the
   threshold is unambiguous in practice. A 96px asset, if one is ever added, takes `-noflute`.

## Raster derivation

PNGs and the ICO are rasterised from the same outlines at 8x and downsampled (Lanczos), with the
gradient composited through a glyph mask. **The ICO was hand-assembled**: Pillow's ICO writer
ignores `append_images` and downsamples one image instead, which produced a single 16x16 entry
and would also have discarded the per-size artwork.

- `icons/truestill-*.png`: 16, 24, 32, 48, 64, 128, 256, 512, 1024
- `favicon.ico`: 16, 24, 32, 48, 64, 128, 256 - **16 and 24 carry the pillar T**, the rest carry
  TS. An ICO is a container of independent images, which is exactly what that difference needs.

**Re-derivable, but not from this repo alone**, because the font is not committed. Fetch Libre
Caslon Text 1.100 and re-run the authoring script recorded in the commit that added these.

## Icons carry their own ground - measured, then built

A transparent mark cannot serve both grounds. Measured on the light gradient:

| stop | white tab | dark tab (`#202124`) |
|---|---|---|
| `#4C63C4` | 5.40:1 | 2.98:1 |
| `#2A3B8C` | 9.99:1 | **1.61:1** |

Not an AA failure - a favicon is not UI text - but invisible, which is worse. So the **raster**
marks are an opaque rounded gradient tile with the glyph **knocked out**: the tile supplies the
contrast, and the knockout shows the host background through the letterform, so it reads light
on light chrome and dark on dark. Verified at 16, 24, 32 and 64 on both grounds.

**The in-app SVGs stay transparent** - they sit on surfaces we control, and the rail is dark in
both themes.

Known edge: a knockout over a *patterned* background shows the pattern through the letter. Every
place these are used - browser tab, Windows taskbar, Linux launcher - paints a solid ground, so
this has not been designed around.

## Not in this repo

`apple-touch-icon`, `mstile-*`, `site.webmanifest` - website only, per `docs/brand.md` §6.
