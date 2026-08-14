# The Organize result - design brief

Recorded 2026-08-14, Stage A of the grid redesign. **A brief, not an implementation.** Every
number here is measured on the maintainer's 4,108-photograph corpus; nothing is an estimate.

## The subject, and the one job

A person has just moved four hundred photographs. The screen's single job is to **let them
believe it happened correctly**. Not to browse, not to celebrate - to show the evidence.

That distinction is the whole design. A gallery invites you to look around; this is a **receipt
you can see through**.

## The thesis

truestill's promise is that your originals are untouched - byte-identical, §1's rule, the reason
the product exists. **And its only view of a photograph crops it.** 48 identical 148px squares
under `object-fit: cover`, so a portrait is trimmed to a square and a panorama loses its ends.

**An uncropped grid is not a cosmetic change; it is the product's central claim made visible.**
Every photograph keeps the shape it was taken in. That is the brief.

## Palette - inherited, not chosen

Stated as hex so nothing is guessed, but **these are `tokens.css`'s existing values and the design
does not get to re-pick them**:

| role | token | hex |
|---|---|---|
| ground | `--gray-50` | `#faf8f5` |
| surface | `--gray-0` | `#ffffff` |
| hairline | `--gray-200` | `#e8e3db` |
| ink | `--gray-900` | `#1c1a17` |
| secondary | `--gray-500` | `#5f574c` |
| muted | `--fg-muted` | `#6e665a` |
| accent | `--accent` | `#4c63c4` |

⚠ **The warm ground is one of the three looks AI design defaults to** (cream + serif + terracotta).
It is kept because it was measured and shipped long before this brief, not because it was chosen
here - and the design deliberately spends none of its distinctiveness on the palette. **The
photographs are the only saturated thing on the screen.** Everything else is warm grey and one
indigo, used once.

## Type - the rule already exists, unwritten

Two faces, two jobs, and the split is meaningful rather than decorative:

- **`--family-sans`** (system UI stack) - sentences a person reads. The headline, the prose.
- **`--family-mono`** (DejaVu Sans Mono 400/700, bundled) - **anything the machine is asserting**:
  counts, file names, paths, hashes.

**Mono is a fact under oath; sans is a sentence.** The app already does this by habit; the brief
makes it a rule, because the numbers beneath a grid of photographs are exactly the case where the
distinction earns its keep - they are the claim the picture is evidence for.

Scale, from the existing tokens: headline `--type-lg` (18→20.25px) in sans; the count line
`--type-sm` (14→15.75px) in mono; the truncation note `--type-xs` in mono, muted.

**No display face is introduced.** A photographic contact sheet has no typography of its own, and
adding one here would be the design competing with its subject.

## Layout - justified, with a ceiling at exactly 16:9

Rows of photographs at a common height, each drawn at its true aspect, filling the row width.

```
target row height   172px
hard ceiling        178px
the wall            180px      <- 320 / (16/9) = 180.0 exactly
```

**The wall is not a preference, it is arithmetic.** A thumbnail is 320px on its long edge, so a
16:9 photograph runs out of pixels at exactly 180px of row height - and **20.5% of the corpus is
16:9 or wider**. Below that the distribution is empty:

| row height | photos below 1.0x | share |
|---:|---:|---:|
| 148 (today) | 138 | 3.36% |
| 160 | 138 | 3.36% |
| **172** | **141** | **3.43%** |
| 180 | 840 | **20.45%** |

**172px buys 35% more photograph area than today's 148px tile for 0.07 percentage points of extra
softness.** That is the free run in this corpus, and it is why the number is 172 and not a round
160 or a hopeful 200. No second cache size. No cache rebuild.

**The last row does not stretch.** It ends where the photographs end. A justified layout that
inflates its final row is inventing width the content does not have - and this screen is about
not inventing things.

```
+--------------------------------------------------------------+
|  Done. 412 photos copied into Library.                        |   sans, --type-lg
|                                                               |
|  +------+ +----+ +--------------+ +------+ +----+ +---------+ |   ONE justified row
|  |      | |    | |              | |      | |    | |         | |   true aspects, 172px tall
|  |      | |    | |              | |      | |    | |         | |
|  +------+ +----+ +--------------+ +------+ +----+ +---------+ |
|                                                               |
|  Show all 48 photos                                           |   accent, mono
|  Showing 48 of 412.                                           |   muted, mono, --type-xs
|                                                               |
|  412 copied · 8 duplicates skipped · 2 could not be read      |   mono, beneath. always.
+--------------------------------------------------------------+
```

⚠ **The grid will read markedly more vertical than the square version, and that is the corpus
speaking: 52.3% of these photographs are portrait.** Designed for, not discovered.

## The signature: the contact strip

**Collapsed, the result is a single justified row - a contact strip.** That is the one thing this
screen is remembered by, and it is chosen because it is the artifact the subject's own world
already contains: a photographer's contact sheet is how you check a roll came out. Opening it
unfolds the strip into the full sheet.

It is also **already the shipped behaviour** - the grid collapses to one row above six photos.
What changes is that the row stops being six identical squares and becomes a strip of real
frames, which is what makes the metaphor true rather than decorative.

**Everything else gets quieter, not louder**, per the one-bold-place rule:

| today | brief |
|---|---|
| tile radius `--corner-md` 10px | **0** - a frame on a contact sheet has no rounded corners |
| gutter `--space-3` 12px | **`--space-1` 4px** - a hairline of ground, not a margin |
| `object-fit: cover` | **removed entirely** - nothing to crop |
| card padding, borders, chips | unchanged, and deliberately unexamined |

## The risk, stated so it can be refused

**Dropping the radius and closing the gutter to 4px reverses a measured decision.** `app.css:794`
records that 8px/6px "rendered correctly and too small to read as separate tiles at this size. One
step up each."

That finding was true **for uniform squares**, where nothing but the gutter separates one tile
from the next. With true aspects, **shape variation does the separating** - a portrait beside a
panorama beside a square is legible at 4px in a way six identical squares never were. The
condition the old measurement was taken under no longer holds.

**This is the one aesthetic risk in the brief and it is the whole look.** Frames butting together
at a hairline is a contact sheet; frames floating in 12px of ground with rounded corners is a
photo gallery, and a gallery is the wrong genre for a custody record.

> **THE RETREAT, named in advance so it is not invented under pressure: `--space-2` 8px and
> `--corner-sm` 6px.** If 4px/0 reads wrong against real photographs, go back to the values
> `app.css:794` actually measured - **not to today's 12px/10px, and not to a number someone likes
> the look of.** The retreat from a measured decision is the measurement it replaced.

## Copy

- **`Done. 412 photos copied into Library.`** - the outcome, in the same verb the button used.
- **`Show all 48 photos`** / **`Showing 48 of 412.`** - truncation stated, never implied.
- A photograph that will not decode gets **`This photo will not open`** on the frame, not a broken
  image icon. `(adq)` left this open on purpose; it belongs to the grid, not to the route.

## Critique against the templated-default test

Worked honestly, by asking what a generic answer to "design a photo result grid" would produce:

| the default | this brief |
|---|---|
| a hero number with a small label and supporting stats | **refused** - the numbers move *beneath* the photographs and stay one mono line |
| a characterful serif display face | **refused** - no display face at all; a contact sheet has no typography |
| cream ground, serif, terracotta accent | ground is inherited and measured; **no serif, no terracotta**, one indigo used once |
| rounded cards floating on a tinted surface | **inverted** - square frames, hairline gutter |
| `01 / 02 / 03` numbered markers | **refused** - run order carries no meaning a reader needs; numbering it would assert a sequence that is not one |
| a scroll-triggered reveal or stagger animation | **none** - photographs arriving one by one is what lazy loading already does honestly |

**What survives the test is the thesis, not the styling:** uncropped because the product's promise
is uncropped, mono because the numbers are evidence, one row because a contact strip is how you
check a roll. Take those away and the brief is a grid of pictures; they are the parts a similar
prompt would not have produced.

## Before judging the result

⚠ **33.3% of thumbnails were drawn the wrong way up until `(adp)` landed today.** On this machine
the cache at `~/.cache/Truestill/thumbs` has never been written, so there is nothing stale to
clear and the first render is correct. **On any machine that has used the grid before, delete that
directory before forming an opinion** - otherwise a third of the frames are rotated and the design
gets blamed or credited for something it did not do.
