# (agm) MIGRATE WRITES A RECORD, BAKE WRITES AN INDEX LINE.

*Body of backlog entry `(agm)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agm) MIGRATE WRITES A RECORD, BAKE WRITES AN INDEX LINE.** Recorded 2026-08-23, split out of
  `(afw)` **when it closed**, because two of its five surfaces were never decided and closing the
  entry must not silently decide them. Ruled 2026-08-25 (P79).

  *Titled* **"WHETHER MIGRATE AND BAKE SHOULD WRITE A RECORD AT ALL"** *until the ruling below
  answered it. Retitled in place, `afx.md`/`agv.md`'s pattern; the question is kept here.*

  ## ⚠ THIS BODY EXISTS BECAUSE THE CORRECTIONS HAD NOWHERE LEGAL TO GO

  `(agm)` carried its reasoning inside [`afw.md`](afw.md) and its index line pointed there. That is
  a **closed** entry's body, so it is a record: doctrine forbids rewriting it, and
  `test_live_documents_cite_code_that_exists.py` does not read it. Three of the arguments held
  there are now wrong, and **a record is not where a correction may be written.** `(agm)` was also
  the only one of **96** open letters with no body of its own, measured 2026-08-25.

  ## 1. MIGRATE'S PREMISE WAS FALSE. The journal has retention ONE.

  It read: *"`migration_journal` already holds per-file state **durably**... A second copy of the
  same facts with weaker guarantees is a cost, not a feature."*

  `catalog.py:1478` opens a run by **deleting the previous one**:

  ```
  DELETE FROM migration_journal WHERE drive_uuid = ?   # catalog.py:1486
  DELETE FROM migration_runs    WHERE drive_uuid = ?   # catalog.py:1487
  ```

  and its own docstring says what it is: *"exactly one run's worth of **reversal record** exists
  per drive"* (`catalog.py:1481`).

  ⚠ **Neither word of "a second copy of the same facts" survives.** Not the same facts - it is
  reversal state, whose consumer is undo, not history. Not a copy - **the previous migrate's
  per-file truth is destroyed the moment the next one starts.** The journal is durable against a
  *kill* and holds nothing against the *next run*; a run record is the opposite on both axes.

  The ordering strengthens rather than weakens this: `migrate.py:759` mints a `run_id` and
  `migrate.py:761` journals the **entire plan** before the first move, closed at `migrate.py:809`.
  That is real per-file durability, scoped to one run, then overwritten.

  🔑 **Migrate is the surface with the history gap, and the entry led with the argument against it.**

  ## 2. BAKE'S PREMISE WAS RIGHT, for a reason the entry never gave

  It argued from *"returns counts"*. The load-bearing fact is `file_copies.date_baked_at`
  (`catalog.py:159`): a **permanent per-copy timestamp, never superseded**. Bake already has what
  migrate lacks - per-file provenance that outlives every later run.

  **What bake could put in a record, re-derived at the loop after `(ahd)` and `(agv)`:** nothing.
  `BakeOutcome` (`bake.py:266`) names only **drives** (`bake.py:363`). `relative` is rebound each
  pass at `bake.py:324` and discarded at `bake.py:335` (`absent`) and `bake.py:355` (`failed`).

  **So a bake record carries `files=[]` - a header, whatever the run's size.** Over the index line
  it would add only the drive label and the stop reason.

  ## 3. THE THIRD "NOT DECIDED" ITEM IS ANSWERED, AND WAS ANSWERED INSIDE `(afw)` ITSELF

  [`afw.md`](afw.md) still reads: *"One rolling file per catalog... **This is the part to design
  before any second writer is added**, and `(afu)` did not hit it because organize is currently
  the only writer."*

  `run_record.py:420` answers it by name - *"Two runs on two drives share one catalog and therefore
  one `runs/`... Serialised across processes by `drive_lock`"* - and `_supersede`
  (`run_record.py:364`) rotates the old `last-run.json` into `runs/` rather than overwriting it, so
  *"whichever finished last"* no longer costs the other. **Two writers, backup and undo, landed
  inside `(afw)` and the line was never struck.**

  ⚠ **The correction cannot go where the claim is.** `afw.md` is a record. This is the note that
  resolves it, the way `CLAUDE.md` resolves `docs/CLAUDE.md`'s surviving pointers.

  ## 4. THE MEASUREMENT

  **Machine: the maintainer's, 16 cores / 30 GiB. Filesystem: ext4** - not `/tmp`, which is tmpfs
  here. Read from the **real record on disk** at
  `/data/TruestillLibrary/abs-repro-2026-08-23/last-run.json`, not a synthetic payload. These are
  byte counts, so no throughput number is involved that a tmpfs could have flattered.

  | | bytes |
  |---|---|
  | real record, 1 entry, format 3 | **1,434** (header 417 + **1,017** detail) |
  | the same, gzipped as `_supersede` demotes it | **643** |
  | one `runs/index.jsonl` line | **119**, kept forever, outside the 64 MiB budget |
  | migrate entry, failures-only | ~128-271 |
  | migrate entry, every file | ~319-466 |
  | bake entry | **n/a, `files=[]`** |

  At 33,000 files an every-file migrate detail is **10-15 MiB, 16-23% of the budget**;
  failures-only at a 1% failure rate is **0.04 MiB, 0.06%**. Ten years of daily index lines is
  **424 KiB**. P61's **271 B per failure entry** (`SHIPPED.md:186`) re-prices at the same order and
  its scope is confirmed as failures-only, which is `(afd)`'s ruling applied.

  ## THE RULING

  1. **Migrate writes a record**, failures-only, reusing the `run_id` at `migrate.py:759` that
     `record_organize` and `superseded_record_path` already accept and nothing passes.
  2. **Bake writes an index line and no detail.** `files=[]` is the honest shape, and
     index-without-detail is **already a state every reader handles** (`run_record.py:410`) - the
     same state a pruned run is in. Per-file truth stays in `date_baked_at`, which outlives any
     record.
  3. **Neither is blocked.** `bake_confirmed_dates` has no `try`/`except` and `_cmd_bake` adds
     none, so a throw after the exiftool write loses the *account* of the run - but not the work:
     `confirmations_to_bake` filters `date_baked_at IS NULL` (`catalog.py:1746`, `catalog.py:1758`)
     and the re-bake is byte-identical (`SHIPPED.md:262`). That is a reporting defect, it belongs
     to `(ahh)`, and what it constrains here is **where** a record is written, not whether.

  ## WHAT IT DOES NOT CLOSE

  **3 of 9** mutating operations write a record today, measured by running `(ahj)`'s `_declared()`
  against `_wires_a_record`. This takes it to **6 of 9**; `trip apply`, `clean empty` and
  `archive unpack` remain, which is `(ahi)`'s set. ⚠ **`PROJECT_STATUS.md` §1b condition 1 must not
  be marked met** - and its wording changes with this ruling, because *"every mutating run writes a
  record"* cannot be satisfied by a run that deliberately writes no detail.

  ## RELATED

  `(afw)` (the four surfaces that shipped, and the two it left here), `(afl)` (the record itself),
  `(ahd)` (the bake engine's move to core), `(agv)` (the bake mark), `(ahh)` (the reporting defect
  above), `(ahi)` (the remaining three), `(ahj)` (the derived inventory this counted with).
