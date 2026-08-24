# (agv) A KILLED BAKE MAKES `verify` CALL AN INTACT PHOTO CORRUPT, AND ADVISE UNDOING IT.

*Body of entry `(agv)`. **SHIPPED 2026-08-24.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-24 (P55)
>
> **Schema v22 `file_copies.bake_started_at`**, set before the exiftool write and cleared in the
> same statement that records the hash. `verify` answers **UNVERIFIABLE** with the remedy in its
> detail, never MISMATCH. The constraint below was honoured: the regression test asserts the false
> MISMATCH and the kill is a real `os._exit(9)`.
>
> ⚠ **`copy_sha256` is deliberately NOT cleared**, which was the cheaper-looking fix: `reclaim`
> fails closed on a NULL but `migrate._matches` treats one as *"existence is the best we can
> check"*, so clearing it would have weakened the command that rewrites every byte of the library.
> Found by the sixty-ninth member before anything was written.

> ## ⚠ CORRECTED IN PLACE 2026-08-24 (P47), AFTER THE REPRODUCTION
>
> **An open entry, not a record**, so it is corrected rather than annotated - the never-rewritten
> rule protects records, and leaving a misleading headline at the top of the open list is the cost
> of pretending it covers entries too. The original title was *"a bake that dies between the write
> and the record leaves an irreversible change unrecorded"*.
>
> ⚠ **I FILED THIS FROM A CODE READING AND RANKED IT ON THE WORD "IRREVERSIBLE". THAT WORD IS THE
> LEAST RELEVANT FACT ABOUT IT.** The bake is irreversible whether or not it is recorded, and
> re-running it is harmless - so irreversibility argues for nothing here. It is written down
> because the next reader meets the same word in `IRREVERSIBLE_NOTE` and would re-derive the same
> wrong rank from it, which is exactly what this correction exists to prevent.
>
> **Both halves of the original reasoning were wrong, in opposite directions**: the window is
> **narrower** than claimed, and the consequence is **worse** and was not in the filing at all.

## The premise holds - reproduced 2026-08-24

Killed a bake with `os._exit(9)` in place of `record_bake` - an uncatchable death at exactly the
point between the exiftool write and the catalog write - over three real camera files, 16-23 MB,
copied onto scratch:

```
file       DateTimeOriginal on disk   date_baked_at   copy_sha256 matches disk?
p0.jpg     2014:08:01 12:00:00        NULL            NO  <-- the catalog hash is stale
p1.jpg     2018:01:30 09:55:19        NULL            YES (never reached)
```

The file carries the confirmed date and the catalog does not know.

## 🔑 THE ACTUAL HARM, and it is not the missing record

`truestill verify` against that state:

```
MISMATCH : 1
  MISMATCH   p0.jpg
  (read-only: Truestill never repairs; re-copy the source to restore a bad file.)
exit 1
```

**The photograph is perfectly intact and carries exactly the date the user asked for.** The product
calls it damaged, exits `1`, and recommends an action that - if followed - **overwrites the
correctly-baked file with the pre-bake source and discards the confirmed date**. The advice even
appears to work: re-copying restores the hash the stale catalog expects, so the MISMATCH clears and
the user's date is gone.

That is `IMPLEMENTATION_STANDARDS.md` §9's user-facing-truth contract inverted - not a missing
disclosure but **a false one about the user's own photograph**, in the command whose entire job is
telling them whether their photos are safe.

## The unrecorded bake itself costs nothing - measured

| | result |
|---|---|
| bytes after a re-bake | **identical** (same sha256, same size) |
| the confirmed date | preserved |
| `copy_sha256` | **healed** - matches disk again |
| `date_baked_at` | set |
| `_original` sidecars left | none |

Writing the same date twice is **idempotent**, and the ordinary remedy already runs itself:
`confirmations_to_bake` is driven by `date_baked_at IS NULL`, so the file stays queued and the next
bake fixes both the record and the hash. **So there is no second loss and no bookkeeping debt** -
only the window during which `verify` lies.

## The window is ~6% of a per-file bake, not "orders of magnitude"

⚠ **The original entry said the window was *"far wider than the rename `(agk)` closed"* because it
contains a full `sha256_file`.** In absolute terms that is true (microseconds against 12-40 ms).
As a fraction of the operation it is small, because exiftool's write dominates:

| file | MB | exiftool write | sha256 read | window |
|---|---|---|---|---|
| Nikon D610 | 16.4 | 326.8 ms | 12.0 ms | 3.6% |
| Samsung S8 | 23.0 | 293.5 ms | 40.0 ms | 12.0% |
| Nikon D810 | 18.5 | 322.5 ms | 13.0 ms | 3.9% |
| iPhone 4S | 4.0 | 239.9 ms | 8.6 ms | 3.5% |
| **total** | **61.9** | **1182.7 ms** | **73.7 ms** | **5.9%** |

A kill at a random moment lands in it roughly **1 time in 17**, against `(agk)`'s measured **2 in
8**. **The window is narrower in practice than the defect this was filed beside**, and the entry
should never have implied otherwise.

## The fix is a design, not a wiring - three shapes

`(agk)`'s remedy **does** transfer, and the disk can answer: `date_confirmations.captured_at` holds
the date that was to be written, so reading the file's `DateTimeOriginal` settles *"was this
baked"* definitively. Cheaper still, and particular to bake: because a re-bake is byte-identical,
an unknown-outcome row can simply be re-baked rather than discriminated.

1. **Intent log** (`(agk)`'s shape) - intent before exiftool, outcome after, reconcile unknowns on
   the next run. Matches the precedent; costs a table or columns.
2. **Stage and replace** - bake a copy, hash it, then rename atomically and record. Closes the
   window **structurally**, and `organizer._MetadataBaker` already stages for the Takeout path.
   Costs a full file copy per bake, and `bake_run`'s docstring **deliberately chose in-place**:
   *"each write is followed by its own read-back and its own single-transaction record"*.
3. **Teach `verify` about a pending confirmation** - narrowest, and treats the symptom rather than
   the cause. Named for completeness; a hot patch by this repo's standard.

## ⚠ THE CONSTRAINT ON WHICHEVER SHAPE IS CHOSEN

**The regression test asserts the FALSE MISMATCH, not the missing record.** A test aimed at
`date_baked_at` would go green against a fix that still leaves `verify` calling the photograph
corrupt - because the record and the hash are two different facts, and only one of them reaches a
user. Reproduce with the kill above, then assert that `verify` reports **0 MISMATCH and exits 0**
over a file whose bake was interrupted.

## Rank - deliberately not raised

**Mid.** It needs a crash landing in a 6% window and it self-heals on the next bake, so it sits
**below `(abb)`**, which a first stranger meets on day one.

⚠ **THIS ROW SAID "below `(aco)`" AND THAT COMPARISON IS WITHDRAWN (2026-08-24, P50).** It read:
*"a still with a UTC `DateTimeOriginal` is misdated on every ordinary run, no crash required."*
The clause *"for anyone with such a camera"* was doing all the work and **nobody had checked
whether such a camera exists**: two censuses of 1,434 stills found **no body with a Make and Model
that writes UTC into `DateTimeOriginal`**, and `(aco)` is now **retired**. What I verified that day
was that the code path is closed - which is true and is not the same claim as the defect having a
population. **Ranking on an unverified prevalence premise is the class this repo has filed seven
times**, and it is left visible here rather than quietly deleted for that reason. It sits **above `(agx)`**, which is report-only and makes no false
claim about a user's data.

⚠ **The evidence raised what it costs and lowered how often it is hit; those do not cancel into a
promotion.** Ranking it on the new sentence would repeat the mistake of ranking it on the old one.
