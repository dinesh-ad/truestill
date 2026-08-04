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

**Contrast with DejaVu** (`LICENSE-DejaVu.txt`, superseded): Bitstream Vera has **no** equivalent
carve-out, so its notice genuinely had to ship with the outlines derived from it.

**Not used, and deliberately:** Georgia, from the original brand sheet. It cannot be
redistributed in any format, and outlining does not end a font EULA.

## Files

- `wordmark-{light,dark}.svg` - "Truestill", expanded sidebar and website header
- `monogram-{light,dark}.svg` - "TS", the 64px collapsed rail
- `pillar-t-{light,dark}.svg` - the T alone, for 16px where TS closes up
- `master-1024.png`, `icons/truestill-*.png`, `favicon.ico`

**Light and dark are authored, not filtered.** The dark variant is a different gradient chosen
for a dark ground, not a CSS filter on the light one:

- light ground: `#4C63C4` to `#2A3B8C` (the brand sheet's own)
- dark ground: `#A9B6F0` to `#7D90E6` (authored - the sheet's low stop measures **1.81:1** on the
  dark rail and is unusable there)

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

## Known limitation - transparent icons on dark chrome

Measured, so it is a known state rather than a surprise:

| stop | white tab | dark tab (`#202124`) |
|---|---|---|
| `#4C63C4` | 5.40:1 | 2.98:1 |
| `#2A3B8C` | 9.99:1 | **1.61:1** |

A transparent mark in the light gradient is close to invisible on a dark browser tab. Inherent
to a transparent icon: one colour cannot serve both grounds.

**The remedy, not built:** give the raster icons an opaque gradient **tile** with the mark
knocked out, so the host background stops mattering. That is what app icons normally do, and it
would replace the transparent PNG for installers. Not done here because the brief asked for
transparent PNGs; raise it if the dark-tab case matters.

## Not in this repo

`apple-touch-icon`, `mstile-*`, `site.webmanifest` - website only, per `docs/brand.md` §6.
