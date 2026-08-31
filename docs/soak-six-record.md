# Soak six: the reversal paths, and the central claim - a record

**Ran 2026-08-25 (P98).** Machine: 16 cores / 30 GiB. Filesystem: **ext4** (`/data`), 712 G free.
The half [`soak-five-record.md`](soak-five-record.md) named as missing.

> ## ⚠ DATED CORRECTION - 2026-08-26 (P103)
>
> **A correction beside the record, never an edit** - the bullet it corrects is left standing
> below, verbatim, because a record rewritten to stay correct stops being one.
>
> **The *"Trips and event naming"* bullet under "What was NOT reached" is wrong.** It reads *"a
> name that lives only in the catalog dies with it"*. **A name has never lived only in the
> catalog.** The claim came from the advisor, was carried into
> [`handoff-2026-08-25.md`](handoff-2026-08-25.md) §4, and **was never checked against
> `decisions.py`** - it was about to fund a whole soak.
>
> `.truestill-decisions.json` (`decisions.py:711`) carries `trips`, `events` and `albums`
> (`decisions.py:76-78`) with the name in each (`decisions.py:390-404`, `:418`), and
> `catalog_session.open_catalog` writes it to every reachable registered drive on any dirty exit
> (`catalog_session.py:137`). `decisions.py:1005` names the comparison itself - *"which is the
> Lightroom failure - a backup the user believes in and does not have"*.
>
> **A flat retraction would replace one wrong claim with another**, because the three sections
> answer differently:
>
> | section | restored after a lost catalog? | by what |
> |---|---|---|
> | trips | **yes, unconditionally** | `_apply_trips` (`decisions.py:442`) rebuilds by day; `trip_days.day` is a primary key, so a day list is an identity |
> | events | **no** | `apply_decisions` renames an event found by signature and cannot create one; after a rebuild `events` is empty, so every name lands in `unmatched` (`decisions.py:526-531`) |
> | albums | **no** | `not_applied=("albums",)` (`decisions.py:590`), ruled at `research/backlog/acg.md:9-11` |
>
> **Measured P103**, 353 files from `IV Bangalore`, ext4, one trip and three events named through
> the app's HTTP routes: the trip came back, **all three event names were lost**, and the
> re-derived signatures were **byte-identical** to the document's - so the product's stated reason,
> *"its photos have changed"*, is false. `(ahv)`.
>
> ⚠ **And the whole mechanism is defeated by an ordinary command line.** `truestill organize src
> dest` with a **relative** destination stores a relative path hint (`cli.py:2852`, `:2862`), and
> `write_decisions` refuses every save for the life of that drive (`decisions.py:741-746`). No
> document is ever written and the names really do live only in the catalog. `(ahu)`. **So the
> bullet below is false as a design claim and accidentally true for a common invocation** - which
> is a worse defect than the one it described.

---

## The central claim, and it leaks in one specific place

Soak five's organized library - **10,710 files, 28 GB** - catalog moved aside, rebuilt from the
files alone.

| path | result |
|---|---|
| `truestill restore` | **drive identity only** - 1 drive, 1 setting, **0 files, 0 copies** |
| `truestill rescan` | 30.1 s - all **10,710 reported "ON THE DRIVE, NOT IN THE CATALOG"** |
| `attach_drive` | 31.5 s - **`linked=0`, `unmatched=10710`**: it links by content against zero rows |
| re-organize (1,127-file subset) | rebuilds the rows |

**So the inventory is rebuildable only by re-organizing.** No read-only path restores it. That is
`(ahs)`, filed as a product ruling rather than ruled here. ⚠ `rescan`'s own sentence - *"No command
repairs any of the above yet. This one only tells you."* - is honest, and is also the whole gap.

**And the rebuild is not faithful.** 1,127 of 1,127 matched by content hash, **dates identical for
every one**, and **3 changed category `Camera` -> `Saved`** and moved folder. Reproduced directly:
with EXIF Make/Model the answer is `Camera` either way; with **no metadata** the original matches
the `camera_filename` rule and the renamed file falls through to `fallback`. `naming.py:49` prefixes
`%Y%m%d_%H%M%S_`; every name rule in `categorize.py` is `^`-anchored. **Organize is not idempotent
in categorisation** - that is `(ahr)`, and the original name survives as a suffix, so the fix is a
categoriser that knows its own rename, not a wider document.

**Not extrapolated** to the full library: the rate depends on how many files lack capture metadata.

## What ran

| feature | result |
|---|---|
| **backup** | **147.0 s**, 10,710 files / **29.1 GB**. ⚠ Refused an unregistered drive first - `(ahf)`'s ruling, and the sentence was true and actionable |
| **verify ON THE BACKUP DRIVE** | **44.7 s** - 10,710 verified, **0 missing, 0 mismatch, 0 unreadable, 0 unverifiable** |
| **organize --in-place** | 37.1 s - **60 moved by rename**, 10,650 already in place; a typed `move` required |
| **undo-organize** | **2.88 s** - 60 restored, and **all 10,710 paths byte-identical to before** |
| **migrate-layout x2** | see below |
| **reclaim (preview)** | 29.9 s - 10,710 files, **29.05 GB** would be freed, re-verified before offering |
| **second ingest of one archive** | **does not stage again** - `(aht)` |

🔑 **The backup was verified at the DESTINATION, not the source.** That is the drill every 2026
comparison of the alternatives records as the one people skip, and it is the difference between
"copied" and "restorable". 10,710 of 10,710, zero of everything else.

## `(agm)`'s argument, demonstrated live

Two migrations on one drive, then the state:

| | after migration 1 | after migration 2 |
|---|---|---|
| `migration_journal` | 215 | **215** - migration 1's rows **destroyed** |
| `migration_runs` | 1 | **1** - retention one, as `catalog.py:1481` says |
| `runs/index.jsonl` | 6 lines | **7 lines** - migration 1's record **survived** |

**That is exactly why migrate needed a record**, and the first migration's index line carries the
`run_id` `(agm)` reused: `{"attempted": 215, "kind": "migrate", "run_id": "fd5ebbda...", ...}`.

## Reclaim: the one command that deletes

10,710 candidates, 29.05 GB, and the preview says *"safely backed up and re-verified"*. **Spot-check:
5 candidates sampled at random, each hashed against its backup copy - 5/5 byte-identical.** Never
applied; preview only, by rule.

## What was checked that could have been dirty

Artifacts, not ticks: `rescan`'s own repairs-nothing sentence; `attach_drive`'s returned counts; a
content-hash join between the old and rebuilt catalogs; `index.jsonl` line by line; five reclaim
candidates hashed end to end. **`Input/` is byte-identical across BOTH soaks** (20,237 files, size +
mtime). Corpora git-clean; `scratch-race-2026-08-22` (4,226 files) and `abs-repro-2026-08-23`
intact.

## ⚠ What was NOT reached

* **The dates rescue** (1,254 undated files draining out of the tier) - not run.
* **Trips and event naming** - not run. ⚠ **This is the one that mattered most after the rebuild
  drill**, because a name that lives only in the catalog dies with it, and the drive document this
  library carries has `trips: []` and `events: []`. Untested, and now the obvious next soak.
* **`undo-organize`'s 3.1 min / 33k estimate is still unvalidated.** The in-place run moved **60**
  files - the input was already organized - so undoing 60 in 2.88 s says nothing about 33k. The
  estimate needs an in-place run over an *unorganized* tree.
* `reclaim --apply`, and `migrate-layout --undo` (the second-migration destruction was tested
  instead, which is what `(agm)` turned on).

**So: soak five covered the forward paths, this covered the reversal paths and the rebuild drill,
and the naming layer is covered by neither.**
