# `Input/Testing-new` as a corpus - what it is and what it can answer

Measured 2026-08-12, the first time anything used it. Recorded because two premises about it were
wrong and the next person will hold the same two.

## What it is

**1,836 files, 4.7 GB, one flat directory - no subfolders at all.** 1,835 JPEG and one WebP.
Mostly a OnePlus GM1911 (OnePlus 7 Pro), 2020.

| files | shape | what it is |
|---|---|---|
| 1,179 | `IMG_20200603_142740.jpg` | Android camera |
| **306** | `img_1080x1920x24_0146420.jpg` | **screen captures - see below** |
| 299 | `IMG_20201220_162320_Bokeh.jpg` | portrait mode |
| 50 | `IMG_..._01`, `__01__01`, `__01__01__01` | re-saved copies, suffix per save |
| 1 | `r-what-size-toilet-seat-do-you-need-1.webp` | a web download |

## Two premises that were wrong

**1. It is not messy in the way the naming layer needs.** The premise for pointing the folder-name
suggester at it was "a messy folder reads worse than hand-sorted ones". It is the *opposite* case:
it is perfectly uniform and has **no folder structure whatsoever**, so there is nothing for
`suggest_name` to read. The nested material is `Input/2014` (`Wayanad '14`,
`Siveram & My Treat ILP`, depth 3), which `local-naming-research.md` §6 already measured.

Run against it directly, `suggest_name` returns `None` - correctly, since chains are empty. That
**confirms `(acy)` rather than reopening it**: on material with no folder names there is nothing
for a rules layer *or* a model to read, so the comparison that entry settles cannot even be posed
here.

**2. `Input/2015` does not exist.** Only `2013`, `2014` and `Testing-new`.

## What it did answer

**The date resolver and the categoriser, on camera-default names at scale.** 1,530 files resolve
from EXIF and categorise as `Camera` through the device rule. **No filename-tier date is needed by
any file in this corpus**, and no rule misfires.

**The 306 screen captures are correctly `Saved/Undated/`, and it is worth saying why** so nobody
"fixes" it:

* They carry **no EXIF at all** - JFIF only, no `Make`, no `Model`, no date tag.
* `img_<width>x<height>x<depth>_<n>.jpg` holds no date either. The trailing number is a
  **counter, not a time**: the range runs 0145811 → 0149142 monotonically across the 306, and
  `0145811` would be 81 seconds.

So there is no date evidence anywhere in these files, and `Undated/` is the honest answer rather
than a gap. `Saved` is likewise correct - origin cannot be proven. They are *probably* screenshots
(phone-shaped 1080x1920 and 1080x1808, 24-bit, no camera metadata), but the screenshot rules key
on a `screenshot`-shaped name or `SamsungCaptureInfo`, and neither is present. **Nothing here
evidences what writes this name**, so no rule was added for it - the same standard applied to the
WhatsApp shapes in `date-resolver-corpus-measurement.md` §3.1.

## The one defect it found

**`Testing-new` was proposed as an event name for all 1,836 files.** `trips.SourceHints` builds
chains from absolute path parts, so `Testing-new` is level 0 for every member and wins a 100%
majority. `_suggestion_roots` suppresses it only when a name is carried by **>= 80% of one
proposal's cards**; below that, its own docstring says "the junk list carries it alone" - and
`is_junk("Testing-new")` was `False`.

The class was already in the list (`scratch-`, `pytest`, `temp`, `tmp`, `new folder`,
`untitled`); this name was not. Fixed. The discriminator is the **separator**, not the prefix: a
bare `^test[a-z]*` would eat `Testimonial`, `Teston` and `Test Match` - a real event people
photograph - which is the `Mary`/`mar` mistake recorded one pattern above it.

**Known limit, accepted:** `test_batch2` tidies to `test batch2` (rule 4 turns `_` into a space)
and is then indistinguishable from `Test Match`. Left uncaught: a wrongly discarded real name is
worse than a scaffolding name reaching a screen where a person can decline it.
