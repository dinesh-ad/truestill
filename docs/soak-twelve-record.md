# Soak twelve - the damaged decisions document, and a half that never ran

**Ran 2026-08-31 (P167). A record: never rewritten to match the present.** Written **2026-09-01,
one day after the run** - deliberately, and the reason is
[`soak-one-record.md`](soak-one-record.md)'s own header: soak one was reconstructed two days late
from commits, and *"five of the seven [steps] are visible only through what they found, and two
left no trace at all."* This one is written while the scratch tree, the script and the shell
history still exist.

**Machine**: Linux 7.0.0-15-generic x86_64, Python 3.14.4. No removable media - this soak is
entirely local.
**Instrument**: `damaged_doc.py`, its own docstring heading it *"Soak 12a"*.
**Evidence**: `/data/TruestillLibrary/soak-twelve-2026-08-31/` - the script and **the tree exactly
as the run left it**, moved off `/data/tmp` on 2026-09-01 because scratch is not evidence.

## WHAT SOAK TWELVE WAS FOR

Soaks ten and eleven pulled a stick mid-write and produced a damage vocabulary: zero-length files,
truncated files, files of the right size with wrong bytes. **All of that was measured against
photographs.** Soak twelve asks the same question about the one file on a drive that is not a
photograph and cannot be re-derived from anything: **`.truestill-decisions.json`**, which holds
names a person typed.

🔑 **The dangerous direction is the PUBLISH, not the read**, and the script's docstring says so
before the run: *"a damaged document still HOLDS somebody's names, so overwriting it is the data
loss `(ahz)` exists to prevent."* The question was whether `(ahz)`'s refusal survives contact with
the damage shapes soaks ten and eleven actually produce.

**Two halves were scoped. Only 12a ran.**

## 12a: THE DAMAGE MATRIX

Six shapes, each against a fresh drive with a marker, a catalog, one trip (*"Wayanad"*) and a
freshly written document. After damage, the catalog's trip is renamed to *"Placeholder"* via
`Catalog.rename_row`, so a publish would genuinely lose a name - `would_lose` has something real
to answer about.

**Re-run against today's code, 2026-09-01, in 0.38 s wall:**

| damage | `found` | `decisions` | `error` | `would_lose` | publish |
|---|---|---|---|---|---|
| zero-length | True | - | not readable JSON | (n/a) | **refused**, file untouched |
| truncated-json | True | - | not readable JSON | (n/a) | **refused**, file untouched |
| **not-json** (`\x00\xff` × 64) | True | - | **not readable as text** | (n/a) | **refused**, file untouched |
| json-not-object (`[1,2,3]`) | True | - | not a decisions document | (n/a) | **refused**, file untouched |
| valid-but-empty | True | ✅ | - | `()` | **overwritten** |
| none (control) | True | ✅ | - | `('trips',)` | **refused**, file untouched |

**The two bottom rows are the ones that make this a test rather than a formality.** A guard that
refused everything would pass the four damage rows and be useless; `valid-but-empty` is a document
that parses and carries nothing, so overwriting it is correct, and it *is* overwritten. The
control is refused for a completely different reason - `would_lose` returns `('trips',)`, because
the catalog now says *"Placeholder"* and the drive still says *"Wayanad"*. **Damage refuses on
`error`; a real conflict refuses on `would_lose`.** Both arms fire, and they are not the same arm.

## THE FINDING: `(aje)`, AND THE RUN DIED AT ROW THREE

⚠ **The table above is what the code does TODAY. On the day, the run never printed it.**

`read_decisions` documents itself as **"Never raises."** `Path.read_text(encoding="utf-8")` raises
`UnicodeDecodeError` on invalid bytes, and that class is a **`ValueError`, not an `OSError`**, so
the function's `except OSError` arm missed it entirely. The script calls `read_decisions`
unguarded - as every caller is entitled to, that being the documented contract - and died.

**The physical evidence is the shape of the preserved tree**, and it is better than a transcript:

```
soak-twelve-2026-08-31/
  zerolength/     zerolength.sqlite       ← row 1, completed
  truncatedjson/  truncatedjson.sqlite    ← row 2, completed
  notjson/        notjson.sqlite          ← row 3, drive built, document damaged, then nothing
                                          ← rows 4-6 have no directory: never reached
```

Each iteration builds its drive *before* reading it. Three directories exist and the fourth,
`jsonnotobject`, does not. **The run stopped inside row three, at the read.**

**Re-checked from source rather than recalled, 2026-09-01**: the pre-fix `read_decisions`, loaded
out of `2d8a1ca^` into a scratch module and handed `b"\x00\xff\x00\xff" * 64`, raises

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 1: invalid start byte
```

🔑 **Why one script crashing mattered enough to fix that night.** `catalog_session.open_catalog`
calls `ensure_decisions_on_drives` **before** `yield` and `save_decisions_to_reachable_drives`
**after** a dirty body, both **with no `try`** - they are unguarded precisely because this function
promised never to raise. So one bad byte on any reachable registered drive bricked **entry** to
every command, and could turn a successful `organize` of thousands of photographs into a crash on
**exit**. The user's remedy - unplug the drive - is the one thing nothing told them.

Fixed the same night in `2d8a1ca`: catch `UnicodeDecodeError` beside the `OSError` arm and return
`found=True` with a sentence, matching what `drive.read_marker` already did. Closure in
[`SHIPPED.md`](SHIPPED.md); body in [`research/backlog/aje.md`](research/backlog/aje.md).

## 12b: PREDICTIONS, WRITTEN AND COMMITTED BEFORE THE RUN

**Committed 2026-09-01 in its own commit, before any of 12b executed.** Soak twelve's CLI half
had no predictions and said so; this half does not repeat that. `(aiq)` is the prediction under
test - it claims the app is **worse than the CLI on detail** - and it is scored below, not
restated.

Each claim was re-read in today's code first, so what is predicted is the *outcome*, not the
mechanism:

| # | prediction | the mechanism it rests on, checked |
|---|---|---|
| **P1** | A drive vanishing mid-`organize` shows the app user a sentence and **no counts at all**, where the CLI prints a named file, a cause, `N organized / N failed / N not attempted` and exit 4 | `jobs.py`'s error terminal is `{type, message, code}` - **no `summary` key**; `app.js:170` then forces `summary: failed ? {} : ...` |
| **P2** | A `backup` that raises behaves the same way - message, no counts - where the CLI after `(ajd)` names what landed | same two sites; `BackupStoppedError` has **zero occurrences in `truestill-app`** |
| **P3** | The FAT32 ceiling is the one condition where the app is **NOT worse**, because the refusal is a core preflight rather than a stop | `filesystem.py` computes `max_file_bytes_for` and both surfaces consume it; no `jobs.py` error path is involved |
| **P4** | The app names **no failing file**; the CLI names up to `_STATUS_PREVIEW` of them and says how many more | `service/organize.py:1562` is a scalar `"failed": sum(...)`; `cli._print_capped` names them |

⚠ **P3 is the one I expect to be wrong in the good direction, and it is stated so it can be.**
If the app refuses identically, `(aiq)`'s framing needs the qualifier that it is worse on *stops*
and equal on *preflights* - which changes what the entry should build.

## 12b: THE APP HALF, WHICH NEVER STARTED

**Nothing below was run. It is scope, not result.** The app was to be pointed at a drive carrying
each damaged document while a loop device made the drive vanish underneath it. Both the browser
lane and the loop device were approved and neither was used.

## 🔑 THE STANDING GAP, MADE COUNTABLE

**Recorded as a number so it stops being a thing people remember and starts being a thing people
check.** Not an apology - the soaks that ran were worth running.

> **Twelve soaks. The app has been the SUBJECT of none of them.**

⚠ **Two precisions, because the round number is not quite the true one and the difference is
checkable:**

1. **Only soak twelve had an app half that was PLANNED and did not run.** Soaks ten and eleven
   name the app under *what was not done* - a stated gap, not an abandoned plan.
   [`soak-eleven-record.md`](soak-eleven-record.md) §9 is the form: *"The app - every command here
   was the CLI."*
2. ⚠ **"CLI-only" is not exactly true of soak eleven, by that record's own evidence.** Its NTFS
   pass named a trip **through the app's own HTTP routes** (`/api/events/propose` -> `/apply`) as
   *fixture setup*, which its §9 sentence above does not allow for. **That record is not corrected
   here** - a record rewritten to stay correct stops being one - and the distinction it accidentally
   exposes is the useful one: **the app has been used as an INSTRUMENT and never as a SUBJECT.**
   Nobody has watched it fail.

The 2026-08-31 handoff ranks *"nobody has watched the app fail"* third of five, and this is what
that ranking is counting: the screen's behaviour under every failure these twelve soaks
manufactured is inferred from a code read.

## ⚠ METHOD, AND THE LIMITS OF THIS ONE

- **No predictions were written before the run, so none are scored.** Soaks eight, nine and eleven
  each recorded predictions first and each caught themselves being wrong; this one cannot make
  that claim, and the absence is recorded rather than glossed.
- **The harness carried a defensive `hasattr(c, "rename_row")`**, which would have silently
  skipped the rename - and made `would_lose` trivially false for every row - had the method been
  absent. **Checked 2026-09-01: `Catalog.rename_row` exists**, so the rename did happen and the
  control row's `('trips',)` is real. A guard that turns a missing dependency into a weaker test
  rather than an error is the shape soak two's *"three harness defects that nearly became false
  findings"* is about; it did not bite here, and it was one `hasattr` away from doing so.
- **`expected=None` is passed where the signature says `str`.** Harmless - `expected` is read only
  inside `if document_key is not None`, and `document_key` is `None` here - but it is a type
  violation the script got away with, and the next person to copy this file should not.
- **Damage was written by hand, not produced by an interruption.** The byte pattern is *modelled*
  on what soaks ten and eleven found on three filesystems; no stick was pulled to make these
  files. That is the right trade for a matrix of six shapes, and it means this soak proves the
  **handling** and not the **incidence**.
- **One document, one drive, one catalog per row.** Nothing here tested two reachable drives
  disagreeing, which is where `(ahz)`'s lease design actually lives.

## WHAT THIS LEFT STANDING

- **The app half**, above.
- **The `damaged` document has no repair.** `(aje)` makes truestill refuse to overwrite it and say
  why. Nothing offers to rebuild it from the catalog, and nothing tells the user which drive is
  holding the bad file - the same gap `(ajb)`'s `damaged` bucket has, which is `(abn)`.
- **Whether `read_decisions` has a third unguarded raise.** Two arms were found by trying two
  shapes. The function was not audited exhaustively against everything `Path.read_text` and
  `json.loads` can throw.
