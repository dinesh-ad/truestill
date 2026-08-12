# The date resolver against messy real files - measurement

Status: **Measurement only (2026-08-12). No code changed, nothing recommended.** Every number
below came from running the real `dates.resolve_capture_datetime`, not from reading it.

What was run:

* The **reference library** - 2,276 files (`Input/2013` + `Input/2014`), five date tags read with
  exiftool, every file put through the resolver.
* A **fixture of 83 filename shapes** from messengers, phones, cameras, screenshot tools,
  scanners and exports, each with the day a human reads out of it, resolved with **no embedded
  metadata** so tier 4 is the only tier that can answer.
* A **pathological corpus** (10,731 files) for embedded values, plus 32 hand-built malformed
  tags for the cases the corpus does not contain.

---

## 1. The reference library cannot answer the question, and that is the first finding

The resolver dates **2,271 of 2,275** files from embedded EXIF. Four are `Undated/`, all
WhatsApp names, refused on purpose. **Tier 4 fires zero times.** Three files were never a small
sample of the filename tier; they were a sample of a tier this library never reaches.

So the library was used the other way round - as a **labelled set**. Every file the resolver
dates from EXIF is an example whose answer is known, and the question becomes what tier 4 *would*
have returned had the EXIF been absent:

| | files | share |
|---|---|---|
| tier 4 returns the **right** day | 631 | 27.8% |
| tier 4 returns **nothing**, though the name carries the true day | **643** | **28.3%** |
| name genuinely carries no date, tier 4 correctly silent | 997 | 43.9% |
| tier 4 returns a **wrong** day | **0** | 0% |

And where tier 4 does fire, it is exact: **631 of 631 agree with EXIF to the day, none off by
one.** The tier is not inaccurate. It is narrow.

## 2. Gaps, sorted by how many real files each would affect

### 2.1 A digit next to the date - 643 files (28.3% of the library)

`_COMPACT_DATE` is fenced by `(?<!\d)` and `(?!\d)`, so the eight date digits must be bounded by
non-digits. Any name that runs the time straight on to the date fails the fence:

| shape | source | files here |
|---|---|---|
| `2014815120755.jpg` | unpadded `YYYYMDDHHMMSS` | **614** |
| `2014815120755_1.jpg` | the same, duplicate suffix | **29** |
| `20131115120755.jpg` | padded `YYYYMMDDHHMMSS` | 0 |
| `ch01_20130704123045.mp4` | CCTV/NVR export | 0 |
| `DJI_20230715120000_0001_D.JPG` | DJI, timestamped firmware | 0 |
| `00100dPORTRAIT_00100_BURST20190413181239_COVER.jpg` | Google Camera burst cover | 0 |

**The 643 need two different things, and this matters because one of them looks sufficient.**
`2014815120755` is `2014` + `8` + `15` + `120755`: the month is **one digit**. Relaxing only the
digit fence gains nothing here, because `(0[1-9]|1[0-2])` still refuses `8`. Relaxing only the
padding gains nothing either, because the fence still refuses the trailing time. The largest
shape in the library is invisible to either repair alone.

### 2.2 A separator other than `-` - 0 files here

`2013_07_04.jpg`, `2013.07.04.jpg`. `_ISO_DATE` accepts only the hyphen. Volume in the wild is
unmeasured; nothing in this library uses either.

### 2.3 Unpadded month or day with separators - 0 files here

`Scan 2020-3-14 0001.jpg`. Same padding requirement as 2.1, reached by the ISO pattern instead.

### 2.4 Not gaps - refused on purpose

`IMG-20191120-WA0001.jpg` (4 files here), the Telegram, Signal, Viber, Facebook, WeChat and LINE
conventions. These are the `messenger-dates-research.md` ruling working. They are listed only so
a later reader does not count them as coverage lost.

## 3. Wrong answers, kept separate

### 3.1 Three of WhatsApp's four naming conventions are trusted as capture dates

`is_messenger_filename` delegates to `categorize.NAME_PATTERNS`, which holds one WhatsApp shape.
The other three are absent, so the date chain reads a **send date** as a capture date:

| name | `is_messenger_filename` | resolver returns |
|---|---|---|
| `IMG-20191120-WA0001.jpg` | True | `Undated/` |
| `WhatsApp Image 2022-07-14 at 18.48.47.jpeg` | **False** | **2022-07-14, `FILENAME`** |
| `PHOTO-2022-07-14-18-48-47.jpg` | **False** | **2022-07-14, `FILENAME`** |
| `VIDEO-2022-07-14-18-48-47.mp4` | **False** | **2022-07-14, `FILENAME`** |

The ruling is implemented exactly as designed. The list it delegates to is incomplete, and the
delegation converts a gap in the **categorizer** into a wrong **date**. The Desktop/Web shape is
what a browser download produces and the `PHOTO-`/`VIDEO-` shape is what iOS share-to-Files
produces, so these are not exotic. Zero files here, because this library predates them.

### 3.2 US `MM-DD-YYYY` is read as `DD-MM-YYYY`

Across the 4th and the 25th of all twelve months: **11 wrong days, 12 `Undated/`, 1 right** (only
04-04, where the two readings coincide). A US-exported name whose day is 12 or under gets a
confident wrong month; above 12 it falls to `Undated/`. Zero files here.

### 3.3 A truncated seconds field invents a value

`'2013:07:04 12:30:4'` parses as **12:30:04**. `strptime` accepts a one-digit `%S`. Right day,
wrong second - it changes no folder, and it is the only case measured where a malformed value
produces a plausible number rather than nothing.

## 4. Malformed and hostile embedded dates

### 4.1 The 19-byte field: we are more tolerant than Lightroom, and correctly so

EXIF `DateTimeOriginal` is 20 bytes - 19 characters and a NUL. A 19-byte field is the same 19
characters with the terminator missing; Lightroom demands the NUL and shows nothing.
`parse_exif_datetime` never sees bytes - it parses whatever exiftool hands back - so
`'2013:07:04 12:30:45'` parses normally. **Nothing is lost on the case as asked.**

Two adjacent forms behave differently and one is a real fragility:

* `'2013:07:04 12:30:45 '` (trailing space) parses - `.strip()` removes it.
* `'2013:07:04 12:30:45\x00'` (NUL retained) returns **None**. `str.strip()` with no argument
  strips whitespace, and NUL is not whitespace in Python. Should a reader ever hand the
  terminator through, the date is dropped and the file falls to the next tag.

### 4.2 What the wild actually contains

Of **895 date-tag readings** across the pathological corpus (491 distinct values), **839 parse
and are sane** and **56 are refused**. The refusals, all real values from real files:

| refused value | ×  | what it is |
|---|---|---|
| `0000:00:00 00:00:00` | 17 | documented unset field; refused correctly |
| `    :  :     :  :` | 4 | the space-filled unset form; refused correctly |
| `200Ô-04-07T19:06:16-07:00` | 4 | a corrupted byte in the year; refused correctly |
| `2005:0<?>:03 15:31:45` | 1 | corrupted month byte; refused correctly |
| `40096:09:19 03:52:44`, `Test Year` | 2 | garbage; refused correctly |
| `20020904`, `20030701` | 5 | **date-only, no separators** |
| `2011:06:14 15:47+02:00`, `2020:01:05 15:04Z` | 2 | **minute precision, no seconds** |
| `2011-03-15T10:14:46-04:00` | 1 | **ISO 8601 instead of EXIF colons** |
| `2008.07.10  15:16:55` | 2 | **dot separators, double space** |
| `2019:04:24 22:24:00+02:00 DST` | 1 | **trailing DST marker** |
| `Tue Dec 14 09:54:11 2004` and 3 more | 4 | **C `asctime`** |
| `Monday, September 11, 2000, 2:45:40 PM` | 1 | **long human form** |
| `12/29/93 13:52:11` and 11 more | 12 | **US slash, two-digit year** |

The first block is refusal working. The bold block is **~30 readings carrying a recoverable date
that the resolver discards** - the embedded-tier equivalent of §2, and the same root shape: one
`strptime` format, no alternates.

Two future values occur in the wild - `2038:05:05` (the 32-bit `time_t` overflow year) and
`2041:09:02`. Both are refused as `REJECTED_FUTURE`. No hard sentinel appears in this corpus;
1904 and 1970 come from video containers, which it does not contain.

### 4.3 Absurd dates, measured

| value | result | source reported |
|---|---|---|
| `1904:01:01 00:00:00` | refused | `REJECTED_SENTINEL` |
| `1970:01:01 00:00:00` | refused | `REJECTED_SENTINEL` |
| `1904:01:01 00:00:01` | **accepted as 1904** | `EXIF` |
| `0000:01:01 00:00:00` | refused (unparseable) | `NONE` |
| `1899:12:31 23:59:59` | refused by the sanity floor | **`NONE`** |
| `1900:01:01 00:00:00` | accepted | `EXIF` |
| `2027:01:01 00:00:00` | refused | `REJECTED_FUTURE` |
| `2026:08:14 11:59` / `12:01` (now +2d) | accepted / refused | `EXIF` / `REJECTED_FUTURE` |
| `2101:01:01 00:00:00` | refused | `REJECTED_FUTURE` |
| `2013:07:04 25:00:00`, `2013:02:30 12:00:00` | refused (unparseable) | `NONE` |

`REJECTED_SENTINEL` and `REJECTED_FUTURE` exist so a refusal is never reported as "this file had
no date". **The sanity floor has no such member.** A `1899` value is found, refused, and reported
as `NONE` - indistinguishable from a file that never carried a date. The ceiling is covered only
because `FUTURE_TOLERANCE` happens to catch everything above it first.

Every one of these falls through the whole chain, so a good `CreateDate` or a good filename
beside a bad `DateTimeOriginal` still wins - measured for all 32 values.

## 5. Which wins when the name and the tag disagree

**The tag, always, silently, at any distance.** `IMG_20200603_142740.jpg` carrying
`DateTimeOriginal 2013:07:04` resolves to 2013-07-04 as `EXIF`; the seven-year disagreement is
not counted, flagged or recorded anywhere. The name only wins when the tag yields nothing -
sentinel, future, empty or unparseable, all measured.

On real files the question is currently moot: of the 631 name-dated files with EXIF,
**631 agree exactly and none disagrees by even a day.**

## 6. A name with a date but no time

`date_from_filename` returns **midnight**, and it discards a time the name **did** carry.
`IMG_20130704_235959.jpg` and `IMG_20130704_000001.jpg` both resolve to `2013-07-04 00:00:00`.

**The day folder is right at both ends of the day**, and structurally so: the value is naive
local, no conversion happens between the resolver and `strftime`, so `{yyyy}-{mm}-{dd}` renders
the day the name named. Both files render `2013/2013-07/2013-07-04 - Everyday`. This is also why
`is_suspect_default` already excludes `FILENAME` - already built, not re-derived here.

**What midnight does reach is clustering**, because there 00:00:00 is a real instant and every
same-day filename-dated file collides on it. Measured on nine files across one day, with a real
afternoon, a 22:40 and a 23:55:

* real EXIF times - **no event** (the segments fall below `DEFAULT_MIN_FILES`)
* the same nine files at filename midnight - **one 9-file event**

A gap of zero is never a boundary, so the collision manufactures an event the real times do not
support. Across two days the collision is harmless in the other direction: consecutive midnights
are 24h apart, which does split.

**Separately, and not caused by filename dates - one of the two documented invariants is false
on this library.** `events.py`'s `DEFAULT_SENSITIVITY` docstring states that "every overnight gap
exceeds `MIN_BOUNDARY_GAP_S`, so segmentation produces within-day clusters only", and `trips.py`
repeats it as "a cluster never spans midnight on real data". Clustering the library's own 2,271
EXIF timestamps:

* Of 16 consecutive pairs that change calendar day, **one is 43.9 minutes** -
  `2014-08-15 23:19:29 -> 2014-08-16 00:03:25`. That is below `MIN_BOUNDARY_GAP_S` (1h), so it
  **cannot** be a boundary, and the segment containing it spans midnight. The first claim -
  "segmentation produces within-day clusters only" - is **false, on the library it was tuned
  against**.
* At `DEFAULT_MIN_FILES = 8` that segment holds **4 files** and is discarded, so of the 16 events
  actually emitted, **none spans a calendar day**. Dropping the threshold to 2 emits 29 segments,
  of which exactly that one spans midnight.

So the second claim - "a cluster never spans midnight on real data" - is currently **true here,
and true for a reason it does not give**: the minimum-files filter, not the gap floor. A fifth
photo that night, or a lower threshold, ends it. Whether a merged New Year event is *wrong* is a
product question and is not answered here.

---

## What this measured, in one paragraph

Tier 4 is exact and narrow: it is never wrong on 631 real files and silent on 643 more that carry
their day in their name, and one root cause - a date digit sitting next to another digit, plus
unpadded months - accounts for all 643. The embedded tier has the same shape of limit, one
`strptime` format against roughly 30 recoverable readings it discards. Two wrong-answer classes
exist and neither occurs in this library: US `MM-DD-YYYY`, and three WhatsApp naming conventions
that the messenger ruling never sees because `NAME_PATTERNS` does not list them. Nothing here is
recommended; §2 and §3 are sorted so that a decision can be.
