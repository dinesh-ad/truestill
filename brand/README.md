# Brand assets

The one directory for authored brand artwork. `docs/brand.md` is the reference - the wordmark,
the mark, the indigo gradient and, importantly, **which surfaces each file is for**. Read it
before wiring anything in, because most of the web icon set belongs to the landing page rather
than to a localhost tool.

## What belongs here

**Authored source, and the artefacts rendered from it that a build consumes.** Not a file list -
this section stated one until 2026-08-13 (*"Nothing but this file"*, written when that was true
and left behind when `0ba93b7` and `703e3b1` landed the artwork). A list of what is present is a
**machine state**, and it expires the day somebody adds a file, with nothing to notice
(`ENGINEERING_STANDARD.md` §4, thirty-second member). `ls` answers that question and cannot be
wrong. So the rule instead:

- **The marks, as SVG with outlined paths.** Never text in a font: the wordmark is a fixed shape,
  and a font that is absent on a platform changes it. `PROVENANCE.md` records what each was
  outlined from and under what terms.
- **The rendered icons a build consumes**, produced from those SVGs by
  `scripts/build_brand_assets.py` and **committed deliberately**. They are rendered rather than
  authored, so the "generated media never goes in git" rule has to be answered: packaging reads
  them, and a release must not depend on a rendering toolchain being installed on the runner. The
  generator is committed beside them and its output is pinned, so regenerating is checkable.
- **Nothing invented.** Artwork under the name of the brand is authored or it is absent; a
  fabricated size is a drawn asset nobody drew.

## The one mark, and the retired one

**`truestill-mark.svg` is the product's mark.** The maintainer authored it; the rail inlines it and
every icon in `icons/` and `favicon.ico` is rasterised from it by `scripts/build_brand_assets.py`.
There is no second mark and no light/dark variant: it brings its own plate, and `#161826` measures
4.79:1 on the rose stop and 7.78:1 on the amber, so what sits behind it is not an input.

⚠ **`pillar-t-*.svg` ARE RETIRED, 2026-09-10, and reach no surface.** They are the pillar T - a
fluted column serif - which was the tab and installer icon until that date while the rail carried
the maintainer's T. Two unrelated marks shipped together for weeks because both favicon tests tied
the icon to `brand/` and the artwork test tied the rail to `brand/`, but to *different files in
it*. `test_the_shipped_icon_is_a_current_render_of_the_mark_the_rail_shows` now re-renders the icon
from the source the rail is proved against and compares pixels.

**They are kept rather than deleted, and the reason is the record.** `PROVENANCE.md` documents
where the geometry came from and its licence position, `scripts/make_pillar_t.py` still generates
them, `test_pillar_t_is_deterministic.py` still pins the pair, and `.scratch/pillar-t-render/`
holds the size measurements taken against them - a lost answer key corrupts every measurement
taken against it. **Do not point a consumer back at them.**

⚠ **The retirement is recorded HERE and not inside the SVGs**, deliberately: those files are
byte-compared against their generator's output, so a comment added to one breaks that guard. The
first attempt did exactly that and turned four green tests red. A fact about the product belongs
in the product's documentation, not inside a derived drawing.

## What is NOT here, and where those live

The web icon set in `docs/brand.md` §4 - `apple-touch-icon.png`, `mstile-144x144.png`,
`site.webmanifest` - is for the **landing page**, which does not exist yet. `docs/brand.md` §6
rules on which surfaces may use what; that section is the authority, not this file.

`brand/` is **not packaged**. The wheel and the frozen bundle carry their own copies of what they
need - `truestill_app/static/favicon.ico` is byte-identical to `brand/favicon.ico` and is pinned
that way by `tests/e2e/test_one_mark_the_truestill_t.py`, and the installers stage from `brand/` at
build time.

## Two things not to get wrong

**The wordmark must be a vector with outlined paths.** Georgia in the original sheet was always a
placeholder: absent on most Linux systems, so the shape of the word changes per platform. (The
shipped rail wordmark is monospace *text* rather than the vector - a deliberate reversal recorded
in `docs/brand.md` §1, not an exception to this.)

**Installer icons are their own deliverables.** Windows embeds a `.ico`, macOS wants an `.icns`,
Linux desktop entries resolve a themed name to PNGs at hicolor sizes. `brand/favicon.ico` **is**
the Windows artifact and `brand/icons/truestill-<N>.png` are the Linux ones; **macOS has no
`.icns` here** and is unserved. What must never be assumed is that satisfying one platform
satisfies another - `packaging/verify_icon.py` asserts each shipped artifact separately, on its
own bytes.
