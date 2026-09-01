# (ajn) THE APP CANNOT SAY A COPY ARRIVED WITHOUT ITS TIMESTAMPS

*Body of backlog entry `(ajn)`, under **Build next**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01 (P175), **split out of `(aiq)` when its other two thirds shipped.** This is
`(aiq)`'s gap 3, and it is the only part that survived - so it is carried on its own letter rather
than left inside a closed entry, which would have dropped it silently.

## MEASURED

| where | state |
|---|---|
| core produces the fact | `models.py:845` `metadata_ok: bool = True`, set at `organizer.py:1702` `metadata_ok=metadata_warning is None` |
| core owns the sentence | `drive_unwritable.py:219` `metadata_not_preserved_note` - *"One home, because there are now TWO ways to reach this state and they must not word it"* differently |
| the CLI prints it | `cli.py:2737` `_print_capped([r for r in results if not r.metadata_ok], label="METADATA NOT SET")` |
| **the app** | ⚠ **`metadata_ok` has ZERO occurrences under `packages/truestill-app/src`** |

**Check that settles it**: `grep -rc "metadata_ok" packages/truestill-app/src` returns nothing.

## WHY IT MATTERS

`(aie)` and `(ain)` shipped the honest outcome for a drive that accepts the bytes and refuses the
timestamps: *"copied to X and is safe, but this drive does not let Truestill set timestamps or
permissions."* **A person on the CLI is told. A person on the screen is not told at all** - not a
worse wording, an absent one. `(aek)` and `(aep)` each closed one instance of that shape before.

## WHAT IS NOT ESTABLISHED

- **Whether the field belongs on the completion payload or the per-file list.** `(ajl)` shipped
  `failed_files` for the failure half; this is a **success with a caveat**, which is a different
  bucket and must not be folded into `failed`.
- **Whether backup and migrate need it too.** `(aip)` is the entry for the note being reachable
  only through organize; this one is about the app not reading it at all.

## RELATED

`(aiq)` (closed 2026-09-01; this was its gap 3), `(aie)` / `(ain)` (the fact and the wording),
`(aip)` (the same note missing from other commands), `(ajl)` (the failure half of the payload).
