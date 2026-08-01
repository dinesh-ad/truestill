# Date provenance: design for (n) + (ii) + (bbb)-recovery, and where (kk) sits

> **FROZEN RECORD - PROGRAM COMPLETE (2026-07-31).** The status line immediately below was true
> when it was written and is not true now. The program shipped in six steps: schema **v13**
> (`files.date_source`), **v14** (`date_tag`), **v15** (`date_confirmations`) and **v16**
> (`file_copies.date_baked_at`), the honesty view, the rescue flow, the bake, and the
> `_original` candidate offer. Obligation **O4** is a named test file,
> `packages/truestill-core/tests/test_confirmation_survives.py`.
>
> Two carve-outs, so nobody reads the design as fully delivered: one clause of `(bbb)` item 4 -
> noting an embedded conflict against a confirmed date - was **decided against**
> (`BACKLOG.md` `(aaj)`, consciously out of scope), and `(kk)`'s `GPSDateStamp` half was **never
> built**.
>
> Read this for the reasoning that produced the design. The built truth is
> `IMPLEMENTATION_STANDARDS.md` §1 and §3, and `BACKLOG.md`. Kept for provenance; do not edit it
> to keep it current.

**Status: design only. Nothing built. Awaiting approval.**

One program, because the backlog audit found four items converged on the same schema step and the
same screen. This states the storage decision, the tier model, the three surfaces, the conflict
rule, and the build order.

---

## 1. Two claims verified before designing on them

### 1.1 The bake path IS reusable, but one layer lower than expected

The suggestion was to reuse the Takeout bake. Checked in code, and the answer is a qualified yes:

| Layer | Reusable? | Why |
|---|---|---|
| `exif.build_metadata_args` | **Yes, directly** | Already emits `-DateTimeOriginal=`, `-CreateDate=`, `-QuickTime:CreateDate=` from a `datetime`, plus GPS and description. Exactly the write a rescue needs. |
| `exif.write_metadata_batch` | **Yes, directly** | Batched, `-overwrite_original`, per-file verdicts, silence-is-failure. Contract-pinned in §8. |
| `organizer._MetadataBaker` | **No** | Keyed on `decision.source` and driven by a queue built from the organize loop (`_bake_queue`). A rescue has no `Decision` and no source in hand - it has a **drive-relative copy** of an already-organized file. |
| `organizer._upload_with_metadata_write` | **No** | Stage -> bake -> `sha256_file(staged)` -> `destination.upload(...)`. It writes a copy that does not exist yet. |

So the **primitive is reusable and the orchestrator is not**, which is the useful finding: a rescue
is not "run the bake path again", it is a new, small write path built on the same two functions.
That is a feature, not a workaround - the bake path's staging exists to protect a *source*, and a
rescue never touches one.

### 1.2 Baking into the copy fits copy-only, and the dual-hash rule already anticipates it

§1 permits exactly one byte-changing exception today (the Takeout write) and §3 states the rule that
makes it safe:

> `files.sha256` is the **source** (pre-write) hash - the **dedup identity**. `files.copy_sha256` is
> the organized copy's **post-write** hash - the **verification identity** (equal to `sha256` for the
> byte-identical normal pipeline; **differs after a Takeout metadata write**).

A human-confirmed date baked into the copy lands in precisely that shape: `sha256` unchanged (so
dedup, resume and `reclaim` are untouched), `copy_sha256` updated (so `verify` keeps passing). The
dual-hash rule was designed for a copy that legitimately differs from its source; this is a second
instance of the case it already handles, not a new class.

**Two consequences that must be built, not assumed:**

1. **`copy_sha256` must be updated in the same transaction that records the confirmation**, or
   `verify` reports a mismatch on a file truestill itself just rewrote - a false corruption alarm,
   which is worse than no verification.
2. **`file_copies.copy_sha256` is per drive.** A content hash lives once in `files`, but the same
   content can sit on three drives, and a rescue can only rewrite the copies that are *connected*.
   So a rescue is **per copy, resumable, and partial by nature** - the same shape `migrate` and
   `reclaim` already have, and it needs the same honesty: name the drives that were not present.

**Where it does not fit cleanly, stated plainly.** Baking rewrites bytes on a drive, so it is a
*write to a user's drive*, which §5's dry-run rule governs: it needs preview-then-typed-confirm like
every other bulk change. And a rescue of 4,000 files is 4,000 exiftool writes at a measured
9.3 ms/file batched - about 37 s - so it is a **job**, not a synchronous request (backlog `(oo)`).

### 1.3 The external framing: partly confirmed in-repo, partly not mine to confirm

The repo already surveyed this in `date-layering-gap-check.md` §3, and it **supports the shape of
the claim without confirming its specifics**:

- **PhotoPrism** "keeps a separate `TakenSrc` field recording *which* source won - the provenance
  idea `(n)`/`(ii)` want" (`:30`). So PhotoPrism does persist provenance, in its database. The §5
  observation calls this "a third argument for that same column".
- **Immich** "falls back to **mtime** as a last resort; has repeatedly shipped bugs where a
  re-copied library dated to the copy date" (`:29`).

**What I did not verify:** the specific claims that Immich users lose corrections on rebuild, and
that an archivist wrote a plugin to push edits back into EXIF. Those are external and I have no
repo evidence for them; confirming them means going to upstream trackers, which §3 permits but I
have not done. **The design does not depend on them.** It rests on the in-repo survey plus a
first-principles argument that stands alone:

> A correction stored only in a catalog is only as durable as the catalog. truestill's own
> `PROJECT_STATUS.md` §3 lists absolute-path portability as an open risk, `BACKLOG.md` `(xx)`
> records the hash-cache as deliberately disposable, and `moving-machines.md` exists because
> libraries move. A product whose promise is "a library you can still read without the tool"
> cannot store the user's own contribution somewhere the tool is required to read it.

That is also `BACKLOG.md` `(x)`'s argument for XMP export, arrived at independently: user-created
context is "the one thing that is currently lost if someone stops using truestill".

---

## 2. Storage: both, with the catalog authoritative and the copy durable

Neither DB-only nor file-only. **Two stores with one direction of truth.**

| | Catalog (`files.date_source`, `date_confirmed_by`, `date_confirmed_at`) | Organized copy (baked EXIF) |
|---|---|---|
| Role | **Authoritative.** What routing reads. | **Durable.** What survives truestill. |
| Written | Always, at confirmation | On confirm, per connected drive, as a job |
| If absent | Rescue is lost | Rescue still routes correctly |
| If they disagree | Catalog wins for routing; disagreement is **surfaced**, never silently reconciled | |

**Why the catalog is authoritative rather than the file.** Reading the confirmed date back out of
the copy on every run would mean re-reading every file to know where files go, which is the exiftool
cost §8 spends the metadata cache avoiding. And a drive can be disconnected. The catalog answers
instantly and offline; the bake is what makes the answer survive the catalog's loss.

**Why the copy is written at all, given the catalog is authoritative.** Because the catalog is
machine-local and the copy is the artifact the user keeps. This is the whole point of the design and
the one thing the compared tools do not do.

**Schema.** Three columns on `files`, at whatever version is free on the day - `IMPLEMENTATION_
STANDARDS.md` §1's schema note is explicit that reserving a number is a guess that keeps being
wrong, and it asks that no number be named. `date_source` finally persists what `DateSource` already
resolves and then discards at write time.

---

## 3. Tier model: human-confirmed outranks everything, permanently

`DateSource` is already an ordered chain. This adds one member above all of it:

```
HUMAN_CONFIRMED  <- new, highest, never overridden by machine derivation
EXIF | TAKEOUT | INFERRED_LOCAL | TAKEOUT_UPLOAD | FILENAME | REJECTED_SENTINEL | NONE
```

The resolver gains one branch at the top: **if the catalog holds a human confirmation for this
content hash, it is the answer, and no evidence is consulted.** Keyed on `sha256`, not path, so it
survives rename, migrate, re-layout and in-place organize - the same reasoning `(z)` gives for
hash-keying and the reason `(ii)` says "the catalog row is the identity; the rescue edits it".

This is what makes `(ii)`'s real requirement hold: *"a rescue that does not survive every future
whole-disk operation has not happened."* Today a hand-moved file is actively reverted by the next
`migrate-layout`, because the catalog still holds the old, untrusted date. With this tier, migration
re-renders it to the confirmed date instead.

---

## 4. The three surfaces, and they are one screen

`(n)`, `(ii)` and `(bbb)`-recovery are not three features. They are **a view, an action on it, and a
better-informed version of that action** - which is why the backlog audit found them converged.

### (n) The honesty view - "how your dates were determined"

A provenance mix over the library: *"82% embedded EXIF, 11% filename, 5% Takeout, 2% undated."*
Answers "how much should I trust this timeline?"

Two things the walkthrough already ruled and this must honour: every slice is **explorable** (click
it to see which files and why), and the bare *"N no date -> Undated"* count that confused a first
user becomes a way in rather than a dead end.

It is a `COUNT(*) ... GROUP BY date_source` once the column exists - the same shape as the Stats
screen's aggregate-only contract, no file reads.

### (ii) The rescue - a catalog event, not a file move

From a slice of (n) - undated, or side-binned - the user confirms the true capture date. truestill
does the placement through the normal seam; nobody drags anything.

Preview-then-typed-confirm (§5), because it moves files. Then: write the catalog row, and queue the
bake for every connected copy.

### (bbb)-recovery - the same action with a candidate pre-filled

When a `file.jpg_original` sits beside a live file and carries a *different* parseable capture date,
offer it: *"An exiftool backup beside this file has 2014-08-17. Use that date?"*

The design constraints are already written in `(bbb)` and this design changes none of them: reading
`_original` **never auto-wins** in `resolve_capture_datetime`; accepting it records
`HUMAN_CONFIRMED`, because a human chose it; `_original` stays an unorganized sidecar and is never
ingested as a second library citizen. `is_exiftool_original_backup` already identifies these files
at scan, so the detection half exists.

**This is the argument for building all three together:** (bbb)-recovery is (ii) with a suggested
value. Built separately it is a second screen doing the same job.

---

## 5. Conflict: the human wins, and the disagreement is visible

`(ii)` names this as "the design's real question". The rule:

**A human confirmation is never silently overridden, and never silently *upheld* either.**

When a later read finds embedded metadata that disagrees with a confirmation, the file keeps the
confirmed date and the disagreement becomes a *disclosure*, not a prompt: counted, named, and
reachable from (n) - the same never-silent treatment §1 gives Tier A/Tier B dates and §7 gives the
HEIC skip. The user can look, and change their mind, and nothing changes under them if they do not.

**The case that makes this non-trivial**, and it is truestill's own doing: after a rescue bakes
`DateTimeOriginal` into the copy, a later read of *that copy* finds the confirmed date and agrees -
correctly. But re-ingesting the **source** still finds the old evidence. So the comparison must be
against the confirmation's recorded *provenance*, not a naive "does EXIF match" - otherwise every
rescued file reports a conflict with its own source forever. This is exactly why `date_confirmed_by`
records what the confirmation was made against.

---

## 6. (kk) GPS: separable, and should be separated

`(kk)` (persist GPS at ingest) is **not** part of this program, on the evidence:

- It shares only the schema step. Its consumers are a future map view and trip-edge detection, not
  dating.
- Its own entry says the trip case "is only the symptom that exposed it" - the value is a places
  view, which is a different feature with a different design.
- It is a **column plus a write at ingest**, with no UI, no confirmation flow, and no conflict
  model. Bundling it means holding a one-day change behind a multi-week one.

**The one genuine overlap** is `GPSDateStamp`, which `date-layering-gap-check.md` §4(b) already
ruled "the cross-check for a suspect dead-clock date" - and that is a *dating* concern. So:
`GPSDateStamp` comes into this program as a cross-check tag; latitude/longitude persistence stays
`(kk)` and ships whenever it is scheduled. Both are the same exiftool read, already batched, so
neither adds a pass.

**Recommendation: keep (kk) separate, and take its `GPSDateStamp` half here.**

---

## 7. Binding test obligations (ruled 2026-07-31)

Four requirements, recorded as tests rather than prose because prose does not fail a build. Each
names the step that must carry it. **A step is not done until its obligation is a passing test that
has been seen to fail against the defect it names.**

| # | Obligation | Step | Why it is not optional |
|---|---|---|---|
| **O1** | `copy_sha256` updates in the **same transaction** as the confirmation. *Test: confirm a date, run `verify`, assert clean.* | 4 | The worst failure this feature can have: **a tool telling a user their photo is damaged because it edited it.** A false corruption alarm on a file truestill itself just rewrote destroys the trust `verify` exists to build. |
| **O2** | A rescue **names the drives it could not reach**, as `migrate` and `reclaim` do. *Test: two drives, one connected, the report names the other.* | 4 | `file_copies.copy_sha256` is per drive, so a rescue is partial by nature. §9's never-silent rule: a partial outcome is counted and named, never folded into a success total. |
| **O3** | Conflict comparison is against **recorded provenance**, never the file's current embedded metadata. *Test: confirm a date, bake it, re-read - no conflict reported.* | 6 | Once a rescue bakes `DateTimeOriginal` into the copy, a naive "does EXIF match" comparison makes every rescued file report a conflict with its own source, forever. The trap is truestill's own doing, so the guard is permanent. |
| **O4** | A confirmation survives migrate, re-layout and in-place organize. *Test: confirm, then migrate, assert the file routes by the confirmed date.* | 3 | `(ii)`'s actual requirement: "a rescue that does not survive every future whole-disk operation has not happened." Today the catalog actively reverts a hand-move. |

## 8. Build order

Each step is independently shippable and leaves the product coherent.

| # | Step | Why here | Rough size |
|---|---|---|---|
| 1 | **Schema + persist `date_source`** on every organize/ingest write | Nothing else can start. Zero UI. Immediately makes the existing `models.date_quality` durable instead of per-run. | ~1 day |
| 2 | **(n) the honesty view**, read-only, explorable | Pure value on step 1, no writes, no new risk. Proves the column before anything depends on it. | ~2 days |
| 3 | **`HUMAN_CONFIRMED` tier + catalog-only rescue** | The routing half of (ii): confirmations survive migrate/re-layout. Deliberately **before** any baking, so the risky half ships against a working, tested tier. | ~2 days |
| 4 | **Bake into connected copies**, as a job, with `copy_sha256` updated in the same transaction | The durability half. Separated from step 3 so a bug here cannot cost a correction - the catalog already holds it. | ~3 days |
| 5 | **(bbb) `_original` candidate offer** on the step-3 surface | (ii) with a value pre-filled. Trivial once the flow exists; a separate screen if built first. | ~1 day |
| 6 | **Conflict disclosure** | Needs real confirmations to exist before it has anything to report. | ~1 day |

**Steps 3 and 4 are deliberately not one commit.** Step 3 makes rescues *work*; step 4 makes them
*survive truestill*. Shipping 3 alone leaves the product strictly better and no worse than today;
shipping 4 without 3 would be a write path with nothing to write.

**Before step 4, one thing must be measured, not assumed:** the bake writes to a user's drive, and
every figure we have for `write_metadata_batch` (9.3 ms/file) was taken on local SSD. `PERFORMANCE.md`
§1.1 records the FUSE column as unmeasured. A 4,000-file rescue over a cloud mount is the case to measure
before shipping it, to the §2.1 method.

**Not in this program, recorded so it is not smuggled in:** rewriting live EXIF from `_original`
without a confirmation, treating `_original` as a second library citizen, inventing merges, and
backfilling GPS for already-organized libraries (`(kk)`'s own open question, which wants its own
decision).
