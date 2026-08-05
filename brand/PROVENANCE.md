# Brand artwork - provenance

Not a licence file. Nothing here is legally required; it is recorded so a future maintainer can
see what the artwork derives from.

## One mark: the geometric pillar T

`pillar-t-geometric*.svg` is **drawn, not outlined**. Every point comes from named constants in
`scripts/make_pillar_t.py`; no typeface was traced or referenced. **No font licence attaches and
no attribution is required.** Four files, two flags: gradient or solid paint, flute or no flute.

**It is the only mark in the product.** The rail shows it when collapsed, the browser tab and
every icon size are built from it, and the installer icons will be. There is no TS monogram.

**Regenerate:** `python scripts/make_pillar_t.py` for the SVGs,
`uv run --with pillow python scripts/build_brand_assets.py` for the icons and the ICO - **no font
needed for either.** Output is pinned byte-for-byte by `test_pillar_t_is_deterministic.py`.
`TOP_BAR_EXTRA` is a deliberate knob; the test pins its current value, it does not freeze it.

**The flute needs 128px.** It is 12% of the stem, sub-pixel below ~61px, and only reaches paper
white at 128. **Rule: `-noflute` at 64 and below, fluted at 128 and above.** The measured
crossover is 96, but the generated ladder is 16/24/32/48/64/128/256/512/1024 and nothing lands in
the ambiguous 80-112 band.

**On the rail it is flat, not the authored ramp.** The ramp's stops measure 2.45:1 and 1.11:1 on
`#14161b`, so the foot disappears; the rail draws it in `--rail-accent` (9.17:1). Same answer the
wordmark reached on the same ground. A dark-ground *ramp* is still unauthored - it would need
both stops at relative luminance >= 0.124, and `#5B6FCB` is the darkest usable stop at 3.95:1.

**On icons it is knocked out of an opaque tile.** A transparent mark in the light gradient
measures 1.61:1 on a dark browser tab. The tile carries the contrast and the letterform shows the
host background through itself, so one asset reads on light chrome and dark. Known edge: over a
*patterned* background the pattern shows through the letter. Every place these are used paints a
solid ground.

## Colour

| ground | ramp |
|---|---|
| light | `#4C63C4` to `#2A3B8C` (the brand sheet's own) |
| dark | `#A9B6F0` to `#7D90E6` (authored - the sheet's low stop is 1.81:1 on the rail) |

## Nothing Libre Caslon derived is in use

**As of 2026-08-05, no shipped surface renders anything outlined from a font.** The monogram and
the Libre Caslon `pillar-t-{light,dark}.svg` were deleted rather than left to confuse a reader
with a second letterform of the same letter.

`wordmark-{light,dark}.svg` survives with **no consumer**, kept for a possible website header
where a serif at display size is a different question from a serif at 18px in a rail. It is the
only thing `build_brand_assets.py` still needs a font for, and only when one is passed:

- **Libre Caslon Text** 1.100, `Copyright 2012 The Libre Caslon Text Project Authors`, SIL OFL 1.1
- OFL condition 5 and OFL-FAQ 1.13 put artwork outside the licence, so no notice is required and
  no Reserved Font Name applies
- **Not Georgia**, deliberately: it cannot be redistributed in any format, and outlining does not
  end a font EULA

**DejaVu is a separate matter.** Bitstream Vera has no OFL-style carve-out, and the app bundles
the DejaVu **font files**, so its notice ships with them at
`packages/truestill-app/src/truestill_app/static/fonts/LICENSE-DejaVu.txt`. Nothing in *this*
directory derives from DejaVu.

## Raster derivation

PNGs and the ICO are rasterised from the SVG at 8x and downsampled (Lanczos). The path is
flattened to polygons in `build_brand_assets.py` - no browser, no SVG library.

- `icons/truestill-*.png`: 16, 24, 32, 48, 64, 128, 256, 512, 1024
- `favicon.ico`: 16, 24, 32, 48, 64, 128, 256. **Hand-assembled**, because Pillow's ICO writer
  ignores `append_images` and downsamples one image instead - which produced a single 16x16 entry
  and would have discarded the per-size artwork.

## Not in this repo

`apple-touch-icon`, `mstile-*`, `site.webmanifest` - website only, per `docs/brand.md` §6.
