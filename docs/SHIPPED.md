# truestill - Shipped (provenance)

Work that is **built**. Split out of `BACKLOG.md` on 2026-08-01 so that file carries open work
only: one file doing both jobs is what let `(aae)` and `(jj)` sit in the wrong section while
they were shipping. **Nothing in this file is a to-do.** Read it to find out whether something
already exists, and what it was called when it was built.

**Item letters are allocated in `BACKLOG.md`'s Item letters section; this file never allocates a
letter.** An entry keeps the letter it was raised under, so the two files share one namespace and
only one of them hands letters out.

---

## Approved and built (provenance - do not rebuild)

These were approved here and **are shipped**. They keep their letters, because
`IMPLEMENTATION_STANDARDS.md` cites `(ii)` by letter and a retired letter is not a free one -
see **Item letters**. They stay in this file rather than moving to **Shipped (kept for
provenance)** below, which records work that never had a backlog letter.

**Read an entry's own status line, never this heading.** The heading told you these are built;
only the entry tells you *how much* of it, and two entries elsewhere in this file were found
recording shipped work as unstarted, which is the more expensive direction of the same mistake.

- **(aep) A FAILED COPY SAYS NEITHER "UPLOAD" NOR A RAW `errno`.**
  Shipped 2026-08-22. Two §9 violations lived in one fall-through line, and the rule against each
  was already written down elsewhere. What a user read, verbatim:
  *"FAILED: IMG_0001.png: cannot upload to 'Saved/Undated/IMG_0001.png': [Errno 13] Permission
  denied: '/.../dest3/Saved'"*.
  **1. "upload" is backend vocabulary** - honest inside the code, where `Destination.upload` covers
  rclone remotes, and false on screen: it names an event that did not happen and contradicts the
  promise that files never leave the machine. ⚠ `cli._print_execution`'s own comment states the
  rule a little above the `print` that emitted it.
  **2. The raw errno reached the user** - an errno, a path they never named, and no advice. The
  `EFBIG` branch strips it and is pinned for that; the fall-through passed `{exc}` through.
  🔑 **THE REMEDY ALREADY EXISTED AND THE FIX WAS TO REACH IT.** `(aek)` built `drive_unwritable`
  for the two writes that touch a user's own drive, and it is *"the only errno table in the
  product"* on purpose. Both copy-path sites now word from it - the copy failure and the
  make-the-folder failure - rather than a second table being written here, which is §4's rule that
  the remedy is usually to delete one of two copies rather than add a second assertion.
  ⚠ **THE EXISTING GUARD COULD NOT SEE IT.** `test_status_labels_cover_every_outcome` asserts every
  `ActionStatus` has a user-facing **label** and says nothing about `detail`, the free string that
  carried the leak - a guard aimed at the right subject through a lens that cannot resolve part of
  it (§4's fifty-fourth member).
  **Three tests, two mutations, both directions**: the leaking line restored (caught), and - the
  cry-wolf half - one generic sentence for all six conditions (caught), because a fix that
  replaced one raw errno with one bland string would have passed the first two assertions while
  telling a full disk it had a permissions problem.
  ⚠ **Its own citations had drifted before it was built** - `local.py:67,125` to `:68,:134`, and
  `cli.py:2137-2138` to `:2395`, in three weeks. Re-cited by symbol, which is what
  `IMPLEMENTATION_STANDARDS.md`'s header asks for. [Full entry](research/backlog/aep.md)

- **(aef) THE RELEASE LIST EXISTS, AND ITS STATE COLUMN CANNOT GO STALE.**
  Shipped 2026-08-22 as **Option B**, ruled 2026-08-19. `PROJECT_STATUS.md` §2b carries the list;
  `test_the_release_list_is_answerable.py` guards it.
  **The finding was never that the answer was wrong - it was that there was no answer.** The
  release question *"is not stored anywhere - it is RECOMPUTED from judgement every time it is
  asked, which is why it comes out different."*
  🔑 **The state column is DERIVED from which file each entry lives in, never trusted**, so a
  letter that ships without its row changing is a red test rather than something somebody has to
  re-read. That is the class the whole-backlog re-read found and nothing automatic could see:
  `(abo)` open two weeks after shipping, `(ach)` thirteen days, both closed by commits naming a
  **different** letter - the closure gate keys on a commit *declaring* a letter and is blind to
  work that closes somebody else's entry.
  **Doc-to-CODE, which is the shape §4 says is writable**, against the doc-to-doc guard it refused:
  the claim is machine-checkable by construction. Four mutations caught, including a reshaped row
  the parser would otherwise read as an empty list.
  ⚠ **Seeded with ONE row, and that is the ruling being honoured rather than an unfinished job.**
  `(aad)` is on it because the backlog's own text says *"LAUNCH-BLOCKING"*. The entry rules that
  the list is the maintainer's to populate and that filling it from today's backlog *"would encode
  today's guesses as the answer - the same mistake in one file instead of 57"*. **The mechanism
  exists so the ruling has somewhere to land and cannot rot once it does.**
  ⚠ **B's honest limit stands and is restated where a reader meets it**: this makes the LIST
  answerable, not the BACKLOG. *"Is `(aci)` needed for v1?"* still returns silence, and a shape
  that admits that beats one manufacturing 57 answers. [Full entry](research/backlog/aef.md)

- **(agg) A ROUTE THAT WRITES TO THE DESTINATION NOW DECLARES IT AND HOLDS THE DRIVE.** Shipped
  2026-08-23. `/api/ingest/archives/run` unpacks an archive set into a staging tree **on the
  user's destination drive** (`archive_extract.py:303,312`) while registered
  `operation="import preview", mutating=False` - and `mutating` is exactly what gates `(aaw)`'s
  cross-process lock (`jobs.py:253`), so a route that writes gigabytes took no lock. Now
  `operation="archive unpack", mutating=True`.
  ⚠ **The label was the defect, not the location.** Staging is on the destination **deliberately**
  (`archive_set.space_for`: *"on many machines `/tmp` is a tmpfs or a small partition, where a
  200 GB export fails in the least informative way available"*), and `(afy)` corroborated it the
  same day. ⚠ **An EXDEV / "one rename per file" argument was proposed for that placement and is
  recorded as REFUSED**: nothing renames out of staging - `--move` is copy-then-delete
  (`organizer.py:1379-1386`) and the ordinary path copies - so a temp location would cost the same
  copies, not an extra one. The space argument carries it alone.
  🔑 **THE GUARD HAD TO CHANGE FIRST, because it ENFORCED the defect.**
  `test_every_job_declares_whether_it_mutates.py` ruled out deriving from `operation` in its own
  docstring and asserted `if "preview" in operation: assert not mutating` one screen below, so the
  fix turned it red. ⚠ **Renaming alone made it green** - the wrong reason. It now checks an
  explicit table of recorded decisions. **A table is a declaration, not a derivation, so the cause
  is still open.**
  ⚠ **WHAT CHANGES FOR A USER, as a decision rather than a discovery: a second process now REFUSES
  where it interleaved.** A CLI `organize --apply` running makes the app's unpack refuse and write
  nothing, and the reverse. **This is `(afq)`'s question from the other side and is answered
  differently because the facts differ** - `(afq)` objects to a preview that writes *nothing*
  inheriting a safety argument; this one writes to the drive, so it earned it. `(afq)` is
  untouched.
  **Cost, measured on 99 real files (48.35 MB): bytes written unchanged, copy phases unchanged,
  one lock acquisition - median 1.16 ms, ~150x the catalog lock, because `lock_for` reads the
  drive marker from disk.** ⚠ A *"-2.8 MB and one fewer copy phase"* saving was proposed and is
  **not real**; there is no mechanism, and it is recorded as refuted rather than quietly dropped.
  [Full entry](research/backlog/agg.md)

- **(agr) THE FOURTH MINT SITE IS GUARDED, THE APP'S DOOR LEARNED THE GHOST, AND THE PHANTOM
  QUESTION CLOSED INTO `(aba)`.** Closed 2026-08-23 in three parts. **Part 1 (`b250ee4`)**:
  `_refuse_ghost_before_minting` inside `attach_drive`, immediately before the mint - the fourth
  caller of core's one rule, the refusal riding `DriveGhostError` through `jobs.py`'s existing
  route; the one test that failed was found resting on the unguarded door. **Part 2
  (`07f7183`)**: the app's door (`drive_support.py`) answers `ghost_drive_refusal` with
  `can_register: False`, and the exception door changes TYPE to `DriveGhostError` because
  `FRIENDLY_ERRORS` keys on `NotABackupDriveError`; thirteen call sites pass the catalog, and
  payload == exception == CLI, byte-identical. **Part 3 ruled NO BUILD**, folded into `(aba)` as
  its drive-identity sibling: the signature collides with legitimate re-registration by
  construction, and since part 1 every future instance is an explicit human
  `--force-new-identity` - a detector would fire only on people who followed our own
  instruction. Population measured zero across eleven catalogs; specimen preserved at
  `/data/TruestillLibrary/abs-repro-2026-08-23`; the ruling is conditional on part 1 holding and
  `aba.md` says so. The four-instance CLI-remedy census surfaced on the way is filed on
  `(agp)`. [Full entry](research/backlog/agr.md)

- **(abs) THE READ-ONLY SURFACES NOW LEAD WITH THE GHOST - CLOSED, BUILT BY `(afc)` UNDER
  ANOTHER NAME.** Closed 2026-08-23; **the work is `5345500 fix(afc)` (2026-08-21)**, instance
  six of the fixed-under-another-name family. The entry's own closing shape - *"the read-only
  surfaces do not refuse, they lead with it"* - exists verbatim: `_drive_or_explain`, the shared
  door `verify` and `rescan` pass, prints *"...is where Truestill recorded the drive X, but that
  drive's marker file is not there. The drive is probably not plugged in or not mounted"* plus
  the shadowing warning the entry never asked for. Reproduced on scratch, both commands; the
  listings speak the reach vocabulary (`offline` / *"(not plugged in)"*, `app.js:2624`).
  ⚠ **AND THE ENTRY WAS ITSELF A SIXTY-NINTH-MEMBER INSTANCE**: it counted *"the two places that
  MINT an identity"* and there were **three** - `attach_drive` (`drives.py:345`) predates it,
  mints with no ghost check, and is reachable `write=True` from `backup_run`. Finishing this
  entry's verification demonstrated it minting a phantom identity at an unplugged drive's
  recorded path. Filed as **`(agr)`**, top of the engine list, with the refusal shape ruled and
  the design recorded. [Full entry](research/backlog/abs.md)

- **(agq) THE FIRST SCHEMA BUILD WAS ALREADY OFF THE REQUEST PATH - CLOSED UNBUILT.** Closed
  2026-08-23; **the work is `b0a5d7e` (2026-08-14)**: `migrate_catalog`
  (`catalog_startup.py:332`) creates and migrates at every app boot, before serving, with
  presence captured first so `WILL_CREATE` stays honest - fused into one function so the order
  cannot be silently swapped. The entry was filed **nine days after the fix, by the same person
  who was investigating the code** - the read stopped at `inspect_catalog:242` (*"does not
  create"*, true) three functions short of `migrate_catalog:332` (*"⚠ This CREATES the file"*).
  🔑 **Fifth instance of the fixed-under-another-name family, second found by the author
  auditing their own filings** - now `ENGINEERING_STANDARD.md` §4's sixty-ninth member: a true
  answer from the first function is not the answer; read to the last function that can change it.
  ⚠ **The same partial read put a false sentence into `(adt)`'s close** - *"in production that
  window opens at the user's first ever click"* - and `b0a5d7e` is an **ancestor of the failing
  run's commit**, so the accepted hypothesis there cannot be what happened as stated; corrected
  beside that close, with the cross-process re-attribution kept explicitly a hypothesis.
  **Verified before closing**: field-failure cases already guarded (`(aen)` reports, `(adr)`
  refuses before the socket); `(ady)`'s copy untouched (chain-gated, `catalog.py:1157`); a fresh
  build measures **1.0 ms median / 1.4 ms max** on ordinary disk - there was never a wait to
  move, only contended CI I/O. ⚠ *Corrected 2026-08-23: that ran on tmpfs; real ext4 measures
  4.6 ms median - same conclusion, honest label. `agq.md`.* Tier 1 of `(agp)`'s ladder is ruled dead with it.
  [Full entry](research/backlog/agq.md)

- **(adt) THE 6558 ms IS RETIRED; THE CLASS IS MEASURED; THE RESIDUES HAVE LETTERS.** Closed
  2026-08-23 by investigation, not by a build. Recorded 2026-08-15 from CI run `31895987230` - a
  one-row settings write waited 6.5 s and a preview job was refused - and it outlived three
  structural hypotheses, each killed by measurement: the per-open lock (61x short, then removed by
  `(adu)`), the handler boundary (M4: dispatch max 1.0 ms), and the WebKit tail (the trace
  itself).
  🔑 **What is actually happening**: post-`(adu)`, exactly one holder class can exhaust the 5 s
  timeout - the **fresh-schema build**, once per catalog lifetime, measured at up to **5091.2 ms**
  on contended 2-core CI I/O against 9.0 ms max across 32,119 ordinary commits. The census
  distribution is flat with a three-orders-of-magnitude gap: **one long-holder class, not a
  convoy.** In production that window opens at the user's **first ever click** (`inspect_catalog`
  deliberately does not create at startup); the e2e lane re-rolls it every test, which is why CI
  saw it and a user very likely never will.
  ⚠ **The number itself is retired as unreproducible-but-classed, reasoning kept**: M4's 80
  attempts peaked at 105.8 ms, six consecutive nightlies are green, and 1.29x the measured max on
  a loaded runner is an unlucky draw from a characterised class - *"chasing it further would be
  hunting a number rather than a defect"* (the ruling).
  **Not the `(aci)` shape, checked**: `(aaw)` fixes staged file copies and names this bypass as
  its deliberate known gap; nothing serialises a settings write against a job, and that race
  stays open **inside the residues**: `(agp)` - the busy message names a second window that does
  not exist, ranked first - and `(agq)` - the first build off the request path.
  ⚠ Its own `(ads)` cross-reference was corrected beside, dated: a delete-mode writer does NOT
  exclude readers - RESERVED permits them - which `PERFORMANCE.md` settled 2026-08-18.
  [Full entry](research/backlog/adt.md)

- **(aci) A DELETED DECISION BLOCKED DRIVE SAVES - CLOSED BY `truestill restore`.** Closed
  2026-08-23 by the open-entry sweep; **the work that closed it landed in `2505a36`**, *"feat(cli):
  truestill restore <root>, the command the lost-machine user needs"*.
  🔑 **THE MECHANISM IS THE POINT, and it is the case no guard can see**: this entry was closed by
  a commit carrying **a different letter**. `scripts/check_entry_closure.py` watches for an entry
  LEAVING the backlog without a trailer, and `test_closed_entries_leave_the_backlog.py` watches for
  a trailer naming an entry that stayed - **neither can see a defect fixed under another name.**
  That needs a sweep, and a sweep needs judgement.
  **It was never a defect**: the save refuses to write a document that would lose decisions the
  drive already holds, which is what protects a re-attached drive from a rebuilt catalog, and a
  decision the user deleted locally looks identical. The entry's own body said so from the day it
  was recorded - *"Closed by restore; recorded so it is not rediscovered as a bug"* - and it then
  sat in the open-work file for two weeks after `restore` shipped.
  [Full entry](research/backlog/aci.md)

- **(ago) A DOCUMENTATION AUDIT: 632 CITATIONS, AND NOTHING CHECKED ONE.** Shipped 2026-08-23.
  `BACKLOG.md` had recorded the exposure in its own text - *"Nothing would tell us. Checked: no
  test or guard asserts a line number."* - and nothing acted on it. **Research names the pattern:
  docs as tests**, fail the build rather than rely on review; the study behind it found 230 stale
  code-element references across 82 repositories.
  ⚠ **THE RAW NUMBER WAS MISLEADING AND THE CLASSIFICATION IS THE FINDING**: 32 of 632 citations
  did not resolve, and **31 of the 32 sit in records**, which this repo never rewrites. The one in
  canon is a **Pillow** file, correctly absent. A guard over all of it would have gone red on the
  past on day one and been switched off.
  **Sixteen stale citations fixed in LIVING documents** - canon, guides and the bodies of open
  entries - several of them drifted by my own commits earlier the same day. ⚠ **`DECISIONS.md` was
  stale twice over**: it offered a comment as evidence that is no longer in the source, and the
  correction says so rather than swapping the quote, because that would have hidden the drift.
  **The guard covers the living set only**, with open-entry bodies read from `BACKLOG.md` so an
  entry leaves scope in the commit that ships it. ⚠ **What it cannot see is stated**: a line that
  moved onto other real code. Of five drifts found by hand it would have caught two; the rest
  needs symbol anchors, named and not smuggled in.
  **Also audited and clean**: the document map is complete at 64, every command-backed number
  holds, and six open entries were spot-checked as genuinely open. The browser lane read 505.
  Five mutations, all caught, three cry-wolf - ⚠ **two survived first and both mutants were
  valid**: with the corpus clean, a detector with no positive case is unfalsifiable.
  [Full entry](research/backlog/ago.md)

- **(agn) THE PUSH GATE JUDGED A COMMIT THE REMOTE MAY NOT HAVE HAD.** Shipped 2026-08-23.
  `ENGINEERING_STANDARD.md` §2's *"a pending result outranks a ready batch"* carries **contention**
  and **outcome**; `scripts/check_push_gate.py` separated them in prose and answered both from one
  sha it derived with `git rev-parse @{upstream}`, then sieved the fifteen most recent runs
  locally. 🔑 **The two have different keys** - contention is about the **branch** (any live push
  run on the ref dies), outcome is about **one commit** (the remote tip). Three reachable
  consequences: a stale tracking ref asked about the wrong commit; a red tip aged out of the window
  read as no evidence of failure; a run in flight for another sha was invisible and got cancelled.
  ⚠ **git hands the answer over and the gate did not take it** - `githooks(5)` puts
  `<local ref> <local sha1> <remote ref> <remote sha1>` on **stdin**, and the file contained no
  reference to stdin at all. **Null result**: `gh run list --commit SHA` existed all along.
  ⚠ **A CORRECTION TO MY OWN REPORT.** I said the gate had printed a green verdict while the
  remote was red, and offered it as evidence the override might be inert. Wrong: the override
  **fired**, and pre-commit **suppresses a passing hook's output**, so the only visible line was
  the hook's *name* - which was a claim - followed by `Passed`. An overridden gate, a failed-open
  gate and a genuinely-green one all printed the same sentence. The name is now a subject and the
  override says what it bypassed.
  **A tip with no run is REFUSED** (checked: `ci.yml` has no `paths` filter, so every push to main
  creates one), and that is deliberately distinct from failing open when `gh` cannot be reached -
  `_gh` returns `None` for *cannot ask* and `[]` for *asked, nothing there*.
  Seventeen tests; seven mutations, all caught, three cry-wolf. ⚠ **One survived
  twice for two different reasons** - a too-weak test, then an invalid mutant, because the new
  fail-closed rule made both implementations refuse and only the stated REASON distinguished them.
  [Full entry](research/backlog/agn.md)

- **(afw) THE OTHER MUTATING APP RUNS NOW WRITE RECORDS - BACKUP AND UNDO BUILT; MIGRATE AND BAKE
  DELIBERATELY DEFERRED.** Shipped 2026-08-23, schema unchanged, record **format 3**.
  `IMPLEMENTATION_STANDARDS.md` §1 says *"a run that changes the library writes down what it
  did"* - **a run**, not an organize - and `(afu)` had carried that to one of five surfaces.
  ✅ **Backup** in four stages, ending with the partial-failure policy and a `verified` derived
  from the count rather than asserted. ✅ **Undo**, last.
  ⚠ **THIS ENTRY'S OWN UNDO ROW - `| organize_undo | counts | - |` - WAS FALSE THE DAY IT WAS
  WRITTEN**, not made false later: `UndoOutcome` has carried `plan.steps` and typed per-file
  outcomes since the original in-place commit `dee4785`. Grouping undo with bake made it look
  like a design problem; it was the **cheapest** of the four, not the hardest.
  🔑 **The record could not simply be added, and that is the entry's real content.** One rolling
  `last-run.json` meant an undo record would **destroy the organize record of the run it had just
  reversed** - the two documents a person needs together. `IMPLEMENTATION_STANDARDS.md` was
  **edited rather than worked around**: `runs/index.jsonl` keeps one line per run forever, detail
  is bounded and compressed, and `last-run.json` stays the newest record itself - not a symlink
  (a privilege ordinary Windows users lack), not a copy (two sources of truth), not a naming file
  (breaks every reader). ⚠ **A line never says whether its detail exists; a reader looks** - which
  is what makes an orphan impossible, because the line is written first and append-only text can
  never be corrected.
  ⚠ **The bound is MEASURED**: a real 33,000-file in-place run over `~/TruestillLibrary` wrote
  **36.9 MiB** beside an **8.0 MiB** catalog - **4.6x the catalog it describes**. Compressed on
  demotion: **6.9%**. A byte budget, not a count, because run sizes span four orders of
  magnitude. The newest is never pruned, structurally. Pruning takes no confirmation because it
  cannot delete a **fact** - only detail.
  Undo also consults `persists_for_the_run` now (a user mid-recovery may have remounted
  read-only; a failing device is often *why* they are undoing) and returns `UndoOutcome.stopped`
  rather than raising - `RunStoppedError` exists to carry results past a raise from a frame that
  unwinds, and `run_undo` is the outermost loop.
  **Split out, not built**: `(agl)` undo's dropped cancel, `(agm)` migrate and bake.
  Seven mutations, all caught, three cry-wolf.
  [Full entry](research/backlog/afw.md)

- **(agk) THE IN-PLACE JOURNAL NOW RECORDS INTENT, BEFORE THE IRREVERSIBLE STEP.** Shipped
  2026-08-23, schema **v21**. ⚠ **A RELEASE BLOCKER, and the most serious thing in this arc**: an
  `--in-place` rename was covered by nothing until after it had happened, so a crash left a
  photograph moved with no way back. 🔑 **Measured on real photographs**, not in a fixture: eight
  `SIGKILL`s of a run over 150 files from `~/TruestillLibrary/Input`, scored by **inode**, left an
  orphan in **2 of 8** - and `undo-organize` then printed *"Restored 27 file(s)"*, exited 0 and
  left the photograph displaced, against a confirmation prompt promising the run is reversible.
  The unprotected span was `rename → catalog row → journal row`; the orphan had no catalog row
  either.
  **Guarding the write was the hot patch and was refused**: it turns a silent lost undo row into a
  loud one, and the file is still moved. The order is now **journal intent → rename → catalog row
  → journal outcome**, so a row that cannot be written means no rename is attempted and there is
  nothing to undo. Prior art is explicit - Microsoft's TxF writes the log record **before** the
  operation is requested, because after a failure you cannot know whether the rename happened;
  danluu's *"Files are hard"* adds that POSIX `rename` is atomic in normal operation and **not**
  on crash, which `LocalDestination.adopt` already claimed the journal covered.
  ⚠ **`outcome IS NULL` MEANS UNKNOWN, NEVER "DID NOT HAPPEN"** - a crash between the rename and
  the write-back leaves exactly that over a file that moved. `undo` reconciles against the
  **disk**, and now verifies **identity** as well as position (`size` rejects for free, SHA-256
  confirms, unreadable refuses) because a row can name a rename that never happened while its path
  is legitimately taken by another file. `organizer._move_source` already re-hashed before
  unlinking a source; undo checking less would have been a second divergence on one user action.
  ⚠ **THE MIGRATION CARRIES NO BACKFILL AND THE FIRST DRAFT DID** - `test_migration_safety.py`
  refused it, correctly, and the rule that replaced it is better: **the journal never asserts an
  outcome it did not observe.**
  ⚠ **A wording defect found by the fix**: a row whose rename never happened read as *"no longer
  at the path this run left it"* and cost exit 1. It is `NEVER_MOVED` now, and not a failure.
  Costs, measured against a real run: the second write is **0.060 ms/file, 0.44%** of 13.7 ms/file,
  ~2.1 s at 33k files. ⚠ **Corrected 2026-08-23: that ran on tmpfs. On real ext4 the outcome
  write is 2.486 ms - 41x - and ~19% of per-file cost with the intent write; the "not material"
  ruling is REOPENED. `agk.md` carries the full re-measurement.** **Acceptance: the same eight kills now score ZERO orphans.**
  Twelve tests, 9 of 10 failing first; ten mutations, all caught, three cry-wolf.
  [Full entry](research/backlog/agk.md)

- **(agj) AN ABORTED ORGANIZE WROTE NO RECORD - AND THE CLI WROTE A FALSE ONE.** Shipped
  2026-08-23. ⚠ **A REGRESSION FROM ONE COMMIT AGO, and naming it as one is the point.** `(agi)`
  gave `execute` its first *raising* stop; every stop before it was a `break` (`:2014` cancel,
  `:2048` health, `:2077` catalog), so partial results always came back by return and both callers
  recorded on their ordinary path. A raise leaves that path, and `results` is local to the frame.
  **The app wrote nothing; the CLI wrote a record saying every file was never attempted**, because
  its handler was written for the pre-flight refusal where that is true. 🔑 **A false custody
  record is worse than a missing one** - `(afa)`'s shape with the reader actively misled, in a
  product whose promise is verified custody. `RunStoppedError` carries the partial results out;
  `stop_block` needs no help, because `(agi)` records the offending file as `FAILED` with the
  reason *before* re-raising. **An exception that carries state rather than a results sink**: a
  sink is opt-in and its omission is invisible until the first abort - this defect reintroduced
  silently - while an ignored exception is loud.
  ⚠ **THE WRAPPER BROKE A CLASSIFIER, WHICH IS `(agi)`'s OWN LESSON ARRIVING AGAIN.**
  `jobs.is_catalog_busy` is an `isinstance` check that does not walk the chain, so behind a
  wrapper a held catalog would have reported SQLite's *"database is locked"* instead of the
  sentence written for it - **reachable**, because `record_inplace_move` is a bare catalog write
  inside the loop. `jobs._underlying` looks through `RunStoppedError` and nothing else.
  **Found and NOT fixed, deliberately**: `record_inplace_move` is unguarded by `_record_or_stop`,
  so on an in-place move a failed journal write leaves the file moved with no undo row - reported
  as its own letter. **Found and fixed here** because it is the same exit path: a stopped run
  leaked a `TemporaryDirectory`, `baker.close()` having sat on the return path only.
  **Checked and clear**: no partial can wear an organized name (`local.py:165-167` stages and
  renames), and no screen can stop showing something - the only class-keyed UI string is
  `NotABackupDriveError`, which `execute` cannot raise.
  Nine mutations, all caught, four of them cry-wolf.
  [Full entry](research/backlog/agj.md)

- **(agi) A CONDITION THAT OUTLIVES THE FILE NOW STOPS THE RUN, ON BOTH SURFACES.** Shipped
  2026-08-23. `(afw)` Stage 4 made both surfaces continue past a per-file failure - right - but
  neither classified it, so **a filling destination read exactly like one unreadable photo**: N
  wasted attempts and N record entries reading `failed` when the truth is one condition at file 12.
  `drive_unwritable.persists_for_the_run` answers *"will the next file hit this too?"* and both
  `organizer.py` and `service/backup.py` consult it. **The errno table is the implementation of
  that predicate, never the rule** - every branch says why the condition persists, and an
  unreasoned errno continues, because continuing is recoverable and aborting a good run is not.
  🔑 **`ENOSPC` is persistent for a MECHANISM**: a full copy-on-write filesystem needs metadata to
  **delete**, so it can refuse the cleanup too, and btrfs *"will change your filesystem to
  read-only to protect itself"* - after which every remaining file fails.
  ⚠ **TWO DEFECTS IN THE FIRST DRAFT, BOTH CAUGHT BY ITS OWN TESTS.** It was **inert on organize**,
  the surface that runs most, because `LocalDestination.upload` raises `DestinationError(...) from
  outcome.error` and the guard tested `isinstance(exc, OSError)`; the predicate now walks the cause
  chain in one place. And the abort **threw away the errno** by raising a fresh
  `OSError(detail)`. The first is this repo's signature *"stops one step short"* shape, committed
  and then caught end to end.
  ⚠ **Linux is proven with a real kernel `ENOSPC` via `/dev/full`; Windows is ASSUMED** - the
  `ERROR_DISK_FULL` (112) / `ERROR_HANDLE_DISK_FULL` (39) to `ENOSPC` link is Python's and is
  exercised by nothing here, so a green Windows lane must not be read as evidence of it. A real
  full volume via `diskpart` is costed in the entry and not built.
  **Prior art**: rsync's fatal 11 against per-file 23, restic's fatal destination-write with no
  snapshot, and rclone as the counter-example whose users file this behaviour as a defect
  (rclone#6355, #5308). PEP 3151 is the general form - inspect `errno` rather than catching broadly.
  [Full entry](research/backlog/agi.md)

- **(agf) A FENCED `python` BLOCK IN A DOCUMENT IS A QUOTATION TO A READER AND AN INPUT TO A
  FORMATTER.** Shipped 2026-08-23. ruff 0.16 formats Python inside Markdown, and `make check`
  rewrote `(age)`'s quotation of `filesystem.py` from `free_bytes=need if free is None else free,`
  - a keyword argument - into `free_bytes = (need if free is None else free,)`, a tuple assignment
  that appears nowhere in the file. In the entry whose subject is a value silently transformed one
  line after it was got right.
  🔑 **There is no tell**: a misquotation produced by a formatter is syntactically perfect,
  consistent with every block around it, and passes every gate **because the gate produced it**.
  ⚠ **Not only fragments** - a whole statement is normalised too (`{'a': 1}` -> `{"a": 1}`), so the
  exposed set is every block and a rule about what may be quoted would have been the wrong shape.
  **Remedy is a config line, measured before it was chosen**: `[tool.ruff.format] exclude =
  ["*.md"]`. `python`/`py`/`python3` fences are owned, `text`/`sh`/bare are not, and excluding
  costs no diagnostics because an unparseable fragment is silently skipped - ruff rewrites only
  what parses, which is exactly where the rewrite is wrong.
  **Swept mechanically**: 13 fences across the corpus, **1** the formatter would rewrite, and it is
  the one repaired. The records are the real exposure - `trip-grouping-research.md` carries six -
  because a record rewritten by a tool is the never-rewrite rule broken by something nobody thinks
  to check. Two guards, one reading the setting and one proving it still bites.
  §4's **sixty-fifth member**. [Full entry](research/backlog/agf.md)

- **(aft) AN UNREADABLE PROBE NO LONGER STOPS A RUN SAYING THE DISK IS FULL.** Shipped
  2026-08-23. `run_health.free_bytes` returned **0** when `shutil.disk_usage` raised, so an
  unreadable probe and a genuinely full disk were one value - and `_check_space` **stopped the
  run** with *"this computer's disk is nearly full (0.00 GB free)"* about a disk that might be
  empty, telling the user to check a cloud cache that had nothing to do with it. `(aek)`'s
  conflation, third surface.
  🔑 **The open question was ANSWERED BY MEASUREMENT, which is what the entry asked for** (§4's
  thirty-first member): the branch is **live**, reproduced twice without root - a deleted probe
  directory (`ENOENT`) and an unsearchable parent (`EACCES`) - so `_check_space`'s *"a local read
  does not fail transiently"* is false. The probe is `catalog_path.parent` and `--db` is
  unconstrained, so it is not reliably local either.
  ⚠ **Nothing guarded it, and that was proven rather than asserted**: mutating `return 0` to a
  huge number survived **2,560 passed against a 2,560 control**, because all fifteen space-axis
  tests monkeypatched `free_bytes` and none called it. Inverted, that mutation is now **caught by
  five tests**; four mutations in total, each with a 22-passed control.
  **`int | None`, two call sites, both inside `run_health.py`** - it is imported by nothing else,
  so no consumer of `RunHealth.check` changed. ⚠ The entry said *"three call sites"* and the brief
  said four; the count is what made the choice look expensive.
  **No `definite` flag and no errno table**, because a full disk answers **successfully with 0** -
  so every `OSError` here is indefinite and `int | None` *is* the split. The strikes were not
  copied (`_check_space` argues correctly against them) and neither was `(aek)`'s substitution (a
  number that passes, in the slot where a non-value belongs).
  ⚠ **WHAT IT DOES NOT DO**: a run whose ground cannot be read now proceeds **silently**. That is
  the module's recorded posture honoured, not a ruling that silence is right - `(agd)` carries
  that question whole, and organize-only was refused because a channel built for one of three
  watchers is §4's fifty-sixth member scheduled rather than inherited.
  [Full entry](research/backlog/aft.md)

- **(agc) A RULE CITED BY SECTION NUMBER ALONE WAS FILED UNDER THE WRONG AUTHORITY, THIRTEEN
  TIMES.** Shipped 2026-08-23. *"One bad file never aborts a batch"* is `ENGINEERING_STANDARD.md`
  §4's **Errors** bullet; it was cited as `IMPLEMENTATION_STANDARDS.md` **§1** at **13 sites
  across 9 files**, two of which named that file outright. ⚠ **The difference is authority**: the
  contract *"overrides `ENGINEERING_STANDARD.md` on any conflict"*, so every site claimed more for
  the rule than it has - and `(afw)`'s open question, *"is backup's fail-fast a §1 violation?"*,
  could not be answered correctly while the rule sat under the wrong one.
  🔑 **Why it survived is the finding**: the quoted text was **right every time**, so the corpus
  looks consistent *because* it is uniformly wrong, and **both files have a §1 and a §4**, so
  every citation resolves and nothing can go red. ⚠ **The one site that got the section right
  shows the second failure** - `code-quality-audit.md` says §4 one line below an explicit
  `IMPLEMENTATION_STANDARDS.md` §8 citation, and calls both *"binding"* when only one is.
  **Name the file, never the section alone.** §4 gains the **sixty-fourth member**, the inverse of
  the thirty-fifth. [Full entry](research/backlog/agc.md)

- **(agb) A POSIX ABSOLUTE PATH IS NOT ABSOLUTE ON WINDOWS, SO `(afy)`'s REDIRECT FIRED ON A
  PLATFORM IT WAS NEVER MEANT FOR.** Shipped 2026-08-23, **found by the Windows `check` lane on
  `(afy)`'s own push** (run 32621001403, `main` red for 14 minutes). `/data/tmp/truestill` is
  **drive-relative** on Windows, so `Path(...).mkdir(parents=True)` succeeded on whatever drive
  was current - the runner's header read `scratch: \data\tmp\truestill`, the suite wrote to
  `D:\data\...`, and it **overrode the runner's deliberate step putting `TEMP` on the fast
  drive**. Five tests red.
  ⚠ **The root cause is the thirty-second member exactly**: *"the directory could not be
  created"* is a **machine state** standing in for the **intent** *"this default names one POSIX
  volume on one machine"* - and it was false on the single platform that cannot be checked
  locally. The volume is now asserted in both halves, `os.name != "posix"` **and**
  `SCRATCH_VOLUME.is_dir()`, and is **never created**: creating it would answer its own question.
  The returned path is `resolve()`d, which was the second half of the same failure - an
  unanchored `WindowsPath('/data/...')` never compares equal to `WindowsPath('D:/data/...')`.
  ⚠ **`(afy)` shipped with no guard for this and could not have had one on this machine**, which
  is the honest half: the reproduction is `monkeypatch.setattr(os, "name", "nt")` over a volume
  made to **exist**, so the platform rather than the absent directory is what declines it. Both
  mutations caught with an 8-passed control. **The three-OS matrix did the job
  `PROJECT_STATUS.md` §3 keeps saying it is kept for.**

- **(aga) THE TYPE FENCE WAS A DIRECTORY LIST, SO A FILE THAT SATISFIED ITS RULE SAT OUTSIDE
  IT.** Shipped 2026-08-23, found while shipping `(afy)`. The `Makefile` states the rule as a
  **property** - *"real code that imports the core"* - and implemented it as five directory
  names, so `conftest.py` and `suite_scratch.py` satisfied it and were unchecked anyway. **Same
  shape as `(afu)`**: a rule scoped to a set of places, with the file that matters outside them.
  ⚠ **The fear had a number and it was zero**: both report **0** errors under `strict` on the
  path the gate uses, and the widened `make typecheck` reads *"no issues found in 118 source
  files"*. The two errors `conftest.py` showed were **one cause** - `pytest` missing from the
  hook's isolated env - and cost one word to fix.
  ⚠ **AND THE COMMENT DESIGNED TO PREVENT THIS DRIFT WAS ITSELF FALSE**: `.pre-commit-config.yaml`
  claimed its regex, `make typecheck` and the CI step *"cover exactly this set"* while the regex
  omitted `packaging/`, which both others had checked since it was added. The sentence asserting
  they agree is what stopped anyone comparing them. Fixed in the same commit; **the residual is
  that it is still prose**, and that is said rather than closed.
  ⚠ **The test corpus stays out with a MEASURED reason**: `mypy` over the four test directories
  cannot run at all - four `conftest.py`, no `__init__.py`, duplicate module names, *"errors
  prevented further checking"*. §6 is vindicated rather than agreed with. `tests/e2e/conftest.py`
  has one real finding and is noted as near-ready, **not proposed**.
  [Full entry](research/backlog/aga.md)

- **(afy) THE TEST SUITE WROTE DISK-SHAPED DATA TO RAM, AND §4's OWN tmpfs MEMBER WAS AMONG
  ITS VICTIMS.** Shipped 2026-08-23. `/tmp` on this machine is **tmpfs** and nothing set `TMPDIR`,
  so every `tmp_path`, catalog, rollback journal and Playwright video went to RAM. Measured from
  an empty `/tmp`: `make test` **282 MB**, the browser lane peaking at **716 MB**, ~850 MB
  resident between runs. The root `conftest.py` now points `TMPDIR` **and** `tempfile.tempdir` at
  `/data/tmp/truestill`, so it applies to `make test`, a bare `uv run pytest <file>` and every
  subprocess alike, with **no variable for anyone to remember**.
  ⚠ **The parent moves, never `--basetemp`** - an explicit basetemp is `rm_rf`'d at session
  start, which would destroy the three-session retention *and* let two concurrent pytest
  processes delete each other's live trees, the class `(aaw)` and `(afp)` just closed.
  ⚠ **`test_a_real_kill_leaves_a_state_a_fresh_process_can_clear` is §4's forty-sixth member's own
  subject and was running on the filesystem that member says cannot observe an interruption.** It
  passed only because it waits for five real extracted files first - it arranged the window RAM
  removes. The member is now satisfied **by construction** for the whole suite rather than by
  whoever remembers `df -T`. **The cost is stated rather than discovered**: `PERFORMANCE.md` §6,
  19.38 s -> 22.96 s median, +18%, ceiling **not** raised per `(afx)`, calibration margin
  2.5x -> 2.0x. No test changed verdict.
  ⚠ **Volume did not decide it.** 282 MB of disk-shaped scratch in RAM is wrong at that size too;
  the 9.8 GB that prompted the work was **not reproduced** on a green lane and is recorded as
  observed-once in `(afz)`'s neighbourhood rather than claimed. `test_the_suite_does_not_write_to_ram.py`.

- **(afu) THE RUN RECORD REACHES THE APP, AND THE CAUSE OF ITS ABSENCE WAS STRUCTURAL.**
  Shipped 2026-08-22, scoped to **organize**. `truestill_core.run_record` now owns
  `build_run_record` / `write_run_record` / `stop_block`; the CLI's `_record_the_run` keeps its
  `args`-reaching and delegates, and `service/organize.py` calls the same builder.
  🔑 **THE ROOT CAUSE IS THE REUSABLE HALF, AND IT IS NOT AN OVERSIGHT.** `(afl)` put the builder
  in `truestill-cli`, which `truestill-app` is **forbidden to import** (§2) - so the app could not
  have called it had anyone thought of it. Its commit touched `cli.py` and `app_paths.py`: the
  *constant* went to the shared package and the *logic* did not, and **that pair is what makes the
  gap invisible - the shared half looks like the whole of the sharing.** §4's fifty-sixth member
  with a structural cause: not a rule nobody carried across, but one the package boundary made
  unreachable. The rule was in §1 as a **product** invariant the whole time, and the surface it
  missed is the one §1's own reasoning names - *"the user who most needs it is the one who did not
  know to ask"* is the app's user, since a person typing `truestill organize` is the one who could
  have passed `--report`.
  ⚠ **A CANCELLED RUN RECORDS THE REASON IT ACTUALLY STOPPED FOR, and that branch was unreachable
  from the CLI.** `stop_block`'s docstring closed *"the CLI passes no `cancel`, so the silent one
  is unreachable from here"* - true of that caller and false of the app, which passes one. The app
  therefore passes `stopped` explicitly rather than letting the record derive *"the reason was not
  recorded"* about a reason it had in hand. **A record matters most on the run somebody stopped.**
  ⚠ **THE RECORD REPRODUCED `(aac)`'s CONFLATION AND IT WAS FIXED BEFORE ANYTHING RELIED ON IT.**
  `hashes.unreadable` was never emitted, so an unreadable file the run never reached recorded
  `"not attempted"` with a null `sha256` - which is **also** exactly what the size pre-filter's
  legitimate skip looks like. One builder now, so the field landed on both surfaces at once.
  ⚠ **A FAILED WRITE REACHES A SCREEN.** The record is automatic, so nobody asked for it and
  nobody would notice it missing - which makes its absence the news. One `NotRequired` key on the
  completion payload, silent on success, **and a renderer**: the key reached no renderer when
  first added, which is a record nobody can find one level up. Pinned by a browser test, and the
  renderer proved load-bearing by mutation.
  ⚠ **`(aac)` residue 2 is ENABLED, not closed** - the names are durable, the screen is unchanged.
  ⚠ **The other four mutating app runs are `(afw)`**, filed before this was built: organize is the
  only one with a per-file outcome list, and backup's fail-fast raise may be a live §1 violation
  rather than a missing record. Enumerated with reasons by
  `test_the_app_records_what_a_run_did.py`. [Full entry](research/backlog/afu.md)

- **(afv) `user_version` MOVED BACKWARDS ON DISK. `(adl)`'s STAMP WAS NOT IDEMPOTENT; `(ady)` ONLY
  MADE IT VISIBLE.** Shipped 2026-08-22 in two commits, the cause first: `1f0dde7` re-reads the
  version inside the `BEGIN IMMEDIATE` `_apply_step` already holds and skips a step the file is
  past; `46b100e` gates `(ady)`'s copy on `version < CURRENT_SCHEMA_VERSION` rather than on
  `fresh`.
  **The mechanism.** The chain reads `version` once, before the loop, into a plain local. Two
  openers of a behind catalog both enter at 3; one completes to 20; the other then stamps 4 over
  it. A version below the schema means the file claims to be **older than it is**, so the next
  open re-runs migrations against columns that already exist - survivable only because every
  migration happens to be idempotent, which `catalog.py` already calls *"luck holding, not a
  design"*.
  ⚠ **THE ENTRY WAS FILED BLAMING `(ady)` AND THAT WAS WRONG.** Its title said `(ady)` introduced
  it and the mechanism was unknown; both halves were false and both are corrected in place. The
  differential behind the claim was **sound** - 12/12 green pre-`(ady)`, red after - and it proved
  **visibility, not causation**. Measured with a probe watching the file rather than the test's
  outcome, 40 rounds each: **7/40 before `(ady)`, 28/40 after, 0/40 fixed.** Now
  `ENGINEERING_STANDARD.md` §4's **sixty-third member**.
  ⚠ **The failing test understated it.** It asserts what each opener *returns*, so it reddens only
  when a read lands in the window - runs where **all six openers returned 20** still moved the file
  `20 -> 5`, `20 -> 19`, `20 -> 4`. The new guard asserts the **property** (monotonicity on disk)
  and **constructs** the interleave rather than sampling for it: 0.08 s and decisive, where the
  first version cost 61 s and drew its power from the very amplification about to be removed.
  ⚠ **`backup()` was exonerated by re-asking the question properly.** `Connection.in_transaction`
  said `False` and settled nothing; writing `99` from another connection after a contended backup
  and reading it back showed the source current, three trials of three. The `after-copy@4`
  observation was a correct read of a file that really was at 4.
  [Full entry](research/backlog/afv.md)

- **(abo) THE HASH CACHE CAN SAY "NOBODY LOOKED".**
  Built **2026-08-07** (`8af88dc`); **closed 2026-08-22**, when a whole-backlog re-read found the
  entry still open. Cache schema **v3**: `perceptual_computed` records whether a perceptual pass
  ran, `get` takes `need_perceptual`, and `put` **requires** the flag rather than defaulting it -
  *"a default is the guess the column exists to end."* That is exactly what the entry asked for:
  *"A third state is the fix, not a `need_perceptual` alone"*, so a legitimately NULL perceptual
  (a video, an over-size image) is a hit rather than a permanent re-attempt.
  ⚠ **THE FINDING IS NOT THE FIX. IT IS THAT THE CONTRACT AND THE BACKLOG DISAGREED FOR TWO
  WEEKS.** `IMPLEMENTATION_STANDARDS.md` §8 has said *"Closed 2026-08-07 at cache schema v3"*
  since the day it shipped, while `BACKLOG.md` carried the entry as open work. **Both documents
  were current; they answered opposite questions about the same thing**, and the split that
  created `SHIPPED.md` on 2026-08-01 exists to stop exactly this. The closing commit is
  `fix(core):` and names no letter, so the closure gate - which keys on a commit declaring one -
  could not have seen it. **Nothing automatic could have caught this**; it was found by reading.
  [Full entry](research/backlog/abo.md)
- **(ach) `skipped_newer_locally` WAS SPLIT INTO TWO SINGLE-MEANING FIELDS.**
  Built **2026-08-09** (`b1d52a3`) as part of `(abx)`; **closed 2026-08-22** by the same re-read.
  `decisions.py:353,361` carry `already_newer_locally` and `awaiting_content`, and the code
  comment names the letter that did it: *"Separate from `already_newer_locally` since `(abx)`"*.
  The entry asked for precisely this - *"`(ack)`'s fix added two single-meaning fields rather than
  a third overloaded one; do the same here"* - and was marked *"Deferred to Stage 4"* while the
  thing it deferred already existed.
  ⚠ **A letter closed by work filed under a DIFFERENT letter is invisible to every gate here.**
  `b1d52a3` correctly declares `(abx)`; nothing declares `(ach)`, because the person fixing
  `(abx)` was not reading `(ach)`. `ENGINEERING_STANDARD.md` §4's sixth member is the shape - when
  something's status changes, grep for every reference to it - and it was not run, because the
  status that changed was a different entry's. [Full entry](research/backlog/ach.md)

- **(ady) THE CATALOG IS COPIED BEFORE THE MIGRATION CHAIN RUNS.**
  Shipped 2026-08-22. A transaction restores what a **failed** step touched; it cannot restore
  what a **successful** step deliberately removed. `(adl)` closed interruption, and this closes
  intent. `catalog_backup.copy_before_migration`, called from `Catalog._migrate` only when a
  chain will actually run - a fresh catalog copies nothing.
  ⚠ **`(adb)`'s refusal does not reach this case, and the difference is measurable.** That entry
  refused a catalog copy taken from a **separate process**, where any external write restarts the
  operation - *"correct-or-never-finishing"*. This runs in-process on the connection that is
  about to migrate, which SQLite documents as the safe case. `VACUUM INTO` stays refused for
  `(adb)`'s own reason: it rewrites every page, and a copy should reproduce a database rather
  than compact it.
  ⚠ **`pages=-1` IS LOAD-BEARING AND IS PINNED AS A VALUE.** Measured on 123 MB against a second
  connection committing at **376 writes/sec**: `pages=-1` finished in **2,581 ms**, one step,
  **0 restarts**; `pages=64` **committed no page in 300 s** and was killed at its bound, leaving
  a 0-byte destination and an uncleared `-journal`. Chunking it for progress reporting is the
  obvious, reasonable change that breaks it, so a test asserts the constant and carries the
  measurement to whoever changes it.
  ⚠ **IT MUST NOT RUN INSIDE `BEGIN IMMEDIATE`, AND A DIFFERENT CONNECTION'S LOCK IS HARMLESS.**
  `Connection.backup` **hangs forever** - it does not raise - when its *source connection* holds
  a write transaction: killed at 8 s, 0-byte destination, `nanosleep`, no CPU. The same source
  with a **different** connection holding `BEGIN IMMEDIATE` completes in **27.1 ms**, and with a
  read-only deferred transaction in **42.1 ms**. Without that contrast beside it the rule reads
  as arbitrary; with it, anyone reasoning *"backup needs a stable read, so hold the lock"* learns
  they have it backwards. On the launch path this would be a product that never starts.
  ⚠ **THE RESIDUE IS NOT AN EMPTY FILE, WHICH IS WHY STAGING IS MANDATORY RATHER THAN TIDY - and
  `(adr)` CANNOT SEE IT.** A write failure part-way left **1,048,576 bytes** at the destination,
  a *plausible* size with a real header, that opens as `UNREADABLE`, beside a stale `-journal`.
  `(adr)`'s discriminator is a **0-byte** file and would have passed this. `decisions.write_decisions`
  already states the general rule and this is its second instance: *"A truncated file at the right
  path is worse than no file, because it looks like a backup."* The copy is staged under a
  per-process name (`safe_copy.staging_path`) and renamed only when complete.
  ⚠ **CPython retries `SQLITE_BUSY` with no timeout of its own**, so the copy carries a deadline -
  verified reachable rather than assumed: the progress callback fires during BUSY retries (41
  callbacks in 2 s), which is the only place a bound is expressible.
  **A failure degrades and is said**: the catalog still opens, and the outcome is reported through
  `catalog_session.open_catalog`'s `backup_report`, the one seam every CLI open already goes
  through. One copy per catalog beside it (`app_paths.backup_path_for`), superseded by the next
  migration on `migration_runs`' own retention rule, with a **fixed** name so supersession is one
  atomic rename and there is no window in which no copy exists.
  **Cost, once per upgrade**: **18.66 ms** median on the real 6,365,184-byte catalog (n=9),
  **200.23 ms** at 110,628,864 bytes (n=5).
  ⚠ **What it deliberately did NOT do is `(afs)`**: a destructive migration should *refuse* rather
  than degrade, and nothing declares which migration is destructive. Filed rather than folded in,
  because it is a policy change about what a migration may do. `(aft)` came out of the same work.
  Pinned by `tests/test_catalog_backup.py`; five mutations, both directions, each with a control
  reporting 9 passed. [Full entry](research/backlog/ady.md)

- **(vv) CLOSED IN TWO HALVES, AND ONLY ONE OF THEM WAS BUILT.** Closed 2026-08-22.
  ⚠ **READ THIS BEFORE TREATING THE LETTER AS SHIPPED.** `(vv)` was a **recorded limit**, not an
  approved build - *"app per-drive job lock is process-local; CLI↔app overlap is not serialized"*.
  It closes because **neither half is still open here**, and the halves closed differently:
  - **The lock half SHIPPED**, as `(aaw)` on 2026-08-22. `(vv)` asked for *"a real cross-process
    guard (e.g. flock on the drive marker or catalog)… a separate design if soak ever shows
    CLI↔app races mattering in practice"*. ⚠ **No soak ever showed it, because no soak tested
    concurrency at all** - it was measured directly instead, two concurrent applies losing 99 and
    45 organized copies. CLI↔app and CLI↔CLI overlap on a mutating operation **is** serialized now.
  - **The remaining half was MERGED, not built.** The session-link residue - a second instance
    overwriting the first's URL file, and quitting it **deleting the link to a still-running
    first** - is single-instance detection, which is exactly what `(adn)` narrowed to once `(aaw)`
    took the write-safety half off it. It now lives in `(adn)` in full, with its `__main__.py:167`
    citation intact. **That work is unbuilt and this letter does not claim otherwise.**
  ⚠ **Why merge rather than leave both open:** two entries describing one remaining problem is how
  one of them gets solved and the other stays open, quietly, still asserting a defect that no
  longer exists. `(vv)`'s headline was already false the day `(aaw)` shipped.
  [Full entry](research/backlog/vv.md)
- **(aaw) A MUTATING OPERATION HOLDS ITS DRIVE AGAINST OTHER PROCESSES.** Shipped 2026-08-22,
  after the deferral it sat under for three weeks was found to be unresolvable by waiting: the
  gate was *"the soak will say which things break"* and **no soak tested concurrency at all**.
  ⚠ **THE ARGUMENT IS THE MEASUREMENT, TAKEN THREE TIMES.** Two `organize --apply` runs on one
  destination, real photographs, loss proven by content and never by name:

  ```
  before unique staging   4 of 5 hit, exits 1   3, 3, 1, 2 copies lost
  after unique staging    5 of 5 hit, exits 0   4, 3, 3, 3, 3 copies lost
  after the lock          5 of 5 refused        0 copies lost
  ```

  **The middle row is why the lock is not optional.** Unique staging (`7564ed6`) fixed the
  mechanism - a `.partial` derived from the target, so two runs wrote into one file - and
  **degraded the outcome**: it removed the loud `ENOENT` and left both processes exiting 0 with
  one catalog row silently wrong. A fix that improves the mechanism and makes the harm quieter is
  the trade this project spends its time refusing.
  ⚠ **Severity is mode-dependent and both halves are true**: bookkeeping plus a missing copy in
  copy mode, **irreversible loss under `--move`/`--in-place`** - the modes a user reaches when
  they have no room for a second copy.
  **Kernel-enforced, no PID check, no TTL**, so *"locked out of my own library"* is unreachable;
  the lock file is in the data dir, never on the drive; no `--force`, because a refusal always
  means a live holder. ⚠ **The FD is the lock**, so it is released when the JOB ends, not when
  `start` returns.
  ⚠ **Every caller declares and nothing defaults**: `_LOCKS_DRIVE_AT` covers all seventeen
  subcommands, and `jobs.start`'s `mutating` is keyword-only with no default, so **mypy found all
  fifteen app routes** rather than a reader having to. Never derived from the `operation` string -
  *"organize"* and *"organize preview"* differ by one word.
  ⚠ **THREE WINDOWS-ONLY FAILURES, AND TWO WERE PRODUCT DEFECTS.** The `check` matrix is the
  only thing that sees them, and this is the entry that proves the cost of not having it.
  - **`mypy` reads one platform's branch.** `import fcntl` in an `else` does not exist on Windows
    while every reference resolves on Linux - green locally, two errors on the lane.
    `ENGINEERING_STANDARD.md` §4's **sixty-first** member carries the general rule and the
    `--platform win32` command.
  - ⚠ **`msvcrt.locking` is MANDATORY where `flock` is ADVISORY, so the locked byte cannot be
    READ** - and the claim naming the holder is written into that file, for the other process to
    read. On Windows the reader got a `PermissionError`, `_read_holder` correctly answered *"no
    usable claim"*, and **the refusal was anonymous**.
    ⚠ **The consequence is the whole point, not the mechanism.** There is deliberately **no
    `--force`**, because a kernel-enforced refusal always means a live holder - so *naming the
    holder IS the escape hatch*, the only route a user has to a genuinely hung process. It failed
    on the one platform where they have no other. Fixed by locking a sentinel byte a gigabyte past
    the claim, which is the ordinary way to do this where locks are mandatory: the exclusion is
    unchanged and the text stays readable.
  - The third was the test's own assumption - `sys.executable` in a uv venv on Windows is a
    launcher that spawns the real interpreter, so `Popen.pid` is not the pid that took the lock.
    The holder reports its own.
  Mutating only; `(afq)` carries the app's preview behaviour, which is not this entry's to
  justify. [Full entry](research/backlog/aaw.md)
- **(afp) A CATALOG ANOTHER PROCESS IS CREATING IS WAITED FOR, NOT CALLED DEBRIS.** Shipped
  2026-08-22, filed the same day. Two runs starting against a catalog path that does not exist:
  one creates it, the other found it **0 bytes with a journal beside it**, refused the whole run
  and said *"Rename or delete this file and run again"* - about a **live catalog the winner was
  writing**. Measured **2 of 6** concurrent cold starts; **0 of 6** after.
  ⚠ **`(adr)`'s refusal is correct and stays - the fix is a DISCRIMINATOR, not a softening.** A
  `copy2` killed by `ENOSPC` really does leave a 0-byte file and no journal, and that case still
  refuses immediately with its original advice. What changed is the case `(adr)` could not tell
  apart: **the journal is evidence its own docstring already reasoned about** and read in one
  direction only - *"a write did not finish"* is the same observation as *"a write has not
  finished yet"*.
  **The rule, written as a rule:** *wait when the contended state is bounded and short; refuse
  when it is not.* Creating a catalog is milliseconds, so this waits, bounded at 2 s; a held drive
  lock is seconds to hours, so `(aaw)` refuses. ⚠ **The bound fails visibly rather than
  extending**: when it fires the message says the file is *still empty after 2 seconds*, that this
  is not another Truestill finishing, and **stops telling the user to delete it**.
  [Full entry](research/backlog/afp.md)
- **(aeo) A HOME DIRECTORY THAT WILL NOT TAKE A WRITE COSTS THE WAY-IN FILE, NOT THE APP.**
  Shipped 2026-08-22. A full or read-only home directory ended the launch in an interpreter stack
  trace before anything was served - `session_link.write` does `unlink` -> `touch(mode=0o600)` ->
  `write_text`, none of it guarded, on the launch path.
  ⚠ **The entry's open question - "stop the launch or degrade" - was already answered twice by the
  module itself**: its docstring rules that a filesystem which discards the mode still gets the
  file, because *"warning beats refusing"*, and `session_link.clear` is documented *"never raises:
  failing to clean up must not take the app down with it"*. The server **is** the product; this
  file is one of two ways in and the browser is the other. **Degrade, and say why.**
  ⚠ **The guard creates a second defect, and the fix includes it**: with the write guarded,
  `link.path` names a file that was never written, and the browser fallback said *"The address is
  in {path}"* - `(aey)`'s *not there offered as there*, introduced by the repair. It now gives the
  address itself. **A mutation proved that branch was unreachable from `main` until the test
  asserted the wiring rather than the renderer** - §4's sixtieth member, caught by the tool.
  ⚠ **The three-step write is untouched**, and `write` still raises: whether a failure is fatal is
  a **launch** question, not a file-format one, and swallowing it inside `write` would have given
  it a second silent contract next to the privacy tests that assert against it.
  **One errno table, two nouns**: `drive_unwritable` gained `classify_unwritable` and
  `explain_unwritable_folder`, because *"the drive is read-only"* is wrong and alarming about a
  folder the user never chose - and a second errno table is the two-copies failure that module's
  docstring exists to prevent. `explain_unwritable_drive`'s output is byte-identical, which an
  app test and an e2e test both assert. [Full entry](research/backlog/aeo.md)
- **(ace) THE MUTATION RESTORE RULE IS EXECUTABLE, AND HAS BEEN SINCE 2026-08-14.**
  - ✅ **CLOSED 2026-08-14 by `daf2656`** - *"a one-off mutation that misses its anchor now refuses
    instead of passing"* - and **filed as open until 2026-08-22**, when a read of the backlog found
    it. `scripts/mutate_once.py` is the tool the entry asked for: it verifies the anchor matches
    exactly once, that the file actually changed, and that the restore returns it byte for byte,
    exiting **2** on a miss rather than reporting success.
  - ⚠ **The entry knew.** It carried *"PROVENANCE QUESTION, FILED 2026-08-15 AND NOT ANSWERED
    HERE… `scripts/mutate_once.py` exists and matches the description"* - a question that answers
    itself the moment anyone runs `ls`, left open for a week. **The proposal asked for
    `scripts/mutate.py` and the tool shipped as `mutate_once.py`**, which is the whole of why it
    was not noticed: the letter was matched against a filename rather than against a behaviour.
  [Full entry](research/backlog/ace.md)
- **(aak) THE SKIPPED-FILE SUMMARY HAS ONE HOME, AND HAS HAD SINCE 2026-08-04.**
  - ✅ **CLOSED 2026-08-04 by `c027dd3`** (*"a hidden file is still skipped, and is now counted and
    named"*), which replaced the duplicated body with `return skipped_extension_counts(scan)`.
    **Filed as open until 2026-08-22.**
  - The surviving docstring states the closure and its date in place - *"A thin alias, deliberately
    not a second implementation. This was a verbatim copy of `organizer.skipped_extension_counts`
    until 2026-08-04"* - so the code has said so for eighteen days while the backlog said the
    opposite. ⚠ It was closed as a **side effect** of a feature commit rather than by a commit
    naming the letter, which is exactly the case the `Closes (xyz)` rule cannot catch.
  [Full entry](research/backlog/aak.md)
- **(abi) THE GEOMETRIC PILLAR T REACHES EVERY ICON, AND HAS SINCE THE DAY THE ENTRY WAS FILED.**
  - ✅ **CLOSED 2026-08-05 by `703e3b1`** (*"one mark everywhere - the pillar T replaces the TS
    monogram"*), which rewrote the builder to read `brand/pillar-t-geometric*.svg`, dropped the
    `fontTools` imports from the icon path and **regenerated every committed PNG and the favicon**.
    Its first line now reads *"THE ICONS COME FROM `brand/pillar-t-geometric*.svg` and need no font
    at all."* **Filed as open until 2026-08-22.**
  - ⚠ **Entry and fix are the same day**, so this was never a gap - it was a note written hours
    before the work and never struck out. Only the wordmark and the orphaned Libre Caslon marks
    still come from a font, which the builder says in place.
  [Full entry](research/backlog/abi.md)
- **(afm) A RUN ARGUES FILE BY FILE ONLY WHILE IT CAN STILL BE STOPPED.** Shipped 2026-08-22.
  An ordinary **successful** organize of 2,110 files printed 15,128 lines, 15,082 of them the
  `NEW UNIQUE` block - and printed them identically under `--apply`, when there is nothing left
  to stop. ⚠ **The defect was not volume; it was one function serving two documents** - a decision
  sheet read before typing a word, and a listing scrolled past after the run was authorised.
  `_print_report` and `_print_skipped_undated` take `listing=not args.apply`; a preview keeps the
  whole argument, an authorised run keeps the counts. **`listing=False` prints nothing rather than
  a compact tally**: `_print_summary` already carries every count those headers did, and a second
  copy is the `(abl)` shape - two blocks of one report, free to disagree.
  ⚠ **What may be dropped is only what something else still holds**, which is why this needed
  `(afl)` first: under `--apply` every file is in the record with what happened to it, so the names
  can go; a preview writes **no** record, so its listing is the only copy and stays whole. `(afd)`'s
  cap was uncomfortable for exactly the opposite reason - there the elided lines were the only copy.
  **Coverage shipped first, in its own commit** (`a4f0d45`): the listing had no test, and **no suite
  in this repo asserted output volume anywhere**. Slope, not size - 7 lines per entry, and zero for
  the capped control. [Full entry](research/backlog/afm.md)
- **(afo) A FOLDER THAT REFUSED IS NO LONGER REPORTED AS ONE WITH SOMETHING IN IT.** Shipped
  2026-08-22. `LEFT ALONE - something is in there (1):` above `Camera/2013   []` was two
  contradictory claims on one line, and the truth was neither. Now a second heading - *"could not
  be opened"*, `(aer)`'s wording - with no bracket, because there are no contents to name.
  ⚠ **A field, not a fourth tier**: `Candidate.removable` is defined NEGATIVELY, so a new member
  would have been removable by default and a refused folder offered for removal - the inversion
  the fix exists to prevent. Pinned by a test that asserts the property rather than the tier.
  ⚠ **Not inferred from `contents == ()`**, which is exact only by accident. Two producers -
  `reach` refusing and `iterdir` raising - the second of which had **no test at all**, and both
  mutation-proved separately. [Full entry](research/backlog/afo.md)
- **(afn) A DRIVE WHOSE SAMPLE CANNOT BE READ IS NO LONGER REGISTERED AS A NEW ONE.** Shipped
  2026-08-22. A **perfect** drive with 30 of 40 sampled paths unreadable returned `[]`, printed
  nothing, and was minted a second drive id for one library - the exact harm `cli.py`'s refusal
  states and never fired. `AdoptionVerdict.UNREADABLE` now separates *nothing matched* from
  *nothing could be read*, and both registration paths refuse. ⚠ **The denominator was NOT
  changed**, and the reason is recorded: with 39 of 40 refused, one readable file would carry a
  verdict that authorises attaching rows `reclaim` deletes on. `source_repoint` was the control -
  already safe, green **unedited** at 40 insertions / 0 deletions - and now says which refusal it
  was rather than *"0 of 0 sampled files matched"*. Cost is a message with `--force-new-identity`,
  pinned. Two findings from the tests: a precondition that could not fail (`os.stat` on a mode-000
  directory succeeds), and a surviving mutation that was §4's sixtieth member inside a guard's own
  test. [Full entry](research/backlog/afn.md)
- **(afh) THE STRONGER ACT GETS THE STRONGER WORD: `reclaim` NOW ASKS FOR `delete originals`.**
  Shipped 2026-08-22. Measured from two real runs: `reclaim` removed 161 of the user's own
  photographs behind **three lines and `delete`**, while `clean-empty --permanent` removed three
  empty folders Truestill itself emptied behind **six lines and `delete forever`**. Neither was
  untruthful; the ceremony was inverted relative to the stakes. Raised rather than levelled down,
  because lowering the strong word is the cry-wolf failure the vocabulary exists to prevent. The
  new confirmation states what is removed, that they are **originals and not spare copies**, that
  they do not go to the trash, and that it cannot be undone. ⚠ **§1's trash condition (d) is
  explicitly NOT extended to `reclaim`** - recorded as a ruling with its reason: trashing 117 GB of
  originals is a second copy on the same filesystem, in a command whose purpose is to free it.
  [Full entry](research/backlog/afh.md)
- **(afl) A RUN WRITES DOWN WHAT IT DID.** Shipped 2026-08-22, and **re-ranked rather than
  deferred**: filed as "the product has no verbosity control", closed with a record instead,
  because the right destination for verbose detail turned out to be a **file rather than a flag**.
  ⚠ **The finding that outranked it**: after the terminal scrolled, *nothing* could answer "which
  photos failed?" - `--report` was built from the plan before execution, `files.upload_status` only
  ever holds `'uploaded'`, and there is no logging anywhere. So `(afd)`'s cap had elided the only
  copy. One rolling `last-run.json` beside the catalog, automatic, built from `results`, carrying
  the stop and the count of files never attempted. `--report` now says only *where*. ⚠ **A preview
  writes nothing**, which makes the DRY RUN banner true for the first time. ⚠ **Honest limit
  recorded**: written after execution, so it survives a stop and not a kill.
  [Full entry](research/backlog/afl.md)
- **(afd) A FAILURE LIST IS ONE FACT, NOT TWO THOUSAND.** Shipped 2026-08-22. Measured on the real
  library rather than carried from the soak: a destination denied after ten files gave **2,096
  `FAILED` lines on stderr carrying ONE reason**, beside a summary that already said
  `2096  failed`. Now **25 stderr lines**: 20 named, then *"... and 2,074 more FAILED (all the same
  reason)"* - and *"N distinct reasons in total"* when the tail is mixed, which is the half that
  makes eliding safe. Capped with the existing `_STATUS_PREVIEW`, whose comment claimed it was
  `status`'s while six sites shared it. ⚠ **The stream was never the defect**: clig.dev puts errors
  on stderr on purpose, and *"don't treat stderr like a log file"* is what 2,096 lines violated -
  which is also why `> log.txt` never helped. A pager was **considered and rejected** (organize
  runs non-interactively; clig's own caveat). `MOVE KEPT` shares the fix; ⚠ its worst case stays
  **unmeasured**. Wording stayed with `(aep)`; `--verbose` did not exist to use, which is `(afl)`;
  the title's "one uncapped list" claim was falsified and split to `(afm)`.
  [Full entry](research/backlog/afd.md)
- **(afi) `clean-empty` SEES WHAT AN IN-PLACE ORGANIZE EMPTIED, AND THE RUN SAYS SO.** Shipped
  2026-08-22. `migrated_old_paths` read `migration_journal` alone; `organize --in-place` writes
  `inplace_moves`, so the mode that leaves the most behind was the one whose leftovers nothing
  could see. ⚠ **Two halves**: the query, and the fact that `organize` never called
  `_offer_cleanup` at all - a comment beside its report claimed an offer "follows" that did not
  exist. ⚠ **The union is restricted to `source_root == dest_root` as a SAFETY condition**, not a
  tidiness one: `Relocation` is built for plain `--move` too, whose `old_relative` is relative to
  the user's import folder, so an unrestricted union would have offered folders on the wrong root.
  A second hazard was closed on the way: an absolute journal path escapes `root / relative`
  outright, and with the guard removed the ancestor walk **hangs** rather than fails - the walk now
  breaks on the fixed point too. Decided: one query, not one journal, because `undo-organize`
  reverses those tables and `(yy)` left that decision alone.
  [Full entry](research/backlog/afi.md)
- **(afj) `clean-empty` NO LONGER REMOVES A FOLDER ITS OWN PREVIEW DID NOT NAME.** Shipped
  2026-08-22, together, because neither ordering existed. The contents now go to the trash and the
  **folder goes to `rmdir`**, whose emptiness precondition the kernel enforces atomically -
  `send2trash` has none, measured, so a folder that gained a file between the preview and the typed
  word was handed over whole. ⚠ **Not "make trash re-verify like permanent"**: neither path ever
  re-verified, and a check before the move would be the race the module was written against.
  `--permanent` now governs only the junk; the typed word stays `clean` (see `(afh)`). The `rmdir`
  guarantee moved out of the flag-keyed block and is printed for every run. Uncovered three things:
  a refusal test that was **passing while testing nothing**, `send2trash` raising where
  `unlink(missing_ok=True)` shrugged, and `folder.is_dir()` being check-then-act on the path whose
  property is that it does not check. ⚠ The trade is recorded: the directory entry is removed
  outright on every path, and trashed junk records a parent that no longer exists, so the report
  may say *"the junk is in the trash"* and never *"you can put it back"*.
  [Full entry](research/backlog/afj.md) · [`(afk)`](research/backlog/afk.md)
- **(afk) A PARTIAL REMOVAL NO LONGER READS AS NONE.** Shipped 2026-08-22, **inside `(afj)`**,
  which is what its own entry predicted: *"`(afj)` option A would introduce an unlink-then-check
  step there and would inherit this exactly."* Neither ordering existed - shipping `(afj)` alone
  gives every ordinary run a partial state its report cannot describe, and fixing this first fixes
  the reporting of a code path `(afj)` replaces. The remedy is
  `cleanup._partial_removal_reason`: *"not removed (directory not empty); its .DS_Store is in the
  trash"*. ⚠ The order was **not** touched, per this entry's instruction - junk still goes before
  the `rmdir`, because `rmdir` being last is the whole guarantee.
  [Full entry](research/backlog/afk.md)
- **(yy) RECONNECT A MOVED LIBRARY - `truestill repoint-sources OLD NEW`.** Built **2026-08-02**;
  ⚠ **moved here 2026-08-22, having sat in `BACKLOG.md` as unbuilt for three weeks while
  `PROJECT_STATUS.md` said it was built and this file did not mention it at all.** Which of the
  three was right was settled by asking the product: the subcommand exists and `(yy)`'s own body
  has said *"BUILT 2026-08-02"* since the day it landed. Preview, content proof (`inspect_root`:
  stat-sample then three full reads that must agree), typed `repoint`. ⚠ **`(xx)` stays open** and
  is the other half: the stored paths are still absolute, so this repairs a move rather than
  preventing the next one. `reclaim_journal.source_path` and `inplace_runs.*_root` are
  out of scope by decision, not oversight - see the entry.
  [Full entry](research/backlog/yy.md)
- **(aen) A CATALOG WHOSE LOCATION CANNOT BE PREPARED IS REPORTED, NOT A TRACEBACK.** Shipped
  2026-08-22. Its own constraint held: `_BUSY_CODES` is unchanged, and the new recognition is a
  separate family beside it. ⚠ **The half neither entry saw**: `Catalog.__init__` creates the
  catalog's parent before connecting, so on a read-only disk the failure is a `PermissionError`
  that is not a `sqlite3.Error` and walked past the handler `(afe)` had just added - now
  `CatalogUnwritableError`, carrying its errno as the diagnostic. Also corrects a §9 wrinkle
  `(afe)` introduced: the backstop sentence described work the command may never have done.
  Residual named, not fixed: the startup banner still offers to create a catalog it cannot.
  [Full entry](research/backlog/aen.md)
- **(afe) A CATALOG THAT CANNOT BE WRITTEN STOPS THE RUN AND REPORTS IT, INSTEAD OF A TRACEBACK
  AND A FILE NOBODY RECORDED.** Shipped 2026-08-22. Split on SQLite's own result code: busy is
  waited out with bounded backoff and stays a per-file event; anything else is permanent within
  the run and ends it with a report - what landed, what was recorded, the difference, and where
  to go - and stops copying. The copy whose row never landed is **removed again**, verified by
  checksum first and never under `--in-place`, where it is the user's only copy. ⚠ **Three
  measurements moved the design**: `sqlite_errorcode` carries *extended* codes, so R5 is 1544 and
  three genuine busy codes were being misread as faults; R5 presents as `SQLITE_IOERR_DELETE` as
  often as `READONLY_DIRECTORY`; and guarding the write loop alone left the traceback to reappear
  from `finish_organize_run`, so the refusal belongs at each surface's one catalog seam.
  Convergence measured before and after: an orphan used to become a `_1` duplicate on the next
  run, and now the next run ends 72 files / 72 rows / 0 suffixes.
  [Full entry](research/backlog/afe.md)

- **(aex) A RELEASE BUILD IS STAMPED WITH A VERSION OR REFUSED - NEVER WITH A REF'S NAME.**
  - ✅ **CLOSED 2026-08-22.** Confirmed twice in real runs: a dispatch from `main` produced
    **`TruestillSetup-main.exe`** - a branch name in the installer's filename and in Add/Remove
    Programs - and **passed every gate**: self-check, comparison, install, verify, uninstall.
  - ⚠ **The Windows guard could not fire, which is worse than not having one.**
    `if (-not $version) { $version = '0.0.0-dev' }` sat directly below `$version` being set to
    `github.ref_name` minus a leading `v` - on a dispatch, `main`, a **non-empty** string. It looks
    exactly like the Linux defence beside it and defends nothing. **A guard that cannot fire reads
    as coverage and stops anyone looking.** Said at the fix, not only here.
  - ⚠ **AND LINUX WAS NOT THE HALF THAT WAS RIGHT.** Its
    `[ "$version" != "main" ] || version="0.0.0"` hardcoded **one branch name**, so a dispatch
    from any other branch failed identically - and `0.0.0` is **indistinguishable from a real
    release**. Windows produced something obviously broken; Linux produced something **plausibly
    wrong**, and the plausible one outlives the obvious one.
  - **So the fix is the shape, not the instance, and the rule is VALIDATE rather than fall back** -
    the industry pattern for a release workflow. The question is *is this ref a version tag*, never
    *is this ref `main`*. On a tag: strip `v`, require **three-component semver**, and **refuse**
    anything else rather than coerce it - `v2`, `v1.2`, `vNext` and `v1.2.3.4` are all refused,
    because the publish job runs on tags and a guess would ship. On a dispatch:
    `0.0.0-dev.<run id>`, unmistakable and traceable. **One derivation, `shell: bash` so the one
    step serves both platforms** - two derivations is how the two answers came to disagree.
  - `packaging/build_deb.py`'s own `--version` default moved from `0.0.0` to `0.0.0-dev` for the
    same reason; `packaging/installer.iss` had defaulted to `0.0.0-dev` all along and the workflow
    ignored it.
  - **The regression test EXECUTES THE STEP'S OWN SCRIPT** out of the YAML with the environment a
    runner sets, so what is pinned is the decision rather than the spelling - four branch names,
    four tag shapes, and five refusals. ⚠ **What it cannot test is stated in the module**: that
    GitHub wires `$GITHUB_OUTPUT`, that `pwsh` interpolates the output into `ISCC.exe`, and that
    `bash` exists on the Windows image. Those need a dispatch, and a dispatch is what found this.
  - ⚠ **AND A THIRD ARTEFACT WAS STILL REF-NAMED, found by reading the artefact list of the very
    run that proved the other two.** The archive was
    `truestill-${{ github.ref_name }}-${RUNNER_OS}`, wrong in both directions and only one of them
    obvious: on a dispatch it produced `truestill-main-Linux.tar.gz`, and **on a tag it would
    produce `truestill-v1.2.3-Linux.tar.gz`** - `v`-prefixed, beside `truestill_1.2.3_amd64.deb`
    and `TruestillSetup-1.2.3.exe`, three artefacts of one release disagreeing about their own
    version. Fixed in its own commit, and the guard widened from the two packagers to **every step
    in the build job**: the search had been for *"version"* rather than for *"a ref name in a
    filename"*, which is why the third was missed.
  - **The publish job is deliberately out of scope**: `gh release create "${{ github.ref_name }}"`
    names a GitHub release after its tag, which is correct and is not a filename.
  - **Four mutations, all caught**: stamping `0.0.0`, stamping the ref name, relaxing the
    three-component rule so `v2` is coerced instead of refused, and re-naming the archive after
    the ref.

- **(afc) A DRIVE THAT IS MERELY UNMOUNTED IS NO LONGER OFFERED REGISTRATION.**
  - ✅ **CLOSED 2026-08-21.** `verify` on a cleanly unmounted mountpoint said *"isn't a Truestill
    drive yet - register it with `drives --init`"*. Following the product's own advice minted a
    **second drive identity** and wrote a marker **into the mountpoint**, after which the real
    drive could not be mounted there again and `verify` reported *"has no recorded copies"* about
    a drive holding forty.
  - ⚠ **THE GUARD ALREADY EXISTED AND WAS WIRED TO THE WRONG COMMANDS.** `ghost_drive_at` and
    `ghost_drive_refusal` were written for exactly this, with the sentence nobody derives alone -
    *"Anything written here now would go onto THIS computer's disk, and would DISAPPEAR from view
    the moment the drive comes back - while still using the space."* Two callers, both on the
    `organize` path. `drives --init` guards by **content**, and an empty mountpoint has none: the
    door `ghost_drive_at`'s own docstring names as the one `(aap)`'s content guard is blind to.
  - **Detection was never the answer, and that is measured, not assumed.** An unmounted mountpoint
    is byte-for-byte an ordinary empty directory - `os.path.ismount` False, `st_dev` equal to the
    parent's, absent from `/proc/mounts`, on Linux and macOS alike; Windows has no such state at
    all. **Only a recorded expectation discriminates**, which is the industry pattern rather than
    our invention: administrators set `chattr +i` on empty mountpoints by hand for this exact
    hazard, and it is recorded in the entry as prior art - **with its cost**, since it breaks
    `borg mount`.
  - **A**: the guard now runs in `_init_drive` and in the resolver every drive command shares.
    **E**: the hint is written at more sites, so the discriminator exists more often. **B**: where
    nothing was ever recorded, the message stops instructing and names **both** readings and what
    the wrong guess costs.
  - ⚠ **E COLLIDED WITH TWO CONTRACTS AND THE TESTS SAID SO, WHICH IS WHY IT IS PLACED WHERE IT
    IS.** A migrate **preview** asserts the catalog file is byte-identical afterwards, and a
    location hint is still a write; and a hint write marked the catalog `dirty`, which fires
    `save_decisions_to_reachable_drives` - turning a read-only command into one that **writes to
    the user's drive**. So `Catalog.set_local_setting` writes without dirtying, justified because
    `decisions._EXCLUDED_SETTING_PREFIXES` filters `path_hint.` **out of the document**: the save
    it would have fired writes an identical file. **It refuses a key the document would carry**,
    which is what keeps it from being a footgun - and that refusal survived its first mutation
    until a test was written for it.
  - **The rule for WHERE is "wherever the command already writes drive facts"**, so a preview
    never gains a side effect. Reclaim records beside its existing `upsert_drive`; migrate records
    past its typed confirmation, so an **aborted** migrate is still byte-identical.
  - ⚠ **Two existing guards fired and were satisfied rather than worked around.** One forbids a
    surface constructing a `Catalog` outside the session wrapper - a probe that skipped it would
    be the one call site where the drive copy silently stops moving; re-testing showed the session
    was never the problem and the workaround was reverted. The other requires every hint write to
    ask whether that uuid answers elsewhere **before** overwriting the evidence, and `(afc)`'s own
    refactor **defeated its detector** by moving the write behind a helper - its count test caught
    that, and the detector now knows both shapes.
  - **Five mutations. One survived the first pass and was then KILLED**, which is the resolution
    rather than the whole story: nothing pinned `set_local_setting`'s refusal of a
    document-carried key, so removing the check failed no test.
    `test_a_setting_the_document_would_carry_is_refused` was written for it and the mutation is
    caught. ⚠ **All five are caught against the code as shipped.**
    > *Correction, 2026-08-21, beside the line rather than into it: this first read "Five
    > mutations, one survived", which is true of the first pass and reads as unresolved. Every
    > other entry this week states the resolution - killed, code changed, or an explained
    > equivalent - and this one did not. The resolution is **killed by a test written for it**;
    > compare `(aey)`, where a surviving mutant was resolved by changing the **code** instead,
    > because the branch it removed carried no weight.*

- **(afb) THE THIRD BARE PREDICATE IN A DELETE PATH, FOUND BY SWEEPING RATHER THAN BY A FAILURE.**
  - ✅ **CLOSED 2026-08-21.** `cleanup.plan_cleanup` gated on a bare `folder.is_dir()`. With the
    folder's **parent** refused it **raised `PermissionError` on 3.13** - inside a function whose
    own docstring promises *"Pure: reads, never writes"*, which is the guarantee that makes a
    cleanup preview safe to run. A traceback at the end of a successful organize.
  - ⚠ **3.14 masked it, exactly as it masked `(aez)`** - the second time the version treated as
    the threat turned out to be hiding a live defect on the version we ship.
  - **Reported `OCCUPIED`, not skipped.** On 3.14 the folder vanished from the plan through a
    `continue` that means *"somebody already dealt with it"*. A folder that will not answer was
    not dealt with. `OCCUPIED` is what `_classify_with` already returns when `iterdir` refuses, so
    the module's two unreadable cases now agree.
  - **Found by the sweep `(aez)` provoked**, on the maintainer's reading that two bare probes in
    one module with the helper adjacent means nobody has looked. Every destructive call in
    `packages/*/src` was read: `organizer._move_source` is **clean and is the correct shape** - it
    verifies by checksum, not by a predicate, and catches around both steps - and the remaining
    `unlink`/`replace` calls touch only Truestill's own temp files and journals. **Two of the
    three delete-adjacent modules carried the defect.**

- **(aey) ABSENT AND REFUSED ARE DIFFERENT ANSWERS, DECIDED ONCE, FROM ONE STAT.**
  - ✅ **CLOSED 2026-08-21.** On Python 3.14 `Path.is_dir()`/`exists()`/`is_file()` stop raising on
    `EACCES` and return `False` ([cpython#144525](https://github.com/python/cpython/issues/144525)),
    so five sites answered *not there* about a path that had refused. `probe_dir` returned
    `MISSING`, which on this product's surfaces means **creatable**: offer to create a folder that
    already exists and whose creation fails exactly as the probe did.
  - ⚠ **3.14 did not invent this; it removed pathlib's exception to it.** Its `is_dir()` is
    `return os.path.isdir(self)`, and `os.path` has swallowed every `OSError` for as long as it
    has existed. **pathlib was the outlier this code relied on** - which is why the fix is a
    primitive of our own, `truestill_core.path_reach`, and not a version check. It answers
    identically on both interpreters, so nothing waits for an upgrade.
  - **The classification is CPython 3.13's, copied deliberately** - `_IGNORED_ERRNOS` and
    `_IGNORED_WINERRORS`, the set 3.14 deleted. That is what makes this a forward fix rather than a
    behaviour change on the version we ship, and each of the three arms is a measured trap, not a
    formality: **`ELOOP`** (a symlink loop answers `MISSING` today, and "any OSError is refusal"
    would flip it), **`ValueError`** (a NUL byte: `stat()` raises it on both versions where the
    predicates return `False`), and **`ERROR_NOT_READY`** (a Windows drive with no media). ⚠ The
    last is **arguably wrong** - *creatable* is a poor thing to say about an empty optical drive -
    and is preserved anyway, because changing it is a 3.13 behaviour change and belongs to its own
    decision. It is also the one branch **no lane but Windows executes**.
  - **Cheaper than what it replaced, not merely equal.** `probe_dir` promised O(1) and spent
    *two* stats on every non-directory (`is_dir()` then `exists()`); it is now one, always.
  - ⚠ **A SURVIVING MUTATION FOUND A SECOND STAT NOBODY HAD NOTICED.** Removing `nearest_device`'s
    refusal branch changed *nothing*, because the code took the stat again and it failed the same
    way - an equivalent mutant, and a fair signal that the branch carried no weight. The fix was
    to stop taking it twice: `path_reach.probe` hands back the `stat` it already took, so a walk
    is one syscall per level as its docstring always claimed. Writing a test that could not tell
    the difference would have been the other option.
  - **The five sites, each keeping its own answer**: `probe_dir` → `UNREADABLE`; `nearest_device`
    stops with `blocked_at` instead of borrowing an ancestor's device; `LocalDestination.exists`
    **raises** rather than telling the write path a slot is free; `date_rescue` skips instead of
    reporting *"none"*; `drive_adoption` counts nothing instead of counting absence - which can
    flip an adoption verdict to `NO_MATCH` for a drive that is merely not answering. **Three of
    the five already carried the rule in a comment while getting it wrong.**
  - ⚠ **`reclaim` deliberately does NOT use the shared home, and that is recorded as a decision
    rather than left as a gap.** It is the only path that deletes a user's files, so *not there*
    and *I could not look* must land on the same conservative side; acquiring the distinction
    would mean acquiring the ability to act on it. `_readable_file` says so in its own words, so
    the next uniformity sweep does not migrate it.
  - ⚠ **AND PINNING THAT PROPERTY FOUND A LIVE 3.13 DEFECT, `(aez)`** - it held by coincidence,
    not by assertion, and in one place it did not hold at all.
  - **Two blindnesses over one defect, and only one was the skip.** `_really_locked` probed *"did
    chmod deny?"* through `is_dir()` - the subject - so on 3.14 it concluded the OS had not denied
    and the test **skipped**. `_deny` **replaces** `Path.stat`/`is_dir`/`exists` with raising
    versions, so its assertions ran against a fake of the *pre*-3.14 stdlib and passed while the
    product was broken - and **fixing the product does not fix that one**. The fake is kept: it is
    this area's only Windows coverage, now annotated with what it cannot catch.
  - **The tests assert the product's answer, never the stdlib's.** The discriminator makes the
    predicates swallow - simulating the **new** stdlib, the exact inverse of `_deny`'s mistake -
    and asserts `probe_dir` is unmoved; it **failed on 3.13 before the fix** and runs on every
    lane including Windows. The real-`chmod` test takes its precondition through `os.stat`, which
    the subject does not share. Verified end to end: `probe_dir(refused)` is `unreadable` on
    **both** interpreters, and the suite now reports an identical **2,681 passed, 1 skipped** on
    each - the version-conditional skip is gone.

- **(aez) RECLAIM ABORTED WITH A TRACEBACK WHEN A BACKUP COPY REFUSED TO BE READ.**
  - ✅ **CLOSED 2026-08-21**, found by writing `(aey)`'s pin and fixed in the same commit.
  - `_verify` probed with a bare `path.is_file()` (`reclaim.py:107`) and `run_reclaim`'s
    re-verify with a bare `candidate.source_path.is_file()`. On 3.13 those **raise** on a refused
    path, uncaught, so `plan_reclaim` died with a `PermissionError` instead of counting the copy
    unverified - and `run_reclaim`'s ran **mid-loop, after earlier candidates had been deleted**:
    a partial run ending in a traceback rather than a kept file and a count.
  - **The guarded helper was three functions above them.** Both now go through it, and it is
    renamed `_readable_file` - for the question rather than for one caller, because calling it
    `_source_present` at a destination site is how the two probes came to bypass it.
  - ⚠ **Ironically 3.14 hides this one**: there `is_file()` returns `False`, so the crash becomes
    a safe skip. The defect was live only on the version we ship, and only until something
    refused.

- **(aev) THE RUN SAYS WHAT IT COULD NOT COMPARE, AND STOPS PRINTING A LIBRARY'S WORDS.**
  - ✅ **CLOSED 2026-08-21.** One `organize` over the format corpus put **866 lines** on stderr.
    It now puts **2** - the progress line - and the report states what was removed and why.
  - ⚠ **THE ENTRY HAD THE SUBJECT BACKWARDS, AND THAT IS THE FINDING.** Measured: **478 image
    files got no near-duplicate check and only 71 of them warned**, while **14 warned and decoded
    perfectly well**. The 131 warnings were a **lossy 15% proxy** for a gap the product never
    mentioned. Suppressing them alone would have made Truestill *quieter about a real gap* - §4's
    forty-second member. **What ships is derived from the decode OUTCOME**
    (`organizer.uncompared_photos`), never from whether a library spoke.
  - **The fact was already in the data and nobody asked the question**, which is `(aer)`'s shape
    again. `FileHashes.perceptual_computed` exists because *"`perceptual=None` answers two
    different questions - not an image and nobody looked"*. That settled two of three; the third,
    *an image a pass tried to decode and could not*, was derivable since the field shipped.
  - ⚠ **`warnings.catch_warnings` IS DELETED, NOT WIDENED.** It assigns process-global module
    attributes and `scan.py` hashes on a `ThreadPoolExecutor` **by default** - CPython's own docs
    say *"the behavior is undefined"* with two or more threads, so the old one-class suppression
    was unsound on the common path and widening it would have widened the race. The upstream fix
    is out of reach: gh-128384 filed it, the `ContextVar` implementation (gh-130010) is *"Changed
    in version 3.14"*, and *"defaults to `1` on free-threaded builds and to `0` otherwise"*. This
    project runs 3.13 *(2026-08-22: 3.14 now, and the flag is still `0` there - the argument was
    written against the flag rather than the version, so it did not move)*. **JAX hit the same
    wall** (jax-ml/jax#25626) and hooks the warning
    infrastructure; `decode_noise` does the same - **one write per process, at a phase boundary,
    never while workers are in flight**, so the race window is never opened rather than managed.
  - **Installed in two places because there are two, and each has its own test.** `pool="thread"`
    is the default and is covered by the parent-side call; `ProcessPoolExecutor` children get
    ``initializer=``. ⚠ The child test is **forced onto `spawn`**: Linux defaults to `fork`, where
    the child inherits everything and the initializer changes nothing - the first version passed
    with it deleted. macOS and Windows are spawn, and both are CI lanes.
  - **The action is `"always"`, and that is load-bearing.** `warn_explicit` consults
    `__warningregistry__` **before** dispatching, so the default drops repeats: **197 raised, 133
    printed**. A hook without it would have counted 133 and called it the truth. The run now
    reports **189**.
  - **fd 2 is process-wide, and the plan says so rather than pretending otherwise.** libtiff and
    libjpeg write there directly; under a worker pool several decodes are in flight and the lines
    name no file, so **per-file attribution is impossible and was not attempted**. They are
    counted at phase level and discarded - safe for one measured reason: `grep -c` for the source
    path over a whole 866-line run returns **0**. Progress survives because
    `_progress_printer` writes through the `sys.stderr` *object* while C writes to the
    *descriptor*; the object is repointed at a duplicate of the real fd 2 - and **only when it is
    actually backed by fd 2**, a condition a red test taught: swapping pytest's capture object
    stole the run's own progress from the harness watching for it.
  - **No thread-local, on the maintainer's own reversal.** The shape first expected was a
    contextvar naming the file being decoded; `_hash_one` already returns its path, so
    per-file facts ride `HashJobResult` and a thread-local would be a second encoding of a fact
    the return value already holds.
  - **Eleven mutations, two survived first.** The process-pool test asserted `>=` against a
    **cumulative** counter, so leftovers from earlier tests satisfied it with the initializer
    deleted - now a delta. And nothing guarded the fd-2 restore, the worst failure here: a leaked
    redirect loses every later line the process writes, unrecoverably on Windows. Its test runs in
    a **subprocess**, because pytest has already replaced fd 2 and could not see the leak.
  - ⚠ **SCOPED TO THE EXTERNAL LIBRARY, AND BOTH DEFENCES ARE PINNED SEPARATELY.** We do not
    silence our own signals: the filter matches ``module=PIL\..*`` and the hook swallows only when
    the raising file sits under a `PIL` directory; everything else is handed to the previous
    `showwarning`. Proved by a warning raised **from inside `truestill_core.hashing`** during a
    real hashing pass, beside a file that makes Pillow warn on the same pass - ours reaches the
    terminal with our own path, Pillow's does not. **Thirteen mutations now**: widening
    `_PIL_MODULE` to `.*` survived at first, because the hook's filename check still refused our
    warnings while every behavioural test stayed green - two defences over one property with only
    one pinned (§4's eighth member). The filter's scope is load-bearing in its own right: its
    action is ``"always"``, so unscoped it would force every warning in the program to repeat and
    **silently defeat a `-W error` setting**, including this repo's own.
  - **What could not be stopped, and what was.** `TiffImagePlugin.py:950` re-emitting an
    `OSError` as a bare `UserWarning`, and libtiff writing to fd 2, are not ours to prevent. What
    the product controls is whether a **venv path and a line number** are shown to a person
    instead of the true thing - and the true thing is *478 photos were not compared, and 787 lines
    naming no file were removed*. Both are now said; neither was before.
  - **Verified on both pools**: thread and process report an identical **787 = 189 + 598**.

- **(aew) ONE REMEDY PER READ FAILURE, WHICH IS WHY THE REASONS EXIST.**
  - ✅ **CLOSED 2026-08-21**, found while measuring `(aev)` and fixed in the same commit.
  - The block printed *"fix the permission or check the disk, then run again"* under **all five**
    reasons. On the format corpus **8 of 8** files named under it were `UNDECODABLE` - nothing
    ails their permissions or their disk - and `UNDECODABLE` was added by `(aet)` *precisely* to
    escape a wording that sent readers after the wrong thing, then rendered under it anyway.
  - ⚠ **The heading contradicted its own rows**: *"Files that could not be read"* sat directly
    above *"could be read, but its contents could not be decoded"*. It now names the
    **consequence** - *"Files that were not organized"* - which is true of all five.
  - `models.unreadable_remedy` beside `unreadable_label`, mirroring `folder_skip_remedy`; the list
    is grouped by reason, so each group carries its own next action. Exactly what `(aer)` did for
    folders, on the file side. The association is pinned **by block** rather than by line, because
    a test that finds a name and a reason anywhere in the output passes with every reason attached
    to the wrong file.

- **(aer) THE SKIPPED REPORT NAMES WHAT IT DID NOT LOOK AT, ON EVERY SURFACE.**
  - ✅ **CLOSED 2026-08-21.** A folder holding 21 photos, 18 of them in `.MyAlbum`, reported
    *"files analysed: 3 · organized (unique): 3"* and **success**. It now names the hidden file,
    names the hidden folder, and says what to do about it - in wording identical to `analyze`'s,
    because both now print the same groups.
  - **The file half was a renderer ignoring a home that already existed.** `_print_skipped` read
    four `SourceScan` fields directly and never `skipped_extension_counts`, which has carried
    `hidden` since `c027dd3`. It now renders the census, like the other two. ⚠ **One surface of
    three, not "analyze right, organize wrong"** - the app already read it, and
    `_skipped_summary`'s docstring even calls itself *"a thin alias, deliberately not a second
    implementation"*. The sharing was done; one renderer never joined.
  - **The folder half had no home at all**, so `organizer.SkippedFolderGroup` is a **sibling of
    the census, deliberately not part of it.** The census is `{group: {label: count-of-FILES}}`,
    and `SourceScan`'s own docstring calls folders *"a different kind of fact from every other
    list here"*: a number there meaning *folders* would be two shapes in one string.
  - ⚠ **ONE ENTRY PER REASON, NOT TWO FLAT LISTS**, on the maintainer's ruling: the two facts are
    the same shape - *a folder the walk did not enter, named without a count* - and what differs
    is **why** and **what to do**, which is a value rather than a field. Two lists would have
    scheduled §4's fifty-sixth member in advance: a third reason gets a third list, a third
    renderer branch, and a third chance for one surface to miss it.
  - ⚠ **THE ABSENCE OF A FILE COUNT IS THE TYPE, NOT A COMMENT.** `folders` is `tuple[str, ...]`
    with no integer beside it, so turning a folder line into *"18 files"* means changing the class
    rather than editing a docstring somebody may disagree with. `c027dd3`'s rule is cited at the
    structure and at the renderer.
  - **The reason drives the remedy from ONE place**, which is the condition the whole shape rests
    on. `label` and `remedy` arrive already worded from `models`, so neither the CLI nor `app.js`
    maps a reason to a sentence. ⚠ **That remedy existed THREE times** before this: verbatim at
    `cli.py:2713` and `:2872`, and again in `app.js` **worded differently** - *"then preview
    again"* against *"then run again"*. The shared string is now surface-neutral (*"try again"*)
    so one sentence can serve a run and a preview both. Pinned by
    `test_the_browser_holds_no_folder_wording.py`, which asserts against `models`' real strings
    rather than a remembered phrase.
  - **And the cap.** `analyze` elided at 20 while `organize` printed the list uncapped - one list,
    two behaviours. `FOLDER_PREVIEW` and `total` now live in core, so the *"and N more"* line
    comes from one number.
  - **The app payload gains a structure and loses a field**: `unreadable_folders: list[str]` ->
    `skipped_folders: [{reason, label, remedy, folders, total}]`. Replaced rather than added
    beside, because keeping both is the compatibility path `(adz)` rules out and no release has
    been cut. A **hidden** folder reached no app surface at all before this.
  - **Seven mutations, and two survived first.** Raising the cap survived because the test read
    `FOLDER_PREVIEW` to build its fixture - §4's twenty-ninth member, *a test written in terms of
    the constant it guards cannot falsify the constant* - rewritten to absolute numbers. And the
    browser's wording was unguarded until `test_the_browser_holds_no_folder_wording.py` existed.
  - ⚠ **THE BROWSER LANE CAUGHT WHAT 2,648 PYTEST CASES COULD NOT, and it is the reason to share
    wording rather than the reason not to.** Sharing means picking one phrasing, and the CLI's was
    the wrong one: *"folders that could not be read"* sat directly above its own *"files that could
    not be read: 2"* - **one phrase for the counted fact and the uncountable one**. The browser had
    the right verb (*"could not be OPENED"*) and pins it: an assertion in
    `test_unreadable_sources_are_visible.py` says the folder block must not contain the file
    phrase, because reusing it invites the count the folder line withholds. Unifying on the CLI's
    text would have spread the collision to all three surfaces. **A folder is opened; a file is
    read**, and `models._FOLDER_SKIP_LABELS` carries the argument. Two smaller ones came with it:
    the shared remedy needed a capital to open a sentence (`app.js` `sentence()`, a `charAt` and
    nothing more - the string still exists only in `models`), and the heading is now `label: count`
    like every other skipped group rather than a sentence the browser built itself.
  - **Three browser tests were added for the half nobody had looked at**: a hidden folder reaching
    a screen **with the rename remedy and not the permissions one**, two reasons rendering as two
    groups with neither borrowing the other's sentence, and a capped list whose number counts
    folders. Proved by mutation - draw only the first group, count what was drawn instead of what
    was skipped, drop the capital - all three caught, each against a control run.
  - **Two payload tests were re-aimed, not relaxed**, and the commit says what they pinned: *the
    payload names the folder it could not open* is unchanged and now also states which reason. A
    third pinned `exiftool backup: 2`, which became `exiftool backups: 2  (exiftool backup x2)` -
    the wording `analyze` has shown all along, so the surfaces now agree rather than one being
    restyled; it asserts the promise its own docstring names instead of the heading.

- **(aes) "NEVER CHECKED" NOW MEANS NOBODY LOOKED, NOT "WE LOOKED AND FOUND GAPS".**
  - ✅ **CLOSED 2026-08-21.** Measured on the soak catalog: five files deleted by hand, `verify`
    reporting `MISSING: 5`, and `status` in the same minute naming that drive as never checked.
    It no longer does - and drives that genuinely have never been verified are still named, which
    is the half that matters more.
  - **Two questions were sharing one field, and one of them was answered correctly all along.**
    `Catalog.refresh_drive_verified` derives `drives.last_verified` as *"MIN over the copies, and
    NULL the moment any of them has never been confirmed"* - `(abg)` Stage 2, and **it is right**:
    it answers *is this drive wholly confirmed, and as of when*. NULL therefore covers *nobody
    looked* and *we looked and found gaps* alike, and `custody_freshness` read it as the first.
  - **No third value, no second column, no new query.** `Catalog.list_drives` already computes
    `confirmed_count` and `missing_count` per drive, and **both** callers of `custody_freshness`
    pass its rows. The evidence was in the row and simply not read.
  - ⚠ **THE FIX IS A SHARED PREDICATE, WHICH IS WHY IT IS NOT A FOURTH PATCH.** `(aej)` closed
    this on `drives` by writing the discriminator at that one call site - and §4's fifty-sixth
    member is exactly that: a rule discovered and applied locally reads as settled while the
    surfaces it never reached disagree in silence. Four surfaces answer *has this drive been
    looked at*, and one was right. They now share `drive.was_ever_checked`:
    `custody_freshness` (CLI `status` **and** the app's custody strip), `cli._verified_cell`, and
    the app's safety table through a new `was_checked` payload field.
  - **`confirmed_count` alone will not do**, which `(aej)` recorded and a mutation now enforces: a
    copy can be unconfirmed without being missing, so a cancelled run leaves confirmations and no
    missing marks while a wiped drive leaves the reverse. Either is a look.
  - ⚠ **`keys()` rather than `.get()`, and that is not style.** `sqlite3.Row` has no `.get()`, so
    a `dict`-only implementation type-checks, passes a `dict`-based unit test, and raises
    `AttributeError` on every real run. Caught because two of the three guards go through
    `custody_freshness` with real `list_drives` rows rather than fabricated ones.
  - **The app's safety table needed one line of `app.js`** (`verifiedCell`), since a null date
    cannot express the difference and the browser cannot recover it. Done without the browser
    lane, by the maintainer's decision, so the four surfaces agree in one commit.
  - **Three mutations, all caught**: back to the stamp alone, `missing_count` dropped, and a row
    without the aggregates claiming a look.

- **(aet) ONE UNDECODABLE FILE NO LONGER ABORTS A RUN, AND THE BOUNDARY IS NOT A LIST.**
  - ✅ **CLOSED 2026-08-21.** `organize` over 1,428 format-corpus files exited **1 with a traceback
    and nothing organized**; it now reports **1,406 organized, 22 duplicates, 8 named** and exits 1
    because §9 requires that when a source could not be read.
  - **The argument, and it is the entry rather than the diff: the defect is a taxonomy that cannot
    be completed.** `perceptual_hash` already caught `UnidentifiedImageError`, `OSError`,
    `ValueError` and `DecompressionBombError` - a careful list. Eight files escaped it in two
    classes nobody would have listed: **`SyntaxError`** ×7, the *builtin*, which Pillow raises for
    a malformed PNG `zTXt` chunk, and **`EOFError`** ×1 from a truncated HEIC. Widening the tuple
    would fix those eight and leave the ninth decoder to abort a run in six months, identically.
    **§1's partial-failure policy is a statement about the BOUNDARY, and a boundary defined by
    enumeration is not one.**
    ⚠ **CORRECTION 2026-08-23: the rule is `ENGINEERING_STANDARD.md` §4 Errors, not §1.** The
    sentence above is left as written because a closure is a record. The distinction is
    **authority**, not shelving: `IMPLEMENTATION_STANDARDS.md` wins on conflict and
    `ENGINEERING_STANDARD.md` does not, so citing this as §1 claims more for it than it has.
    `(agc)` carries the shape and the whole census.
  - **`except Exception`, scoped to that ONE call and argued in place**, per §5: a violation must
    be explicit, commented and contained. The `sha256_file` call beside it keeps its narrow
    `OSError`, because a plain byte read has a knowable failure set. ⚠ There is no `noqa` because
    there is nothing to suppress - `BLE001` is not enabled here, so the rule being bent is §4's
    **prose**, which is exactly why the comment is the whole of the enforcement.
  - **`BaseException` is deliberately NOT caught**, and that claim is pinned: a worker that ate a
    `KeyboardInterrupt` would make Ctrl-C stop working on the operation people most want to stop.
  - **Nothing is swallowed**, which is the condition the exemption rests on.
    `UnreadableReason.UNDECODABLE` is a fifth member rather than a reuse of `OTHER`, whose wording
    is *"could not be opened"* - false about a file whose bytes read perfectly, and it would send
    the reader to check permissions on a file with nothing wrong with them. It reads *"could be
    read, but its contents could not be decoded"*, worded once in `models.unreadable_label` so
    neither surface can drift.
  - **The boundary is what is tested, not any decoder's exception.** The guard injects
    `SyntaxError`, `EOFError` **and a class that exists nowhere** - the third being the whole
    claim - plus the real corpus files when they are present, skipping rather than fabricating.
  - **Three mutations, all caught**: narrowed back to an enumeration, caught-and-swallowed, and
    widened to `BaseException`.

- **(aeu) HEIF RECORDS A ROTATION TWICE, AND EACH CONSUMER SAW ONLY ONE OF THEM.**
  - ✅ **CLOSED 2026-08-21.** Both halves, same session, because they are **one fact from opposite
    ends**: a HEIF may carry a quarter turn as the container property `irot`, which libheif applies
    while decoding, or as the legacy EXIF `Orientation`, or as both. Apple writes both.
  - **The pixels half.** `pillow_heif`'s Pillow plugin calls `set_orientation` on open - *"Reset
    orientation in EXIF to 1"* - and `as_plugin.py` contains **no transpose at all**, so the tag is
    zeroed, the value stashed in `info["original_orientation"]`, and `ImageOps.exif_transpose`
    reads a 1 and does nothing. Its sibling `HeifImage.to_pillow` *does* rotate, so the two ways of
    opening one file disagree and `Image.open` reaches the one that does not.
  - ⚠ **The obvious fix was wrong and the real files said so.** Restoring the stash unconditionally
    corrected the one EXIF-only file and **turned three `irot` files sideways**. The discriminator
    needs nothing new: EXIF's own `PixelXDimension`/`PixelYDimension` describe the image as
    **stored**, so decoded ≠ stored means libheif already transformed it. Computed before
    `draft`/`thumbnail`, both of which change the size it depends on.
  - **The payload half, which is the mirror.** `HMD_Nokia_8.3_5G.heif` records the turn **only** in
    `irot` with `Orientation=1`: pixels right, payload wrong, because exiftool reports the stored
    extent. exiftool *does* surface the container turn, as `QuickTime:Rotation`, so `upright_size`
    now takes it and the fix stayed free.
  - ⚠ **THE TWO SIGNALS ARE REDUNDANT, NEVER ADDITIVE.** Where both are present they state the
    **same** turn - `Orientation=6` with `Rotation#=3` - so the rule is **OR**. Composing them
    makes one 90 into a 180 on exactly the files Apple writes, which is most HEICs in existence:
    a change that looks more thorough and breaks the common case. Pinned by a parametrised row for
    `(6, 3)`, and by a mutation that swaps OR for composition.
  - ⚠ **`Rotation` IS NOT A UNIQUE TAG NAME**, and the bare form was a defect: `[Panasonic]
    Rotation` is a maker-note tag where `1` means *"Horizontal (normal)"*, and requesting it
    unqualified **transposed landscape Panasonic and Leica JPEGs**. Caught by sampling 300 non-HEIF
    files after the change - reading the diff could not have shown it, because the fault is a name
    meaning two things. Now `QuickTime:Rotation`, pinned by its own guard.
  - **The finding itself was corrected**: *"4 of 20"* counted **tag** disagreement; only **1 of 20**
    rendered wrong. Measuring the proxy and reading it as the property is §4's own census member.
  - **Known gap, pinned rather than closed quietly.** Orientations 2, 3 and 4 leave both dimensions
    unchanged, so the stored-vs-decoded comparison cannot tell an applied turn from a pending one -
    `(adp)`'s blind spot, *"a 180-degree rotation leaves width and height alone"*. Asserted by a
    **content-based `xfail(strict=True)`**, so widening the condition becomes a failure and the
    double-rotation risk must be confronted rather than inherited.
  - **Result:** all 17 readable HEIF/HEIC/AVIF in the corpus have payload and pixels agreeing; the
    other three are the fuzzing corpus's deliberately corrupt files.
  - **Seven mutations across both halves**, both directions of every condition. ⚠ **Three of them
    were void on the first attempt**: `pytest $T` with two paths in an unquoted variable is not
    word-split by zsh, so pytest took a usage error, exited 4, and `mutate_once` read that as a
    kill. The control said `no tests ran` - the exact tell the maintainer's standing warning names.
    Re-run with the paths passed literally against a control reporting **29 passed**.
  - **`tags_fingerprint` changed a third time**, deliberately, with its cost and reason recorded
    beside the previous two. Affordable only because no release has been cut.
  - ⚠ **CORRECTION, 2026-08-21, beside the closure rather than into it: THE FIRST FIX WAS INERT
    ON MOST LINUX INSTALLS AND CI CAUGHT IT.** `_TRANSPOSING_CONTAINER_ROTATIONS` was `{1, 3}`,
    the raw quarter-turn index that **exiftool 13.50** reports. **exiftool 12.76 - what Ubuntu
    noble's `libimage-exiftool-perl` ships, and therefore what the CI `check` lane has - reports
    the same tag in DEGREES**, `270`. The set matched nothing there, so the payload correction did
    nothing on the version most Linux users have, silently. Now `{1, 3, 90, 270}`: the two spaces
    are **disjoint except at 0**, which means "no turn" in both, so the union is unambiguous rather
    than a guess.
  - ⚠ **The three-OS matrix caught a DEPENDENCY-VERSION difference, which is a new kind for it.**
    macOS and Windows install a current exiftool through brew and choco and both passed; only
    ubuntu, on an apt package two majors behind, went red. Every previous save was an OS
    difference - `timeout(1)` on BSD, a `WindowsPath` separator, a cp1252 decode. This was the
    same OS with an older tool.
  - **And the guard that found it was a PRECONDITION assertion**, not an outcome one: the test
    asserted that exiftool's reported value is one the rule accepts, before using it. Without that
    line the run would have gone green while the fix did nothing - the outcome assertion cannot
    tell "correctly not transposed" from "never consulted". It is kept and documented as the
    control against a third encoding.

- **(aeq) EVERY exiftool INSTALL NOW PROVES THE BINARY RUNS, AND WINDOWS RETRIES A FEED 503.**
  - ✅ **CLOSED 2026-08-21**, the same day it was filed, because it stopped being a prediction:
    **two of three Windows install attempts inside thirty minutes** died on an identical
    `503 (Service Unavailable)` from `community.chocolatey.org`, one of them on a **docs-only**
    push. The lane was effectively down.
  - **Root cause: a third-party package feed is a hard dependency of every run, and the care taken
    over it differed per lane.** Linux was bounded and retried through `ci_bounded.sh` but had **no
    probe**; Windows had a probe but **no bound and no retry**; macOS had **none of the three**.
    Two surfaces each holding the half the other was missing - `ENGINEERING_STANDARD.md` §4's
    fifty-sixth member, the third instance in two days after `(aei)` and `(aek)`.
  - ⚠ **THE RETRY IS KEYED ON THE PROBE, NOT ON THE EXIT CODE, AND THAT IS THE WHOLE DESIGN.**
    `choco` **returns 0** after a feed 503 - upstream `chocolatey/choco#1609` is titled *"Chocolatey
    reporting success when install fails with 503 error"* - so `$LASTEXITCODE` cannot tell a
    working install from a missing one. A retry written against it is **a loop that never loops**,
    green on every run and indistinguishable from one that works. The probe is the only thing that
    knows, so the loop asks the probe.
  - **Same shape as `ci_bounded.sh`, deliberately not a port of it.** That script keys on exit
    **124** because apt swallows its status and *deadlocks*; this keys on the probe because choco
    swallows its status and *returns success*. Different swallowed signal, different observable.
    Its header's first line - *"We never see the 503"* - was true of apt and false one lane over,
    which is §4's thirty-second member: a clause asserting a state that expires in silence.
  - **Two attempts, one 30 s pause**, matching `ci_bounded.sh`'s arithmetic **and** its reasoning:
    the pause is not backoff, it is a wait for a server-side temporary failure that may still be in
    force, and with two attempts there is one interval and nothing to be exponential about.
    **A sustained outage still fails, loudly** - this converts a coin flip into a rare loss, never
    into a guarantee, and saying so is the point.
  - **Never silent**: a retried install emits a `::warning::` naming the cause, so a green second
    attempt cannot read as a clean first one. Exhaustion `throw`s rather than falling through.
  - **All four installs are now bounded and probed** - both Linux copies, macOS and Windows.
    *Resolving is not running* (§4's forty-second member, where that proxy was caught three times
    on `(aad)`), and an unbounded network fetch destroys its logs at the moment they matter
    (forty-third member).
  - **Prior art, searched rather than assumed**: `astral-sh/uv` hit the same 503 from the same feed
    on 2026-08-05, and Chocolatey publishes a status page for the community repository - the vendor
    treats its availability as a variable. The industry pattern is retry-transient-5xx **plus**
    per-write handling, never either alone, because check-then-use is a TOCTOU window.
  - **Six mutations, all caught**, against a control that reported 5 passed: retry keyed on the
    exit code, no pause, macOS unguarded again, the bound removed, the warning removed, and the
    scan aimed at an empty corpus. ⚠ **One of them was a defect in the test itself**: asserting
    `"LASTEXITCODE" not in run` matched the step's own comment *explaining why it does not use it*,
    so the guard reported the opposite of the truth. §4 names that exactly - assert the statement,
    never an identifier that also appears in the target's commentary - and it cost one red run
    here before the rule was applied.
  - **What this does NOT do**, stated so nobody reads it as more: it does not remove the feed
    dependency. `(aeg)` is the entry that would, and it explicitly does not cover the `check`
    lanes. See [`research/backlog/aeq.md`](research/backlog/aeq.md).

- **(aek) A FULL DISK DURING DRIVE SETUP NOW REFUSES IN A SENTENCE INSTEAD OF A TRACEBACK.**
  - ✅ **CLOSED 2026-08-21.** The last of the first soak's five findings. `organize --apply` into an
    unregistered destination on a full disk raised an unhandled `OSError` from `drive.write_marker`
    with a `pathlib` stack trace; it now prints *"Not enough room: this needs about X and the drive
    has Y free"* and exits **4**, having written nothing - no marker, no `drives` row, no path hint.
  - **THE FIX IS THE ORDERING, NOT ERROR HANDLING**, and that is what made it small. The product
    already had that sentence and already exited 4 on it (`cli.py`'s `DestinationError` handler,
    whose own comment says *"a user-facing answer, not a crash ... rather than showing a
    traceback"*). The sentence was computed **after** the marker write, so the run died before
    reaching the explanation it already had. Registration now happens after the preflight.
  - ⚠ **THE ORDERING MOVE DOES NOT RESTORE `(aei)`, AND THE PROOF IS THE LOAD-BEARING PART.**
    `(aei)` requires the destination's identity to be an INPUT to dedup, which reads as forbidding
    exactly this move. What it requires is the *identity*, not the *write*: `_local_drive_marker`
    already reads the marker off disk before the pipeline starts, so a marked destination has its
    uuid before anything runs, and an unmarked one scopes to `{}` either way - a freshly minted
    uuid holds no recorded copies, and neither does a folder with no marker. Three branches, all
    unchanged. The dedup scope now derives from **identity** rather than from the side effect of
    registering, which is strictly more honest. Pinned by
    `test_dedup_scope_comes_from_the_marker.py` and its app twin.
  - ⚠ **AND THE ORDERING FIX WOULD HAVE BEEN INERT WITHOUT A SECOND DEFECT FOUND WHILE BUILDING
    IT.** `preflight_destination` used `free = 0` as its *"could not measure"* value and returned
    `free_bytes=free or need` - so a genuinely full disk, which reports **0 free**, resolved as
    *exactly enough* and passed its own space check. Two states, one value, and the silent one won.
    The comment's intent was right; zero was the wrong way to say it. Now `None`, pinned in both
    directions: a measured zero refuses, an unreadable `disk_usage` still proceeds.
  - **`write_marker` is hardened anyway, because ordering cannot cover `EACCES`, `EROFS`, or a disk
    that fills between the check and the write.** Confirmed by search rather than assumed:
    quota-aware `statfs` is a per-filesystem feature added piecemeal, so `shutil.disk_usage` cannot
    be relied on to see this finding's own `EDQUOT` - and the industry pattern is the pair, a
    preflight being advisory and never replacing per-write `ENOSPC` handling, because
    check-then-write is a TOCTOU window.
  - **It follows `decisions.write_decisions`, which was already right and already tested** - stage
    to a temp sibling, `fsync`, `replace`, remove the temp on failure, never raise, word the errno
    in English. ⚠ **The entry claimed that write was untested; it was not** - see the corrections
    in [`research/backlog/aek.md`](research/backlog/aek.md). One wording now lives in
    `drive_unwritable.py`, named for the condition it recognises the way `catalog_busy.py` is,
    because `decisions` imports `drive` and the reverse would be a cycle.
  - **A zero-byte marker can no longer be left.** Measured: `write_text` opens `O_CREAT|O_TRUNC`,
    so a write-time `ENOSPC` took the real name and then failed, leaving an empty
    `.truestill-drive.json` - the only truestill-named artifact this product writes to a user's
    disk (§3.1). Staging means the name is taken only by bytes that arrived.
  - **`create_marker` deliberately still raises**, as `DriveWriteError`. The never-raise contract
    is `write_marker`'s, where the two lines were; changing `create_marker`'s return type would
    have been **69 call sites across 34 test files** to fix a two-line defect. Same relationship
    `copy_leaving_nothing` has to `staged_copy` - one mechanism, two ends. The deviation is made
    safe by `test_marker_writes_are_handled.py`, which parses `packages/*/src` and requires every
    mint site to catch the refusal **or document that it propagates**; it reads the live tree, so a
    sixth site is covered the day it is added.
  - **Both surfaces, deliberately.** This entry is itself an instance of `ENGINEERING_STANDARD.md`
    §4's fifty-sixth member, so shipping the CLI alone would have repeated the defect being fixed.
  - **Cost: the CLI pays nothing; the app pays one extra `stat` pass.** The CLI already read the
    preflight twice (the report, then `execute`), so hoisting it to one reading that three callers
    share leaves the count unchanged. `organize_run` had none before `execute` and now has one.
    ⚠ **The figures are ESTIMATES carried from `PERFORMANCE.md`, not measurements of this change**
    - ~9 ms local at 2.3 us/file (`PERFORMANCE.md:428`) and ~2.5 s on FUSE at ~600 us/file
    (`PERFORMANCE.md:576`), over 4,105 files. Both are per-file rates measured on other paths;
    stated here so the next reader knows what they are before quoting them. Once per run rather
    than per file, so it is not the case `PERFORMANCE.md:578` warns about - but if it ever matters,
    measure it rather than citing this line.
  - **Eight mutations, both directions on every conditional**: gate never refuses, gate always
    refuses, app gate removed, staging cleanup removed, `EDQUOT` branch removed, the free-space
    conflation restored, unmeasurable collapsed back onto zero, and a mint site un-handled. All
    caught, against a control that reported **29 passed** first.
  - **Filed, not fixed**: `(aen)` the catalog's first write, `(aeo)` `session_link.write`, `(aep)`
    the write side's missing `unreadable_label`. All three are the same class; none is this
    feature. See [`research/backlog/aek.md`](research/backlog/aek.md).

- **(aem) AN INTERRUPTED COPY-MODE ORGANIZE NOW LEAVES A RECORD, SO A HALF-LIBRARY CANNOT READ AS
  A WHOLE ONE.**
  - ✅ **CLOSED 2026-08-20.** Schema **v20**, `organize_runs`, one row per drive, superseding on
    start. Verified on a real killed run: `⚠ a run was interrupted: 121 of 161 files arrived.`
    and the warning **clears** once the run is finished.
  - **The record is written BEFORE the first byte**, as `start_inplace_run` is - *"so a crash
    leaves a record"*. It had to be: after the process dies the intended total cannot be
    reconstructed, because a restart's own total correctly excludes what already landed.
  - ⚠ **`intended_total` is the drive's TARGET HOLDINGS, not the run's write count**, and that is
    what makes an interruption legible across a restart: the write count is 4,105 then 3,765 and
    cannot be compared, while the target is 4,105 both times. Both halves were already in hand -
    `on_destination` from `(aei)`'s dedup, `write_candidates` from the preflight - so it costs no
    new I/O.
  - ⚠ **"Interrupted" is DERIVED, never read from a flag**, which closes the window a start-write
    design otherwise gets wrong: a crash between the last file and the close reads as **complete**.
    That is `migrate`'s own immunity, which reports pending journal rows rather than a status.
  - ⚠ **AND A BUG IN THAT DESIGN, FOUND BY MUTATION AFTER IT WAS BUILT.** Deriving *purely* from
    `achieved < intended_total` is right for the crash window and **wrong afterwards**: a completed
    run began claiming it was interrupted the moment a file was deleted by hand - the soak's own S5
    scenario, which would have made every finished drive start lying. A closed run is now finished
    whatever the drive holds today, and **both conditions are load-bearing** - each is killed by a
    mutant the other survives.
  - **`.partial` detection was considered and deliberately left out.** The sibling *is*
    unambiguously truestill's own write, so `staged_copy` could look - but the record is strictly
    better evidence (it carries the denominator), the `.partial` is destroyed by the next run, and
    detecting it costs a stat per file on the hot path. Filed separately.
  - **`rescan`'s heading reframed**: *"could not clean up"* described a failed cleanup; it now says
    a run was interrupted. Only the note moved - the title is pinned by tests and the exclusion
    from the health verdict is correct and unchanged.
  - 🔑 **AND THE OBSTACLE THAT BLOCKED THIS AND `(adx)` GAP 2 WAS FOLKLORE.** `(adx)` recorded
    *"`CompletionBase` is a 17-key payload pinned by two e2e tests"* and both entries scoped their
    work around it. Measured: **19 keys**, the Python guard is `set(summary) >= {...}` - a
    **superset** check that had already absorbed three additions - and the e2e files that touch it
    **author their own partial summaries** and assert on rendered text, reading no key set at all.
    The cancel path already ships a 20th key through the same renderer. `(aem)` added **no key**.
    ⚠ **The number was wrong in four places and no test asserted it**, which is how a constraint
    recorded once becomes a fact. §4's fifty-sixth member, in the direction of an inherited
    *constraint* rather than an unevenly applied *rule*. ⚠ `SHIPPED.md`'s own "17" is **left
    alone**: it was true when written (16 keys before 2026-07-31, 18 by 08-13), and a record
    rewritten to stay correct stops being one.
  - See [`research/backlog/aem.md`](research/backlog/aem.md).

- **(aej) THREE SURFACES STATED SOMETHING TRUE OF ONE POPULATION AS IF IT WERE TRUE OF ANOTHER.**
  - ✅ **CLOSED 2026-08-20**, three of the soak's four. **The fourth was split out as `(aem)`
    because it is a different kind of defect** - see below.
  - **S1, the false empty.** Sixteen seconds after a `verify` that reported `MISSING 7` and named
    all seven paths, `drives` printed `D3 … 2026-08-20T09:09:20   never` - the timestamp of that
    very run beside the claim it never happened. And the custody sentence agreed with it:
    *"Never checked: 'D3'. Truestill has not looked since the copy was written."* **Both clauses
    false.**
  - ⚠ **The rule underneath is right and did not change.** `refresh_drive_verified` leaves
    `drives.last_verified` NULL unless every copy is confirmed, so the drive cannot claim a date it
    has not earned (`(abg)` Stage 2). **NULL is a claim-SUPPRESSION flag** - its docstring says it
    covers *"missing, unreadable, unverifiable and not reached before the user cancelled"*. The
    defect was that read sites decoded it as a positive assertion about history: **the field
    answers "may I reassure?" and they asked it "what happened?".**
  - **Three states now render as three**: a date when fully confirmed, `checked, gaps` when a check
    ran and could not confirm everything, `never` when nothing has looked. ⚠ The cry-wolf half is
    the point of the research frame - a fix that merely stopped saying *"never"* would destroy the
    signal rather than repair it, so a genuinely unchecked drive still says it.
  - **S2, the shortfall.** `list_drives` already returned `missing_count` and `missing_at`, and its
    docstring said why - *"a drive reads '2,269 recorded, 2,269 not found on 11 Aug'"*. The CLI had
    both in the row and printed neither; `grep missing_count cli.py` returned nothing. There is now
    a `NOT FOUND` column, `-` when there is nothing to report.
  - **S3, the scope defect.** Re-organizing an already-organized folder printed *"none of these
    files carries a capture date"* beside `undated x0` - false about the 4,111 files just counted,
    and self-contradictory. Both came from one **empty** list: `capture_span` returns `None` for
    *"no file had a date"* and for *"there were no files"*, and the empty case took the first
    branch's wording. It now says **"no files were organized, so there is nothing here to
    describe."**
  - **One aggregate was added, and it is why `missing_count` alone was not enough**:
    `confirmed_count` on `list_drives`. A copy can be unconfirmed **without being missing** - it was
    unreadable, or the run was cancelled before reaching it - so the missing count cannot separate
    the two meanings of NULL on its own. No schema change; the data was always in `file_copies`.
  - **Proved at both poles before building**: a verified-with-gaps drive reads `confirmed 4098 /
    missing 7`, a never-verified one reads `confirmed 0 / missing 0`, and `drives.last_verified` is
    NULL for both. See [`research/backlog/aej.md`](research/backlog/aej.md).

- **(aei) `organize` DEDUPED AGAINST THE CATALOG; IT NOW DEDUPES AGAINST THE DESTINATION.**
  - ✅ **CLOSED 2026-08-20.** Organizing into a second drive copies what is not on **that** drive.
    Measured on the soak's own 4,111-file corpus: a fresh second destination that received **0
    files** now receives **4,105**, and `status` reads *"All catalogued content has at least two
    drive copies. Nicely redundant."*
  - **The defect, in one query.** `Catalog.seed_rows` is `SELECT source_path, sha256, perceptual
    FROM files` - no `drive_uuid`, no `WHERE` - and the index it seeds is a `dict[sha256, path]`
    with no drive dimension. *"Already in your library"* meant *this catalog has ever seen this
    content, on any drive or on none*, so a fresh destination was registered, reported success,
    and stayed empty while `status` warned that 4,088 files sat on only one drive.
  - **Ruled from prior art**: restic and Borg deduplicate within a repository and separate
    repositories get no cross-dedup; a global chunk store is the exception and exists for fleets
    writing into one shared destination. **Truestill implemented the global model while presenting
    the per-repository interface.** The rule is now stated in `IMPLEMENTATION_STANDARDS.md` §2,
    which is the durable half - it had been written for backup and for the preview and never for
    the write path.
  - ⚠ **Scope is three-valued, and the third value is load-bearing.** `None` (no scope available)
    keeps the catalog-global answer - that is **rclone**, deliberately never drive-tracked, which a
    per-drive check would re-copy in full every run, and every direct API caller, so the change is
    opt-in per call site. `{}` (local, no marker) means *nothing is here* - the branch a **preview**
    takes on a fresh folder, since registration is gated on `--apply`; returning `None` there would
    make a preview predict *"already in your library"* for files the run then copies.
  - **The tautology is gone too.** The skip line named `files.source_path` - never repointed, so on
    an ordinary re-run it was the file being skipped, saying *X is identical to X*. It now names the
    copy's path **on this drive**, via `copy_relative`, and *"already in your library"* became
    **"already on this drive"** on every surface, including `left_behind`'s own two copies of the
    phrase.
  - ⚠ **A regression I introduced and the real corpus caught, recorded because the unit tests did
    not.** The first fix made a second drive receive **4,111** files where the first held 4,105:
    `DedupIndex._origin_of` decides RUN-vs-CATALOG by **path string**, so re-scanning a folder the
    catalog was ingested from makes a genuine within-run twin report `CATALOG`, and the gate demoted
    it twice. Fixed by letting the destination grow as the run writes; pinned by
    `test_within_batch_twins_are_not_both_copied_onto_a_second_drive`, whose fixture seeds the
    catalog **from the same source**, which is what the passing test lacked.
  - **`attachable_hashes` was considered and deliberately not widened**: `file_copies.sha256` is the
    source hash, which the dual-hash rule already names as the dedup identity. Attach asks *"is this
    file the copy we recorded"*; dedup asks *"have we placed this content"*.
  - **One test reversed, with its record**: `test_the_same_photo_copied_to_x_is_not_moved_to_y`
    became `..._is_moved_to_y_because_y_does_not_have_it`. ⚠ Its old docstring described the defect
    as its mechanism - *"the index is seeded from the whole catalog rather than from what is at this
    destination"*. Checked before changing, because move deletes originals: the three files end up
    on **both** X and Y, so nothing leaves its only home, and the old behaviour was the surprising
    one - a silently half-completed move.
  - **The class is `ENGINEERING_STANDARD.md` §4's fifty-sixth member**: *a rule applied to two of
    three surfaces reads as settled, and the third disagrees silently.* ⚠ And the coverage gap that
    let it ship is the same shape - **no test anywhere organized into two destinations**; every
    two-drive scenario reached the second drive via `backup_run`, the surface that was already
    right. `(ael)` carries what remains of the CLI gap. See
    [`research/backlog/aei.md`](research/backlog/aei.md).

- **(aee) CI'S TIMEOUTS AND ITS MIRROR RETRIES WERE BOTH DEFAULTS NOBODY CHOSE.**
  - ✅ **CLOSED 2026-08-19** in `6e70ea0`, from run **32279378834**, where the ubuntu `check` lane
    sat **33+ minutes** inside `apt-get update` while the other two finished in **1m07s** and
    **3m02s**. Two findings, one entry: a default is a decision nobody made, and the second is
    only expensive when the first is absent.
  - **(1) An observability property, not an incident.** `ci.yml` had **no `timeout-minutes` at any
    level**, so GitHub's 360-minute default applied - and the cost was not the hang itself but
    that **hung and slow were indistinguishable from outside**, which is how a wedged lane read as
    merely slow for half an hour. `release.yml:176,216` had them; CI never did. **This is
    `(ads)`'s shape** - *"the catalog's concurrency model is SQLite's DEFAULT, not a decision"* -
    and the question *which of these values did anyone pick?* has now found two answers in two
    subsystems. Now `20` on `check` (~6x its slowest real run) and `45` on `e2e`, which bounds a
    hang **before pytest starts**; the existing 2000 s ceiling inside that step cannot see one.
  - **(2) The apt fallback, and it inverts the standard advice.** apt **>= 2.3.2 already defaults
    to `Acquire::Retries=3`** at a 120 s timeout, the failing log shows **exactly four `Ign:`
    rounds** per index, and the mirrorlist's fallback to `archive.ubuntu.com` **works**. So
    `-o Acquire::Retries=3`, the fix in every write-up on this failure, was already in force and
    was the cost. `Retries=1` at a 15 s timeout instead; `update` and `install` split, because
    chained a flaky refresh fails the step even when the package would have installed.
  - ⚠ **THE BOUND WAS AT THE WRONG ALTITUDE, found by a second outage the same day** (run
    **32295312064**). Flags bound the call site you are looking at; the same job had a *second*
    exiftool step nobody touched, and `playwright install --with-deps` runs its own `apt-get`
    that **takes no flags from us** - it spent **43m33s** on the unreachable mirror. The setting
    now lives in an `/etc/apt/apt.conf.d/` drop-in every consumer inherits, guarded by
    `test_ci_bounds_apt_in_one_place`. **Bounding a call site fixes the calls you can see.**
  - ✅ **`timeout-minutes` FIRED, two runs after it was added:** that job was killed at **45m18s**
    instead of running to the 360-minute default, with the three `check` lanes green underneath.
    **Not evidence for raising it** - a bound that fires during an outage is correctly sized.
  - ⚠ **GitHub reports a timeout-killed job as `cancelled`, not `failure`** - the same value as a
    human cancel and as a `concurrency` supersede, and the timeout is the one nobody expects. The
    timed-out run also uploaded **no e2e artifact**, so `flake_report` reads clean over a lane
    that died after 45 minutes.
  - 🔒 **THE SAVING ITSELF IS STILL UNPROVEN, AND THIS OUTAGE DID NOT SETTLE IT** - said plainly
    because a reader who sees an outage recorded will assume it did. An earlier claim of a
    controlled comparison was **wrong and is corrected in the body**: the honest same-run control
    was 58 s bounded against **88 s** unbounded, both fine, and the 33-minute figure came from a
    different run. The catastrophic step was unbounded *and* far larger, so the two variables
    moved together. The next outage is still the test.
  - ⚠ **The two bounds are NOT the same measurement**, found on the run that landed the entry:
    `E2E_SECONDS_MAX` times **pytest**, `timeout-minutes` times the **job**. Measured on
    32287632288 - pytest **1244.11 s**, job **36m40s**, so **43% of the lane is invisible** to the
    ceiling anyone would reach for first. The tempting reading - *"it breached 2000 s and passed"* -
    is wrong: pytest was genuinely under, and the guard was right to stay quiet. A slow lane can
    be correctly reported as fine. The body carries the running spread; **the bound was not
    raised**, per `(aec)`.
  - ⚠ **The third mechanism-fix-without-reproduction in one day**, with the text-size wait and the
    macOS probe. **What makes it acceptable is that the mechanism is measured even when the failure
    is not** - 6,558 ms, a demonstrated late join, four `Ign:` rounds - and the alternative is
    waiting for an outage in order to fix an outage. The cost is that *fixed* means something
    weaker, and all three say so in place. See [`research/backlog/aee.md`](research/backlog/aee.md).

- **(adv) AN EXPLICIT `TRUESTILL_DATA_DIR` NOW OUTRANKS THE LEGACY CATALOG PATH.**
  - ✅ **CLOSED 2026-08-18.** `resolve_catalog_choice()` decides between three rules and says
    which won; `default_catalog_path()` delegates to it. **A compatibility guess no longer beats
    an explicit instruction.**
  - **The defect, reproduced before the fix.** `default_catalog_path` checked
    `reports/catalog.sqlite` - a **relative** path resolved against the working directory - before
    it honoured the environment variable. Measured: with the variable naming a real catalog and a
    legacy file in the CWD, `default_catalog_path()` returned the **legacy** one. A user who set
    the variable could organize, bake and register drives against a catalog they never named.
  - **Precedence taken from precedent, not principle.** `platformdirs` - already a dependency and
    the de facto standard here - reads its own overrides as
    `os.environ.get("XDG_CONFIG_HOME", "").strip() or <default>`: **override first, and blank is
    unset.** Verified rather than cited: with `XDG_DATA_HOME` set to `""` and to `"   "` it
    returns `~/.local/share` both times.
  - **Blank is unset here too**, for the reason platformdirs has it: an unset variable and an
    empty one must not mean different things. Before the fix, `TRUESTILL_DATA_DIR="   "` resolved
    a catalog to **`"   /catalog.sqlite"`** - a directory named by whitespace. Measured.
  - ⚠ **THE HALF THAT IS NOT "THE OVERRIDE ALWAYS WINS", and it is the one that needed the care.**
    The legacy file is still used **when it exists and the override holds no catalog yet**.
    Otherwise someone with a real library and the variable set in a shell profile would be handed
    a brand-new empty catalog and no sign of the old one - the data-loss shape `(aae)` exists to
    prevent, reintroduced by the fix for this. Guarded by its own test; a mutation making the
    override unconditional fails it.
  - **And whenever two real catalogs disagree, it is disclosed rather than picked silently.** The
    banner now states which of the three rules won, and adds what to do when a second catalog was
    found and skipped, or when the override was set and lost. ⚠ **It read identically in all three
    cases before**, which is what made this hard to notice: the resolved path was already on
    screen and nothing said a variable had lost.
  - **Four guards, each proven by mutation, control run first:** the old precedence, blank-is-not
    unset, the override winning unconditionally, and the disclosure dropped. All four caught.
  - ⚠ **THE TESTS HAD TO CREATE A `reports/` IN THEIR OWN WORKING DIRECTORY**, and that is why
    nothing caught this for so long: from a directory without one the legacy branch never fires,
    the override always wins, and a test passes against the broken code.
  - ⚠ **What this does NOT fix, filed as `(adw)`:** the legacy path is still **relative**, so the
    same install finds a different catalog depending on where it was launched. That is the deeper
    defect and it outlives this one - including inside this repo's own suite, where
    `default_catalog_path()` still resolves to the real catalog rather than the test root. `(adv)`
    made that **disclosed**; it did not make it **prevented**.

- **(adb) THE CATALOG COPY IS STILL A PLAIN `copy2`, AND THAT IS NOW A DECISION.**
  - ❌ **REFUSED ON EVIDENCE 2026-08-19 - not built, and the letter is kept.** The verdict is not
    *"no remedy is needed"*. It is that **every real remedy costs more than the hazard is worth, at
    a population of one, on a file nothing in the tree resolves.**
  - **The entry's own premise was right and is not disturbed.** A plain file copy is universally
    the wrong tool for a live SQLite database - SQLite says so, and it is live enough that a
    July 2026 Vikunja thread argues their documentation is wrong to recommend `cp`. `(adb)`'s
    original remedy, `copy_leaving_nothing`, was **correctly refused** as a filesystem answer to a
    database question. None of that changed; what changed is who can reach the hazard.
  - **1. The ordinary-use route died with `(adw)`.** `--move`'s source is `LEGACY_CATALOG_PATH`
    (`cli.py`, the only caller), and that constant now appears **once** in `app_paths.py` - its own
    definition. **Nothing resolves it.** A torn copy needs a second process pointed at that file by
    explicit `--db`, during the copy. That is misuse of a path with one user, who has already
    migrated.
  - **2. `backup()` from a separate process is the restart case.** SQLite: a write *"by an external
    process… using a database connection other than pDb"* means **"the entire backup operation must
    be restarted"**. `move_catalog_to_standard` holds no handle and runs in its own CLI process, so
    against a sustained writer it is **correct-or-never-finishing**.
  - ⚠ **3. AND MY EARLIER FRAMING OF `VACUUM INTO` WAS WRONG, corrected here rather than left.** I
    called it "the candidate". SQLite's own comparison is the other way round: **`.backup` is the
    routine copy** - *"uses fewer CPU cycles and can be executed incrementally"* - and **`VACUUM
    INTO` is what you reach for when you also want the space back**, because it rewrites every
    page. The measured **6,365,184 -> 5,132,288** compaction is a side effect nobody asked for:
    **a move should produce the same database, not a rewritten one.**
  - **4. And it fails, and adopts.** Under a sustained writer at our default 5 s `busy_timeout`,
    **1 of 4 attempts failed** with `database is locked`. A pre-existing **0-byte** destination is
    **accepted and filled** - measured, 2,695 files written into one - so it would **reintroduce
    `(adr)`**. **Our own `destination.exists()` check stays**: it produces a sentence a person can
    act on, where SQLite's refusal is `file is not a database`, a message about parsing.
  - ⚠ **5. A HAZARD NEITHER BLESSED METHOD ESCAPES, recorded because it is new here.** Both need
    room for **a full second copy**. Plain `VACUUM` is worse - SQLite: *"as much as twice the size
    of the original database file is required in free disk space"* - though **`VACUUM INTO` avoids
    that specific doubling**, since it *"uses the file named on the INTO clause in place of the
    temporary database and omits the step of copying the vacuumed database back over top of the
    original"*. The second-copy cost remains for both. ✅ **It is already paid**: `--move` copies
    rather than moves and leaves the original in place, so the user is spending that space today.
  - 🔑 **THE VERDICT, STATED PRECISELY SO IT IS NOT SOFTENED INTO "IT IS FINE".** The copy really
    is the wrong tool. Every remedy is either the restart case, or a rewrite of a database that
    should have been reproduced, or a 1-in-4 refusal that also reintroduces a shipped defect. **At
    one user, on an unresolvable path, the cure is worse.**
  - ⚠ **REOPEN CONDITIONS, and they are structural rather than a date.** This refusal rests
    entirely on who can reach the file, so it expires the moment that changes:
    - **`LEGACY_CATALOG_PATH` becoming resolvable again** by anything - the automatic lookup
      returning in any form;
    - **`--move` gaining a source other than it** - any path a live process might hold.

    Either one restores the ordinary-use route, and this comes straight back with its measurements
    intact. `test_the_legacy_catalog_path_is_retired.py` is what would go red first.
  - ➡ **The `_MetadataBaker` half was split out as `(aed)` rather than refused with this**, on the
    entry's own instruction (*"Do not 'fix' these together"*). Every measurement above is about the
    **catalog** copy; none touches the bake path, and `PERFORMANCE.md` still has no figure for it.
    **Refusing an unanswered question in the same breath as an answered one is how a question
    disappears.**

- **(aeb) TWO PATHS THAT RESOLVE TO ONE FILE ARE ONE FILE.**
  - ✅ **CLOSED 2026-08-19.** `truestill catalog` told a user their correctly-placed catalog was
    *"in the old location"* and advised a `--move` that could not help, whenever a symlink sat
    anywhere in the data directory. `selfcheck` carried the same false claim as
    *"(older location, still in use)"*.
  - 🔑 **THE DEFECT CLASS, AND IT IS NEW HERE: IT LIVED IN THE PAIR, NOT IN EITHER COMMIT.**
    - `(adv)` made the override branch return `.resolve()`d paths, so the path a user is *told* is
      the file that is *opened*. **Right on its own.**
    - `(adw)` retired the legacy lookup, removing the only state in which
      `default_catalog_path()` and `standard_catalog_path()` could legitimately differ.
      **Right on its own.**
    - Together they left a comparison whose only remaining input was **string shape**.
    ⚠ **Neither diff could have shown this.** Reviewing `(adv)` you see a resolve that makes a
    path more truthful; reviewing `(adw)` you see a compatibility path retired. The defect is the
    *interaction*, and it is invisible to any guard that reads one commit. **What surfaced it was
    running the command on a machine that happens to have a symlink** - the maintainer's
    `/home/dinesh/TruestillLibrary` links to `/data/TruestillLibrary`. On a machine without one it
    is not merely unnoticed, it does not exist.
  - **The fix: `app_paths.is_same_file`, comparing device and inode.** Not resolving both sides -
    that works today and breaks the first time a path cannot be resolved (a stale mount raises
    `ENOTCONN`, and `drive.py` already records that such a path must still get an answer). It
    answers **False** rather than raising when either path is missing, which is the right answer
    at its call site and is what separates it from resolve-both.
  - 🔑 **THE STANDING QUESTION, ANSWERED RATHER THAN LEFT: the two resolvers computed one value,
    so there is now one.** `standard_catalog_path` is **gone**. `(adw)` removed the only state in
    which *"where it currently is"* could differ from *"where it belongs"*, so the pair reduced to
    the same expression - and two functions computing one value is how the next divergence gets
    in. Both comparisons that depended on the distinction are gone with it: the `catalog`
    command's *"old location"* hint and `selfcheck`'s suffix were **vacuous, not merely buggy**.
    `truestill catalog` now prints the catalog and its cache and stops.
  - **Where `is_same_file` is genuinely needed, it is used:** `move_catalog_to_standard`'s
    `ALREADY_STANDARD` check compared a **relative** source against an **absolute** destination
    with `==`, which could never be true. It now asks whether they are the same file.
  - ⚠ **Two false claims in `standard_catalog_path`'s docstring went with the function** - that
    `default_catalog_path` *"prefers a legacy file that exists"*, and that the pair *"differ only
    while someone is still on the old layout"*. Both were untrue from the moment `(adw)` landed.
  - **Mutation-proved, control first, and two mutants survived the first matrix** - which is the
    finding worth keeping: replacing `samefile` with `==`, and with resolve-both, both passed,
    because **no test exercised the helper on the case it exists for**. Two were added: two
    spellings of one file must be the same file, and two paths to a file that does not exist must
    not be. All three mutants then died.

- **(adw) THE LEGACY `reports/catalog.sqlite` LOOKUP IS RETIRED, NOT REPAIRED.**
  - ✅ **CLOSED 2026-08-19.** `_legacy_catalog()`, the `_working_directory_was_chosen()` gate that
    served it alone, and the legacy branches of `resolve_catalog_choice` are gone. The path was
    **relative**, so asking whether it existed asked about the **current directory** - the same
    install found a different library depending on where it was launched, with no environment
    variable involved.
  - 🔑 **WHY RETIREMENT RATHER THAN REPAIR, AND THIS REASONING EXPIRES.** Four facts, each
    verified rather than assumed:
    - the path was introduced **2026-07-31** (`5db91b9`, the `(aae)` commit);
    - **no `v*` tag exists** - the only tag in the repository is `preserved/abw-finding-3`;
    - `release.yml` fires on `tags: ["v*"]`, and its **three runs were all `workflow_dispatch`**
      with `dry_run` defaulting to `true` (*"build and verify, publish nothing"*);
    - so the only way to hold a legacy catalog is to have run truestill from a git **checkout**
      before that date.

    **Population: one, and the one is the maintainer.** Anchoring the path or resolving it once
    per process is machinery to make a bad path behave for a population that does not exist.
    ⚠ **This argument stops being true the moment a tag is cut**, which is why it is on the
    record now rather than reconstructed later.
  - ✅ **THE MAINTAINER'S CATALOG WAS MIGRATED FIRST, and the code was not deleted out from under
    a live file.** `reports/catalog.sqlite` was 6.37 MB with 2,695 files, 4,933 copies and three
    registered drives; the standard location already held a **different, empty** catalog (0 files,
    163,840 bytes) which is why `catalog --move` would have refused with `DESTINATION_EXISTS`.
    The empty one was **moved aside, not deleted**
    (`catalog.empty-superseded-<stamp>.sqlite`, keeping its one real setting), then
    `truestill catalog --move` ran. Verified: the copy is **byte-identical**, carries the same
    2,695 files and three drives, and `truestill status` from outside the checkout now reports
    2,695 files from the standard location. The legacy file is **still there** - `--move` copies
    and never removes.
  - 🌍 **EVERY DEPRECATION POLICY FOUND IS RELEASE-ANCHORED, WHICH IS WHY A CYCLE HERE WOULD BE
    THEATRE.** Kubernetes removes only on an API version increment; GitLab announces three
    milestones before a major; OpenSSL requires five years in an LTS release; Docker stages
    warn-then-remove across releases. **All of them presuppose releases we have not made**, so a
    deprecation cycle here would be a warning aimed at an audience of one who is reading the
    commit anyway.
  - **The precedent for removing outright is Git's own `BreakingChanges` document**, which
    retired `.git/branches/` on the grounds that most users are not aware of it and no active
    user complained. That is the shape used here: not "warn, wait, remove", but "establish that
    nobody is relying on it, then remove".
  - ⚠ **AND THE OTHER SIDE OF ccache**, which is the case for *not* doing this once there are
    users: it keeps a legacy `$HOME/.ccache` **permanently**, with no deprecation and no removal
    schedule, precisely because it cannot enumerate who holds one. **We can enumerate. That is
    the whole difference, and it is temporary.**
  - ⚠ **WHAT THIS COSTS, recorded rather than glossed.** `truestill catalog` no longer notices a
    legacy file, so a holder is no longer told one exists or pointed at `--move`. **The migration
    still works; nothing advertises it.** Acceptable at a population of one whose catalog is
    already migrated; **not** acceptable after a release, which is the same expiry as the
    reasoning above.
  - **`LEGACY_CATALOG_PATH` survives as `catalog --move`'s source only**, kept relative on
    purpose: *"migrate the one in front of me"* is exactly the question a relative path answers
    well, and exactly the one it answers badly when the question is *"which library is this?"*.
  - **Guarded** by `test_the_legacy_catalog_path_is_retired.py`, including the property the entry
    was filed for - two directories, one answer - and a source-level check that the resolver does
    not reach for the path again. Mutation-proved: restoring the legacy branch fails four of five.
  - **Nine tests pinned the old behaviour and were handled one at a time**, not swept:
    `test_legacy_probe_scope.py` was **removed whole** (it scoped a probe that no longer exists,
    preserved to `.superseded/`); the `(adv)` banner test became **two-way**, keeping the property
    that matters - a user is told which rule decided; and the CLI's *"reported as in use and
    offered a move"* test is **reversed in place** with the cost above written into it.

- **(adl) A MIGRATION STEP IS NOW ALL OR NOTHING, AND THE CONCURRENT RACE CLOSED WITH IT.**
  - ✅ **CLOSED 2026-08-19.** `Catalog._apply_step` runs each migration in its own
    **`BEGIN IMMEDIATE`** transaction **with `PRAGMA user_version` inside it**, and the ten steps
    that used `executescript` now go through `_run_script`, which splits on `_split_schema`.
  - **The defect, measured before the fix.** Forcing the v4 step to raise after its first of three
    statements left `user_version = 3`, `files.event_id` **present**, `events` **absent** - a
    schema that had moved and a version that had not.
  - 🔑 **WHY A TRANSACTION WORKS HERE, WHICH THIS REPO HAD ARGUED IT WOULD NOT.**
    `PRAGMA user_version` is itself transactional: rolled back it returns to the old value
    **together with the DDL beside it**. So the stamp inside the step makes *"the migration ran
    but the version stayed old"* unreachable by construction rather than by convention.
  - ⚠ **AND `BEGIN IMMEDIATE` RATHER THAN `BEGIN`, WHICH WAS GOT WRONG FIRST AND MEASURED.**
    Several steps *read* before they write, so a deferred transaction starts on SHARED - and
    SQLite refuses the SHARED->RESERVED upgrade **immediately, without honouring `busy_timeout`**.
    Deferred turned 6 of 90 concurrent opens into `database is locked`. The repo already knew
    this: `test_two_openers_build_the_schema_once` records that *"one writer bought by making the
    other fail is not the fix"*.
  - 🔑 **THE SECOND DEFECT CLOSED WITH IT, AND IT WAS NOT WHAT THE FIX WAS FOR.** `(adl)` also
    recorded that every migration's guard is a check-then-act outside any lock - **8% of opens
    failed at six openers, 12% at twelve, 100% forced**, with `duplicate column name`. Taking the
    step's transaction as IMMEDIATE puts the guard's read and the write it decides under one
    RESERVED lock. Measured after: **960 opens, zero failures**, at six and twelve openers, forced
    and natural. **No lock table, no `(aaw)`** - which stays owned by `(aaw)` for the drive case.
  - **Cost, measured three times on the real 6.37 MB / 2,695-file catalog** (full v1->v19 chain):
    **59.48 ms before; 58.40 and 66.08 ms after.** ⚠ **Overlapping, so no price is claimed** -
    the difference is inside this rig's own run-to-run spread at n=9. The prediction that it
    would be *faster* (50 autocommits down to 18 commits) is **not supported** either; a deferred
    `BEGIN` did measure slower at 69-71 ms, which is one more reason it is not what shipped.
  - **What it deliberately does NOT close**, asserted so it cannot be credited with more: a stop
    **between** steps leaves version N with schema exactly N. Schema and stamp agree, so it is
    resumable rather than damaged, and the next open continues at N+1.
  - ⚠ **A RECORDED ARGUMENT WAS REVERSED, NOT QUIETLY EDITED.** `test_migration_safety.py`
    concluded *"they are not a substitute for a transaction; they are the reason one is not
    needed"*, and its interruption test asserted *"the interruption must leave some work
    committed"*. Both are struck in place with the reasoning kept: that file was right about its
    evidence and named, two paragraphs later, the exact case where its conventions break - a
    backfill, where the column commits, the data rolls back, and the column guard then **skips**
    the retry. Idempotency and the no-backfill rule are **not** retired; they are now guards
    beside a transaction rather than in place of one.
  - ⚠ **AND THE BACKFILL GUARD WENT BLIND FOR ONE COMMIT, WHICH IS RECORDED RATHER THAN TIDIED.**
    `_sql_literals` reads SQL out of *attribute* calls, so moving ten migrations' SQL into
    `_run_script(conn, ...)` made it return **zero literals for all ten** - and a guard that sees
    no SQL reports no DML, silently. Caught while checking, fixed by naming `_run_script` in
    `_SQL_RUNNERS`, and pinned by a new cry-wolf that fails if any migration becomes unreadable
    to it again.
  - **Four mutants, control first, all caught:** the stamp moved back outside the transaction, the
    explicit `BEGIN` removed, deferred instead of IMMEDIATE, and `executescript` restored.
    ⚠ **The first survived twice before it was killed** - once because every test injected its
    failure *inside* the step rather than in the gap between the commit and the stamp, and once
    because the `set_authorizer` written to inject there denied `user_version` **reads** as well,
    so the open died at the fast path and "nothing was left behind" was trivially true. Both are
    recorded; the second has its own cry-wolf.

- **(adu) AN OPEN THAT WILL CHANGE NOTHING NO LONGER TAKES THE CATALOG'S WRITE LOCK.**
  - ✅ **CLOSED 2026-08-18.** `_migrate` reads `PRAGMA user_version` and the `files` row first; if
    the schema is current it **returns without opening a transaction**. Everything else falls
    through to today's `BEGIN IMMEDIATE` and **re-reads both under the lock**.
  - 🔑 **THE FINDING THAT DECIDED IT, and it collapsed the question rather than answering it.**
    The lock protects **exactly one state** - two openers both building a fresh schema - and that
    happens **once per catalog in the life of a library**. Measured: on an already-migrated
    catalog the migrate transaction writes **nothing** (`total_changes` 0 over five opens, file
    byte-identical, no journal sidecar), and **removing `BEGIN IMMEDIATE` there changes nothing at
    all** - the mutation *survives*. The same mutation is *caught* on a fresh catalog, where two
    openers immediately both build. Every open after the first was paying to protect a state that
    cannot recur.
  - **Why this is not the check-then-act §5.4 replaced**, which is the entire distinction and it
    is one line. The old defect **acted** on an unlocked read. This fast path can reach only one
    conclusion - *"nothing to do, return"* - and every path that writes re-reads under the lock.
    **Proven before the fix existed**: with the fall-through removed, `test_two_openers_build_the
    _schema_once` fails at `2 == 1` builders; unmutated control green first.
  - **Three routes died by measurement, not argument** (`PERFORMANCE.md` §5.6):
    - **read-first, lock-if-behind** - *is* §5.4's defect; fails the regression test on the first
      run.
    - **`BEGIN DEFERRED` upgraded to a write** - refused after **0.1 ms** with `database is
      locked` against a 5,000 ms `busy_timeout`, which SQLite does not honour on that upgrade. It
      buys one writer by making the other a casualty, which is what the regression test's second
      assertion exists to reject.
    - **an idempotent build** - `_SCHEMA` is *already* `CREATE TABLE IF NOT EXISTS` throughout, so
      it changes nothing about whether the lock is taken.
  - **Measured, on ext4 with a 256x `fsync` control** (the scratchpad on this machine is tmpfs and
    read **1.1x**; it was refused before anything ran - §5.4's own trap, met at the door):

    | already-migrated catalog | before p50 | after p50 | before p99 | after p99 | before max | after max |
    |---|---:|---:|---:|---:|---:|---:|
    | N=1 | 0.575 ms | 0.612 ms | 0.695 ms | 0.727 ms | 1.04 ms | 1.04 ms |
    | N=4 | 2.286 ms | **1.336 ms** | 9.69 ms | **2.40 ms** | 19.0 ms | **2.74 ms** |
    | N=12 | 9.565 ms | **2.237 ms** | 181.9 ms | **3.59 ms** | 232.5 ms | **4.29 ms** |

  - ⚠ **IT IS A TRADE, NOT A FREE WIN, and the uncontended row is here so it cannot be read as
    one.** A single open is **slightly slower** - 0.575 -> 0.612 ms, the one extra read. It buys a
    50x worst case under concurrency with a fixed sub-millisecond cost on every open.
  - **On a fresh catalog it changes nothing**, which was the one real risk: the unlocked read
    landing while another opener is mid-build. 40 trials at 6 and 12 openers, before and after -
    **exactly one builder every time, zero errors**, same open cost.
  - **Five guards, each proven by mutation in both directions**, control run first:
    `test_a_current_catalog_opens_without_the_write_lock.py` dies when the fast path is deleted,
    when the `files` check is dropped from its condition, and when `_refuse_if_newer` is dropped
    from it; `test_two_openers_build_the_schema_once` dies when the fall-through stops re-reading
    under the lock. ⚠ **The first run of that matrix was a FALSE PROOF and is recorded as one**:
    zsh does not word-split an unquoted `$TESTS`, so `pytest` got one unusable argument, exited
    **4** (usage error), and all four mutants read as "caught" while **no test had run**. Caught
    by the control printing *"no tests ran"*. `mutate_once.py` guards the anchor, not the command
    - the same class of false proof it was written to end, one layer out.
  - **What it does NOT do, so it is not credited with it:** it does not make the migration chain
    atomic (`(adl)`, which now has a measured rate), it does not touch `(adt)`'s 6.5 s settings
    write, and it does not decide `(ads)` - it makes `(ads)` **measurable** by removing the
    bottleneck that was identical in both journal modes.

- **(adr) A 0-BYTE FILE AT THE CATALOG PATH IS ITS OWN STATE, AND THE APP REFUSES IT.**
  - ✅ **CLOSED 2026-08-18.** A new `CatalogPresence.ZERO_BYTES` (tone `alert`), a shared
    `refuse_unusable_catalog`, and `CATALOG_UNUSABLE_EXIT = 6`. The CLI refuses ahead of its
    dispatch table, the launcher refuses ahead of the listening socket, and `prepare_catalog`
    refuses ahead of the startup migration.
  - **The defect, measured rather than reasoned.** `shutil.copy2` creates the destination before
    it writes, so patching the copy to raise `ENOSPC` left the destination **existing at size 0**.
    `inspect_catalog` then opened it, `Catalog._migrate` built the **full schema into the empty
    file**, and it was reported `presence=EMPTY, tone="notice"` - *"Opened empty catalog file
    at ..."*. Reproduced live before the fix: **0 bytes in, 159,744 bytes out.**
  - 🔑 **THE RULING, AND ITS REASONING IS THE ENTRY.** A new user has **no file**; this user has a
    file of **zero bytes**, which means something wrote there and failed. Treating them the same
    destroys the evidence of the second - and the product then tells the user to delete the good
    copy (`catalog_move.py:138`: *"Check the copy, then delete the old one when you are happy"*).
    **Refusing costs a first-run user nothing, and that is structural rather than rhetorical:**
    `WILL_CREATE` is `is_file()` being false, so the two states are **disjoint at the branch** and
    no first-run path changes. It is also the only moment the failure is still visible.
  - **A second origin the entry never named, and the fix covers it for free.** `sqlite3.connect`
    creates a 0-byte file before its first write, so a process that dies before the schema commit
    leaves the identical artefact - **our own failed write**, not a failed copy. The design keys
    on the *state*, so both are caught.
  - ⚠ **THE BRANCH POSITION IS THE FIX, and it took two mutations to prove the guard.** The check
    sits **before** the `Catalog` open; one line lower it runs against a 159,744-byte file and can
    never be true. Proven with `scripts/mutate_once.py`, unmutated control green first:
    **(a)** the branch moved below the open becomes dead code and the **presence** assertion
    catches it; **(b)** the `stat()` hoisted above the open but acted on below - the plausible
    tidy-up - reports `ZERO_BYTES` *correctly* and has already destroyed the file, so presence
    passes and only the **size** assertion catches it. **Neither assertion catches both**, which
    is why both are in the test. The first mutation was written believing it proved the second's
    point; it did not, and the test's own docstring was corrected rather than left overstating.
  - **The journal is evidence in one direction only.** Under `journal_mode=delete` (`BACKLOG.md`
    `(ads)`) SQLite removes the rollback journal on commit, so one still on disk means a write was
    **interrupted** - and the message says so. Its **absence proves nothing**: a failed copy never
    creates one either, so the quiet message names both possible causes and chooses neither. Both
    directions are asserted, because only guarding the loud case is how the quiet one grows a
    claim nobody checks.
  - **Exit code `6`, continuing the CLI's allocation** (`3` missing exiftool, `4` unusable
    destination, `5` busy catalog). Deliberately **not** `5`: busy means *retry*, and this must
    never be retried. It lives in **core**, unlike `CATALOG_BUSY_EXIT`, because busy is
    *presented* differently by each surface while unusable is presented the same way by both -
    one meaning spread over two literals is exactly the drift that is being avoided.
  - **`inspect_catalog` stays a pure describer**, so the refusal is a shared helper each entry
    point calls - which trades one risk for another: **a missing call is invisible**.
    `test_every_entry_point_refuses_an_unusable_catalog.py` closes that, **function by function**
    rather than module by module, because `drives.py` legitimately does both (`prepare_catalog`
    must refuse; `library_status` renders presence per request and must not). Both lists are
    checked for staleness in the other direction too.
  - ⚠ **A KNOWN RACE, ACCEPTED RATHER THAN DISCOVERED LATER.** A second process inspecting inside
    the microseconds between another's `sqlite3.connect` and its first write would refuse a
    catalog that is merely being born. `(adn)` records that nothing stops two processes anyway,
    and the outcome is a refusal the user clears by running again - against a retry loop that
    would be real complexity guarding a state indistinguishable from the real defect.
  - **What this does NOT fix, per the entry's own boundary:** `(adb)`, the *torn* copy. Staging
    fixes that and leaves the destination absent, which is correct and separate.

- **(ado) THE E2E LANE HAD A ROTATING WEBKIT TAIL. CAUSE FOUND, TAIL ACCOMMODATED.**
  - ✅ **CLOSED 2026-08-15 BY A RULING, NOT A FIX**, and the distinction is the entry. The
    `expect` budget goes **5 s → 30 s** (`tests/e2e/conftest.py`). Full census, the retired
    shapes, the trace evidence and the experiment are in
    [`research/ado-webkit-tail.md`](research/ado-webkit-tail.md), moved here whole rather than summarised.
  - **The cause is not a defect in this application.** WebKit on a shared 2-core runner is slow in
    bursts. A job reporting **0.2 files/sec recovers to 1.6** and finishes; the lane was killing
    the wait at 5 s while the work was still arriving. Measured over three full lanes at a 60 s
    ceiling: **1,482 tests, zero failures to complete, longest wait 28.4 s. Nothing hung.**
  - ⚠ **THIS ACCOMMODATES THE TAIL. IT DOES NOT REMOVE IT.** Runs will still be slow in bursts;
    they will stop being *red* for it. Anyone reading this as "the flake is fixed" has it wrong -
    what changed is that a slow wait is no longer reported as a failure.
  - ⚠ **THE LANE IS STILL WATCHED, AND THE WINDOW IS AT ZERO (2026-08-18).** Closing `(ado)` was
    a ruling about the *budget*; the exit condition - zero e2e failures across **ten** consecutive
    runs - is a separate, open watch. It had reached **seven** when run `32178286777` failed
    `test_the_choice_survives_a_reload[webkit]`, **a repeat of a censused failure from run
    `31821214510`** - same test, same browser, same assertion - which resets it. Eight distinct
    tests with one repeat became eight with **two**, five days apart, so the census's *"rotating
    almost completely"* is thinner than its wording carries. Recorded in
    [`research/ado-webkit-tail.md`](research/ado-webkit-tail.md).
  - ⚠ **AMENDED 2026-08-15: THE ARC'S "ZERO `database is locked`" EVIDENCE IS THE WRONG
    OBSERVABLE**, so catalog contention was never *excluded* from the census - only never
    visible. `jobs.py:211-214` replaces the sqlite error with `CATALOG_BUSY_MESSAGE` before it
    reaches any log. **This does not retro-claim the censused failures were contention**, which
    is unestablished. The correct observable and what it cost are in
    [`research/ado-webkit-tail.md`](research/ado-webkit-tail.md); the failure that found it is
    `BACKLOG.md` `(adt)`, and the mode behind it is `(ads)`.
  - **Why 30 and not 60.** 60 s was the probe's *ceiling*, picked so a hang would still end a
    test - never a target. A minute per genuinely hung assertion is too slow to fail. 30 s clears
    the 28.4 s worst case with room, and **anything over it is a finding rather than noise**.
    Proven live by timing a failing assertion: **`BUDGET_OBSERVED=30.0s`**.
  - **Why a ruling rather than more measurement.** More samples of the lane whose tail is the
    thing being measured cannot produce a defensible number - the tail moves with the runner.
    Adopted once as the price of WebKit here.
  - 🔢 **THE FINDING THAT REFRAMED THE ARC, and it is the reusable part.** Of **37** waits over
    5 s, only **nine** were job stalls; **28 had no job running at all**, the longest 16.35 s, on
    pure layout and page-load tests. `test_ui_regressions.py` dominated the census because it is
    where the tests **with a 5 s wait** live - a slow layout test has nothing to time out against,
    so it is slow and green, while the same slowness inside a job wait fails and gets censused.
    **The file was selected by the instrument, not by the fault.**
  - ⚠ **EVERY MECHANISM HYPOTHESIS THIS ARC PRODUCED WAS AIMED AT THE WRONG THING** - SSE
    buffering, the catalog lock, fixture teardown order, and `(adk)`'s SSE reader. **`(adk)` was a
    real defect and is correctly fixed on its own evidence; it was never this**, and the green run
    that followed it was a coincidence. Recorded so the fix cannot quietly take the credit.
  - ⚠ **AND THE ANSWER WAS IN THE ENTRY THE WHOLE TIME.** The concentration paragraph ended *"it
    is also where the job-driving tests live"* - correct, recorded, and filed under *evidence of a
    cause* when it was the *explanation*. Not staleness, not a missing measurement: **a true fact
    under the wrong heading**, which no guard and no re-measurement can catch. Only re-reading it
    against a new result did.
  - **Cost, measured rather than asserted.** A budget is only spent when something waits, so a
    green lane should not move - and it does not:

    | | wall clock | result |
    |---|---:|---|
    | before, local (5 s budget) | 1475.09 s (24:35) | 951 passed, 3 skipped |
    | **after, local (30 s budget)** | **1482.89 s (24:42)** | 951 passed, 3 skipped |
    | before, CI, 8 runs | 1169-1391 s | - |

    **7.8 s apart, 0.5%** - inside this lane's own run-to-run variance, which `(ado)` measured at
    19%. The price is paid **only on red**: a genuinely failing assertion now takes **30 s to
    report instead of 5 s**, verified by timing one (`BUDGET_OBSERVED=30.0s`). A red run with one
    failure costs about 25 s more than it used to.

- **(adk) A JOB'S EVENT STREAM COULD PIN A SERVER THREAD FOR EVER.**
  - ✅ **FIXED 2026-08-15**, found while investigating `(ado)`'s WebKit tail. ⚠ **It is NOT
    established as `(ado)`'s cause, and this entry does not close it** - see the negative result
    below. Fixed because it is a real defect on its own evidence.
  - **The defect.** `JobManager.stream` drained the job queue with a **timeout-less**
    `queue.Queue.get()` inside a **synchronous** generator. Starlette runs a sync generator in a
    worker thread, and a thread parked in `get()` cannot be cancelled - so uvicorn's graceful
    shutdown, which waits for the in-flight request, waited for ever.
  - **Both halves reproduced before anything was changed:**

    | probe | result |
    |---|---|
    | a **second** reader of one job | blocked past 3 s, with no producer left to wake it |
    | a real uvicorn told to stop, client already gone | thread **still alive 20.00 s** after `should_exit` |

  - ⚠ **A `queue.Queue` delivers each event to exactly ONE consumer.** The terminal event is put
    once, so the second reader - a page reload, an `EventSource` reconnect - waited on a producer
    that had already finished. In the e2e harness that thread is what `RetiringServers._sweep()`
    waits on, so a leaked server can never be reclaimed: `_pending` grows past `LIMIT = 8` and
    every later test pays `_join_one`'s 10 s join.
  - **The fix is a heartbeat, which is the standard SSE keepalive rather than an invention.** The
    read takes a 1 s timeout; on expiry it emits an SSE **comment** frame (`: ping`). Comment
    lines are ignored by every `EventSource` client, so no client changed - the point is that it
    is a **write**, and a write is what discovers a client that has gone away. On expiry the
    reader also answers from a recorded terminal event, so a reconnecting browser is now **told
    how the job ended** instead of hanging: a product improvement, not only a leak fix.
  - ⚠ **The record is read instead of `status`, and that ordering is the whole correctness
    argument.** `job.status` is set *before* the terminal event is queued - the summary is built
    in between - so a reader that trusted `status` could return before the terminal event
    existed, losing a real completion. `job.terminal` is written after the status and before the
    put, and is what the reader checks.
  - 🔢 **THE NEGATIVE RESULT, recorded because it is what stops this being claimed as the tail
    fix.** Instrumenting a real run of `test_ui_regressions.py` - 31 tests, chromium and webkit -
    showed **zero** live-thread growth (8 threads, first test to last). The suite does not trigger
    this locally. Measured alongside it, and also not proof of anything: **WebKit is 1.79x slower
    than Chromium** under CI's own flags (76.61 s vs 42.83 s over the same 31 tests) on a 16-core
    machine, against CI's 4, with the slowest assertion at **2.58 s of a 5 s Playwright budget**.
  - **Both guards fail against the old code and pass against the new**, and the file went from
    hanging for 12.66 s to passing in 2.21 s.

- **(adp) THUMBNAILS IGNORED EXIF ORIENTATION - A THIRD OF EVERY GRID WAS DRAWN WRONG.**
  - ✅ **FIXED 2026-08-14**, found by running Stage 0 of the grid redesign against 4,108 real
    photographs rather than against generated fixtures. Not introduced by the redesign; **this
    shipped**, and the square crop is what made it survive unnoticed.
  - **The census, on the real corpus:**

    | orientation | n | share | what shipped |
    |---|---:|---:|---|
    | 1 upright | 2,738 | 66.7% | correct |
    | 3 (180 degrees) | 67 | 1.6% | **upside down**, correct aspect |
    | 6 / 8 (quarter turns) | 1,303 | 31.7% | **sideways**, wrong aspect |
    | | **1,370** | **33.3%** | **drawn wrong** |

  - **200 of 200 sampled quarter-turn photos rendered sideways**: a 4000x3000 source whose tag
    says portrait produced a 320x240 landscape tile. The browser could not compensate - `render`
    writes WebP **without EXIF**, so the tag a JPEG carried is gone before anything sees the bytes.
  - ⚠ **The 67 are the ones an aspect check cannot find.** A 180-degree rotation leaves width and
    height alone, so every measurement of shape agrees with a picture that is upside down. The
    first census counted only orientations 5-8 and reported 31.7%; the real figure is 33.3%, and
    the class it missed is invisible to the method that found the rest. Recorded because the next
    person measuring orientation will reach for aspect first, as this one did.
  - **The fix is `ImageOps.exif_transpose` AFTER `draft`+`thumbnail`, and the order is worth 4.4x.**
    `exif_transpose` needs pixels, so calling it first forces a full-resolution decode and throws
    away the DCT scaling `render` exists for. Measured over 40 corpus photos: **27.00 ms/file with
    the transpose last, 117.82 ms/file with it first**, identical output either way.
  - **Guarded twice, deliberately.** A corpus test (real cameras, real tags, skips without the
    corpus) and a generated test covering **all eight** orientations - because the corpus holds
    only 1, 3, 6 and 8. There is **no orientation 5 or 7 in 4,108 photographs**, so a corpus-only
    guard would have claimed coverage it did not have. Both fail against the old `render`.

- **(adq) A DAMAGED PHOTO ANSWERED 500 - 5 IN 4,108 REAL FILES.**
  - ✅ **FIXED 2026-08-14**, same Stage 0 pass. A JPEG that stops early raises a plain `OSError`
    (*"broken data stream"*, *"image file is truncated (31 bytes not processed)"*), which is
    **not** a subclass of `UnidentifiedImageError` - verified, not assumed. So it fell past the
    thumb route's 400/404/415 handlers and reached the browser as a **500**. One damaged photo in
    a grid of forty-eight took the tile out with a server error.
  - **422, not 415, and the line is imgproxy's:** 422 when a source is reachable but cannot be
    processed, media-type codes reserved for media types. A truncated JPEG **is** a supported
    media type; nothing about the format is unsupported. 500 was a lie in the other direction -
    the server is fine, the photograph is damaged.
  - ⚠ **Deliberately NOT salvaged with `ImageFile.LOAD_TRUNCATED_IMAGES`**, which is the common
    remedy and is wrong here: it renders the intact prefix, pads the rest, and **caches that under
    the content hash**, so a damaged photo looks fine forever and the one surface that could tell
    an owner their file is rotting becomes the surface hiding it. truestill is a custody tool.
  - **What is still open:** the grid renders a broken-image tile for a 422. Telling a person
    *which* photo will not decode belongs to the result grid's own design, not to the route.

- **(acj) Write to a temp name and rename, instead of writing straight to the target.**
  - ✅ **BUILT 2026-08-11, and the reason it was worth building is not the one this entry gives.**
    The entry argues the stronger shape for the *copy*. The larger find was one step later:
    **`service/backup.py` hashed the file after it was already at its real name**, and unlinked it
    when it did not match - so a copy that failed verification wore the organized name for the
    length of a full re-read of its own bytes. That is `(abu)`'s exact shape, moved past the point
    `(abu)` was looking at. **`(abu)`'s fix could not reach it**: that fix was aimed at a copy that
    died, and this window opens only after a copy succeeds. The digest is now taken on the staged
    file and a mismatch abandons it, so the destination is never written at all.
  - ✅ **`occupied_before` is deleted, not improved.** The old form had to decide whether a file at
    the target was ours to remove, and a wrong answer there deletes a user's file. Nothing is ever
    written at the target now, so the question has no place to arise.
  - **THE CLAIM IS "no partial ever takes the real name", NOT "atomic".** The first holds on every
    filesystem; the second is a POSIX guarantee, and §1 already records that FAT32 and exFAT
    journal nothing, so a power cut during the directory-entry update can still orphan it. The
    stronger word is kept out of the code and the docs deliberately, because it would be quoted
    back later as a guarantee nobody made.
  - **No `fsync`, and the reasoning lives at the site so nobody adds it as an obvious improvement.**
    `copy2` does not fsync today and `archive_extract` writes media the same way. The defect is a
    *name* worn by incomplete bytes; `fsync` is about whether *content* survives power loss, which
    `copy_sha256` and `verify` already own.
  - ⚠ **THREE PREMISES IN THIS ENTRY WERE WRONG**, corrected rather than quietly worked around:
    1. *"a rename across filesystems degrades to a copy"* - `os.replace` **fails** across
       filesystems; degrading is `shutil.move`. And it cannot arise: the staged file is a sibling
       of the target, which `write_decisions` had already argued is what makes the rename local.
    2. *"it changes the write path for every backend"* - it does not. `RcloneDestination` shells
       out to `rclone copyto` and deliberately has no remote-delete primitive, so there is no byte
       loop to protect. Scope was `LocalDestination` plus `service/backup.py`.
    3. The worry that `LocalDestination.list()` would surface stray staged files - **`list()` has
       no production caller at all.** It is an ABC method exercised only by tests.
  - **A mutation that did not fire, recorded because it is a platform fact rather than a weak
    guard:** swapping `Path.replace` for `Path.rename` kills nothing on Linux, since POSIX rename
    overwrites silently. It raises on Windows, where an occupied target is ordinary at two of the
    three sites. `test_committing_over_an_occupied_target_replaces_it` exists so the **Windows
    lane** is the detector for that choice, and says so.
  - **Named rather than left to be rediscovered - three copy paths this did NOT reach:**
    - `organizer._MetadataBaker` stages into the **system** temp directory and uploads from there,
      so it crosses a filesystem before the real write and `safe_copy` would not help it.
    - `catalog_move.py` copies the catalog with a bare `shutil.copy2`; a failure leaves a truncated
      SQLite file wearing the name the user was told to point at - `(abu)`'s shape on a database.
      Both are filed as `(adb)` rather than left as a note in a closed entry, because the two need
      different remedies and only the second has one.
    - `RcloneDestination`, by design and by its own module rule that no code path there may remove
      data at the remote.
  - **What is still owed is `(acz)`**, rewritten the same day: a survivor is now unambiguous debris
    rather than a possible incumbent, but the seam that found the original - `rescan` reporting it
    as STRAY - no longer sees it, because `.partial` is not a media extension.

  Recorded 2026-08-10, deferred out of `(abu)` deliberately rather than forgotten.
  - **The stronger shape.** `(abu)` removes a partial in an `except`; a temp-then-rename never
    creates one at the target path at all, because the bytes only take the real name once they
    are all there. It is the same reasoning `decisions.write_decisions` already uses for the
    drive document: temp in the same directory, flush, fsync, `os.replace`.
  - **Why it was not done with `(abu)`:** it changes the write path for **every** backend rather
    than one `except` clause, and the rename must be same-filesystem to be atomic - which is a
    property of each destination, not of the caller. That is a decision someone makes, not a
    detail that rides in on a bug fix.
  - **What it would still not fix:** a rename across filesystems degrades to a copy, so the
    guarantee is not free everywhere. `(abu)`'s cleanup stays useful underneath it.

- **(abu) A failed copy leaves the bytes it managed to write, and nothing owns them.**
  - ✅ **MOVED HERE 2026-08-11, and it was already built on 2026-08-10.** It sat in the open-work
    file for a day carrying a `BUILT` marker, invisible to the closure guard because it predates
    the `Closes` trailer rule and no commit ever declared it. That is the `(aae)`/`(jj)` drift
    exactly, caught by a merits read rather than by a check. **Its one live residual - a partial
    that survives because the cleanup itself failed - is now `(acz)`, so the fixed work stops
    being carried as open.**
  Recorded 2026-08-07 from the first real organize onto the maintainer's library. **Ranked at
  the top: it is the only known path that puts a file into a library that nothing accounts for.**
  - **Observed, not theorised.** `VID_20150730_000606.mp4` failed with `[Errno 5]` at 802 MB of
    852 MB. `shutil.copy2` raises and leaves what it wrote, so Morrowkeep now holds an
    **802,684,928-byte truncated video carrying a correct organized name**
    (`20150729_184159_VID_20150730_000606.mp4`) with no `files` row and no `file_copies` row.
    The run said `1 failed`. It did not say 802 MB of it arrived.
  - **What the invariants DID hold**, so the ranking is about debris rather than loss: the source
    was untouched (copy mode), and nothing was recorded as copied - `upload` raises before
    `record_uploaded` is reached. `verify` will never check the partial; `rescan` reports it as
    STRAY, which is exactly right and is how it was found.
  - ⚠ **A retry makes it worse, and that is the sharp end.** `_free_target` suffixes rather than
    overwrites - *"never lose data"*, correct for its real case of two distinct `IMG_0001.jpg` -
    so a second attempt sees the partial, treats it as an incumbent, and writes
    `..._1.mp4` beside it. **Every retry leaves another 802 MB.**
  - **THREE SITES, one shape**: `LocalDestination.upload` (organize), `LocalDestination.relocate`
    (migrate-layout) and `service/backup.py`'s copy loop all use `shutil.copy2` and all leave the
    partial. `relocate` already **knows** - its comment says it *"overwrites a partial copy left
    by an interrupted run"* - so the debris was met once and answered with overwrite-next-time
    rather than remove-on-failure. That works where the path is re-derived identically and fails
    where a suffix intervenes.
  - **THE FIX IS BOTH, and remove-on-failure is the load-bearing half.** Unlink the target inside
    the `except` before raising, so a failure leaves nothing; and name the partial in the report,
    because a user who watched 800 MB cross a slow link deserves to know it was discarded rather
    than wonder. Reporting alone is not enough: it leaves the retry-accumulates behaviour intact.
    A temp-name-then-rename would also work and is the stronger shape, but it changes the write
    path for every backend rather than one `except` clause, so it wants its own decision.
  - **The unlink must itself be guarded**: the failure that produced the partial is often the one
    that will refuse the delete, and a cleanup that raises would replace a reported failure with
    an unreported one.
  - ✅ **BUILT 2026-08-10 as `safe_copy.copy_leaving_nothing`**, called from all three sites.
  - ⚠ **THE FINDING THAT SHAPED THE FIX, and it is not what the entry above assumed: a blind
    unlink would delete files this run did not write.** `shutil.copy2` opens the SOURCE first, so
    a failure before the destination is opened - unreadable source, denied permission, a parent
    that could not be made - leaves the target **untouched**. And at two of the three sites that
    target can legitimately be occupied: `relocate` overwrites an interrupted run's partial by
    design, and `backup` builds its work list from the CATALOG
    (`_files_missing_on_target`), so anything the catalog does not know about can be sitting
    there. The rule is therefore **remove only what this call created**, decided by an
    `exists()` taken immediately before the copy and never accepted from a caller -
    `organizer._free_relative` also checks, some lines earlier, and a stale "it was free" is
    exactly the input that would turn the cleanup into a deletion.
  - **`relocate`'s overwrite was a red herring.** Once `copy2` has opened the destination the
    incumbent is already truncated, so removing it afterwards destroys nothing that survived.
    What makes that site different is only that its target is often occupied, which is a value
    of the same flag rather than a second design.
  - **`backup.py` already unlinked on a bad checksum** (`:312`), so remove-on-failure was not a
    new idea here - it existed at one of the three sites for the neighbouring case.
  - **RETRY-ACCUMULATION IS CLOSED WHEN CLEANUP SUCCEEDS AND REPORTED WHEN IT DOES NOT**, and
    nobody should read this entry as fully closed. If the unlink fails the partial survives, and
    a surviving partial **should** be treated as an incumbent: we could not delete it, so
    pretending it is not there would be the dishonest option, and `_free_relative` suffixing
    beside it is the "never lose data" rule doing its job. What closes the gap is the message -
    the path and the byte count of what was left - not different behaviour.
  - **The TOCTOU at `upload` is not a data-loss path**, stated with the reason rather than tested
    with something that proves nothing: `_free_relative` checks `exists()` some lines before the
    write, so a file could appear in between - but the helper takes its own `exists()`
    immediately before copying, so it would see that file as an incumbent and refuse to remove
    it. The window can cost an overwrite, which is `_free_relative`'s pre-existing hazard, and
    cannot cost a wrong deletion. Pinned by a test asserting the helper's signature offers no way
    to pass an opinion in.

- **(acd) THE BACKUPS CONTROLS MOVE AFTER THE SCREEN IS INTERACTIVE - and the readiness signal
  - ✅ **MOVED HERE 2026-08-11.** Fixed 2026-08-10 and carried in the open-work file for a day for
    the same reason as `(abu)`: a `FIXED` marker with no `Closes` trailer, invisible to the guard.
    **The accepted cost it deferred - state now sits below the forms, so a one-copy warning can
    fall below the fold - is now `(ada)`**, which is the part still owed and the part `(abg)` must
    re-price.
  is about to remove the only thing that reports it.** Recorded 2026-08-10, found while planning
  the readiness signal, **from the DOM order rather than from a failure**. `#drives-list`
  (`index.html:249`) renders **above** the card holding `#bk-preview` (`index.html:276`) in the
  same section, so when `loadDrives` writes it every control below shifts down. A person reaching
  for *Preview copy* inside that window clicks where the button **was**.
  - ✅ **MEASURED 2026-08-10, and it is 30-115x larger than `(abq)`'s mover.** Taken with
    `/api/drives` held open, `#bk-preview`'s box read before and after the write lands, under
    stubbed drive counts. **This entry is confirmed, not retired.**

    | drives | `#drives-list` height | `#bk-preview` moves | click-to-ready |
    |---|---|---|---|
    | 0 | 0 -> 130.4 px | **+142.4 px** | 80 ms |
    | 1 | 0 -> 144.0 px | **+156.0 px** | 87 ms |
    | 3 | 0 -> 551.1 px | **+563.1 px** | 100 ms |

    - ⚠ **There is no no-shift case.** Zero drives still moves the button 142 px, because
      `loadDrives` renders an empty-state card rather than nothing. A library with no registered
      drive - the first-run user - gets the defect too.
    - **The control is LIVE throughout**: `#bk-preview` is visible and enabled for the whole
      window, so nothing refuses the click and Playwright's actionability checks would not help.
    - **A click at the old position is silently swallowed.** Measured with `elementFromPoint` in
      a viewport tall enough to hold both positions: with one drive it lands on
      `#bk-source-hint`, a text span; with three, on an `<h2>`. Nothing happens and nothing says
      anything.
    - **The window tracks endpoint latency about 1:1** - 98 ms local, 329 ms with a 250 ms
      delay, 1,085 ms with 1,000 ms. It is the slower of the two requests in `loadDrives`'
      `Promise.all`, not their sum. On a large catalog or a cloud-mounted library the button is
      mispositioned for **over a second**.
    - *Measurement note:* a first attempt reported "nothing at the old position" and that was an
      artifact - at the default viewport the button already sits below the fold, so
      `elementFromPoint` was querying outside the viewport. Re-run at 1280x1600.

  - ✅ **FIXED 2026-08-10 by moving `#drives-list` below every control.** `#bk-preview` now moves
    **0.0px** at zero, one and three drives - exact, with no bound to declare, because a control's
    position is no longer a function of how many drives arrive. Pinned by
    `tests/e2e/test_the_backups_controls_do_not_move.py`, which asserts the harm directly:
    `elementFromPoint` at the position the button occupied must still be the button. Restoring the
    old order turns all three red.
    - **RESERVING SPACE WAS BUILT, MEASURED AND REJECTED - the numbers are why this is a move.**
      A skeleton sized from the exact registered-drive count cut the shift 4-6x (165->40, 156->30,
      563->91) and **still left it 2-5 button heights**: `#bk-preview` is 34.8px, so the harm
      needs the shift under ~17px, and a card's height is content-driven (optional reach badge,
      optional last-seen note, up to four decisions lines, 68ch wrapping). Matching the fixture's
      cards would have been overfitting to the test.
    - ⚠ **And it introduced a direction that did not exist.** Reserving from a count learned at
      boot can over-reserve, so the region SHRINKS and the button moves **up** - measured at
      **-316.6px** when the boot count said three and the answer was one. Before the skeleton a
      shrink was impossible: the region grew from empty, always downwards. That is a trade for a
      worse defect, not a partial fix.
    - **THE COST, accepted by the maintainer and stated rather than softened.** The Backups pass
      deliberately put state ABOVE remedy so the at-risk banner pointed down at the copy form.
      That is inverted: the forms come first and the state below them. The sharpest form of it is
      that the at-risk banner renders **inside** `#drives-list`, so a user with files in only one
      place now meets two forms before the warning, and on a short viewport that warning is below
      the fold. Accepted on the grounds that a control which cannot be reliably clicked is worse
      than one met before its context. Two shipped strings said "below" and now say "above"; both
      live inside the moved region, so they travelled with it.
    - ⚠ **REVISIT WHEN `(abg)` REACHES THIS REGION.** The inversion is accepted, not settled. The
      at-risk warning below the fold on a short viewport is a live cost, and `(abg)` - the most
      important open item on this project - will put more state into exactly this region. Whoever
      builds it must re-price the order rather than inherit it.
    - *Not a cost:* `test_user_facing_copy.py` was reported as pinning a third "below" string and
      does not - that list BANS retired wording. Editing it would have weakened a guard.
    - *Available if ever needed:* the exact registered-drive count is one binding away in
      `library_status` (`catalog.list_drives()` is already materialised and `places` is a filtered
      view of it). Not added, because nothing reads it - that is `(abm)`'s shape.

  - **Two movers on this screen, and they are not the same defect.** This entry owns the
    **screen-open** mover: `loadDrives` → `#drives-list`, above the whole card. `(abq)` owns the
    **after-typing** mover: `validatePath` is `debounce(run, 400)` and writes into
    `#bk-source-hint` / `#bk-target-hint` (`index.html:270, 274`), immediately above the button.
    **The measured +4.9px on `(abq)` is that second mover, not this one.** This one is derived
    from DOM order and is **unmeasured** - measuring it is the first task here, and the number
    may be larger, since a drive card is taller than a line of hint text.
  - **This is not the flake it was mistaken for.** `(abq)` was read as a click on a not-yet-live
    control. It is not: the `#bk-preview` handler reads only `#bk-source`/`#bk-target` and POSTs
    `/api/backup/preview`, so it needs **neither** endpoint `loadDrives` fetches, and those two
    fields are filled at boot by `loadCustody`. The control was live and correctly wired the whole
    time. What moved was its position. **Layout shift, not uninitialised state.**
  - ⚠ **Why this is filed before the readiness signal lands, not after.** Readiness makes a test
    wait past the **screen-open** shift, so nothing observes it again while it stays live. The
    detector being removed is `open_backups`'s `wait_for_selector("#drives-list *")`
    (`e2e_support.py:141`), which fails today if that region never populates; readiness replaces
    it with a wait that is satisfied whether or not anything moved. **A defect whose only
    detector is being removed must have a replacement detector filed the same day**, and this is
    it. It does **not** follow that `(abq)` is closed - see below.
  - ✅ **`(abq)` is not closed by the readiness work, and not for the reason first written.** The
    plan claimed readiness would launder it. It does not touch it: `(abq)`'s mover fires ~400ms
    after typing, long after `data-ready="ready"`, and readiness is scoped to screen open.
    `(abq)` keeps its own recorded fix - wait for the hint spans to become non-empty before
    clicking - which is in-action work, not Stage 0.
  - **Reserved height only approximates, so it may not be the fix.** Zero, one and three drives
    render different heights, and `loadDrives` conditionally adds a whole summary card when
    `drives.length > 1` (`app.js:2387`). A `min-height` that covers the largest case leaves dead
    space in the common one and still shifts on the largest. **Ordering may be correct rather than
    sizing** - putting the mutable region *below* the fixed controls means nothing it writes can
    move them - or a bounded, declared shift, accepted and stated. The choice is open; the
    approximation is why.
  - **Whichever is chosen needs a bounding-box regression test written as part of it**: measure
    `#bk-preview`'s box before and after `data-ready="ready"`, assert a zero or declared-bound
    delta. Written *with* the change, never after - once the readiness migration lands, nothing
    else will ever notice this again.

- **(acx) THE ORGANIZE PREVIEW NEVER RECEIVED `skip_undated`, SO IT PROMISED FILES THE RUN WOULD
  SKIP.** Recorded **and fixed** 2026-08-11, found while verifying `(abl)`. Filed anyway, and that
  is deliberate: it was never recorded, it is a distinct mechanism from `(abl)`, and a defect
  closed inside another entry's commit is invisible to anyone reading the backlog.
  - **The mechanism.** `organize_run` accepted `skip_undated`; **`organize_preview` had no such
    parameter**, and the preview POST never sent it. The run skips those files
    (`organizer.execute`), so with *Skip files with no date* ticked the confirm control promised
    more than the run delivered, by the undated count.
  - ⚠ **This is the direction that matters.** `(abl)` understated, and its neighbouring button was
    correct anyway. This **overstated**, on the control a person types a word into before files
    move, and nothing else on the screen contradicted it. A preview promising more than the run
    delivers is worse than one promising less.
  - **The CLI did not have it**, which is what makes this the third instance of one operation
    answering differently on two surfaces - after `(aca)` (the app and the CLI disagree about when
    an organize run needs confirming) and `(abe)` (CLI-organized files were invisible to custody).
    The CLI threads the flag into `preflight_for_run`; only the app's preview was blind to it.
  - ✅ **AND THIS ONE WAS MECHANICALLY CHECKABLE, WHICH THE OTHER TWO WERE NOT.**
    `test_preview_accepts_every_run_option.py` asserts that every decision-affecting keyword
    parameter of `organize_run` is also accepted by `organize_preview`, read from the live
    signatures. It would have caught this the day the parameter was added.
    - ⚠ **It is narrower than the class, and the entry says so rather than letting a green run
      imply otherwise.** It compares **one pair of functions in one module**, and only that the
      preview *accepts* what the run accepts - a preview that took the flag and ignored it passes
      here (killed by `test_the_preview_promise_equals_the_run.py` instead, which is why the two
      ship together). It says nothing about `(aca)` or `(abe)`: those are the app against the
      **CLI**, whose preview is a set of print functions rather than a function with a signature,
      so there is no pair to compare.
    - **What the class actually needs** is an assertion that the two surfaces answer the same
      question the same way - which for the CLI means comparing rendered output, not signatures.
      §9's one-home rule is the structural version and is cheaper: `models.status_label`,
      `date_quality` and now `ReportBuckets.will_organize` are single homes precisely so the
      surfaces cannot differ. **Where a number or a word has one home, no guard is needed; where
      it does not, a guard is possible only when both sides are callable.**
  - **A sentence needed its own branch, not just a corrected count.** *"Of those organized, N have
    no date and will go to Undated"* asserts the opposite of what happens when skipping is on -
    those files are not organized and reach no folder. The count being right does not repair a
    sentence, so there are now two.

- **(abl) THE PREVIEW TALLY SAYS "will be organized" ABOUT ONLY PART OF WHAT IS ORGANIZED.**
  - ✅ **CLOSED 2026-08-11.** Verified real first - the defect was still live, and nothing since
    `d9dc8be` had touched the tally. A near-duplicate has `should_upload is True` and finishes
    `ActionStatus.UPLOADED` (`test_organizer.py`), and under `--move` its source is deleted like
    any other, so the row saying *"will be organized"* over `new_unique` alone named less than the
    run took.
  - ⚠ **THIS ENTRY'S PRESCRIBED FIX WAS INCOMPLETE, and the correction is on evidence rather than
    preference.** It ruled *"the fix is wording"*. It was written before anyone noticed that the
    confirm control **already rendered the right number**: `new_unique + near_dup`. So the card and
    the button sat on one screen stating two different answers, and re-wording alone would have
    left them disagreeing while reading better. The fix is one number, computed once, rendered by
    both - `ReportBuckets.will_organize(skip_undated=...)`, published as `will_organize`.
  - ✅ **THE CONSEQUENCE WAS SMALLER THAN THE ENTRY'S POSITION SUGGESTED, and that is worth
    recording.** The number a person types a confirm word against was **already correct**, so a
    user who read the button saw the truth and would rarely have decided differently. This was a
    screen contradicting itself, not a screen lying about a file operation. Said plainly so the
    next reader does not file a wording defect as a near-miss - `(acx)`, found while checking this
    one, is the one that could actually have changed a decision.
  - **Four surfaces, not one**, and the CLI's own two disagreed with each other: the app tally row
    (`new_unique`) against the app confirm control (`new_unique + near_dup`), and `cli.py`'s report
    header *"NEW UNIQUE (n) - would be organized"* against its summary block, which has always
    been honest - *"organized (unique)"* / *"organized (near-dup)"*. A fifth, the inverse, was
    found while checking: the Takeout ingest report printed *"kept (unique)"* over
    `buckets.organized`, a label naming less than its own number, with no test on it at all.
  - **Near-duplicates keep their own row**, as this entry required. A user organizing three files
    one of which is a look-alike is making a different decision from one organizing three new
    files, and folding them hides it. **"flagged" was decided rather than inherited**: the row now
    says *organized too, and listed below*, because `matchListHtml(s.near_dup_matches, ...)`
    renders that list on the same card, above the confirm - so the word points at something the
    reader can open before consenting rather than at a state they are told they are in.
  - ✅ **Detector, in with the fix:** `test_the_preview_promise_equals_the_run.py` asserts the
    preview's promise equals what the run organizes, in both directions. That assertion existed
    **nowhere** before - conservation and disjointness were the only invariants, and both hold
    happily while the promised number is the wrong one. Proved to bite: pointing `will_organize`
    back at `len(buckets.unique)` turns all three red.
  Recorded 2026-08-06, found by running the overlapping-organize sequence on real photos rather
  than on fixtures. Eight photos from one event: the tally read `2 new - will be organized`,
  `1 look-alike - kept and flagged`, `5 duplicates`, and the run organized **3**. Both labels
  are individually true - a near-duplicate IS kept and flagged - and together they mislead,
  because the row that says *will be organized* is not the set that gets organized. **Same class
  as the summing block one layer down**: the block sums correctly, and one of its rows describes
  itself wrongly. It fires on any folder of photos taken at one event, which is most folders.
  - **Not a counting defect.** `partition_for_report` is right and the buckets stay disjoint;
    `new_unique + near_dup + exact_dup + unreadable == files` still holds. Only the wording of
    the first row is wrong, and only because the second row is also organized.
  - **The fix is wording and belongs with whichever screen commit reaches this tally**, not as a
    change on its own - the two rows have to be re-worded together or the pair stays incoherent.
    Do not "fix" it by moving near-duplicates into the first row: the flagging is the point.
  - Pinned by nothing today, deliberately: the assertion that would pin it is the wording, and
    writing it now would fix the wording before it is chosen. The behaviour is covered by
    `test_preview_tally_is_disjoint.py`.

- **(abq) `#bk-preview` is clicked five ways and only one of them is race-free.** Recorded
  - ✅ **CLOSED 2026-08-11, AND NOT BY ANYTHING AIMED AT IT.** Two changes made for other reasons
    removed the mover: `7bb645c` (08-10 09:34) settled the screen before acting, and `92bb104`
    (08-10 15:28) moved `#drives-list` below every control for `(acd)`. **All four recorded
    failures predate both** - 08-06 21:05, 08-07 10:37, 08-09 13:24 and 08-10 **07:10**.
    - **The closure rests on a probability, not on a count.** At this entry's own assumed rate of
      one failure in three runs, **14 consecutive green e2e runs** put the chance an unfixed flake
      produced them at **(2/3)^14 = 0.34%**, about one in 290. The entry's stated bar was 8
      minimum and 12 to call it fixed.
  - ✅ **THE +4.9px HYPOTHESIS IS REFUTED BY MEASUREMENT**, which is the finding this entry ends on.
    `#bk-preview` is **34.8px** tall, so a centre-aimed click misses only past **17.4px**. Measured
    2026-08-11 with `elementFromPoint` at the pre-shift centre, viewport 1280x1600:

    | hint state | shift | element at the old centre |
    |---|---|---|
    | valid paths, short hints | **+9.8px** | `bk-preview` |
    | unusable paths | **+4.9px** | `bk-preview` |
    | source only | **+0.0px** | `bk-preview` |

    **The mover this entry was open on for weeks cannot miss.** The screen-open mover it was NOT
    open on - `(acd)`'s +142 to +563px - is what was losing the clicks.
  - ⚠ **THE MISDIAGNOSIS, and where it came from, because it is the expensive part.** The premise
    that a trace showed the request issued and accepted with a **202** is not this entry's trace at
    all: that is `(acb)`, cited here since 2026-08-08 as the **opposite** mechanism. `(abq)`'s own
    traces show **zero** `/api/backup/preview` requests, three times over. The attribution was made
    from a report about the other entry and restated as fact this session; checking it rather than
    accepting it is what turned the entry around. **Third time in one week that verifying a handed-
    down premise changed the answer.**
  - **Five click sites, not four.** Four real `click()`s plus `test_backups_on_the_pattern.py`,
    which waits on both hints *and* uses `dispatch_event`. Three of the four were converted to
    `open_backups` with the closure - **hygiene, not the fix**: after `(acd)` nothing `loadDrives`
    writes can move those controls, so they were no longer racing anything.
  - ✅ **The replacement detector went in with the closure**, not after:
    `test_the_backups_controls_do_not_move.py` gained a second case for this mover, pinning the
    states that occur and proved to bite against a forced one (+71.8px, landing on
    `#bk-target-hint`). The forced case is **not committed** - it is reachable in the product and is
    filed as `(acw)`; a committed red test is a live defect with a test attached, not a detector.
  - ⚠ **What this closure does NOT cover, so the next person does not read it as a clean screen.**
    `#verify-path-hint`, `#verify-path-carried`, `#verify-result` and the verify run block all sit
    in card 1, **above** `#bk-preview`, and a verify run resizes them. That is the same shape as
    `(acw)` and it is **unmeasured**. `test_backups_on_the_pattern.py` also still uses
    `dispatch_event`, so that one site does not exercise real mouse delivery.

  2026-08-07 from the `test_backup_preview_busy_re_enables` flake (2 failures in 4 consecutive
  CI runs, green locally every time).
  - 📌 **STATUS 2026-08-10: STILL OPEN, and the readiness work did NOT close it.** Stages 0-2
    shipped a screen-readiness signal and closed the screen-OPEN race on this very screen
    (`test_cancel_renders_cancelled.py`'s backup site, which filled `#bk-source`/`#bk-target`
    below `#drives-list`). That is not this entry's mover. **This entry's measured +4.9px is
    `validatePath`'s debounced hint spans, ~400ms AFTER typing** - long after
    `data-ready="ready"` - and readiness is scoped to screen open, so it never reaches it. The
    fix recorded below (wait for the hint spans to become non-empty before clicking) was never
    built and was refuted instead - see the closure above. The screen-open mover was `(acd)`,
    fixed 2026-08-10 and now recorded in this file.
  - ⚠ **Stage 3 of that work - converting the 63 fixed sleeps - was CLOSED ON MEASUREMENT rather
    than abandoned**; the reasoning is on `(acf)` in `SHIPPED.md`. It matters here because this
    entry's own fix is a wait, and the standing answer is now: **let a specific sleep fail and be
    recorded** by `scripts/flake_report.py`, rather than converting on principle.
  - 📌 **READ THIS FIRST: the contradiction that held this entry up was reconciled 2026-08-10,
    and the two records were never in conflict.** One describes a residual race AFTER the screen
    has settled; the other is a click that never settles at all. Nobody could choose between them
    without that distinction, which is why the entry sat from April-era reasoning through four
    failures. The detail is below under RECONCILED; the fix that followed is the smaller half.
  - **The `(aak)` shape again.** `dispatch_event("click")` was applied to
    `test_backups_on_the_pattern.py` with its trade-off documented at the site - *"WHAT THIS
    STOPS EXERCISING: mouse-event delivery to this one button"* - and never carried to the four
    siblings (`test_busy_state.py`, `test_golden_path.py`, `test_ui_regressions.py` x2). All
    four fill path fields and click immediately.
  - **`dispatch_event` is the WRONG remedy for the rest**, and this is the finding rather than
    the observation. It bypasses hit-testing **and** actionability, so it would pass on a
    button that is disabled, covered or off-screen - hiding exactly the class of regression the
    browser lane exists to catch. Making a test immune is not making it correct.
  - **The deterministic fix is the settle signal the product already emits.** Path validation is
    `debounce(run, 400)` and writes into the hint spans **above** the button (`app.js`
    `validatePath`), so the button moves - measured **+4.9px** - inside the click window.
    Waiting for `#bk-source-hint` / `#bk-target-hint` to become non-empty before clicking
    removes the race at source and keeps real mouse-event coverage.
  - ⚠ **2026-08-08: THIS DIAGNOSIS DOES NOT GENERALISE, and a second instance contradicts it.**
    `(acb)` is a cancel failure in the same browser lane and the same family, and its mechanism is
    the OPPOSITE: the cancel request was issued and accepted with a 202, and what failed was the
    event stream afterwards. A lost click and an unreported dead stream look identical from the
    outside - a cancel that does nothing - and folding them together would have lost both. This
    entry's finding stands **for this test only**. Anyone reaching for it as the explanation for a
    cancel flake elsewhere should read the trace first; that is what separated them here, and this
    entry already carried one flagged contradiction nobody had reconciled.
  - ✅ **MECHANISM PROVEN 2026-08-07: the click is lost.** It recurred on run `31208332669` and
    this time the trace uploaded, which is exactly the condition this entry was waiting on.
    From the replay: the organize flow completed in **0.90 s**, then **no `/api/backup/preview`
    request was ever issued**, `#bk-result` was still empty when the assertion gave up 30 s
    later, and `"Checking what to copy…"` - the label `withBusy` sets *before* doing any work -
    **never appears in the trace at all**. So the handler never ran. Not a timeout: raising it
    treats a symptom that does not exist.
  - **What separates the two candidates**, which the final-state snapshot could not. `withBusy`'s
    early return needs `dataset.busy === "1"`, which needs a prior invocation still in flight on
    that same button. The trace's action list shows this is the **first and only** click on
    `#bk-preview` in the test, and `dataset.busy` is written in exactly one place (`app.js:888`).
    So the early return was unreachable, and `!button` is ruled out by the element being static
    markup that Playwright successfully clicked. **A lost click is the only survivor** - and the
    product-side silence candidate is therefore *not* implicated here, though `withBusy`'s
    write-nothing-say-nothing return is still worth its own look on its own merits.
  - ⚠ **The proposed fix above is CONTRADICTED by the tree and must not be applied on faith.**
    `test_backups_on_the_pattern.py` already does exactly it - both hint waits, at its own site -
    and records that it was *not* enough: *"waiting on the hints, on networkidle, and on both
    together all still lose the race"*, which is why that one site uses `dispatch_event`. Either
    that note or this proposal is wrong, and nothing here establishes which. Whoever takes this
    reconciles those two records **first**; a settle-wait added to the other four sites on the
    strength of this entry alone would be a guess wearing a citation.
  - **Not reproducible locally**: 15 runs of the test alone and 5 of the whole file, 0 failures.
    It wants a loaded runner, so the trace is the evidence and CI artifacts expire - the numbers
    above are copied here for that reason.
  - ✅ **RECURRED 2026-08-09, run `31315728976`, and the signature is identical.** Recorded from
    that run's trace before the artifact expired: **zero `/api/backup/preview` entries** in
    `trace.network`, and `"Checking what to copy…"` absent from the trace entirely. Third
    failure now, all on CI, still nothing locally.
  - **Ruled out as the cause: the decisions trigger landed in the same push** (`befcccf`), which
    changed how every app catalog is opened. It cannot be this. **The label `withBusy` sets
    before any request never appeared**, so the handler never ran and nothing left the browser -
    server-side code cannot suppress a fetch that was never issued. Written down because "the
    flake started failing right after your change" is the first thing anyone will think, and the
    trace answers it rather than the timing.
  - ✅ **RECURRED 2026-08-10, run `31364810632` - FOURTH failure, identical signature.** Zero
    `/api/backup/preview` entries in `trace.network`; `"Checking what to copy…"` absent from the
    trace entirely. Ruled out first, because the same push changed `service/backup.py` for
    `(abu)`: the click never left the browser, so server code cannot be implicated - and the
    failing test is a **preview**, which never reaches `_copy_or_raise` (called only from
    `backup_run`).
  - ✅ **THE CONTRADICTION IS RECONCILED, and the two records were never in conflict.** They
    describe different waits at different moments:
    - `test_backups_on_the_pattern._open` waits for the SCREEN to settle after switching -
      `#drives-list *` then `networkidle` - because *"`loadDrives` and `loadCustody` run together
      and both rewrite the screen"*. Its later note, that hint waits and networkidle *"all still
      lose the race"*, is about the **path-validation** race at its own click site, AFTER it has
      already settled the screen.
    - `test_busy_state`'s failing test settles **nothing**. It switches screen and immediately
      fills and clicks, while the two loads that rewrite that screen are still in flight.
    So one record is "a residual race after settling" and the other is a test that never settles.
    The proposed hint-wait was rightly refused; the missing wait was a different one.
  - **RULED OUT ALONG THE WAY**, so the next reader does not re-walk it: the handler is attached
    once at module level (`app.js:3140`), so it is never absent when the button is clickable;
    `#bk-preview` is static markup and only its SIBLING `#bk-result` is rewritten, so the node is
    never replaced; and neither `guarded` nor `withBusy` can swallow a first click.
  - ⚠ **FIXED AT ONE SITE OF FOUR, and that is the `(aak)` shape this entry already names.**
    `e2e_support.open_backups` now does the settle, and only `test_busy_state` uses it. The other
    three - `test_golden_path:57` and `test_ui_regressions:60,:645` - switch to this screen and
    act immediately too. They were **not** changed blind: their fixtures may render a drives list
    with no children, where `wait_for_selector("#drives-list *")` would hang for 15 s and fail a
    passing test. Closing them needs a settle that tolerates the empty case, which is its own
    small piece of work.
  - **VERIFICATION IS CI, NOT LOCAL, and passing locally means nothing here.** This entry already
    records 15 local runs of the test alone and 5 of the file with 0 failures; 5 more after the
    change also passed. It wants a loaded runner, so green CI runs are the only evidence that
    counts.
  - 🔢 **WHAT WOULD COUNT AS EVIDENCE, written down so nobody calls it fixed on the second green.**
    At the observed rate of roughly **one failure in three runs**, an unfixed flake survives N
    consecutive green runs with probability `(2/3)^N`:

    | consecutive green e2e runs | chance an UNFIXED flake produced them |
    |---|---|
    | 2 | 44% - proves nothing |
    | 4 | 20% |
    | **8** | **4% - the minimum bar** |
    | **12** | **1% - call it fixed** |

    **Do not close this before 8, and prefer 12.** Two greens is the number that will feel
    convincing and is worth 44% odds of being wrong. The denominator is approximate - the
    failures are known (four), the total e2e runs in the window are not counted precisely - so
    treat 1-in-3 as the rate this entry has always assumed rather than as a measurement.
  - **And a green run does not clear the other three sites**, which still act without settling.
    Only `test_busy_state` changed, so any of the others firing is the same defect at a site that
    was never fixed - not a regression of this one.

- **(acq) "PLACE" MEANS "SOMEWHERE TRUESTILL ORGANIZED INTO", NOT "SOMEWHERE A COPY IS KEPT" -
  and custody counts it as the latter.** Recorded 2026-08-10 while verifying `(abg)`'s premises.
  A separate defect from a stale number: `(abg)` is about a count that was true once, this is
  about a count that was **never** the thing its word implies.
  - **What the code does.** `service/organize.py:902-906` registers the **destination as a drive
    on every organize run**, and `_identity_for` (`organize.py:829`) mints a marker for *any*
    directory - there is no removable-media test, and none would be right, since a backup drive
    is just a folder. In **in-place mode the destination IS the source**
    (`_effective_destination_for_mode`, `organize.py:602`), so the source folder itself becomes a
    drive with a `file_copies` row per file.
  - **The consequence a user reads.** After a plain organize with no backup at all,
    `places = 1` - and the panel says *"Kept in 1 place"*. True, and useless: the one place is the
    folder they just organized into, on the disk they were already using. Organize a second
    folder and it can read **"2 places" for two folders on one disk that dies together**, which is
    the opposite of what 3-2-1 means and the opposite of what the sentence promises.
  - ⚠ **This also corrects a premise in `(abg)`.** That entry says the folder a user is about to
    empty *"was never counted"*, on the grounds that a source has no `drive_uuid`. That holds for
    copy mode and **fails for in-place**, where source and destination are the same path and it is
    registered like any other drive.
  - **Three candidate fixes, and the entry is open because they are not equivalent:**
    - **The word.** Stop saying "places" for drives and say what it is - *"organized into 1
      folder"* - reserving custody language for copies that are somewhere else. Cheapest, changes
      no counting, and may be the whole fix.
    - **The registration.** Do not register a destination as a drive unless it is distinguishable
      from the library itself. Attractive and probably wrong: it would break the attach/verify
      path that legitimately treats the library as a drive, and there is no reliable test for
      "different disk" that survives a bind mount or a symlink.
    - **The count.** Exclude same-device places from custody arithmetic. Honest, but `st_dev` is
      not a durable identity (`(xx)` already records absolute paths and device ids as
      non-portable), so it would be right on this machine and wrong after a move.
  - **Do not fix this by renaming the drive.** `(abg)` already records the general form: a
    cosmetic fix on a wrong number is worse than the wrong number, because it looks handled.
  - ✅ **Stage A built 2026-08-10, and it is none of the three candidates above.** The fix was
    already in the payload: the panel renders `held_floor` - the copy count of the **weakest
    file** - instead of `places`. This is not a new rule, it is a stated rule the panel was
    violating; `service/drives.py:632-634` already says `places` *"must never be the number a
    sentence about files is written against."* On the maintainer's catalog: **3 -> 1**, which is
    what the rail's custody strip had been saying all along. No schema change, no backfill.
    - **What ruled out "the registration"** - the candidate that looked most principled - is
      **not** the attach/verify path guessed at above. It is `decisions.py:953-955`:
      `drives = catalog.registered_drives(); if not drives: return ()`. Un-registering the
      destination would leave a single-folder user's trip names, event names and settings
      **written nowhere outside the catalog**. A data-durability regression, found only by
      searching every caller.
    - **The cry-wolf case is safe by construction, not by care:** `held_floor` is the per-file
      minimum, so it cannot fall while a real second copy exists.
    - **Two folders on one disk still count as two.** Nothing here knows about hardware, and
      nothing can: `local.py:164` already rules that `st_dev` can agree across subvolumes and
      bind mounts, and the converse is worse - two partitions of one physical disk differ in
      `st_dev` and die together. The claim is per-FILE and makes no hardware promise.
  - ✅ **Stage B, the wording, built 2026-08-10.** The label is **"In at least"**, the
    maintainer's choice: `held_floor` is a FLOOR, and "Kept in 1 place" states a floor as an
    exact quantity - false for every file that has more. Same number, saying what it guarantees.
  - ✅ **Stage C, the contract, amended 2026-08-10.** §3.1's marker-creation row said registering
    is what makes a folder *"countable toward 3-2-1"* - the binding contract asserting the exact
    equivalence `(acq)` disproves. **The contract was wrong, not the code**: registration is
    necessary for a copy to be counted and never sufficient for it to count as redundancy.
    Searched every doc and source file for the same equivalence stated elsewhere; it appears once.
    `drives.py:169` and both CLI sites state necessity or make per-file claims, and are true.
  - ⚠ **THE CLASS DOES NOT LIVE IN ONE LAYER, and it came back three days later from the other
    side.** Stages A-C took a per-drive count out of a per-file sentence - a defect in the
    **query**. On 2026-08-10 the same sentence was found understating for a second reason
    entirely: `filled` is `Math.min(held_floor, 3)`, a **drawing constant** for a three-glyph pip
    strip, and it was also the number the sentence was written against, so a library with every
    file on four drives read *"every file in 3 places"* while the panel said four. Fixed with
    `172e3e2`; the rule is now §9's *a drawing constant is never the number in a claim*.
    **Understating is still misstating**, and this entry is where the pair belongs: closing the
    query half did not close the class, because the presentation layer can restate the same
    mistake with none of the query's evidence in sight.
  - **Closed.**

- **(acr) A DRIVE'S LABEL IS NOT UNIQUE, AND CUSTODY WARNINGS NAME DRIVES BY LABEL ALONE.**
  Found by the maintainer on screen 2026-08-10, reading `(abg)` Stage 0's own output: the strip
  says *"never checked: Morrowkeep"* and he cannot tell **which** Morrowkeep - a local folder, a
  cloud folder and an external disk may all carry that name.
  - **Not enforced, and not unique by accident either.** `drives.label` is `TEXT NOT NULL` with
    **no UNIQUE constraint and no unique index** (`catalog.py:133-140`). Three drives labelled
    `Morrowkeep` insert cleanly - checked, not assumed.
  - ⚠ **Collisions are LIKELY, not merely possible, because the label DEFAULTS TO THE FOLDER
    NAME.** Three of the four registration sites do `label=path.name or "Library"`
    (`service/drives.py:310`, `service/organize.py:847`, `cli.py:2010`); only `drives --init`
    takes a typed one. Two folders called `Backup` on two disks become two drives called
    `Backup`, and any unnamed root falls back to the literal string `Library`, which collides
    with itself.
  - **Why it is sharper on a custody warning than anywhere else.** A wrong pointer sends someone
    to check a drive that is fine; they find their files, conclude nothing is wrong, and stop
    looking. **A confident wrong pointer is worse than no pointer** - it does not merely fail to
    help, it actively ends the search.
  - **What is available to disambiguate, per drive, and it is uneven:**
    - `uuid` - always present, and **unusable to a human**. Never show it as the answer.
    - the path hint (`settings['path_hint.drive.<uuid>']`) - usable, and **not always there**:
      of the three drives in the maintainer's catalog, `The Memory Cabinet` has **no hint at all**.
    - `last_seen`, `first_seen`, `file_count`, `size` - present, but none identifies a place.
  - **The smallest honest disambiguation, argued rather than chosen:** show the path **only when
    the label is ambiguous among the drives being named** - always showing it is noise on the
    common case where names are distinct - and when there is no hint, **say that** rather than
    pointing at nothing: *"Truestill does not know where this one is"* is honest and actionable
    (it tells the user to plug it in and let it be seen), where silence is not.
  - **The deeper fix may be upstream and is the real argument for filing this separately.** The
    surface is not where the defect is: labels collide because registration mints them from
    folder names. Options are to stop defaulting to the folder name, to disambiguate at
    registration, or to enforce uniqueness in the schema - all of which touch every surface that
    names a drive (`status`, `where`, the drive cards, stats), not one sentence.
  - ✅ **Stage 1 built 2026-08-10: `drive.distinguishing_names`, core only, nothing user-visible.**
    A name per drive, disambiguated **only** where the label collides within the set being named.
    **The invariant is not that labels are unique - it is that Truestill never names a drive
    ambiguously**, which is a property of the moment of naming, where the set is known, and cannot
    be established at registration, where it is not. That dissolves the registration-or-display
    question: it is neither surface nor schema, it is one function every namer calls.
    - **A prior ruling honoured, not a new one invented.** `ghost_drive_at` already decided that
      matching a label against a directory name is *"a coin toss, because `create_marker` defaults
      the label to that same directory name and every second `Backup` folder would be refused."*
      This project met label collisions before and concluded that treating one as an error refuses
      legitimate drives.
    - **Nothing is renamed and no schema changed.** A label lives in the marker on the user's own
      disk, so renaming would mean writing to their drive to fix our bookkeeping - the copy-only
      instinct applied to metadata.
    - **`file_count`, `size` and `first_seen` are refused as discriminators**, and the reasoning is
      in the docstring because they will look tempting to whoever extends this: they discriminate
      but do not locate, and answering *where is it* with *how big is it* is a change of subject
      dressed as an answer.
    - **No detail-level parameter.** An unused seam built for an undecided feature is a guess with
      a type signature; `(acs)` adds it in one line when it is ruled on.
    - The `Library` fallback that collides with itself is filed as `(act)`, not fixed here.
  - ✅ **Stage 2 built 2026-08-10: wired into `custody_freshness`, and it reached BOTH surfaces
    without a line of JavaScript.** `app.js:1441` (panel) and `app.js:1540` (rail) render the same
    `never_checked_drives` field, so one payload edit fixes both - proved by a browser test that
    asserts the string on each, and by a mutant removing the panel's row which kills it. `app.js`
    has **no diff**.
    - ⚠ **Two callers, not one.** The plan said one; `cli.py` `status` calls `custody_freshness`
      too, so the CLI's *"Never checked: ..."* line gets the same naming without asking for it -
      which is §9's one-home rule paying out rather than a coincidence.
    - **A collision is a property of what the USER owns, not of the sentence**, and this closes a
      hole the plan's own wording would have left. `library_status` filters to drives holding
      copies; judging collisions among those alone would print a bare `Morrowkeep` when a second
      `Morrowkeep` holds nothing. `custody_freshness` now takes the registered set separately -
      same rows, no extra query.
    - ⚠ **What the real catalog did and did NOT show.** Its three drives have **no colliding
      label**, so the run confirmed only the **guard**: output byte-identical, `['Morrowkeep']`,
      bare, on the app and the CLI alike. `The Memory Cabinet` has no hint - the unplaceable
      *condition* is live - but with no collision its hint is never read and it is never
      qualified. **The collision case and the unplaceable-and-colliding case exist today only in
      fixtures**, and the real-catalog run must not be read as evidence for them.
  - ⚠ **`(abg)` Stage 1 inherits this and must not deepen it.** The resting panel will name drives
    in a NEW place, so the ambiguous name gains a third surface. That is recorded rather than
    fixed there: a per-surface repair would be one fix per surface and would leave registration
    still minting collisions.

- **(acs) THE DRIVE CARD ALREADY SHOWS THE FULL PATH. THIS IS A REVIEW OF WHAT IS EXPOSED, NOT A
  FEATURE WITH A TOGGLE.** Recorded 2026-08-10, and the framing is the finding: the question
  looked like *"should custody warnings say where a drive is, and should that be hideable?"* It is
  not. **`app.js:2510` already renders every drive's absolute path as a clickable link, with the
  path repeated in `title`, unconditionally.** The sensitive data is on screen today. So the work
  is to decide what should have been shown all along and to whom - not to add locations to the
  strip and then offer to hide them.
  - **The need, in the maintainer's words:** he wants to know **where** a drive is, and wants a way
    to hide **the provider's name and the path** - for screenshots and over-the-shoulder viewing -
    **while keeping the folder name**. Both halves are real: a warning naming only `Morrowkeep` is
    a riddle, and a warning naming the service he pays for is a disclosure.
  - **Where a drive names itself, today:** the drive card (label **+ full path**, `app.js:2510`)
    and `drives --init` (label + path) show a location; the custody strip, the resting panel,
    `status`, `verify`, `where` and the decisions notice show **label only**. **A setting reaching
    some and not others is worse than none** - a user who hides the path on the card and then
    reads a bare label in the strip has been told nothing, twice.
  - ⚠ **Location is not in the marker, by design.** `DriveMarker` is `{uuid, label, created}` -
    checked against the real file on disk. So a drive's whereabouts exists **only** as the
    settings key `path_hint.drive.<uuid>`, and **one of the three drives in the real catalog
    (`The Memory Cabinet`) has none at all**. Any design must answer for a drive that cannot say
    where it is.
  - 🚫 **THE "KIND OF PLACE" MIDDLE IS NOT AVAILABLE, and this is a measurement rather than a
    reservation.** The attractive compromise - say *external drive / cloud / this computer* and
    name neither vendor nor path - has no honest source today. `facts_for` is the only candidate
    and it fails three ways: it needs the path **reachable**, so it is blind exactly when the
    warning fires; it returns `None` on **macOS** entirely, by deliberate refusal to guess; and
    worst, **it does not fail silently**. It falls back to `_nearest_existing()`, so measured on
    the real unreachable cloud path it returns **`ext4`** - the filesystem of `/home`. **A kind
    derived from it would tell the user their cloud drive is on this computer, and would be wrong
    precisely when it mattered.** A reassuring-direction failure is the worst thing to build into
    a privacy feature, and it is why the middle is unavailable rather than merely imperfect.
  - **The version that could work, named as what it is:** derive the kind **at registration**,
    when the place is reachable, and store it. That is a **schema change and a migration**, not a
    display option, and **every existing drive would read `unknown`** on day one. Worth doing only
    if the kind is judged to carry its own weight.
  - **Precedent, and it is this repo's own instinct** (`decisions.py:53-55`): `path_hint.` is
    excluded from the decisions document because it holds *"an absolute local path - a username, a
    folder layout, and in one real library the existence of a Vault"*, on a file that
    *"lands on a drive the user may lend or sell"*. The same reasoning applies to a screenshot.
  - ✅ **THE INVARIANT, whatever the design:**
    > **Hiding may reduce detail. It may never reduce the count, the drive's identity as a
    > distinct thing, or the fact that something is unverified.** A privacy setting may turn
    > *"never checked: Morrowkeep at /home/…"* into *"never checked: 1 drive"* - but never into
    > silence, and never into a number that omits it.

    The earlier phrasing - *never whether a problem is stated* - has a hole: it permits stating
    the problem while dropping the drive, which on a **label collision (`(acr)`)** collapses two
    distinct drives into one warning. **Identity preserved**, not merely *problem stated*.
  - **Related:** `(acr)` labels are not unique and are minted from folder names; `(abg)` is the
    custody claim this would qualify.
  - ✅ **BUILT 2026-08-10, narrowed by the maintainer to the concern that actually exists:** nobody
    glancing at the app should learn which cloud service he uses. Not a demo mode, not redaction,
    **and not a setting** - there is no state to store, so there is nothing to configure.
    - **The rule, which answers both directions:** *a path is shown unasked only when it is doing
      identity work.* The drive card's path is now behind `<details class="more inline">`,
      collapsed by default and **expanded where two drives share a label** - because two cards
      both titled `Morrowkeep` are told apart by nothing else, and collapsing there would collapse
      two drives into one indistinguishable card, which is exactly what the invariant above
      forbids. The same rule the panel obeys when `(acr)` writes *"Morrowkeep at /mnt/photos"*.
    - ⚠ **It defends against a glance and a screenshot, NOT against inspection.** `data-open` and
      `data-path` still carry the path because the Open and *Check now* buttons take it. Making it
      inspection-proof means those buttons take a uuid the server resolves - a real change, not
      needed for this concern and not made. The tests assert on rendered **text**, never on the
      attribute's absence, so they describe the protection that actually exists.
    - **The mechanism was reused, not invented:** `<details class="more">` already appears three
      times (`app.js:530`, `:732`, `:764`), which brings keyboard and touch support for free.
      Hover was never viable - it does not exist on touch, and `title` is hover-only. It gained an
      `inline` modifier because `details.more` is a section break with a border-top meant for a
      card's foot, and unmodified it drew a rule through the middle of the card; a privacy fix is
      not the place to smuggle in a design change. Measured by a test, per the `<fieldset>`
      precedent.
    - ⚠ **A correction to this entry as filed:** it said the drive card repeats the path in
      `title`. It does not - `title` is the literal *"Open in file manager"*. The path-in-`title`
      is a **different site**, the rail's catalog path (`app.js:1525`), and the entry conflated
      them.
    - **Everything else that prints a path, from a search rather than assumption, and deliberately
      left alone:** the rail's catalog path (`app.js:1525`, on every screen) names no provider and
      is the one path a user needs to quote when something is wrong; the prefilled fields
      `org-dest`, `ev-source`, `bk-source`, `verify-path` and **`bk-target`** (`:1479-1483`) are
      **latent, not live** - both hints are `None` on the real catalog - and `bk-target` is where a
      cloud path would appear, so the maintainer ruled to wait until it is visible on the screen he
      opens daily rather than guess now. `truestill drives` prints no path at all; the CLI's other
      commands echo the path just typed on the command line, which reveals nothing a
      shoulder-surfer did not watch being typed.

- **(acf) Stage 1 of the readiness signal: the suite depends on it - BUILT 2026-08-10.**
  The two entry points (`open_app`, `open_screen` in `e2e_support.py`), the `ui` fixture waiting
  after `goto`, `open_backups` reduced to a wrapper with its reasoning corrected, and the six
  direct `goto` sites. Stage 0 (the mechanism and its proof) shipped in `af782a0`.
  - ✅ **Gated on a differential, not a run count, and the maintainer changed the gate to that
    after the reasoning was laid out.** The count originally proposed here (5 green e2e runs) was
    kept only as **smoke-aging: reported, not gating**. Why, in one line: a flake fails
    intermittently so repetition is evidence; a signal that lies produces green runs, so
    repetition certifies the very state it is meant to test. Recorded as `ENGINEERING_STANDARD.md`
    §4's twenty-fifth member.
  - ✅ **The differential, run before the rest of the file was converted.** With `loadLayout`
    broken so it never resolves: the converted test **failed**, and the same test in its old form
    **passed**. That pair is the whole proof - it separates a real dependency from a decorative
    one, which no green run can do.
  - ⚠ **Measured, and it qualifies the change rather than selling it:** removing the wait from
    `open_screen` leaves its 37 tests green, and removing it from the `ui` fixture leaves **all
    407** green. No test's outcome rests on these waits today; they are insurance against a class
    of race, and they cost nothing measurable. Anyone reading a green lane as proof this works
    has read the wrong thing - the differential is the proof.
  - **Stage 2 - BUILT 2026-08-10.** A ratchet on screen switches, plus the 8 live races closed by
    screen. **Its honest yield was 8 sites out of 68**: 23 were legitimately bare (12 to screens
    that fetch nothing, 11 acting only above what their screen writes) and were deliberately never
    converted, and 18 already carried an ad-hoc wait. The guard encodes the position rule rather
    than banning bare switches, so those 23 never enter an allowlist and the allowlist reached 0.
  - ✅ **Stage 3 (the 63 fixed sleeps) is CLOSED, not abandoned, and closed on measurement.**
    Three independent results this week say these waits change no test's outcome today: removing
    the wait from `open_screen` left its 37 green, removing it from the `ui` fixture left all 407
    green, and Stage 2 - the same class of fix - yielded 8 real sites from 68. Converting 63
    sleeps across 19 files would touch nineteen files to fix nothing currently broken, which is
    the sweep the staging existed to avoid, and its yield could not be named in advance.
    **The telemetry is now the instrument** (`scripts/flake_report.py`): letting a specific sleep
    fail and be recorded is evidence, whereas converting 63 on principle spends it. What replaces
    the stage:
    - the "sleep guarding a read of an element a screen load writes" kind folds into whatever
      commit next touches those files - `test_large_viewports.py:201` was one, and removing it
      was a genuine fix. The ratchet already refuses new ones, so this shrinks without a campaign.
    - the rAF / resize / EventSource / post-paint kind is left alone until a specific sleep
      actually fails. Some have **no becomes-true anchor available** and may legitimately stay.
  - **Stage 4** (the ~39 raw one-shot reads and their ratchet) is unbuilt and still open on its
    own merits - it is a different failure mode from the sleeps: a read that never waited at all,
    rather than one that waited by the clock.
  - One screen switch in `test_busy_state.py` was converted during Stage 1 because it was the
    differential's subject.

- **(n) "How your dates were determined" honesty stat - BUILT 2026-07-31.**
  **Part of the date-provenance program, and that program is complete.** Step numbers are
  deliberately not repeated here: this entry and `BACKLOG.md`'s **Converged programs** block
  used to number the same program differently, so a reader of this entry alone could not tell
  how much of it had landed. That block is the single place the program is numbered end to end -
  check it before touching any part of this, and do not build this alone.
  - **Built:** the durable provenance column (`files.date_source`, schema **v13**, plus
    `date_tag` at **v14**), `Catalog.stats_date_provenance`, and the honesty view itself, live
    in the app at `service/stats.py` (`_date_provenance`). `date_explain.py` is the single place
    a tier becomes a sentence, including the calm **NOT_RECORDED** wording for libraries
    organized before v13 - which on the maintainer's own 2,300-row catalog is **every row**.
  - **The drill-down shipped in step 5** (`Catalog.files_in_date_tier`,
    `stats.date_tier_files`, `GET /api/dates/files`): each tier opens to the files in it, every
    row carrying the sha256 the rescue action is keyed on. That answers the walkthrough finding
    below - a bare count with no way in - for the **files** and not only the **mix**.
  - ⚠ **This entry read as unstarted until 2026-07-31**, after the column, migrations and view
    had all shipped, and then read as *partly* built for one more day after the drill-down
    landed. A cold start would have rebuilt `date_source` from scratch. That is the inverse of
    `(bb)`'s optimistic marking and the more expensive direction of the two - and it recurred
    twice in one program, which is why status now lives on the entry and the entry lives in the
    section matching it.

  The original description, kept because the requirement it states is still the target: a
  per-run/library figure in the reports/UI showing the **provenance mix** of capture
  dates - e.g. "82% from embedded EXIF, 11% from filename, 5% from Takeout, 2% Undated" (a
  metadata-accuracy %). truestill already resolves and could persist `date_source` (see the
  metadata-chain §1b.3 schema-v9 note); surfacing it honestly tells a user how much to trust
  their timeline, in truestill's voice.
  - **Validated by the UI-v2 walkthrough:** the organize result's "**N no date → Undated**" line
    confused a first user - a bare count with no way in. It must be **explorable**: click it to see
    *which* files were undated and *why* no date was found (which tags were checked, whether a
    filename date was tried). Same treatment for the provenance mix - each slice drills to its
    files. This is the concrete first slice of (n) to build first post-launch.

- **(ii) Rescue flow for side-bin and undated files - BUILT 2026-07-31 (steps 3 and 5).** Ruled by the
  maintainer from a soak finding, and the finding is the argument: real memories genuinely do sit
  in `Saved/`, `WhatsApp/` and `Undated/` - a photo someone sent you of a day you were there is
  still your memory. **Part of the date-provenance program** (see **Converged programs**) - do
  not build this alone.
  - **Built - the storage half.** `date_confirmations` (schema **v15**), `Catalog.confirm_date`
    (one transaction: the durable row plus the `files` update that makes catalog-driven
    re-render place by the confirmed date) and `Catalog.confirmed_date`. Obligation **O4** is
    tested against every whole-disk operation by name in `test_confirmation_survives.py`:
    migrate-layout, re-layout under a different preset, in-place organize, undo-organize, and a
    re-ingest. The re-ingest case found a real defect - `record_uploaded` reverted a confirmed
    date while the confirmation sat intact beside it - now fixed and pinned.
  - **Built - the surface, in step 5.** `POST /api/dates/confirm`
    (`date_rescue.confirm_file_date`) records the date, refuses a precision the model cannot
    represent rather than rounding it, and answers with the three states a user needs: what the
    library now believes, that the file has not moved, and what the file itself still says.
    Reached from the honesty view's drill-down. **App-only by recorded deferral** - see
    *App-surface deferrals*.
  - So the sentence this entry used to open with - *"today there is no durable way to move one
    onto the timeline"* - is now simply **out of date**, and kept only as the argument that
    produced the item.
  - **The problem, precisely.** A hand-move is *undone by the next whole-disk operation*. The
    catalog still records the old location and the old, untrusted date, so `migrate-layout`
    re-renders the file straight back to the bin it was rescued from. The user's correction is
    not merely forgotten - it is actively reverted, which is worse than not supporting it.
  - **A rescue is a CATALOG event, not a file move.** The user confirms the true capture date
    (and optionally an event); truestill places the file in the timeline itself, through the
    normal seam, and records the date with provenance **`human-confirmed`**. Nobody drags
    anything; the tool does the move because the tool owns the placement.
  - **Human-confirmed provenance outranks machine derivation, permanently.** Every subsequent
    organize, migrate and verify routes the file by the confirmed date. This is the whole
    feature: a rescue that does not survive every future whole-disk operation has not happened.
  - **It fits the existing model rather than bolting on.** `DateSource` already ranks tiers
    (EXIF → Takeout → filename → none/rejected-sentinel); `human-confirmed` becomes the new
    highest tier and the resolver's ordering does the rest. Persisting it needs the date-source
    column that item **(n)** has been waiting on - so (n) and (ii) share a schema step.
  - **Surfaced from the bins and the Undated view**, and it shares (n)'s UI surface: (n) makes
    "why is this undated?" explorable, and this is the action offered once the user is looking
    at the answer. Building either alone builds half a screen.
  - **Research pass before build:** how Google Photos and Immich handle user date edits, and
    specifically their *persistence* semantics - whether a corrected date survives re-scan,
    re-import and library moves, and what they do when embedded metadata later contradicts a
    human edit. That last case is the design's real question: truestill's answer must be that
    the human wins, but the disagreement should be visible rather than silent.
  - ⚠ **Interaction with dedup, to design against:** a rescued file's content hash is unchanged,
    so a re-run must not treat the rescue as a new file *or* re-place it by its old evidence.
    The catalog row is the identity; the rescue edits it.
  - **Sequencing: post-arc.** Priority argued **up** by the soak finding - without it, rescuing
    anything out of a side bin is not merely unsupported but impossible to do durably. **Same
    program as (n) / (bbb) recovery / (kk) GPSDateStamp** - see **Converged programs**.

- **(oo) Long-running actions must show they are running.** Ruled by the maintainer from a soak
  finding, 2026-07-29, same class as the silent-failure gap fixed in `670ab5d` - that one hid
  **errors**, this one hides **work**.
  **Built (2026-07-29).** Core progress through rederive/plan; job-ify of migrate/events/ingest
  preview; server-side per-drive JobManager lock; reusable `withBusy` UI helper (disable for
  the duration, re-enable on success/cancel/error) covering job-ified and sync triggers;
  DriveBusy surfaced as its own message; Playwright e2e for disable/progress/second-click/
  DriveBusy.
  - **The finding.** After "Save names" on a 2,057-photo trip over a cloud mount, the preview
    step (`/api/events/{session}/preview`) took **~3 minutes with zero UI feedback** - no
    spinner, no progress text, no disabled button. The screen looked frozen. A user in that
    position will assume it is broken, click the button again, or force-quit mid-operation -
    the same "did anything happen?" defect the soak test kept surfacing, just on the *work*
    axis instead of the *error* axis.
  - **Root cause, verified in code, not guessed.** Two different mechanisms exist side by side.
    `organize_preview`/`organize_run`/`verify_run`/`backup_run`/`migrate_run`/
    `events_apply_to_disk` all go through `jobs.start(...)` - a background job the client polls
    via `streamJob`/SSE, with a real progress bar (`createProgress`). Everything else is a
    **plain, blocking request/response** with no progress channel at all:
    `backup_preview`, `migrate_preview`, `ingest_preview` (Import), `events_propose` (Find
    trips & events), `events_merge`, `events_split`, `events_apply`, and
    **`events_preview`** - the exact call this finding is about. Nothing about `events_preview`
    is special; it simply happens to be the one that runs long enough (a real `migrate.py`
    plan over 2,057 files on a network mount) to expose that none of this group has ever had a
    busy state.
  - **Requirement (met).** Every action that can exceed ~1s must: (1) show busy state on its own
    trigger the instant it is clicked (disabled/spinner), (2) show a progress or status line
    naming what is happening **and its scale** ("Planning moves for 2,057 photos…", not just
    "Working…"), and (3) refuse a second click while the first run is still in flight.

- **(uu) CORRECTNESS: non-Apple videos with only UTC `CreateDate` are filed as local wall-clock.**
  Ruled by the maintainer from a discovery pass, 2026-07-29. **Built (2026-07-30).** Evidence ladder
  after Apple `CreationDate`: MakerNotes `TimeZone`, GPS UTC proof (wired, unexercised by
  corpus), filename+duration (half-hour grid, unique match, ε=3s). `DateSource.INFERRED_LOCAL`
  + parseable `date_tag`; fallthrough is `CreateDate|not_proven_utc` (treated as local, usually
  correct - not a defect). Never-silent report names file + before/after + offset. Canon
  `MVI_2550.MOV` regression pin stays **14:28:39** via `DateTimeOriginal`. Stills untouched.
  Rung 5 corroboration-only. Mutation tests lock unique-match, duration, half-hour grid, and
  messenger refusal. **Do not blanket-convert** - cameras often write local into CreateDate.
  - **The defect (historical).** Video containers store `CreateDate` in UTC per spec; many
    cameras write local instead. Treating digits as local without evidence mis-dates Android
    clips ~5.5h early (IST soak); near midnight, wrong day/trip folder.
  - **Documented trap - do not walk into it:** EXIF `OffsetTime` is modification time, never
    use it to convert `DateTimeOriginal`.

- **(pp) No in-app undo for a trip/migration apply-to-disk - CLI-only today, and the visible
  in-app "undo" is the wrong one.** Ruled by the maintainer from a soak finding, 2026-07-29.
  **Built (2026-07-29).** `GET /api/migrate/undo`, preview/apply jobs through JobManager,
  durable affordance on Trips and Settings (re-queried on load and after every migration),
  reusable `typedConfirm` with the word `undo`, refusals surfaced. Reuses `undo_migration`
  directly - no parallel journal. The `undo-organize` CLI string on the in-place card is a
  different mechanism and is unchanged.
  - **The finding.** `migrate.py`'s reversal (`undo_migration`, keyed on
    `catalog.reversible_migration(drive_uuid)`) exists and works - it is the mechanism behind
    `truestill migrate-layout <path> --undo` (preview) / `--undo --apply` (typed `undo`
    confirm) - but it was wired **only into the CLI** (`cli.py`'s `_cmd_migrate_undo`). Nothing
    in `server.py` exposed it, and nothing in `app.js` linked to it. A user who names trips,
    applies them to disk from the app, and regrets it had no way back inside the app at all.
  - **The mismatch is worse than the absence.** The only "undo" string the app shows for
    in-place organize is still `truestill undo-organize` - a **different** reversal, for a
    **different** operation (`inplace_runs`/`inplace_moves`), sharing no code with
    `migrate.py`'s journal. That CLI hint remains; migration undo is now a separate in-app
    affordance so the two cannot be confused.
  - **Requirement (met).** Preview first, typed confirm `undo`, refuse changed files out loud,
    state plainly that only the most recent migration on a drive is reversible, re-query after
    every migration because supersession has no other signal.

- **(qq) The path on a trip/event completion card's reveal link does not open the folder.**
  Ruled by the maintainer from a soak finding, 2026-07-29, from a live trip apply.
  - **Built.** `migration_apply` joins each `file_copies.relative` ancestor onto the connected
    drive mount before putting it in the reveal `path` field (`_reveal_folder_on_drive`).
    `/api/reveal` then receives an absolute folder under the drive, not a cwd-relative fragment.
  - **Audit (same class):** the only other `data-open` / reveal callers are drive cards
    (`list_drives` path hints - already absolute) and the shared click handler. Find/inventory
    rows show `relative` as display text only, never as a reveal target. No second site.

- **Empty-folder cleanup (provenance: (rr), (zz), (eee) Commit 4).** **Built**
  (`7d9830c` + Commit 4 of `(eee)`). One shared capability across move / in-place organize,
  undo-organize, and trip/migrate apply-to-disk: leftover empty folders are **reported**
  (count + names) and the same preview + typed-confirm `clean-empty` flow is **offered**,
  reusing `emptied_directories` / `plan_cleanup` / `run_cleanup`. Folders are never
  auto-deleted. Do not treat `(rr)` / `(zz)` as separate open work - they closed as this.

- **(ww) Stale absolute path hints after a drive moves.** Ruled by the maintainer from a soak
  finding, 2026-07-30; **fixed 2026-07-30.** `locate_drive` / `path_is_usable_dir` swallow
  ``OSError`` (ENOENT, PermissionError, …) and return the drive-correction payload instead.
  Failed hints are **cleared** (not ignored) so Backups does not re-stat a dead mount every
  load; Check now / open-folder only appear for live paths. Verify soft-fails the same way
  migration already did. Identity remains the marker uuid.
  - Remaining absolute-path / hash-cache portability is **(xx)**, not a re-open of this item.

- **(v) BK-tree for perceptual dedup - CLOSED 2026-08-02 WITHOUT BUILDING IT.** The item asked
  for a tree once `LINEAR_SCAN_ALARM` fired. The alternatives were measured and **the tree
  lost.** Recorded here rather than left open because "not built" and "measured and refused"
  are different states, and only one of them stops someone building it.
  - **The trigger was never a real run, and the first draft of this entry said it was.** `(v)`
    asked to be unblocked *"when that line appears in a real run"*. It has not: the alarm was
    made to fire on a **synthetic** 10,000-hash index, and all three implementations below were
    timed on synthetic corpora. The measurements stand - they are of the algorithms, which do
    not know their inputs are synthetic - but the provenance does not, and this entry claimed
    the stronger one for a day. Corrected here rather than quietly reworded.
  - **What was actually wrong.** `PERFORMANCE.md` §3 asserted the per-comparison cost was
    *"already optimal - a 64-bit XOR and a CPU popcount"*. It was not: the comparison was
    `(int(hex_a, 16) ^ int(hex_b, 16)).bit_count()`, and **each pair re-parsed two hex strings
    into Python integers**. Measured 263-269 ns/pair, flat in n. The XOR and popcount were free;
    the parsing was the whole bill. The algorithm was never the problem, so a better algorithm
    was never the answer.
  - **Measured, all three, same machine and same corpus** (synthetic 64-bit hashes with ~8%
    planted near-duplicate clusters):

    | n | linear, hex strings | **packed uint64 + NumPy** | BK-tree at threshold 5 |
    |---|---|---|---|
    | 10,000 | 13.5 s | **0.1 s** | 3.2 s |
    | 33,457 | 147 s | **0.5 s** | 38.4 s |
    | 150,000 | 2,996 s | **8.9 s** | 794 s |

  - **The number that decides it: the BK-tree prunes only ~85%.** It visits 82.1% / 84.8% / 89.0%
    of the index per query at those three sizes - not log n, and at the unfavourable end of the
    power law that BK-trees are known to follow. **The cause is geometric, not implementational,
    so no better BK-tree exists:** Hamming distances between random 64-bit hashes concentrate
    tightly around 32 (σ≈4), so the triangle-inequality band `[d-5, d+5]` that the tree prunes on
    covers most of the mass at every node. A *wider* threshold makes it worse, never better.
  - **So it lost to vectorisation by 89x at 150,000, for a fraction of the code.** The packed
    match is one array, one XOR, one `np.bitwise_count`; the tree is a data structure with build,
    insert and recursive-query paths to maintain and test.
  - **When a tree would become interesting: millions of images, not hundreds of thousands.** At
    150,000 the packed scan costs ~9 s against per-file stages measured in the thousands of
    seconds - it is not the bottleneck and cannot be made into one by growing a library 5x. The
    superseded design note (BK-tree over Hamming distance; VP-tree more general and buys nothing;
    LSH trades away exactness) is preserved in this entry's history and remains correct *as a
    description of the alternatives* - it was the premise about where the cost lay that was wrong.

- **(aar) A messenger filename beat the camera evidence. Evidence wins now.** Recorded and
  **fixed 2026-08-02**, both the same day: it was filed first so the reasoning existed before the
  change did, then built against that record.
  - **The measurement that produced it.** Three files, one `organize --apply`:

    ```
    2025/2025-08/2025-08 - Everyday/20250801_150500_IMG_4021.jpg    own phone (control)
    WhatsApp/2025/2025-08/20250801_143000_IMG-20250801-WA0001.jpg   document-mode, FULL EXIF
    WhatsApp/Undated/IMG-20250801-WA0002.jpg                        compressed, stripped
    ```

    The middle file carries `Make=Apple`, `Model=iPhone 15 Pro`, real GPS and a real
    `DateTimeOriginal`. **Truestill used that EXIF to name and date it - `20250801_143000`, and
    the run's own summary said `date sources: exif 2` - and then side-binned it on its filename
    anyway.** A file trusted enough to date from its EXIF was not trusted enough to leave the
    messenger bin. The cause was structural, not a tuning error: `categorize` is first-match-wins,
    `rule_filename_convention` sat at position 3 with the signature `(path, _metadata)`, and an
    underscore-prefixed parameter cannot see the evidence even in principle.
  - **The ruling: evidence-first**, made by the maintainer. Genuine camera evidence decides the
    category regardless of how the file arrived. **Accepted consequence, and it is user-visible:**
    a photo someone forwards back to you rejoins the timeline. It is in the CHANGELOG.
  - **Built as a stand-down inside rule 2, NOT as a reordering**, and the difference is the
    reason this entry is worth reading. `rule_filename_convention` returns `None` when
    `capture_device_model` finds a device. Moving the rule below the device rule reaches the same
    answer for this case *and changes every other convention at once* - including handing
    messenger files to `rule_software` the day `(aaq)`'s tag is requested. Deferring changes only
    the files that carry capture evidence.
  - **"Genuine capture evidence" is defined as `Model` (or `SamsungModel`), and the definition is
    shared with the rule it defers to.** `Make` alone, a date alone and a coordinate alone are
    each rejected, for one reason: deferral hands the file to the *rest of the chain*, and
    `rule_device` is the only rule downstream that claims a camera photo. Standing down on
    evidence it cannot use would drop the file past every rule into `Saved` - origin unknown -
    losing the camera reading and the messenger reading together. One function answers for both
    rules so they cannot drift, and a parametrized test asserts the two agree.
  - **Forward-only, verified rather than assumed.** Files already filed under `WhatsApp/` stay
    there, and **`migrate-layout` will not move them**: `WhatsApp` is a deterministic side-bin
    label, so `rederive_rules` never re-reads those files - checked directly, the route comes back
    `side bin`, `needs_decision=False`. That optimisation's premise still holds (only the filename
    rule emits that label), so nothing in `migrate.py` is wrong. But it does mean a pre-existing
    library diverges from what a fresh run would decide, and only a re-import closes the gap.
    **Rescuing already-organized side-bin files is a separate question** and belongs with `(ii)`'s
    rescue flow, not here.
  - **Exactly one existing expectation moved** across 1,345 tests:
    `test_whatsapp_wins_over_camera_exif`, whose docstring asserted the premise being reversed. It
    was rewritten with the reversal and its reason rather than silently updated.

- **(aaa) Typed confirmations crash with raw `EOFError` in non-interactive runs.** Ruled by
  the maintainer from the 2026-07-30 maiden voyage: `organize --in-place --apply` aborted with a
  traceback when stdin was non-interactive (pipe/script/CI).
  - **Built (`f19a45c`).** Shared `_typed_confirmation` catches `EOFError` and exits with a
    clear refusal: interactive confirmation is required. Wired to every typed-confirm site:
    in-place `move`, migrate `move`, migrate-undo `undo`, clean `clean`, permanent
    `delete forever`, reclaim `delete`.

- **(ccc) Plain-language audit of user-facing copy.** Ruled by the maintainer, 2026-07-30.
  - **Built 2026-07-30.** Inventory + rewrites across app/CLI help/README (CHANGELOG excluded).
    Kept `custody` (defined once), kept `catalog` where it names the file, distinguished
    folder pattern vs saved folder pattern, bridged UI "in this same folder" to `--in-place`,
    and rewrote errors as plain sentences that still carry what/why/next without scaffold
    labels. Living-grep guard + allowlist in `test_user_facing_copy.py`.

- **(ddd) Stats view (custody-first).** Ruled by the maintainer, 2026-07-30.
  - **Built 2026-07-30.** New `Stats` screen in the app with three sections:
    Custody (photos/videos/size, 2+/1/0-drive counts, per-drive rollup, never-verified),
    Completeness (undated, timeline-vs-side-bin, near-duplicate flagged), and Shape (by-year,
    by-format, oldest/newest capture).
  - **Performance contract kept:** catalog-only aggregate SQL (`service.library_stats` +
    `Catalog.stats_*`), no file reads, no hashing, no exiftool, no per-file Python loops.
  - **Actionability:** at-risk and never-verified route to Backups; undated routes to Find and
    shows sample paths.
  - **Intentional omission:** exact-duplicate "found" count is not persisted in catalog and is
    omitted here rather than recomputed by a fresh scan; the UI states this plainly.
    **That omission is now its own item, `(aaf)`**, with the reason it is (m)-sized: `Resolution`
    objects die with the job, so there is no row to read later and it needs a new table. Do not
    treat this bullet as the whole story - `(aaf)` carries the market evidence and the open
    design questions.

- **(eee) Three organize modes in the app (copy / move / in-place).** Ruled by the maintainer,
  2026-07-30; CLI modes already proven.
  - **Built 2026-07-30.** App surfaces Copy / Move / Reorganize in this same folder with
    mechanism-aware reversibility before typed confirm; durable `undo-organize` affordance;
    Playwright + mutation coverage. Empty-folder leftovers on these paths are the shared
    **Empty-folder cleanup** capability (provenance `(rr)` / `(zz)` / Commit 4), not a
    separate feature.

- **(fff) Collapsible sidebar.** Ruled by the maintainer, 2026-07-30.
  **Built (2026-07-30).** Hamburger toggle (expanded icon+label / collapsed icon-only rail);
  required hover **and** focus tooltips when collapsed; persist via catalog setting
  `ui.sidebar.collapsed` (no localStorage); compact custody pips-only in the rail; keyboard
  toggle keeps focus; short width transition; Playwright collapse/expand, persistence,
  tooltips, custody bounds, keyboard; each guard broken once then restored.
  - Hamburger toggle: expanded = icon+label; collapsed = icon-only narrow rail.
  - Collapsed **must** show label tooltips on hover **and** focus (not optional polish).
  - Persist via existing catalog settings key/value - **no** localStorage / new store.
  - Custody strip adapts when collapsed: compact indicator only; must not reintroduce path
    overflow in the narrow rail.
  - Keyboard: toggle focusable/operable; collapsing must not trap or lose focus.
  - Short width-transition animation only.
  - Playwright: collapse/expand; persists across reload; tooltips on hover when collapsed;
    custody stays inside rail; keyboard toggle works. Break each, watch fail, restore.

- **(tt) No fast, no-hashing inventory - progressive disclosure is missing.** Ruled by the maintainer
  from a soak finding, 2026-07-29, the natural complement to **(ss)**: a user who only wants
  "how many photos/videos, which formats, how big" has to wait for the full hashing preview to
  get an answer neither dedup nor dating touches.
  - **Built 2026-07-29.** `organizer.inventory_source` + `service.organize_inventory` +
    `POST /api/organize/inventory` return counts by type/extension and total media bytes after
    the walk + one dedicated `stat` pass - no exiftool, no hashing. UI: **Look inside** shows
    that card immediately; **Check for duplicates** is the explicit second step that runs the
    existing full preview job. Size is a dedicated pass (not `compute_hashes._sizes`) so
    inventory stays off the expensive path; profile evidence puts that `stat` at ~0.3 s on
    a cloud mount vs ~231 s for exiftool.
  - **Not the same thing as backlog (r)'s Analyze mode - complementary, likely its precursor.**
    (r)'s Analyze mode explicitly runs "the existing dry-run engine" for a *richer* report
    (duplicates, look-alikes, capture-date range) - it is the same expensive pass as preview,
    with better output, not a cheaper one. (tt) is the tier **before** that.

- **(u) Metadata (exiftool) cache.** **Built 2026-07-29** into the existing
  `hash_cache.HashCache` sidecar (same path+size+mtime_ns key; tag-set fingerprint; force
  re-read via `--refresh-metadata` / app checkbox). Known mtime-without-bump limit documented
  at the cache site. Verify and reclaim still never use it.

- **(aa) Introduce an `Event` value object** (`start`, `slug`, `name`, `id`). **Built
  2026-07-30.** One object replaces the three parallel dicts (`assignments`, `event_ids`,
  `names`) that were the root cause of the audit's F1 (missing names): parallel collections is
  the anti-pattern where each new need adds another array instead of changing the existing
  type. `apply_events`, `execute`, CLI review, and app `commit` all take `dict[str, Event]`;
  a member cannot carry a slug without its id/name slot. Optional `name=None` keeps the slug-
  folder fallback. Golden paths + catalog event rows pinned in `test_event_value_object.py`.
  Day/sub-day distinction respected - `start` is the cluster timestamp, not a calendar day
  (see `(ll)`).
- **(bb) `rule` becomes a `StrEnum`.** **Built 2026-07-30** (input half; output/`Placement`
  half shipped earlier in Stage 2a). `RuleName` enumerates the seven emitters;
  `TIMELINE_RULE = RuleName.DEVICE`; `classify` coerces/`assert_never`-matches on the enum so a
  typo raises instead of silently side-binning. Not a catalog column - no durable string is
  validated against the enum.
- **(cc) Collapse `preview()` into `preview_scheme()`.** **Built 2026-07-30.** Dead
  `preview()` deleted; collision + path-length risk lives once in `_preview_rows`, used by
  `preview_scheme`. Tests retargeted at the shared helper so the rule cannot diverge.
- **(dd) Extract `execute()`'s per-file body into named steps.** **Built 2026-07-30** in two
  commits. Matrix first (`test_execute_matrix.py`): ActionResult sequence + destination tree +
  catalog `files` + `inplace_moves` for exact-dup, near-dup, undated skip, dry-run, in-place
  rename, cross-device fallback, Takeout bake, and cancel mid-run (cancel was **new** coverage).
  Extract Method second: `_write_organized_bytes` -> `_record_organized_file` ->
  `_journal_or_delete_source` under `_execute_one_write`, order bake/write -> catalog ->
  journal/delete unchanged; exception boundary and `baker.close()` unchanged. PLR0912/PLR0915
  suppressions removed (honestly earned); PLR0913 kept (kwargs API).
- **(ee) Move the pin out of `layout.py`.** **Built 2026-07-30.** The catalog-touching trio
  (`pin_existing_layout`, `effective_layout_string`, `resolve_scheme`) now lives in
  `layout_settings.py`, which imports `Catalog` directly. Invented `CatalogLike` Protocol
  retired. `layout.py` stays pure grammar/routing/rendering.
- **(ff) Typed payloads at the app boundary.** **Built 2026-07-30** (six slices). `service.py`
  returns `dict[str, Any]` many times was not theoretical: the `dict(PRESETS)` regression -
  dataclasses about to be serialized into the API - was invisible to mypy precisely because the
  return type was `Any`. Boundary is now TypedDicts mirroring JSON exactly; `-> dict[str, Any]`
  count at the service boundary is zero.
  - **Slice 1 - Built 2026-07-30:** `LayoutState` / preview / set-layout TypedDicts. `presets`
    is `dict[str, str]`; mypy rejects `dict(PRESETS)`. Key-set pins in `test_settings_http`.
  - **Slice 2 - Built 2026-07-30:** organize mode, sidebar, filesystem-relationship leaves.
  - **Slice 3 - Built 2026-07-30:** reveal + `fs_dirs` / `fs_create` / `fs_validate` (optional
    keys preserved, including the resolve-failure shape without `is_drive`).
  - **Slice 4 - Built 2026-07-30:** sync leaves - `organize_inventory`, `clean_empty_*`, `where`,
    `library_stats`, `library_status`, `backup_preview`, plus `list_drives` / `at_risk` element
    types. Shared `MediaBreakdown` helper typed; `_completion` / job summaries deferred (fan-out
    report before typing).
  - **Slice 5 - Built 2026-07-30:** `CompletionBase` (17 keys), `OrganizeDoneSummary` (plus mode /
    mechanism / drive_label / single_copy; `leftover_empty_folders` NotRequired), shared
    `LeftoverEmptyFolders` used by organize + migration apply. `cancelled` is UI-only (commented);
    `elapsed_seconds` NotRequired - jobs.py injects it on dict summaries (documented boundary).
  - **Slice 6 - Built 2026-07-30:** remaining job targets and helpers (`_summarize`, organize
    preview/undo, verify, ingest, backup run, migration preview) typed to zero
    `-> dict[str, Any]` at the service boundary.
- **(aab) Split `dates.py`.** **Built 2026-07-30.** Video ladder + offset grid + `LadderHit`
  moved to `video_utc.py`; inferred-local ``date_tag`` / ``format_offset`` to cycle-free
  `date_provenance.py`. `models._format_offset_hhmm` / `_parse_offset_hhmm` deleted - both
  sides share the provenance module. `dates.py` keeps resolve chain, EXIF/filename parsing,
  and Tier A/B sentinels.

- **(aae) Catalog and cache belong in OS-conventional locations, and are not the same kind of
  data.** Ruled by the maintainer, 2026-07-31.
  - **Built.** `5db91b9` resolved catalog and cache to OS-conventional locations; `5bf98b1`
    added the `truestill catalog` command that says where the catalog lives and moves it on
    request; `42b30d0` made the resolution happen per call and isolated it in tests; `df9bd13`
    narrowed the legacy question to the case where a working directory was actually chosen.
  - **Current state, verified against code 2026-08-01.** `default_catalog_path`
    (`app_paths.py`) resolves **on every call** rather than as a module constant, so an
    override set after import is still honoured and a test can isolate it. The old
    `DEFAULT_CATALOG_PATH` is **gone** - `catalog_startup.py` carries a comment at the site
    saying why it was removed. `TRUESTILL_DATA_DIR` and `TRUESTILL_CACHE_DIR` (`DATA_DIR_ENV`,
    `CACHE_DIR_ENV`) override both roots on every platform, which is what makes the suite
    isolatable by construction rather than by discipline. `LEGACY_CATALOG_PATH` wins when it
    exists and a working directory was genuinely chosen, so an upgrade keeps using the catalog
    the user already has instead of silently opening an empty new one; `standard_catalog_path`
    is where it *belongs*, and `move_catalog_to_standard` (`catalog_move.py`) is the explicit,
    refusing-on-doubt move between the two.
  - ⚠ **AMENDED 2026-08-19: THE LEGACY LOOKUP IS RETIRED, AND THE PROMISE BELOW IS WHY.**
    `(adw)` removed the automatic adoption of `reports/catalog.sqlite`. The entry below is
    **correct and is not rewritten** - it describes what was built and why, and the reasoning was
    right for the case it was written for. What it never did was **state a horizon**: no end date,
    no version, no condition under which the compatibility path would stop. That open-ended
    promise by omission is what `(adw)` closed, and the policy it prompted is `(adz)`.
    `truestill catalog --move` still migrates a legacy catalog; nothing adopts one.
  - **The open questions are answered.** `platformdirs` **is** justified in writing, at the top
    of `app_paths.py`, against the stdlib alternative as `ENGINEERING_STANDARD.md` §4 requires.
    ~~An existing `reports/catalog.sqlite` is **adopted, never orphaned**.~~ **Retired 2026-08-19,
    `(adw)`** - it was adopted against whichever directory the process started in. The filename stayed
    `catalog.sqlite` (`CATALOG_FILENAME`), the enclosing directory now naming the app instead -
    which was the recorded weak point, and the enclosing directory answering it was one of the
    options this entry listed.
  - **`--db` stays the override, traced 2026-08-01 because this entry left it open.** Both
    surfaces take an explicit path ahead of the resolved default: every catalog-touching CLI
    subcommand declares `--db` with `default=default_catalog_path()`, and the app does
    `args.db if explicit_db else default_catalog_path()`. Whether the path was **named** rather
    than **resolved** is carried separately as `explicit_db`, threaded to `inspect_catalog`,
    `create_app` and `library_status`, so the startup announcement can say which of the two
    happened rather than printing a path with no provenance.
  - **The finding that produced it, kept as provenance: two different kinds of data sharing one
    fate.** `catalog.sqlite` is **user data** - the custody record, human-confirmed dates
    (`date_confirmations`), trip names. Losing it is unrecoverable. `catalog.cache.sqlite` is
    **cache** - derived, disposable, and its own module already says "delete this file and
    nothing is lost but time" (~12 s to rebuild). The cross-platform convention separates them
    precisely because their correct treatment differs: `user_data_dir` vs `user_cache_dir` (XDG
    on Linux, `~/Library/Application Support` vs `~/Library/Caches` on macOS, `%APPDATA%` vs
    `%LOCALAPPDATA%` on Windows).
  - **Why it was more than tidiness.**
    - A cache in the OS cache location may be **cleared by the OS or excluded from backups** -
      which is *correct* for a cache and *catastrophic* for a catalog. Sharing a directory meant
      any such policy hit both.
    - **CWD-relative defaults produced the silent-empty-catalog trap.** Announcing the resolved
      path (`catalog_startup.inspect_catalog`) treated the symptom; the cause was that running
      from a different directory silently addressed a different catalog.
    - **(aad) installers make it fatal.** A double-clicked desktop app has no meaningful working
      directory, so a relative default is not merely untidy there - it is undefined.
  - **The cache is ONE file, deliberately, and that does not change.** Not per-folder and not
    per-year. It is keyed by absolute path + size + `mtime_ns`, so a single sidecar serves every
    drive and every run. Scattering cache files through a user's library would make the library
    non-portable and would leave truestill's droppings inside the very folders it promises only
    to organize. Moving the file must not become an excuse to split it.

- **(jj) Archive ingestion - read a library straight out of its archives.**
  **BUILT AND COMPLETE 2026-08-01. Nothing outstanding.** Zip and tar, core through UI, in eight
  commits: the preconditions (`abcd1fb`), the extractor (`346135c`), the pipeline wiring
  (`ca6effc`), tar and `.tgz` (`d330fce`), this record (`c08ed03`), the scope correction
  (`c08eb50`), the `--source` rename (`8dbbb50`) and the UI (`4606713`). Guard rule 8
  (`720b217`) came out of the tar work and is recorded in `ENGINEERING_STANDARD.md`.
  - ⚠ **SCOPE, corrected 2026-08-01: this is NOT a Takeout feature.** It reads any `.zip`,
    `.tar`, `.tgz` or `.tar.gz` from any source - a friend's shared folder, an old backup, a
    phone export, a NAS dump. **Takeout is the motivating case, not the scope**, and the export
    table below shows why: every major photo service hands a user a `.zip`. Every user-facing
    string was audited and reworded; six read as Takeout-specific and no longer do.
    **Two strings survived that audit, corrected 2026-08-06:** the Import screen's own `<h1>`
    ("Import from Google Photos") and the button on the Stats empty state that points at it.
    Prose was not something any gate could read; there is one now - `SERVICE_SCOPED_IMPORT` in
    `test_user_facing_copy.py`, keyed on the shape rather than on this vendor's name.
    **What stays named "Takeout", correctly:** `scan_takeout`, the JSON sidecar matching and the
    `photoTakenTime` parsing are **Google's own format**, and `takeout.py` says so at the top so
    a future sweep does not "fix" a correct name. A second service with its own sidecar format
    would get its own module, not a widened name here.
  - **What shipped.**
    1. *Preconditions, before anything is written* (`archive_set`, `archive_ingest`). Header
       reads only - it does not even create the destination, so declining is free. Numbered
       parts are grouped into one logical set, **gaps are named** (a set missing `-009` would
       otherwise yield a library with a hole in it, silently), and space is checked against the
       destination drive. The size shown is labelled in the user-facing text as **the archives'
       own claim, never a measurement truestill made** - it is a header field whoever built the
       archive chose.
    2. *Extraction* (`archive_extract`). The journal is written and **fsynced before any byte
       exists**, so a crash never leaves files nothing can attribute; recovery is proven against
       a real `SIGKILL` and asserted **from a fresh process**. Entry names are **refused, not
       rewritten**. Files are written to a sibling and renamed, because a truncated JPEG still
       hashes. The byte budget is the *lower* of free space minus a 1 GiB reserve and the claim
       plus 10%, and it aborts on the **real running total** rather than the declared one.
    3. *Pipeline wiring* (`scan_takeout` unchanged - **that it needs no change is the claim, and
       it is asserted**). The multi-part correctness test builds a `Photos from 2014` folder that
       genuinely straddles two parts and proves the sidecar still matches; its cry-wolf
       counterpart proves extracting the parts separately **loses the date**.
    4. *Tar and `.tgz`*, via `tarfile.data_filter` **per member** rather than
       `extractall(filter="data")`, so tar shares the same counter, journal and rename as zip
       instead of forking the extractor.
  - **CLI:** `--source` takes an archive or a directory, and **pointing at one part finds the
    rest**. That is correctness, not convenience: requiring every part would mean forgetting one
    does not fail but *succeeds*, quietly leaving those photos undated.
    `--takeout` remains as a **permanent hidden alias** - it shipped, scripts use it, it costs
    one line and resolves to the same `dest`, so there is no second code path and a removal
    window would break those scripts in exchange for nothing.
  - **REFUSED, with reasons, so they are not proposed again as obvious wins.**
    - **`.7z` is out of scope, and the deciding evidence is demand rather than dependencies**
      (re-examined 2026-08-01 on request, rather than resting on the first refusal).
      **Users do not choose their archive format - the exporter does**, and no major photo
      service emits `.7z`:

      | Service | Export format |
      |---|---|
      | Google Takeout | `.zip` / `.tgz` |
      | Facebook | `.zip` |
      | Flickr | `.zip` |
      | Amazon Photos | `.zip` |
      | Dropbox | `.zip` |
      | iCloud | no archive - individual files |

      So `.7z` is not a format users *receive*; it is one someone might *make* by re-compressing
      by hand. That distinction is what decides it. The dependency argument (`py7zr` is a new
      runtime dependency under §4) still applies and is now the *second* reason rather than the
      only one.
      **Research gap, recorded honestly:** two searches for user voices on whether the
      DataHoarder audience re-compresses photo archives to `.7z` returned vendor and reference
      pages, not people. That question is **unanswered**, and the instrument for it is the soak
      or a direct forum read - not more web search. If it ever turns out to be common, this
      refusal is the one to revisit, and the export table above is not the evidence that would
      settle it.
    - **`.rar` is out of scope for an INDEPENDENT reason that holds whatever the demand.**
      `rarfile` **shells out to an unsigned external `unrar` binary**, and a product whose whole
      proposition is custody should not invoke one on a user's files. This reason survives even
      if `.rar` turned out to be common, which is why it is recorded apart from the demand
      question rather than bundled with it. The honest answer for a user holding a `.rar` is
      "extract it yourself first": one step for them, no attack surface for us.
    - **Archive-inside-archive is refused outright**, naming the entry. Recursive extraction is
      **unbounded depth on untrusted input**, and the Takeout case never needs it.
    - **Delete-staged-files-as-you-go is refused, and deliberately NOT built as an option.**
      It would halve the peak disk requirement, which is exactly why it looks like an obvious
      win. truestill's whole posture is that **it never destroys the user's source**, and an
      option to delete the input is a switch that exists only to be regretted at 3am. If disk
      space is genuinely the blocker, the honest answer is *"extract fewer archives at a time"* -
      a step for the user, and no invariant lost.
  - **The UI shipped in `4606713`** and is not outstanding. Preview-then-confirm in the Rescue
    screen, progress and cancel through the existing job machinery, and the space figure
    labelled in the copy as the archives' own claim.
    **Refusals carry their CODE in the DOM** (`data-refusal="<code>"`), and the browser tests key
    on that rather than on the sentence - five refusals render similar-looking prose, so matching
    words lets a test pass because a *different* refusal fired. That is guard rule 8, and it is
    mutation-proved: dropping the codes fails the same three tests as ignoring the refusal
    entirely, so the provenance assertion is load-bearing rather than decoration.
    Eight Playwright tests drive the flows rather than asserting about them, per
    `ENGINEERING_STANDARD.md` §2, and the seven HTTP tests cover the two API routes that were
    briefly untested.
  - **Original design notes below, kept for the reasoning that produced the above.** Three of
    them were **overtaken by what was built** and say so inline, rather than being left as a
    second, contradictory answer in the same entry.
  - Near-launch priority: it is central to the Takeout-rescue pitch, because what a refugee
    actually has is a pile of archives, not an extracted folder. Generalized from the older
    "zip-direct Takeout" note, which was too narrow - the problem is archives, not Google's.
  - **One archive-source interface**, so the pipeline sees a source of media and does not care
    what it came out of. The same shape `Destination` already demonstrates, at the other end.
  - ⚠ **SUPERSEDED - `.7z` was to be first-class via a pip package.** It is not: see the refusal
    above. A pip package is still a **new runtime dependency** under §4, and the format is not on
    the path this feature exists for - Google offers `.zip` and `.tgz`.
  - ⚠ **SUPERSEDED - `.rar` was to be optional, lighting up when `unrar` is present.** Refused
    above instead. "Optional" understated the cost: `rarfile` **shells out to an unsigned
    external binary**, and a product selling custody should not invoke one on the user's files.
    The honest-about-absence instinct in the original note is right and survives - it is now
    applied to the *refusal* (name the format, say to extract it first) rather than to a
    degraded mode.
  - ⚠ **A multi-part set is ONE archive.** Google splits an export across `takeout-001.zip`,
    `-002.zip` and so on, and **a photo and its JSON sidecar can land in different parts**.
    Treating the parts independently silently breaks date rescue for exactly the files this
    feature exists to rescue. The set is opened as a unit or not at all.
  - ⚠ **SUPERSEDED - "streamed extraction, never a full unpack".** Extraction to disk was ruled
    2026-08-01 and is **forced, not chosen**: exiftool is a subprocess that needs a real file,
    and hashing, EXIF reading and copying all assume one, so a pure stream cannot feed the
    pipeline. The design question was never *whether* to extract but *where and with what
    protections*.
    The cost this bullet was worried about is real and is answered rather than dodged: staging
    goes on the **destination drive** (not the system temp dir, which on many machines is a
    tmpfs), the space precondition states the requirement **before** any work starts, and the
    only way to halve the peak - deleting staged files as you go - is **refused above**. The
    honest mitigation for a user short of space is to extract fewer archives at a time.
    What did survive from this bullet is *streaming within* extraction: entries are read in
    fixed chunks through a running byte counter, never whole into memory.
  - **Copy-only, as everywhere else: an archive is never modified**, never deleted, never
    rewritten in place. It is a read-only source.
  - **Encrypted archives are detected and surfaced**, never silently skipped. "I could not read
    this, here is why" is the never-silent rule applied to a container.


**Not doing, and why:** the audit found no inheritance-for-reuse and no deep hierarchies
anywhere (the only inheritance is `Destination` -> `Local`/`Rclone`, a genuine is-a), so there is
no composition refactor to schedule.

- **(ack) A RESTORE GAVE THE FIRST TRIP EVERY OTHER TRIP'S DAYS - FIXED 2026-08-09**, in the
  same commit as the test that proved it. Found by reading `decisions.py`, **disputed, and then
  demonstrated before anything was changed** - the claim was four inferences deep and plausible
  is not proven.
  - **The defect.** `gather_decisions` wrote `trip_days` as `day -> trips.id`, a rowid local to
    the catalog that minted it, while the trip entries carried no id. The mapping was present in
    the document and **unresolvable by any reader**. `apply_decisions` then handed *every* trip
    the *entire* day set and gated on `days[0]`.
  - **IT CORRUPTED RATHER THAN OMITTED, which is the part that matters.** Two trips in, one trip
    out - holding all four days. Not "Goa was skipped": **Wayanad came back owning Goa's days**,
    so those photos render under the wrong folder. `applied["trips"]` said `1`, and no channel
    said anything else. A missing trip is visible to a user; a trip that absorbed another's days
    is not.
  - **Fixed at the gather, because apply cannot repair what the document discarded.** A trip now
    carries its own `days`. `trip_days.day` is a primary key, so days are disjoint across trips
    and a day list identifies a trip exactly - the same property that makes `events.signature`
    work, which is why events were never affected (proved by a passing two-event test written at
    the same time). The redundant top-level `trip_days` map is gone: two representations of one
    fact can disagree, and the one that would have won is the one that caused this.
  - **Rejected: keying by slug.** `trips.slug` has **no UNIQUE constraint** (checked in the
    schema, not assumed), unlike `events.signature` - two trips may legally share one and the
    mapping would be ambiguous again. No schema change was needed.
  - **A silent skip now has a channel.** `ApplyReport` gained `conflicting_trips` (days already
    claimed by a different trip) and `trips_without_days`, deliberately two single-meaning fields
    rather than one overloaded one - see `(ach)` for the field that got that wrong.
  - **Why it survived: the real catalog holds exactly one trip.** The suite is not naively
    single-instance - `test_catalog_trips.py` creates five - but the decisions fixture was
    modelled on the library and inherited its blind spot. That lesson is now
    `ENGINEERING_STANDARD.md` §4's seventeenth member.
  - **The real catalog also holds zero events and zero date confirmations**, so until this commit
    the restore path had only ever met *seeded* examples of the decisions it exists to protect.
    The round-trip was run against a copy of the real 6.4 MB catalog as part of the fix: two
    trips, 5 settings and 6 skipped clusters out and back identical, 1,353 bytes, no `path_hint`.

## Shipped (kept for provenance)

- **BUILT 2026-08-13: truestill can show a photograph. Organize's result is the photos.**
  No backlog letter - it came out of the UI reconnaissance, whose finding was that the remaining
  gap was not styling: the product had **zero `<img>` elements**. Three pieces:
  `truestill_core/thumbnails.py` (sha256 -> WebP, cached under the OS cache dir),
  `GET /api/thumb/{sha256}`, and the grid in `organizeCompletion`, above the tally.
  - **Addressed by content, never by path**, so traversal is unrepresentable rather than
    defended. `LocalGuard` wraps the whole app and exempts only `/static/`, so the route inherits
    token/Host/Origin; the tile URL carries `?token=` because an `<img>` cannot set a header.
  - **Lazy, not batched** - browsers cap ~6 connections per host on HTTP/1.1. A batch endpoint
    would defeat per-thumbnail HTTP caching, which is what makes a revisit free. `GRID_SAMPLE_LIMIT`
    is 48; the whole-library browse is still `(abk)` and is not a bigger constant here.
  - **Two defects found by building it, both older than it.** `execute` computed the content id
    for a unique-size file the scan skipped, wrote it to the catalog and dropped it - so results
    alone lost about half a run (`ActionResult.sha256` now carries it). And `THUMB_PX` had no
    enforced relationship to the rendered tile, which measured ~100px at every width.
  - Costs, measured over 600 fenced-corpus files rather than sampled: **~23 ms cold** (20 decode,
    3 encode), **0.05 ms warm**, median 13 KB. An earlier 80-file sample said 14 ms and was wrong
    by 2.3x; `docs/PERFORMANCE.md` has the standing numbers.


- **(acw) CLOSED 2026-08-12: the hint spans above `#bk-preview` can no longer move it.**
  - **The root was an unbounded server string in a fixed-width slot, and it is closed as a defect
    on its own terms rather than as a side effect.** `fs_create` interpolated `str(OSError)` -
    which embeds the offending path and has no length limit - into a hint above a button. The
    entry's blocker was exact: *"Reserving is exact only when growth is bounded, and a server
    string is not bounded."* So the string was bounded first (`_ERROR_DETAIL_LIMIT`, 60 chars,
    keeping the **tail** of the path because that is what identifies the folder) and the reserve
    followed.
    - **The bound costs no information:** `error_detail` carries the untruncated failure and the
      caller puts it in `title`. A mutation dropping it kills the cry-wolf test, which is the one
      that matters here - an error truncated into unreadability trades a click-miss for an
      unusable message.
      - **The bullet above claimed more coverage than it had, and the Windows lane said so the
        same day** (CI run 31626239285). That cry-wolf test, and the tail test beside it, asserted
        a planted 180-character name against `str(OSError)` - a property of POSIX error strings,
        not of this code: `Path.mkdir(parents=True)` fails at a different node of its recursion on
        Windows and names only the parent. **The bounding code was correct**; both tests were
        repaired to assert `error_detail == str(exc)` verbatim and `failure.endswith(kept)`, and a
        third now runs the contract against both platforms' recorded strings. Left standing rather
        than rewritten - the record is what was believed then. `ENGINEERING_STANDARD.md` §4,
        thirty-ninth member.
    - **Found while reading it: the client was WRAPPING the server's message in a second one.**
      `"Could not create this folder. " + r.error + " Choose another folder..."`, where `r.error`
      already ends *"Choose another location, or create it in your file manager."* The sentence
      said both things twice and ran ~190 characters before the OS reason was added. That
      duplication was most of the length.
  - **The costed decision, measured rather than asserted, because the obvious fix was wrong.** A
    flat two-line reserve on every hint costs **+112px** on this screen and puts `#bk-preview` at
    **936px against an 800px viewport** - below the fold. That trades a rare click-miss for a
    permanently harder-to-reach control, so it was rejected.
    - Shipped instead: one line globally, and **two lines only under `max-width: 1100px`**, scoped
      to Backups. Whether a hint wraps is a *width* question, so the reserve is priced as one.
    - Final cost **+57px** on Backups (`#bk-preview` 818 -> 875 at 1280), and the worst-case shift
      goes **+36.1px -> +0.0px**.
  - **`.carried` reserved rather than hidden.** It went `display:none` -> a full line plus margin,
    and it is the element the missed click actually landed on. Its height is one line of fixed
    text, so unlike a hint there was nothing to bound first.
  - ✅ **THE WIDTHS WERE THE FINDING.** The entry measured 1280x1600 only. At **820px the same
    shipped strings wrap and the pre-fix shift is +60.9px** - three and a half times the miss
    threshold. A reserve priced at 1280 alone passes there and still misses on a smaller laptop.
    The detector is now parametrized over 1280/1000/820, and dropping the media query leaves the
    first two green and kills only 820 - which is exactly why it is parametrized.
  - The forced case is now a **committed** test. That file's own docstring had explained why it
    was not: *"it is reachable in the product... so it is a live defect filed as `(acw)`, and a
    committed red test is not a detector."* It is reached entirely through product branches -
    `validatePath`'s unreadable-folder message (76 characters against a 68ch cap) and
    `offerBackupPath` unhiding the carried note.
  - **Not closed here, and filed with its number: `(adg)`** - the verify result block moves the
    same button **+92.4px**, which this entry had listed as unmeasured. It cannot be reserved
    (a card listing problems is unbounded) and the only remedy is a reorder refused for `(ada)`'s
    reasons.

- **(acz) CLOSED 2026-08-12: a surviving staged copy is findable again, as its own outcome.**
  - **What was owed, and why it was owed.** `(acj)` made a survivor *safe* - named
    `<target>.partial`, so `_free_relative` never suffixes beside it and `scan_source` can never
    take it for a photo - and in doing so **moved the discovery seam**. `(abu)` was found because
    "rescan reports it as STRAY", true only while the leftover wore a media extension. `rescan` is
    fed `scan_source(...).media`, so a `.partial` stopped reaching it. The entry's own words: a
    user who hit a full disk mid-copy had debris whose only record was a message that scrolled
    past.
  - **The decision the entry left open was where it belongs, and the answer is a FIFTH outcome,
    not a widened STRAY.** Rescan's own definition of a stray already covers "a file no record
    accounts for", so folding it in was available and is wrong: a stray may be a photograph the
    user wants adopted, while this is Truestill's own failed write whose only sane remedy is
    deletion. **One count meaning both would be `ApplyReport.skipped_newer_locally` again** -
    `(ach)`'s lesson, applied at the point where it would otherwise have been repeated.
  - **`debris` deliberately does not affect `reconciled`.** That property drives the CLI's exit
    code, and a leftover is not a disagreement between the record and the disk - it is litter
    beside them. Failing a run for it would turn a successful copy into a scripted failure.
    Reported, not failed on; stated at the site and pinned by a test.
  - **A mutation found a test that did not test its own docstring.** The suffix-not-substring case
    was written with `partial-scans.txt`, which contains no `.partial` at all - so the substring
    mutant survived it. Re-fixtured on `notes.partial.bak`, which contains the suffix without
    ending in it *and* lands in `scan.unrecognized` where the filter can see it.
  - Verified on a real drive: a planted survivor beside five organized files is reported at its
    full relative path, does not appear as a stray, and the exit code stays `0`.

- **(acl) CLOSED 2026-08-12: JPEG 2000 reaches the pipeline.** `.jp2`, `.jpf` and `.j2k` added to
  `IMAGE_EXTENSIONS`. Such a file was never handed to exiftool at all - not dated, not
  categorised, not organised, and **silently skipped rather than reported**.
  - **The entry's own precondition was checked first, and it is the reason this waited.**
    Recognition is one answer and *hashing* is another - `format-coverage-audit.md` records RAW
    differing on exactly that. Pillow was confirmed on the real `jpg2000/balloon.jp2`: it opens
    and downsamples it, so perceptual dedup works rather than merely not crashing.
  - Verified end to end on the real files: `balloon.jp2` and `balloon.jpf` now reach exiftool and
    return 6 and 5 tags respectively.

- **(acm) CLOSED 2026-08-12: an AVI carrying its date only in RIFF `DateCreated` is dated by it.**
  - **`(add)` is what unblocked this.** The entry said adopting the tag needed "the resolver to
    accept a dayless-precision source or to say why it will not" - `DateCreated` here is
    `2020:08:28`, date-only. `(add)` taught `parse_exif_datetime` the year-first numeric forms
    earlier the same day, so the precondition was already met.
  - **The rate is per-AVI, not per-file, and that is what earned the tag.** The entry read "one
    file in 1,322". Measured: of the **two** AVIs across both corpora, **one carries this and
    nothing else**. A whole container format was half-failing.
  - **Scoped to `RIFF:`, which the entry demanded and which is load-bearing.** A bare
    `DateCreated` is an IPTC field on stills meaning something else, and the corpora hold
    malformed ones (`2010:00:00`). `-RIFF:DateCreated` returns nothing on a real still that
    carries the IPTC field - verified - while exiftool still keys the result plainly as
    `DateCreated`. A mutation that unscopes it dies.
  - **Last in `DATE_TAGS`, and the position is the rule.** Date-only means midnight, so a file
    carrying both this and a real capture time must keep the time. A mutation that promotes it
    above `CreateDate` dies.
  - **It tripped `test_no_new_exiftool_tag_was_requested`, which is exactly what that test is
    for** - *"that may be right, but it is never incidental"*. The fingerprint was updated
    deliberately with the trade recorded at the site: one cold exiftool pass per library at
    upgrade (~2.2 ms/file, ~5 s on the 2,275-file reference library) against a container format
    that half-fails without it.
  - Verified end to end through the real reader: `100_0306.AVI` resolves to **2020-08-28** where
    it was `Undated/`, and `MVI_4823.AVI` keeps its precise `2012-09-10 20:52`.

- **(abx) CLOSED 2026-08-12: where the library lives is now DECLARED, not inferred from a run
  that already happened.**
  - **The mechanism is worse than the entry recorded, and this is the finding rather than the
    missing question.** `path_hint.library` is written *after* a successful organize
    (`organize.py`) and read through `take_live_path_hint`, whose own docstring says a hint "is
    never identity - only a convenience". So the library's location was **whatever the user
    typed into one field once**, recorded as a side effect. The missing question is the symptom;
    inferring the answer from a run is the cause.
  - **The only guidance the screen offered was a placeholder reading `e.g. /media/BackupA`** - a
    removable drive, which is the one place a library should not live. On a first run it was the
    sole hint about where anything should go. Now a home-library example, with the trade said in
    words in the first-run card.
  - **The design is the declared/observed split**, and `library.root` exists because
    `take_live_path_hint` **clears** a hint whose path is unreachable. Storing a declaration that
    way would make an unplugged library drive erase the answer and **re-arm first run every
    time** - the defect re-created rather than closed. Recorded in `IMPLEMENTATION_STANDARDS.md`
    beside *identity is never a path*, which it completes rather than extends.
    - **Load-bearing test, named so nobody weakens it:**
      `test_the_declared_root_survives_its_path_becoming_unreachable` asserts both halves on one
      vanished path - the declaration stands, the hint beside it is cleared. A mutation that
      reads the declaration through the hint reader kills it and two others.
  - **The gate is "no declaration AND no files", not the declaration alone**, and the second half
    is what keeps this off an existing library: a user who organized before this shipped answered
    the question by doing it. Proved both ways - absent declaration *with* files, and present
    declaration whose path is *gone* while the catalog is empty. Computed server-side so the rule
    has one home; a mutation that re-derives it in the browser kills the cry-wolf test.
  - **A blocking setup wizard was considered and REFUSED**, not overlooked. The app has no such
    pattern, a modal gate would be the first thing sitting outside the `data-ready` readiness
    contract every screen follows, and the PhotoPrism/Immich framing in the entry is recorded
    there as the maintainer's own unverified input. The one-time decision is honoured without
    inventing an architectural shape for it.
  - **Two existing contracts broke and both were repaired rather than weakened**, which is the
    part worth reading:
    - `test_rearrange_sits_directly_under_the_layout_it_answers` - the new Settings card had been
      inserted between `Folder layout` and `Rearrange`, which that test deliberately keeps
      adjacent. Moved to **first** on Settings: where the library is, then how it is laid out,
      then rearranging it. Both that adjacency and *Appearance stays last* hold.
    - `test_the_panel_starts_level_with_the_first_content_card` - it selects
      `.screen.active .card`, and the new first-run card is `.hidden` (`display:none`, a
      zero rect), so it compared the panel against `0` on a layout that was correct. The
      selector now says `:not(.hidden)`; the claim was always about the first card a person can
      **see**.
  - Verified on real material as well as fixtures: an empty catalog is asked; 161 real files
    organized from `Input/2013` and the question never returns.

- **(add) CLOSED 2026-08-12: the uncommon embedded date forms, split three ways as the entry
  said it must be.** 11 of the ~30 readings recovered; the other two groups **refused, each for
  its own stated reason**, which is the ruling rather than a shortfall.
  - **Recovered - numeric and year-first, so no reading is in question.** `20020904` (date-only
    compact), `2011-03-15T10:14:46-04:00` (ISO 8601), `2008.07.10  15:16:55` (dots and a double
    space), `2019:04:24 22:24:00+02:00 DST` (a trailing zone abbreviation), `2011:06:14 15:47+02:00`
    and `2020:01:05 15:04Z` (minute precision), plus `2013:07:04` and `2013/07/04 12:30:45`.
  - **Refused as ambiguous:** `12/29/93` (12 readings), `12/5/95 10:44 PM`, `2/5/14`, `12/09/14`,
    `02-Aug-99`. Reading these needs a US-or-EU choice, which is the wrong-answer class
    `date-resolver-corpus-measurement.md` §3.2 exists to avoid. `/` **is** admitted when the year
    leads, because that is what removes the ambiguity - `12/29/93` cannot match at all.
  - **Refused as locale-dependent, a reason the entry did not have:** `Tue Dec 14 09:54:11 2004`
    (4 readings) and `Monday, September 11, 2000, 2:45:40 PM`. `%a`/`%b` resolve against
    `LC_TIME`, so these parse on an English machine and fail on a French one - **the same file
    landing in a different folder depending on the computer reading it**, which is the failure
    this project exists not to have. Five readings do not buy a hand-rolled English month table.
  - **Built as a pure addition:** the EXIF spelling is still tried first and the new parser is
    reached only when it fails, so **no value that parsed before changes**. Verified: the
    reference library resolves identically (2,271 EXIF / 4 Undated; tier 4 still 1,274 right and
    997 silent) and Testing-new identically (1,530 / 306).
  - The existing sub-second strip could not be reused - it cuts on the first `.` in the whole
    string, which turns `2008.07.10 15:16:55` into `2008`. A mutation that widens it to any `.`
    kills the dot-separated case, which is how that is pinned.
  - **A mutation found a missing test rather than a missing guard.** Making the two patterns one
    with optional separators lets a seven-digit run split as `2002`+`09`+`4`. The source comment
    asserted this could not happen; nothing tested it, so the mutant survived until a test went in.

- **BUILT 2026-08-12: a dead metadata path deleted, and the class given a detector. No letter -
  this is half of `(aaq)`, which stays open in `BACKLOG.md` for its other half.**
  - **The letter stays in the backlog on purpose.** An entry that is genuinely part-done cannot be
    in both files: one letter names one item, and `test_backlog_letters_are_unique` enforces it.
    So the open half keeps `(aaq)` and this entry records the built half without claiming it.
  - **`SamsungModel` deleted rather than enabled.** `rule_device` read
    `_text(metadata, "Model") or _text(metadata, "SamsungModel")`, and the second was never
    present because `SamsungModel` is not in `REQUESTED_TAGS`. Enabling it means requesting the
    tag, which changes `tags_fingerprint` and invalidates **every cached metadata row in every
    library** - for a case with no evidence anywhere available: neither sample corpus holds a
    single file carrying `SamsungCaptureInfo` or `SamsungModel`. The failure direction of not
    having it is the safe one (`Saved`, origin unknown, rather than misfiled), and
    `SamsungCaptureInfo` **is** requested and still serves the screenshot rule.
  - ✅ **THE REAL OUTPUT IS THE DETECTOR, which would have caught both halves at the moment they
    were written.** `test_categorizer_tags_are_requested.py` parses `categorize.py`'s **AST** and
    fails if any tag it reads is absent from `REQUESTED_TAGS`. Nothing else notices this class:
    the rule compiles, its unit tests pass a hand-built dict containing the key, and it simply
    never fires. Two such paths shipped and needed an audit to find.
    - Parsed rather than grepped, and that is not fussiness: the first version scanned raw source
      and matched the literal inside the *comment* explaining the deleted call, reporting a dead
      path that no longer existed. A detector that reads prose can be argued with.
    - `Software` sits in a documented exemption list naming `(aaq)`. **An exemption is the record
      of an open decision, not a licence** - and a second test fails if an exemption names a tag
      nobody reads any more, so deleting the rule must also delete its exemption.
  - ⚠ **STILL OPEN AND EXPLICITLY NOT MINE: what to do with `rule_software`.** Both remaining
    options are product decisions rather than repairs - *reorder below the device rule and
    constrain the label set, then request the tag* launches a folder-per-application rule across
    every library at once (measured: 159 files with a working camera `Model` leave the timeline,
    and 3 folder labels become 97), while *delete* forecloses the "everything I edited in
    Lightroom" case for good. The entry carries both numbers; the choice needs the maintainer.

- **(adc) CLOSED 2026-08-12: a documented clustering invariant was false, and the code was
  right.** Decided and closed on the evidence in the entry; **no production behaviour changed**,
  which is the finding.
  - **What was false.** `events.py`'s `DEFAULT_SENSITIVITY` note claimed "every overnight gap
    exceeds `MIN_BOUNDARY_GAP_S`, so segmentation produces within-day clusters only", and
    `trips.py` built its module docstring on it: "a cluster never spans midnight on real data".
    Of 16 consecutive day-changing pairs in the reference library one is **43.9 minutes**
    (`2014-08-15 23:19:29 -> 2014-08-16 00:03:25`) - below the floor, so it cannot be a boundary
    and the segment straddles the day.
  - **What is true, for a reason the note did not give.** No *emitted* event spans a day on that
    library because the spanning segment holds **4 files against `DEFAULT_MIN_FILES` of 8** - the
    minimum-files filter, not the gap floor. A fifth photo that night ends it.
  - **The ruling: correct the documents, do not touch the clustering.** Forcing a break at midnight
    would split a night photographed across it, which is a real event and not two.
    `trips.detect_trips` already keys off `cluster.start.date()`, so nothing depended on the false
    half - and that start-date rule is now stated as **the rule** rather than as an approximation
    of a stronger one. Its own docstring had flagged the case as "possible in principle,
    unobserved on the real library"; it is now observed, and says so.
  - **The detector, because nothing else would notice.** Reading every date a cluster *touches*
    looks strictly more faithful to the old phrase "a calendar date that produced at least one
    entry in clusters", and would silently start proposing a two-day trip for one party.
    `test_a_cluster_that_spans_midnight_contributes_one_active_day_on_purpose` fails on exactly
    that change. Its fixture deliberately avoids 31 Dec / 1 Jan: the year split would mask the
    mutation there, and the first version of the test proved it by letting the mutant escape.

- **(ade) CLOSED 2026-08-12: the Twitter filename convention claimed any MD5-named JPEG beginning
  with `e`.**
  - `^(?:twitter_|E[A-Za-z0-9_-]{12,}\.jpg$)` compiled `re.IGNORECASE`, so the `E` alternative
    matched a lowercase hex hash - roughly **one hash-named JPEG in sixteen**, which is browser
    saves and some cloud exports. Six real files in the sample corpora. It cost no *date* (those
    names carry none); it filed someone's photo under `Twitter/`.
  - **The discriminator is the character set, not the case**, and that distinction is the whole
    fix. Tightening to a capital `E` would still claim an UPPERCASED hash - the same string
    shouted. A Twitter media id is base64url, so beyond 15 characters it carries a letter past `f`
    or a `-`/`_`; hex by definition cannot. A lookahead requires one.
  - Proved by mutation in both directions, including a mutant that fixes it *by case* - that one
    dies on the uppercase-hash case, which is why the comment says what it says. Verified on the
    corpus that found it: **0 of 9,294** names now claimed.

- **BUILT 2026-08-12: the date resolver's wrong answers, then its largest gap. No letter - this
  came out of a measurement (`docs/date-resolver-corpus-measurement.md`), not the backlog.**
  - **Ordering was the decision, and it followed from the numbers.** Tier 4 produced **zero**
    wrong days on 2,271 real files. The wrong answers were in the *messenger list*. A gap sends a
    photo to `Undated/` where a user can find it; a wrong date files it under a day that never
    happened, so the list was fixed first and the 643-file gap second.
  - **Three of WhatsApp's four naming conventions were read as capture dates.**
    `is_messenger_filename` delegates to `categorize.NAME_PATTERNS`, which listed one. The
    `messenger-dates-research.md` ruling was never wrong; the list it delegates to was short, and
    the delegation turned a **categorizer** gap into a wrong **date**. Two entries added, both
    reusing the existing `WhatsApp` label so `deterministic_side_bin_labels()` is unchanged and no
    migration is involved.
  - **Neither new shape is evidenced by a file, and the entry says so at the site.** Every
    messenger-named file available anywhere - both sample corpora and the whole reference library,
    9,294 + 2,276 names - is `IMG-20140817-WA00NN.jpg`, four of them. These are documented
    conventions, not observations. Skype, Slack and iMessage were **left out** for the opposite
    reason and that refusal is recorded too: no convention could be stated with confidence, and
    this table makes the date chain *refuse* names, so a guessed pattern costs real photos real
    dates.
  - **The gap was two repairs, not one, and that is the highest-value comment in the change.**
    `2014815120755` (614 files) defeats `_COMPACT_DATE` twice: the trailing time defeats its
    `(?!\d)` fence, and the one-digit month defeats `(0[1-9]|1[0-2])`. **Either repair alone
    recovers 0 of the 614.** Someone making one of them would measure no improvement and conclude
    the analysis was wrong, so the number is at the site and a test isolates each half.
  - **Whole-run matching rather than a looser fence**, because relaxing the fence in place would
    let an 8-digit window inside a 17-digit Facebook id match. Two valid readings **refuse**
    (`2014121120755` is both 2014-01-21 and 2014-12-01) - §1's never-guess rule reaching a new
    site. A pattern-local floor of 2000 is justified by what *writes* these names, and its
    residual is disclosed rather than hidden: a bare, unprefixed epoch-ms filename **after
    2033-05**, 150 of 16,436 sampled.
  - **Two silences ended.** A terminating NUL survived `str.strip()` (NUL is not whitespace in
    Python) and cost the file its date; edges only, so an embedded NUL still refuses.
    `DateSource.REJECTED_EARLY` gives the sanity **floor** a member - `1899:12:31` used to be
    found, refused, and reported as `NONE`. `REJECTED_FUTURE` turned out to have **no explanation
    entry at all** and fell back to "not recorded"; both now say what was refused and why.
  - **What the identical trees actually earn - the correction that mattered most.** Organizing the
    whole library before and after gave byte-identical trees, 2,271 files, empty diff. That is not
    proof the fix works and reading it as such teaches nothing: it earns exactly *the change is
    inert wherever EXIF exists*. The 643 are EXIF-dated - that is why tier 4 never fires here - so
    they were never in `Undated/` and could not move. A third run on **EXIF-stripped copies** is
    the only one that shows the fix: 643 of 643 in `Undated/` before, **0** after, every one on
    the day its original EXIF says.
  - **Gates:** right-day 631 → 1,274, correctly silent 997 → **997**, wrong days **0**, the four
    WhatsApp files still `Undated/`. Across 78 camera makes the two new patterns match **0 of
    9,294** names and the digit-run pattern refuses **201 of 204**, dating only a genuine AVCHD
    camcorder stamp.
  - Filed, not fixed: `(adc)` (a falsified clustering invariant), `(add)` (~30 discarded tag
    readings needing three separate rulings), `(ade)` (the Twitter pattern claiming hex hashes).

- **(abv) CLOSED 2026-08-08: the disambiguated event folder was computed and thrown away.**
  Found while planning folder-name suggestions, fixed in the same commit as this entry. Recorded
  because what it says about the *tests* outlives the one-line cause.
  - **The defect.** `disambiguate_event_folders` separates two events that spell one folder on
    one date with a `(2)` suffix. `migrate._disambiguated_folder_notes` returned
    `[f.note for f in folders if f.note]` - the notes, never the folders - so the render spelled
    each event from its own name and every collision landed in **one directory**, while the
    preview stated that one of them *became* `... (2)`.
  - **Severity, measured rather than assumed.** Not byte loss: `plan_migration` guards duplicate
    targets on the full relative path *including the filename*, and the real case
    (2015-10-25 on the maintainer's library) holds **146 files and 146 distinct filenames**. The
    wrong part is that folders merge contrary to intent and **the preview promises a folder that
    is never created** (§9). `test_filename_safety.py` already called this "data loss by
    presentation", which is the accurate phrase and the one used here.
  - **Why five existing tests missed it.** `test_filename_safety.py` covers the helper thoroughly
    - collisions, case-insensitivity, three-way, different dates, slug naming - and **every one
    asserts what the function computes, never that the computed folder is what gets used**.
    `ENGINEERING_STANDARD.md` §4's own failure mode, in the tests written to prevent it. The new
    tests assert the *placement*, so they cannot pass while the render ignores the decision.
  - **Three render sites spell an event folder, not one**: the event append, the `{event}` token,
    and the trip header. Each is now routed through `layout._decided_folder`. Mutating the
    `{event}` site alone fails only the `{event}` test while the other four pass - the append-site
    tests do not cover it, which is exactly how a partial fix would have shipped unnoticed.
  - **The trip-header site is UNREACHABLE today, and is handled anyway.** No test was written for
    it, because a test that cannot fail is worse than none. Three facts make it unreachable, all
    named in a comment at the site: `trip_days.day` is the PRIMARY KEY so two trips can never
    share a start date; `classify` returns TRIP_DAY before EVENT_DAY; and an event never spans
    more than one day, so `_migration_headers` excludes a trip-claimed event outright. None is
    permanent - a reachability argument would rot silently where an unconditional lookup cannot.
  - **Named, not fixed.** (a) Libraries whose events already merged will now see
    `migrate-layout` propose moves that separate them - correct, but a behaviour change on
    existing data. (b) `organizer.py:_apply_events` renders event folders with **no
    disambiguation pass at all**, so two identically-named events in one organize run merge with
    no note whatsoever - same defect class, untouched here. (c) `plan_migration` warns about a
    same-path collision and then **still plans both moves**, so a genuine filename collision
    would have the second overwrite the first - narrower, and the only one of the three that is
    about bytes.

- **(acb) CLOSED 2026-08-08: a dead event stream froze the screen with no outcome at all.**
  Found by reading a CI trace rather than re-running it. **Ranked as the worst UI defect this
  session produced**: the person is given no outcome, no error, and no way to learn the job is
  gone.
  - **The mechanism.** `streamJob`'s `es.onerror = () => es.close()` closed the stream and never
    called `onDone`, so `awaitJob`'s promise never resolved and `runJob` awaited it forever.
    `progress.stop()`, `setJob(null)` and the whole onCancelled/onSuccess/onError branch never
    ran. The screen kept the card it had before the run and the trigger stayed disabled.
  - **Observed, not theorised.** CI run `31276824490`: `POST /api/ingest/archives/run` 200,
    `POST /api/jobs/<id>/cancel` **202 accepted**, and then **no `/api/jobs/<id>/events` request
    at all** - zero occurrences in the network log and in the trace. The final DOM still held the
    precheck card and its "Unpack and scan" button, 60 seconds later.
  - **It was never archive ingest's defect.** `streamJob` and `runJob` are the shared job
    skeleton for thirteen call sites - organize, backup, verify, migrate, rescan, ingest. Pinning
    it where it surfaced would have left the other twelve silent, so the test drives it through
    organize and kills the stream outright rather than racing a cancel: a timing test passes on a
    fast machine and proves nothing.
  - **PROVENANCE, not apology.** The ordering that exposes it is mine, from `6fbb4d3`: the queued
    cancel is awaited BEFORE the stream is opened, so a job that finishes first is already reaped
    when the stream is attempted. That path was correct; the gap is that opening the stream was
    not made unconditional alongside it. **Left open deliberately**: reordering deserves its own
    thought, and the fix here holds whatever the order, because it covers every way a stream can
    die rather than one race.
  - **Still worth doing**, named not built: open the stream before firing a queued cancel, so
    that window reports "Cancelled" rather than "lost contact". Honest either way, but one names
    what happened.

- ~~**(mm) `migrate.py` asks the wrong template how an event folder is spelled.**~~ **Delivered.**
  `plan_migration` no longer reads `scheme.template_for(Placement.EVERYDAY).event_naming` for
  every event; each event's naming now comes from its own placement, resolved with one
  `classify()` lookup per event (a representative row supplies the rule) in place of the fixed
  lookup - `O(events)` either way, same cost as building the `events` dict already was. Events
  are grouped by the naming their own placement resolved to before disambiguation, since
  `disambiguate_event_folders` takes one naming per call; collision detection is therefore
  scoped per group, not across the whole drive, which is exact today (every event still
  resolves to `Placement.EVENT_DAY`, so there is exactly one group) and a known, explicitly
  flagged boundary for whoever adds a second naming (Stage 2d's `TRIP_DAY`) to close with
  evidence, not guessed here.
  - **Proven behaviour-preserving today, and proven to actually matter.** Two fixtures, each run
    against the defect first: a scheme where `EVERYDAY` and `EVENT_DAY` genuinely disagree
    (`READABLE` vs `SLUG`) shows the old, fixed lookup reporting a same-date, same-name
    collision that real per-file rendering (which already routed through each row's own
    placement) would never actually produce - the fix reports none. The same two events on a
    scheme where every placement shares one naming (every shipped preset, today) still collide
    exactly as before, proving no regression the other direction.
  - **Unblocks Stage 2d.** `TRIP_DAY` is the first placement whose template genuinely needs a
    naming that differs from `EVERYDAY`'s; migration now asks the right question for whichever
    shape a file's own placement turns out to be.

- ~~**(w) Self-describing month preset.**~~ **Delivered by the year-first default correction**
  (2026-07-28). Self-describing months (`2014-08`, never a bare `08`) are baked into every
  shipped preset and into the default itself, so the standalone preset this item asked for would
  have been redundant. The argument it recorded - a folder must still say what it is once copied
  away from its parent - is now `IMPLEMENTATION_STANDARDS.md` §4.

- ~~**Browser end-to-end test layer.**~~ **Delivered** (`9be7529`, `0103454`). Playwright via
  `pytest-playwright` against an in-process app server, run in CI as its own chromium-on-ubuntu
  lane. Every UI bug the soak era found is now a **named regression test**, the golden path is
  one journey rather than six set-up tests, and the "a clean runtime install pulls no browser"
  claim is itself tested. Rules in `IMPLEMENTATION_STANDARDS.md` §6; scope rulings and the
  Playwright-over-Docker rationale in `DECISIONS.md` D2/D3.
- ~~**Performance audit + its convictions.**~~ **Delivered** (`1e458df`, `39d889a`, `8f77de1`).
  Measured every pipeline stage, then fixed only what evidence convicted: the per-file exiftool
  write (255ms → 9.3ms/file) and the custody strip's row-building count (224ms → 17.5ms at
  100k). The O(n²) perceptual scan was **deliberately not fixed** - it became item (v) with a
  runtime alarm. Baseline, rule and the do-not-touch list in `PERFORMANCE.md`. *(Both have since
  moved: the alarm was removed and `(v)` closed on measurement 2026-08-02 - see `(v)` above -
  and the do-not-touch list's `hamming_distance` entry was withdrawn with it.)*
- ~~**(q) In-place organize (same-device optimization).**~~ **Delivered.** `organize --in-place`
  moves files by rename when source and destination share a filesystem: no bytes rewritten, no
  zero-copy window visible to another process, hash unchanged because the inode is. (Crash
  atomicity is the filesystem's to give; FAT32/exFAT do not, and the undo journal covers them.) Plain `--move` takes the
  same fast path automatically; `--in-place` *requires* it and refuses a cross-device
  destination rather than silently copying. Typed `move` confirmation, mechanism split in the
  report, empty folders left and reported. `truestill undo-organize` ships with it (catalog
  v10, `inplace_runs` + `inplace_moves`) - reversible, not merely resumable. The `Destination.adopt`
  seam is on the interface, so `migrate-layout` can adopt it later without rework.
  **Two landmines found in the build and fixed with it:** `reclaim` would have deleted the only
  copy of an in-place file (source and drive copy are one inode, so its re-verify gate was a
  tautology), and an undo that left `files` rows behind would have made the library
  un-organizable by re-running dedup against itself. Both pinned by tests. See
  `IMPLEMENTATION_STANDARDS.md` §1. App surface for in-place + move shipped as **`(eee)`**;
  `reclaim` remains CLI-only (see App-surface deferrals).
  - **Still open:** cloud tier (server-side move within a remote, never via mounts) waits for
    the rclone work; a `--prune-empty-dirs` opt-in waits for soak evidence that the folders
    left behind are actually intolerable.
- ~~**`--skip-undated` on organize/ingest (j).**~~ Delivered: default OFF (undateable files still
  copy to `Undated/`); with the flag, they are skipped as `SKIPPED_UNDATED` and **counted + named**
  in the report - never silent. CLI on organize/ingest, plus an app organize toggle.
- ~~**Space-safe move: source reclamation (k).**~~ Delivered as one verify-gated mechanism, two
  surfaces: `organizer.execute(move=True)` / `organize --move` (copy → record → re-verify → delete,
  `MOVE_KEPT` on failure, no zero-copy window) and `reclaim.run_reclaim` / `truestill reclaim` (dry-run
  default, re-verify-at-delete on a connected drive, typed `delete` confirmation, `--min-copies N`
  with single-copy warning, `reclaim_journal` at schema v9). The copy-only-invariant exception is
  documented in `IMPLEMENTATION_STANDARDS.md §1`. **`organize --move` is in the app via `(eee)`**;
  **`reclaim` stays CLI-only** until an app surface is explicitly approved.

- ~~**(gg) Adaptive day-folder threshold for Everyday photos.**~~ **Built 2026-07-30.**
  Un-evented days over `layout.everyday_day_threshold` (default 40) get
  `{yyyy}-{mm}-{dd} - Everyday`; under stay in the monthly bucket. Both-direction migrate
  reconcile with per-day reasons; Settings warns on threshold change and routes to migrate;
  app migrate uses `typedConfirm("move")`. Research: `docs/adaptive-day-folder-research.md`.
  - **Soak finding (2026-07-30), recorded so it is not misread later.** `(gg)` is correct but
    **rare on real data.** One hit in the full soak catalog: **2013-09-30**, 62 photos,
    un-evented and non-trip-claimed (still in the monthly Everyday folder until migrate). The
    **2,057-photo 2014-08 Everyday folder that prompted `(gg)` was explained entirely by the
    Wayanad trip claim**, not by threshold behaviour - the trip work had already solved that
    folder. Do not treat `(gg)` as the fix for Aug 2014.
  - **Product implication (note, do not act on):** heavy days are usually trips or named
    events, so the threshold mostly guards the residual case - a genuinely busy day that
    belongs to nothing. Worth having; frequency is low. Any future tuning of the default
    should be judged against that residual rate, not against the Aug 2014 example.

- ~~**Metadata recovery fallback chain - decided on evidence.**~~ A 37-file, 22-format corpus
  test (`docs/metadata-chain-research.md`) showed exiftool already dates every datable file
  (including AVCHD `.mts` and WhatsApp `.mp4`), **no** fallback parser recovered a genuine capture
  date it missed, and naive parsers emit epoch sentinels (1904/1970) that would misfile. Outcome:
  **no parser added**; shipped the never-silent **skipped-file reporting fix** (`scan_source` +
  report); recorded the **sentinel-rejection rule** and ffprobe/schema-v9 reservation as binding
  conventions (`IMPLEMENTATION_STANDARDS.md §1`). The `CreationDate` UTC-vs-local fix shipped
  earlier (`01ebaa0`). Remaining follow-on tracked as item (l).
- ~~**Event merge/split.**~~ Delivered in the local web UI's Event review screen (merge/split
  are UI-only capabilities the CLI's name/skip flow lacks), exercised end-to-end through the HTTP
  API against real clustered fixtures. The CLI stays name-or-skip only, by design - a terminal is
  the wrong surface for interactively re-partitioning clusters.
- ~~**Configurable organization structure.**~~ Delivered: `LayoutTemplate` seam + token grammar,
  catalog v7 settings (`layout_template`) + validation, `truestill config` with 5 presets and live
  preview, and `truestill migrate-layout` (crash-safe, journaled, catalog v8) plus the app Settings
  screen. Split-era default: a template change affects new files only; migration relocates an
  existing library preview-first. See `docs/org-structure-research.md`.
- ~~**Drive identity + offline catalog + verify.**~~ Delivered: `.vaeon-drive.json` marker,
  catalog v6 (`drives` + `file_copies`), and `truestill drives`/`where`/`verify`/`status`. See the
  CHANGELOG and `docs/drive-identity-research.md`.
