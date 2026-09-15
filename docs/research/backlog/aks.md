# (aks) FIND'S SUBJECT IS NARROWER THAN THE SCREEN IMPLIES: IT CANNOT MATCH A DRIVE LABEL IT PRINTS, OR AN ABSOLUTE ORGANIZED PATH.

*Body of backlog entry `(aks)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-15 while closing `(abj)`, from asking what Find searches rather than why a query
failed. **No work attached.** `(abj)` fixed *how* terms combine; this is about *what they are
matched against, and the two are independent.

## WHAT IT SEARCHES, MEASURED

`catalog._SEARCH_COLUMNS` is exactly three: `files.original_name`, `file_copies.relative`,
`files.source_path`. Measured against the 3,828-copy catalog at
`/data/TruestillLibrary/Test 1/look-2026-09-05/`:

| query | matches | why |
|---|---|---|
| `2014/2014-08` | 2,062 | `file_copies.relative` - the organized path **relative to its drive** |
| `three` | 3 | `files.source_path` - where the file was imported **from** |
| `dest-three` | **0** | the drive label, which is **printed on every result line** |

## ⚠ THE TWO GAPS, AND THEY ARE DIFFERENT IN KIND

**1. The drive label is unsearchable and is the most visible thing on the screen.** Every result
renders `drive 'BackupA'` (`cli.py:_cmd_where`) and the app's table has a Drive column. A person
who can see a label there and cannot type it into the box has been shown a facet that is not one.
`drives.label` is a column on a table the query **already joins** (`JOIN drives d`), so adding it
is one entry in `_SEARCH_COLUMNS` and nothing else - cheap, and deliberately not done here because
`(abj)` was about term combination and widening the subject in the same commit would have made
neither reviewable.

**2. An ABSOLUTE organized path matches nothing, and no column can currently answer it.** This is
the harder one. `file_copies.relative` is relative by design; the drive's root is **not on the
`drives` table at all** - it lives in `settings` as `path_hint.drive.<uuid>` (verified: the table
is `uuid, label, first_seen, last_seen, last_verified, notes`). So a person who copies
`/media/BackupA/2014/2014-08/…` out of their file manager and pastes it in gets **zero results**
for a file Truestill is holding, while the **source** path - a location that may no longer exist -
matches happily. ⚠ **The asymmetry is the defect**: the path that is true today is unsearchable
and the path that was true once is not.

## WHY THE SECOND ONE IS NOT A ONE-LINE FIX

A root is per-machine and mutable - that is the whole reason it is a *hint* in `settings` rather
than a column. Making it searchable means one of:

- **match the tail**: strip a leading root that matches a known hint before searching. Cheap, no
  schema, but it silently rewrites the user's query, which §9 would want said out loud.
- **join the hint in**: `settings` is key/value, so this is a correlated subquery per row inside a
  statement that is already a full scan - the cost lands on the query `PERFORMANCE.md` §7.1 just
  measured at 229 ms.
- **store the root on `drives`**: a schema change, and it duplicates a fact that is deliberately
  kept in one place because it changes when a drive is remounted.

**This entry does not choose.** It records the measurement and the three shapes.

## WHAT IS DELIBERATELY NOT A GAP

`files.source_path` being searchable is **not** a defect even though it surprises - `where`'s own
help is *"find which drive(s) hold a file, even when unplugged"*, and a person searching for the
folder they imported from is asking a real question. It is listed here only so a reader does not
"fix" it by removing the column.

## RELATED

`(abj)` (how the terms combine - closed 2026-09-15; this is the other half),
`(afa)` (`unreachable` meaning four things - the same class of a screen implying more than it
holds), `PERFORMANCE.md` §7.1 (the cost any widening is charged against).
