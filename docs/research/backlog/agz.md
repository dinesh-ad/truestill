# (agz) A STILL CAN DECLARE ITS OWN UTC OFFSET AND WE THROW IT AWAY.

*Body of entry `(agz)`, under **Real, but conditional**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agz) A STILL CAN DECLARE ITS OWN UTC OFFSET AND WE THROW IT AWAY.** Filed 2026-08-24 (P50),
  out of `(aco)`'s retirement census - **the live evidence found while withdrawing a false one.**
  - ⚠ **THIS CHANGES NO FOLDER TODAY, AND THE ENTRY LEADS WITH THAT SO NOBODY BUILDS IT EXPECTING
    TO FIX A MISPLACED FILE.** `OffsetTimeOriginal` is the offset *of* a local `DateTimeOriginal`,
    so reading it moves no wall clock and no placement. **What it BUYS is the true instant** - the
    one thing needed to order photographs from two devices in different zones, and precisely what
    the April 2026 Lightroom thread is complaining about when two cameras seconds apart sort five
    hours apart. Placement is correct today; **ordering across devices is not, and cannot be**,
    because the information that would fix it is being discarded at parse time.

## The mechanism

`dates.parse_exif_datetime` strips a trailing `Z` or `±HH:MM` and keeps the digits. That is right -
the digits are local - but the offset it strips is thrown away rather than recorded, and the
separate tag is never even fetched: **`OffsetTimeOriginal` is absent from
`exif.REQUESTED_TAGS`** (checked by grep across `packages/*/src/`: zero hits, in any form).

**Two real cameras write the offset INSIDE the tag**, so this is not hypothetical:

| file | `DateTimeOriginal` | maker |
|---|---|---|
| `metadata-extractor-images/jpg/FLIR Vue Pro 640.jpg` | `2016:06:27 15:29:42.041-04:00` | FLIR |
| `metadata-extractor-images/jpg/FLIR iPhone device.jpg` | `2021:05:16 12:27:36.107-07:00` | FLIR Systems AB |

**Placement for both is correct today by luck of convention, not by reading what the file says.**
Truestill keeps the digits because cameras conventionally write local time; these two *declare*
that they did, and we discard the declaration and rely on the convention holding.

## ⚠ THIS DOES NOT CONTRADICT `(uu)`'s DOCUMENTED TRAP - it is the other tag

`(uu)`'s closure in [`SHIPPED.md`](../../SHIPPED.md) records: *"Documented trap - do not walk into
it: EXIF `OffsetTime` is modification time, never use it to convert `DateTimeOriginal`."*

**That rule is correct and this entry obeys it.** They are different EXIF tags:

- **`OffsetTime` (0x9010)** is the offset of `DateTime` - the *modification* stamp. `(uu)`'s trap.
- **`OffsetTimeOriginal` (0x9011)** is the offset of **`DateTimeOriginal`** - the capture stamp.
  **This is the only tag this entry proposes reading.**

⚠ **And the corpora agree with each other in a way that is luck rather than licence**: all 25 files
carrying both have them **identical**, 0 disagreements - because a camera writes both from one
clock at capture. **A file edited later would not**, which is exactly why the spec separates them
and why `(uu)`'s trap must survive this entry intact. **Read 0x9011. Never 0x9010.**

## Prevalence - and the 2.37% figure is from the WRONG DENOMINATOR

⚠ **The wrong figure is mine, named so the correction survives whoever repeats it.** In P49 I
measured **34 of 1,434 stills - 2.37%** and applied my own rule from the same turn (*"a signal
present in 3% of files decides nothing"*) to file this and not build it. **That was wrong, and the
maintainer withdrew the file-and-do-not-build instruction on the corrected measurement.**

**The corpora are archives of format edges going back to 2003, and `OffsetTimeOriginal` did not
exist before EXIF 2.31 in 2016.** Counting it against files that could never have carried it is the
proxy-census error:

| era | stills | declare an offset | rate |
|---|---|---|---|
| pre-2016 | 391 | 3 | **0.8%** |
| **2016 and later** | **71** | **27** | **38.0%** |

**11 makers, 14 models**: Apple (iPhone 11 Pro, 11 Pro Max, 13 Pro Max), **Canon (EOS R3, EOS R8)**,
Sony (ILCE-6000, ILCE-7M3, ILCE-7M4), Samsung (Galaxy S24 FE), HMD (Nokia 8.3 5G), OM Digital /
Olympus (OM-1, TG-6, TG-7), Reconyx (HYPERFIRE HP4K), FLIR.

🔑 **So this is not two files in fourteen hundred. It is 38% of the files whose era supports the
tag, from every major maker, and rising with every camera sold.** The right denominator is files
that *could* carry it.

## The market gap

**Lightroom ignores `EXIF:OffsetTimeOriginal` entirely** - EXIF 2.31 added it in 2016 and Adobe
never adopted it. The April 2026 thread is the cost in a user's words: two cameras photographing the
same moment, sorting five hours apart, with the information to fix it sitting in both files.
**Reading it puts Truestill ahead of the incumbent rather than catching up**, which is a different
kind of argument from every other entry here and worth stating plainly.

## ⚠ THE PERMISSION, INHERITED FROM `(aco)`'s FAILURE

**An offset PRESENT and read is evidence. An offset ABSENT must never be inferred.**

That is the whole licence, and it is the rule the codebase already states twice -
`video_utc.gps_confirms_utc` (*"Proves UTC-ness; never supplies an offset"*) and
`stills_corroborate_local` (*"Never returns or invents an offset"*). **The timezoneFixer defect is
what inferring costs**: Android read local digits as UTC and misdated real photographs.
`(aco)`'s own census is the second proof - 14 of 37 GPS deltas were not a real offset at all, one
group of nine off by twenty-two hours.

## What would REFUTE this entry

**The premise is *"the digits are local and the offset names the zone"*, and it is falsifiable.**
Verified over every corpus file carrying both an offset and GPS - Nokia 8.3 5G declaring `+03:00`
against a `3.00` delta, Sony ILCE-7M4 declaring `+08:00` against `7.99`; **4 of 4 agree**.

⚠ **A survey of post-2016 files showing declared offsets that DISAGREE with the local digits would
refute it outright** - it would mean some cameras write the offset against UTC digits, and reading
the tag would then move files that are correctly placed today. Four agreements is evidence, not
proof; the sample is small because the intersection of *has an offset* and *has GPS* is small.
**Whoever builds this widens that check first**, and stops if it fails.

## Not designed here

Where it would live is `dates.py`'s EXIF tier and `exif.REQUESTED_TAGS`. ⚠ **Adding a tag changes
`tags_fingerprint` and invalidates every cached metadata row** (`exif.py:_NUMERIC_TAGS`) - one full re-read,
paid once. What to *do* with a known instant - store it, sort by it, expose it in the date
provenance view - is a design question this entry does not answer.
