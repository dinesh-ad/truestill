# (aje) ONE INVALID BYTE IN `.truestill-decisions.json` BRICKS EVERY CATALOG OPEN.

*Body of backlog entry `(aje)`, **CLOSED 2026-08-31**. The closure is in
[`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Filed 2026-08-31 during soak twelve's decisions-document damage matrix. Measured against the live
`read_decisions` contract before the fix.

## MEASURED

`read_decisions` claims **Never raises.** Against a drive root whose
`.truestill-decisions.json` holds invalid UTF-8 (`b"\x00\xff" * N` - the interrupted-write shape
soaks ten and eleven produced across three filesystems):

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 1: invalid start byte
  File ".../decisions.py", in read_decisions
    text = target.read_text(encoding="utf-8")
```

Truncated JSON, a JSON array, and a zero-length file already returned
`DocumentOnDrive(found=True, error=...)`. **Only the byte-damage arm raised.**

## WHY THE RAISE IS WORSE THAN A TRACEBACK ON ONE SCREEN

`catalog_session.open_catalog` calls, with no `try`:

1. `ensure_decisions_on_drives(catalog)` **before** `yield` - every CLI/app open that uses this
   seam
2. `save_decisions_to_reachable_drives(catalog)` **after** a dirty body - a command that already
   succeeded

Both go through `read_decisions`. So one invalid byte on any **reachable** registered drive:

- bricks **entry**: every command raises before doing anything
- bricks **exit**: organize copies thousands of photographs, then dies on close with a decode
  error, so a run that worked reports a crash

The user's remedy - unplug the drive - is the one thing nothing tells them.

## WHAT `(ahz)`'S GUARD DOES AND DOES NOT COVER

The publish loop already fails closed when `found.error is not None`:

```
if found.too_new:            → NEWER_VERSION, continue
if found.error is not None:  → SaveOutcome.FAILED, continue    ← never overwrites
if found.decisions is not None and would_lose(...): → WOULD_LOSE, continue
```

`would_lose` is never reached with a damaged document, because `error` short-circuits first.
**That half is correct and was not changed.** The defect is that `read_decisions` never returned
an `error` for invalid UTF-8 - it raised before the loop could refuse.

## ROOT CAUSE

`Path.read_text(encoding="utf-8")` raises `UnicodeDecodeError`. That class is a **`ValueError`,
not an `OSError`**. The existing arms were:

```
except FileNotFoundError: → absent
except OSError:           → found, error=explain_unwritable_drive(...)
# json.loads ValueError:  → found, error="... not readable JSON"
```

`drive.read_marker` already caught `(OSError, json.JSONDecodeError, UnicodeDecodeError)` together.
This module's "Never raises" promise was load-bearing for two unguarded callers and was false for
one damage shape.

## FIX

Catch `UnicodeDecodeError` beside the OSError arm; return
`DocumentOnDrive(found=True, error="the file on the drive is not readable as text")`. Publish
then refuses and leaves the bytes untouched. No change to `catalog_session` - the contract is
restored at the function that claimed it.
