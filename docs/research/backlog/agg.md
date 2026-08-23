# (agg) A ROUTE THAT WRITES TO THE DESTINATION NOW DECLARES IT AND HOLDS THE DRIVE.

*Body of entry `(agg)`. **SHIPPED 2026-08-23.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(agg)** Found 2026-08-23 inventorying CLI subcommands against app routes; shipped the same day.

  > ⚠ **RETITLED TWICE, and the second correction is worth more than the entry.** It was filed as
  > *"the archive ingest route writes while declaring `mutating=False`"*, then retitled to
  > *"`mutating` is declared per route by judgement… `(agg)` and `(afq)` are two instances of one
  > cause pointing opposite ways."* **That framing was wrong and is removed.** `(afq)` is the
  > **in-process** claim (`jobs.py:236-242`), which is taken unconditionally *before* `mutating`
  > is read; `(agg)` is the **cross-process** lock (`jobs.py:253`), which is gated on it. Flipping
  > `mutating` cannot move `(afq)` in either direction. Two mechanisms twelve lines apart, read as
  > one.

  ## THE CAUSE

  `mutating` decides whether `(aaw)`'s cross-process drive lock engages (`jobs.py:253`:
  `cross_process = _hold_across_processes(held) if mutating else []`). It is **declared at each
  route by hand**. Nothing derives it from what the route does, and nothing checks it against
  that.

  ⚠ **`(afq)` is NOT an instance of this**, though the retitle said so for half a day. It is the
  **in-process** claim, unconditional and taken before `mutating` is read. Different mechanism,
  same function, and the resemblance is the whole reason to say so here.

  ## THE INSTANCE

  Four links, each read:

  1. `/api/ingest/archives/run` (`server.py:832`) reaches `service/takeout.py:201` ->
     `extract_archive_set`, which writes *"one merged staging tree under `destination`"*
     (`archive_extract.py:303,312`). Real bytes, on the user's drive.
  2. It **was** registered `operation="import preview", mutating=False` (`server.py:405-406`).
  3. `mutating` gates the cross-process lock (`jobs.py:253`).
  4. The staging path is `destination / STAGING_DIRNAME / archive_set.stem`
     (`archive_extract.py:211-213`) - **derived from the input, not the process.**

  🔑 That last line is the sentence `7564ed6` wrote for `(aaw)` - *"a staging path is private to
  the process that made it"* - **on a path it did not reach.**

  ## 🔑 AND THE GUARD ENFORCES IT, WHICH IS THE PART THAT MAKES THIS URGENT TO DECIDE

  `test_every_job_declares_whether_it_mutates.py` opens by ruling out the obvious shortcut, in its
  own words:

  > ⚠ **Why not derive it from `operation`.** `"organize"` and `"organize preview"` differ by one
  > word, and a control derived from a display string is one rename away from a lock that stops
  > firing.

  **One screen below, the assertion is derived from `operation`:**

  ```
  for operation, mutating in _declared():
      if "preview" in operation:
          assert not mutating, ...
  ```

  `"import preview"` contains `"preview"`. **So the test requires `mutating=False` for a route
  that writes** - and the obvious fix for the instance above makes an existing test go red.

  ⚠ **Its own failure message is the correct diagnosis, arrived at by accident**: *"a preview that
  writes is either mislabelled or is not a preview."* This route is **both**. The test cannot
  detect that, because it compares the label with the declaration and neither with the behaviour.

  Measured across all **15** declarations: 7 carry `"preview"` and are therefore pinned to
  `mutating=False` by the label alone.

  ## ⚠ COULD IT BE DERIVED AT ALL? - the question this entry exists to answer

  **From the route: no, and it should not try.** The docstring above is right, and the current
  guard is the demonstration of why.

  **From the call graph: partially, and the bounded version catches this.** A job target that
  reaches a known write helper - `extract_archive_set`, `safe_copy.*`, `LocalDestination.upload`,
  `_apply_move` - is writing, whatever it is called. Full cross-package reachability is not worth
  attempting; **one hop from the service function is**, and `takeout.py:201` calls
  `extract_archive_set` **directly**, so a one-hop check would have caught this instance on the
  commit that introduced it. That is the guard the cause deserves: *assert against behaviour, not
  against the label.*

  **From the write itself: yes, completely - and that is the honest answer to "derived".** If the
  **write** took the lock rather than the **route** declaring it, the property would be structural
  and no declaration could be wrong. The costs are real and should not be waved past: acquisition
  moves into a hot path, it needs re-entrancy, and the refuse-or-wait decision arrives **mid-run**
  rather than at the start - which is a worse moment to tell a user their drive is busy, and
  `(afp)` ruled on exactly that trade-off in the other direction.

  **If it stays declared, the declaration needs a REASON rather than a bool.** `mutating=False`
  currently means both *"this writes nothing"* and *"this writes, but not where it matters"* -
  which is the `0`-means-two-things shape `(aek)` and `(aft)` each removed from a different module.
  A reason field makes the second case sayable, reviewable, and greppable.

  ## ✅ WHAT SHIPPED - the label, not the location

  **`mutating=True`, and `operation="archive unpack"`.** The route now takes `(aaw)`'s
  cross-process lock, and its name says what it does.

  ⚠ **"Extract to a temp location instead" was considered and REFUSED, on evidence, so nobody
  re-derives it.** The staging tree is on the destination **deliberately** -
  `archive_set.space_for` records why in its own docstring:

  > *"Staging goes on the destination drive rather than the system temp directory… on many
  > machines `/tmp` is a tmpfs or a small partition, where a 200 GB export fails in the least
  > informative way available."*

  `(afy)` corroborated that independently on 2026-08-23: `/tmp` here is a **15.1 GiB tmpfs on a
  30 GiB machine**.

  ⚠ **And the reason it is NOT is worth recording too, because it sounds right.** A
  "one rename per file, EXDEV would cost a full read and write" argument was proposed and does
  **not apply**: nothing renames out of the staging tree. `--move` is copy-then-delete
  (`organizer._move_source`, `organizer.py:1379-1386` - *"the copy is already written and
  recorded; here we re-hash it and delete the source only if it matches"*), and the ordinary path
  copies through `LocalDestination.upload`. The EXDEV fallback that does exist
  (`local.py:194-211`, `organizer.py:1290,1330`) belongs to `adopt`, the **`--in-place`** path,
  where source and destination are one drive by definition. A temp location would cost the *same*
  number of copies, not an extra one. **The space argument carries this on its own; the rename
  argument is borrowed from a neighbour.**

  ## ⚠ WHAT CHANGES FOR A USER - a decision, not a consequence

  **A second process now REFUSES where it used to interleave, and that is the point of the
  change rather than a side effect of it.**

  - A CLI `truestill organize --apply /dest` is running; the *Rescue* screen is asked to unpack an
    archive onto that drive. It is now **refused**, naming the holder - *"A archive unpack is
    already running on <drive>. Wait for it to finish, or cancel it…"* - and **nothing is
    written**.
  - The reverse holds: an unpack in the app makes a CLI `organize --apply` on that drive exit
    `DRIVE_BUSY_EXIT` rather than proceed.

  Before this, both ran, and both wrote into `destination/.truestill-staging/<stem>` - one path,
  two writers, no lock.

  🔑 **This is `(afq)`'s question arriving from the other side, and it is answered differently
  because the facts differ.** `(afq)` asks whether a preview that writes **nothing** should be
  refused, and objects that it inherits a safety argument it has not earned. This route **writes
  to the user's drive**, so it has earned it. Same refusal, opposite justification - which is
  precisely the distinction `(afq)` exists to protect. **Nothing here decides `(afq)`.**

  ## THE COST, MEASURED - and it is a cost, not a saving

  ⚠ **A *"-2.8 MB and one fewer copy phase"* saving was proposed for this closure and is not
  real.** There is no mechanism: `mutating` changes lock **acquisition**, not bytes, and holding a
  lock across a preview and an apply does not merge copy phases - the unpack writes and the
  organize copies, both still. Measured rather than argued, on 99 real files from
  `exif-samples` (48.35 MB uncompressed, one Takeout-shaped zip):

  | | before | after |
  |---|---|---|
  | bytes written to the destination | 48.35 MB | **48.35 MB** |
  | copy phases | unpack, then organize | **unpack, then organize** |
  | drive lock | none | **one acquisition** |

  **The lock is the whole delta: median 1.16 ms, p95 1.67 ms, max 7.85 ms** over 200
  acquire-release cycles - **once per job**, not per file, and 1.9% of this unpack's 0.06 s.

  ⚠ **That is ~150x the catalog lock's 4-8 µs (`PERFORMANCE.md` §5.5) and worth knowing**:
  `lock_for` calls `drive_identity(root)`, which **reads the marker file from disk**, so it is an
  I/O operation rather than a syscall. `PERFORMANCE.md` carried no drive-lock figure before this.
  A correctness fix that is also cheaper would have been worth pointing at; this one is correct
  and costs 1.16 ms, and saying so is the same discipline.

  ## THE GUARD, WHICH HAD TO CHANGE FIRST

  The label-derived assertion is replaced by an explicit table of recorded decisions, one reason
  per entry, keeping the `>= 12` anti-vacuity floor. ⚠ **Renaming the operation alone made the old
  guard green** - proof the label was never the property, and the wrong reason to be green.

  🔑 **A table is a declaration, not a derivation, so THE CAUSE IS STILL OPEN.** Nothing in the
  guard knows what a route *does*. The two candidates above - a one-hop call-graph check, or the
  write taking the lock itself - remain unruled, and the second is the only one that makes the
  property structural.

  ## ⚠ BOUNDED - what is traced and what is not

  - ✅ **The mechanism is traced**, every link read rather than inferred.
  - ❌ **No collision was reproduced**, and none is claimed. The fix closes the window; it does not
    rest on the window having been hit.
  - **The in-process claim is unconditional** (`jobs.py:236-242`), so **two tabs in one app were
    already refused**. What changed is **app-versus-CLI**.
  - **Severity is still unassessed.** A staging tree is not the user's originals, and what a
    collision there costs - a corrupt merge, a wrong sidecar match, or nothing - was never worked
    out. The fix does not need the answer; a decision about the staging **stem** would.

  ## STILL OPEN AFTER THIS

  - **The staging path is still derived from the input** (`archive_extract.py:211-213`). The lock
    closes the cross-process window; a per-process stem is the belt-and-braces half, and `(aaw)`
    itself split unique-staging from the lock rather than folding them.
  - **Whether `mutating` should be derived** - the cause. Unruled.
  - ⚠ **A pre-existing grammar defect the new label inherits**: `jobs.py:155` renders
    `f"A {operation} is already running"`, so *"A archive unpack"*, and today also *"A organize"*,
    *"A undo"*, *"A import preview"*. Four operations already read wrong; this is a fifth. Not
    introduced here and not fixed here.

  ## RELATED

  `(aaw)` (the lock, and the sentence this path did not get), `(afq)` (a different mechanism that
  looks like this one), `(age)` (the space check this path relies on carries `(aek)`'s
  conflation), `(afw)` (which app runs write a record - the same per-route-judgement shape).
