# Migrating a library between layouts - recon + design

Status: **Decided and shipped (2026-07-28).** Step 2e of the layout correction, and the only
part of it that moves a user's files.

---

## 1. The problem the catalog creates

An organize run routes on `CategoryMatch.rule`. The catalog stores `files.category` - a
**label**. So a migration re-rendering recorded copies has strictly less information than the
run that placed them, and cannot simply ask "was this a camera photo?".

## 2. What can and cannot be decided from a label

`categorize.deterministic_side_bin_labels()` is the set a **side-bin rule alone** can produce:
the two screenshot rules, every `NAME_PATTERNS` convention, and the `Saved` fallback. A file
carrying one of those could not have come from the camera rule.

Everything else is **ambiguous by construction**, and the reason is worth stating because it is
not an edge case: `Camera` is the device rule's default label *and* a perfectly possible
`Software` value (verified - `Software: Camera` yields label `Camera` from `rule_software`), and
under `--by-device` the device label is arbitrary hardware text, so *any* label could be a
camera photo. A static analysis therefore cannot route the majority of a real library: in the
soak catalog, 2,224 of 2,269 copies carry the label `Camera`.

## 3. Re-derivation - feasible, and bounded

The copies are **on the drive being migrated**, which is connected by definition since the
migration is about to move them. So the evidence is available: read the metadata and re-run the
same rule chain. `migrate.rederive_rules` does exactly that, restricted to files under ambiguous
labels - deterministic side-bin labels are never re-read.

Categorization uses the recorded `original_name`, not the organized filename: copies are renamed
`YYYYMMDD_HHMMSS_<original>`, and the screenshot and messenger rules read the name.

**Cost:** one batched exiftool pass (~2.2 ms/file measured at 12 MP - header reads, not whole
files) plus an O(1) rule evaluation each. **O(ambiguous files)**, and exactly zero when nothing
is ambiguous. Everything else in the plan is O(files) with one dict pass; nothing is worse than
linear.

⚠ **Recorded caveat.** Re-derivation can disagree with the stored label, and legitimately: the
copy's metadata may differ from the source's (the scoped Takeout bake), and the rule chain may
have changed since the file was placed. The preview shows the resulting split before anything
moves, which is where that disagreement is meant to be caught.

## 4. Rejected alternatives

- **Persist the rule and backfill it.** Backfilling means writing a guess into the catalog and
  then trusting it forever. Re-derivation is a guess too, but a *visible* one that is recomputed
  each time and shown in the preview.
- **Route everything by label with a hardcoded "Camera means timeline".** Breaks `--by-device`
  silently, which is the same mistake the organize router was built to avoid.
- **Ask the user per file.** Thousands of decisions; the per-label map plus re-derivation is the
  same information at a reviewable size.
- **Default ambiguous labels to the timeline.** The unmapped direction must be the *recoverable*
  one. A file left beside the years is findable and easy to move; one wrongly hoisted onto the
  timeline is mixed into the photo record and hard to pick back out.

## 5. The gate

The preview is a **read**: it plans, renders and prints, and writes nothing. Enforcing that
turned up a pre-existing violation - the command refreshed the drive's label via `upsert_drive`
on every invocation, including previews - which is now on the apply path only. A preview that
has already touched the catalog is not a preview.

The move requires the typed word `move`. There is no default-yes, no bare-Enter path and no flag
that auto-confirms; `--apply` is permission to *ask*. Absent the word, the command's terminal
state is "previewed, nothing moved". The move itself runs on the existing journalled engine, so
it stays resumable after an interruption.


---

## 6. Addendum: resume is not reversal (2026-07-28)

The plan for this step assumed `undo-organize` could reverse a migration. It could not, and the
reason is worth recording because the two words look interchangeable and are not.

`migration_journal` **did** store `old_relative` - but every row was deleted the moment its move
completed. That makes it a **resume** record: it exists precisely while the operation is
unfinished, and erases itself on success. `undo.py`, meanwhile, reads `inplace_runs` /
`inplace_moves` and never looked at the migration journal at all. So a *finished* migration had
nothing left to reverse from, while an *interrupted* one did - the exact opposite of what a user
would assume.

**The fix keeps the row and adds a lifecycle** (schema v11): a row is inserted pending, marked
`completed_at` when its move lands, and dropped only when undo consumes it or a later migration
of the same drive supersedes it. "Pending" became a state rather than mere presence, which is
what let resume behaviour stay identical.

**Retention is bounded by supersession, not by a timer.** Exactly one run's record exists per
drive, and it is always the newest, so the only record that can be dropped is one a newer
migration has already made meaningless.

**The lesson, generalised:** a journal that erases itself on success can only ever answer "what
was I doing?", never "what did I do?". If the answer to the second question matters - and for
anything that relocates a user's only organized copy it does - the record has to outlive the
operation. Worth checking the same question of `reclaim_journal` before trusting it as an audit
trail.

**Complexity:** undo is O(moves in the run) and pays the same hash-verify per file the forward
path already pays. No additional per-file work.
