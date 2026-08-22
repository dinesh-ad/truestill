# truestill - Backlog (approved but unbuilt)

Things that were **decided** but not yet built - captured here so nothing lives only in chat
history. This is not a wishlist of everything possible; only items already agreed, with the
decision context that produced them.

> **How to read this file: status is per ENTRY, never per section. A heading is not a status.**
> Read the entry's own text before acting on it - several are *partial*, and partial is the
> normal state here rather than the exception. This is written at the top because it is the
> defect the 2026-07-31 audit found: 20 of the 36 entries under a heading that said *"not yet
> built"* were built, and separately `(n)` and `(ii)` described shipped work as unstarted. Both
> directions cost real money - one hides finished work, the other invites rebuilding a schema
> that already ships.

> **Items (w) and (x) came from a three-report external research synthesis (2026-07-27) whose
> main result was that it changed nothing.** It reviewed the shipped architecture and validated
> it point-for-point; these two are the entire delta, one of them trivial and one of them
> post-launch. That outcome is worth recording as loudly as a finding would have been - an
> external review that produces two small additive items is evidence the recorded decisions
> have been holding, and it is the kind of result that quietly disappears if only the deltas
> get written down.

## Item letters

Letters are **permanent identifiers, not an ordering** - `IMPLEMENTATION_STANDARDS.md` cites
`(aad)` and `(ii)` by letter and `PROJECT_STATUS.md` cites `(gg)`, so reusing or renumbering one
silently redirects a citation. Since the split those citations reach across **two** files: a
letter is assigned here and the entry may live in `BACKLOG.md` or in
[`SHIPPED.md`](SHIPPED.md). They are assigned across *all* sections, not per-section, and
`SHIPPED.md` never allocates one.

*(The example here used to be "§8 cites `(u)`". That citation no longer exists - the contract
names no `(u)` anywhere - which is exactly the drift this paragraph warns about, found in its
own text. Replaced with citations verified present on 2026-08-01.)*

**Used: (e)-(z), (aa)-(zz), (aaa), (bbb)-(fff), (aab)-(afv). Next free: (afw).**
⚠ `(adk)` was the gap this line flagged as free, and it was taken on 2026-08-15 by the SSE
heartbeat fix in `SHIPPED.md`, so the range is now contiguous. `(adl)`-`(adq)` were allocated on
2026-08-14 and this line was not updated with them, which is the exact drift the warning
below describes. Six letters, one day, and the *next free* answer stayed right by luck
while the *used* range was wrong. `(aap)` was assigned ahead of `(aao)` and the gap has since been filled by `(aao)`; letters are identifiers, not an ordering, so neither was renumbered. Check here before assigning - `(u)` and `(v)` were proposed
a second time on 2026-07-27, four hours after they were first taken, because nothing recorded
which letters were spoken for.

**AN ENTRY IS CLOSED BY A COMMIT WHOSE MESSAGE SAYS `Closes (xyz)` ON A LINE OF ITS OWN, AND BY
NOTHING ELSE** (standing, 2026-08-10). A ruling in conversation is not a closure until a commit
records it, and that commit moves the entry to [`SHIPPED.md`](SHIPPED.md) - this file carries open
work only.

**The trailing full stop is conventional and is deliberately not required**, corrected 2026-08-10
because this line said *exactly* `Closes (xyz).` while the pattern had always accepted both. Of
the two possible reconciliations only one fails safely: requiring the period means a commit that
omits it stops counting as a closure at all, so a shipped entry sits in the open-work file with
nothing to say so - the silence the rule exists to end. A wider marker costs nothing here, because
the line must still be a trailer of its own, which nobody writes by accident.

**Both directions are enforced, in two places, because only one of them is checkable against
history.**

- *Declared closed, but still open work here* - **`test_closed_entries_leave_the_backlog.py`**,
  over the whole corpus. It also fails when a declared letter is in **neither** document, which is
  what deleting an entry outright would look like.
- *Left this file without ever being declared* - **`scripts/check_entry_closure.py`**, a
  `commit-msg` hook (activate with `uv run pre-commit install --hook-type commit-msg`). It refuses
  a commit that removes an entry title from here unless the message declares the letter closed
  **and** the entry arrives in `SHIPPED.md` in the same commit.

**Why that half is a hook and not a test, stated so nobody "finishes the job" later.** As a check
over the corpus it is not honest: *a letter in `SHIPPED.md` must carry a trailer* fails **31 of its
32 entries** on the day it is written, because the whole history holds exactly one; and *an
allocated letter is in one of the two files* is false as well - `(e)` and `(h)` are retired and
legitimately in neither. ⚠ **This sentence named `(gg)` as a third example and that was wrong:
`(gg)` has a full entry in `SHIPPED.md` (*Adaptive day-folder threshold*, Built 2026-07-30).**
Recorded rather than quietly dropped, because the claim was load-bearing - it is one of the two
counter-examples justifying why this check is a hook and not a corpus guard, and one of the two
was false. `(e)` and `(h)` were verified against both files and do hold. A guard that goes red on the past gets switched off and takes its real
signal with it (`ENGINEERING_STANDARD.md` §4).

**And the boundary is structural, not a date.** The hook reads only the staged diff of the commit
being made, so it has no opinion about anything already committed - there is no "from now on" to
record and nothing to grandfather. An undated "from now on" would be the next drift; this way there
is no list of exceptions to maintain and no date to go stale. What it cannot see is stated in its
own docstring: an amend that only edits the message stages nothing, and hooks do not run in CI.

*`(acr)` is the instance that proved the rule.* It was closed by the maintainer in conversation;
neither its entry nor any commit said so, and no repo check could ever have seen it - it sat here
as open work while shipped. Two of the three entries stale that day *were* catchable, because
their commits said so and nothing checked. The trailer is what turns a ruling into something the
repository can observe.

**Retired 2026-08-11, and named here because a retired letter is not a free one:** `(abp)` (the
body sans face is not bundled) and `(abh)` (the nav icons are Unicode glyphs, so their letterform
varies per machine). Both were recorded 2026-08-05, both are cosmetic, and **both were untouched by
the monospace bundling that shipped in between** - a pass that went through the type system and did
not reach for either. Carried a third week they would still be preferences rather than defects, so
they are retired rather than carried. Reopening one needs a reason the font pass did not supply.

> ⚠ **`(abh)`'s STATED REASON WAS FALSE, corrected 2026-08-13 (`4ff3577`). It stays retired.**
> All ten glyphs the rail uses **are present** in the bundled DejaVu Sans Mono - verified against
> the shipped `.ttf`. The letterform varied because `.nav-item .ico` set width, flex and size and
> **never asked for that family**, so it inherited `--font-sans` and resolved from whatever the
> machine had. Two lines of CSS fixed it.
>
> **The paragraph above recorded the right observation and drew the opposite conclusion from it.**
> *"Untouched by the monospace bundling ... a pass that did not reach for either"* was read as
> evidence they were cosmetic; it was evidence the pass had **left a gap**, because nothing pointed
> at the bundled face. `(abh)` was a live rendering defect filed as a preference.
>
> **Correcting it strengthens the retirement rather than undoing it:** a drawn icon set is still
> worth having, and it is now genuinely a want rather than a defect wearing that word. Left in
> place rather than rewritten - a document that states a cause it never verified is the failure
> here, and deleting the sentence would hide it.

Several early letters no longer appear anywhere in this file: their items shipped and the
Shipped entries describe the work rather than repeating the letter. `(e)` and `(h)` are still
cited by name in `drive-identity-research.md` and `org-structure-research.md`. **A letter that
is invisible here is retired, not free.**

## Approved - still to build

- **(afv) `(ady)` INTRODUCED AN INTERMITTENT FAILURE IN THE CONCURRENT-MIGRATION TEST, AND THE
  MECHANISM IS NOT KNOWN.** Found 2026-08-22, hours after `(ady)` shipped, by running the gate on a
  docs-only change. `test_concurrent_openers_of_a_behind_catalog_all_succeed` fails ~**1 run in
  8**: one of six openers finishes at schema **4** instead of 20, without raising.
  ⚠ **Proven `(ady)`'s by differential, not assumed** - 12/12 green on the pre-`(ady)` tree with
  the import resolution printed, after a first control that was **void** through the editable
  install (§4's fifth member, first worked example). Four hypotheses measured and ruled out, each
  recorded. **Filed rather than fixed because the cause is not established**, and a
  non-deterministic failure is quarantined and filed with its trace, never retried (§4's
  twenty-sixth member). ⚠ **Not a test artefact**: `(adm)` records six concurrent `_migrate` calls
  in one app process on a real first run. [Full entry](research/backlog/afv.md)
- **(afu) THE RUN RECORD IS CLI-ONLY, AND THE SURFACE IT MISSED IS THE ONE §1'S OWN REASONING
  NAMES.** Found 2026-08-22 by a whole-backlog re-read, four commits after `(afl)` shipped.
  Measured: `record_path_for` has **one caller** (`cli.py:2787`) and `truestill-app` contains no
  run-record path at all - so no app organize, backup, migrate, bake or undo writes one.
  ⚠ **The rule is a PRODUCT invariant in `IMPLEMENTATION_STANDARDS.md` §1**, whose own
  justification is *"the user who most needs it is the one who did not know to ask"* - **and that
  user is the app's**, since a person typing `truestill organize` is the one who could have passed
  `--report`. §4's fifty-sixth member with the contract on the wrong side of it.
  **Also covers `(aac)` residue 2**, the app run's missing `unreadable_files`, from the record's
  side rather than the screen's. Design the one-rolling-file-per-catalog question first: the app
  can run two jobs on two drives at once, which a CLI never could.
  [Full entry](research/backlog/afu.md)
- **(afs) A DESTRUCTIVE MIGRATION MAY NOT RUN WITHOUT A PRE-UPGRADE COPY, AND NOTHING SAYS WHICH
  ONE IS DESTRUCTIVE.** Recorded 2026-08-22, split out of `(ady)` while building it - **a policy
  change about what a migration may do, which would have been invisible arriving inside a
  copy-before-upgrade fix.** `(ady)` degrades when the copy fails, which is right while every
  migration is additive and wrong the day one is not. The declaration must **not** gate the copy
  itself: that would trust the same judgement that wrote the destructive migration. The guard is
  demonstrated rather than proposed - an AST scan over `catalog.py` cleared all 19 forward steps
  and flagged `downgrade_v12_to_v11`, the one function that really does `DROP TABLE`.
  [Full entry](research/backlog/afs.md)
- **(aft) `run_health.free_bytes` RETURNS 0 WHEN IT CANNOT READ, SO AN UNREADABLE PROBE STOPS A
  RUN SAYING THE DISK IS FULL.** Found 2026-08-22 answering `(ady)`'s M6 against `(aek)`.
  `(aek)` removed exactly this conflation from `filesystem.preflight_destination` and pinned it
  twice; the sibling never got it (§4's fifty-sixth member). ⚠ **The same module guards its
  DEVICE axis against this in its own words** - *"never let an absence serve as the baseline"* -
  with five transient-failure tests, and the space axis has none. Open first: `_check_space`
  claims *"a local read does not fail transiently"*, so the branch is either dead code to delete
  or a live false stop - §4's thirty-first member says find out which before writing the test.
  [Full entry](research/backlog/aft.md)
- **(afr) THE LOCK DIRECTORY GROWS ONE EMPTY FILE PER DRIVE, FOREVER.** `DriveLock.release`
  truncates and never unlinks (`drive_lock.py:208,219`), so `~/.local/share/Truestill/locks/`
  gains a 0-byte file per distinct drive key and keeps it - and `path:` keys mean **every
  destination ever organized** leaves one. ⚠ **Nothing breaks and deletion is safe, because the
  flock is the truth and not the file** - which is exactly why it needs a letter rather than a
  comment: it was **neither designed nor recorded**, and `(aaw)`'s *"no stale lock to detect or
  clear"* is true of the lock and was read as true of the file. ⚠ *"Unlink on release"* is the
  obvious fix and probably the wrong one - it makes routine the one hole here, two processes on
  two inodes at one path. **Measure first**: nobody has counted a real user's key set. Found
  2026-08-22. [Full entry](research/backlog/afr.md)
- **(afq) A PREVIEW OCCUPIES THE DRIVE IN THE APP, AND NOTHING SAYS WHY.** `_start_drive_job`
  passes `operation="organize preview"` to `jobs.start`, which occupies the drive exactly as an
  apply does, so a second tab previewing during an organize is refused - while the CLI has never
  done this. ⚠ **Split out of `(aaw)` rather than folded in**: the lock rests on measured data
  loss, a preview writes nothing, and letting a UX decision inherit a safety argument it has not
  earned is what the 2026-08-03 design did without noticing. May well be right; needs its own
  reason. Filed 2026-08-22. [Full entry](research/backlog/afq.md)
- **(afg) THE DOWNLOAD PAGE HAS NO HOME, AND `truestill.app` EXISTS ONLY IN CONVERSATION.** The
  domain is bought; **nothing about it is in this repository** - `grep -ri truestill.app` matches
  only the package identifiers. D9 binds a requirement to a page that does not exist: *"Windows
  users must be told what SmartScreen will show… on the download page, above the button."*
  ⚠ **Whether it blocks a first tag is NOT DECIDED and this entry does not assume**; the arguments
  either way are recorded for the ruling. §4's fifty-eighth member exactly - a live planning
  assumption invisible to every grep and every audit. Filed 2026-08-22.
  [Full entry](research/backlog/afg.md)
- **(aff) ONE EXTRA NEAR-DUPLICATE ON 3.14, FROM THE INTERPRETER AND NOT FROM A DEPENDENCY.**
  262 look-alikes on 3.13, **263** on 3.14, stable over two runs each - and ⚠ **both pools agree
  exactly on both interpreters**, which is the property the step was run for. Ruled out by
  measurement: the relock moved **no** package version, and the walk order is byte-identical. The
  mechanism is **not isolated**. It did not block the upgrade because a near-duplicate is kept and
  flagged, never removed - the effect is one extra row in a review list, and exact dedup was
  identical in all four runs. Found 2026-08-22. [Full entry](research/backlog/aff.md)
- **(afa) `unreachable` MEANS FOUR THINGS, AND THE TOOLTIP ASSERTS ONE OF THEM.** ⚠ **Narrowed
  and retitled 2026-08-22 after a read-only pass falsified its own thesis.** It claimed
  `date_rescue` told the user nothing; measured, it renders *"could not check"*. What is wrong is
  that `unreachable` is produced by four distinct causes - no catalog row, no `source_path`, the
  sidecar refused, the parent is not a directory - and the tooltip asserts one of them for all
  four. ⚠ **Its central guess is recorded as FALSIFIED**: the three sites shared a cause, not a
  remedy, and one vocabulary would have fixed neither `(afn)` nor `(afo)`. That finding is worth
  more than the fix. Found 2026-08-21, narrowed 2026-08-22.
  [Full entry](research/backlog/afa.md)
- **(ael) NO CLI ROUTE COPIES A LIBRARY TO A SECOND DRIVE WITHOUT A SOURCE FOLDER.** `(aei)`
  closed most of this - `organize <source> <second-drive>` is now the CLI's second-copy route.
  What remains is drive-to-drive when the source folder is gone or no longer matches the drive.
  ⚠ `backup_run` is app-side and the CLI cannot import it, so this is a **move to core**, never a
  second implementation. Recorded 2026-08-20. [Full entry](research/backlog/ael.md)
- **(aep) THE WRITE SIDE HAS NO `unreadable_label`.** A failed copy reads `cannot upload to '...':
  [Errno 13] ...` - backend vocabulary and a raw errno, both against §9, and the rule is stated
  eighteen lines above the `print` that breaks it. Reads have `models.unreadable_label`; writes
  have no equivalent. Split from `(aek)` 2026-08-21. [Full entry](research/backlog/aep.md)
- **(aeh) THE RUNNER IMAGE IS UNPINNED, SO THE apt THAT DEADLOCKS IS NOT A VERSION WE CHOSE.**
  `(aee)`'s hang is fixed in apt 3.1.3 and unbackported on noble; `ubuntu-latest` is noble today.
  ⚠ **A route with a cost, not a recommendation** - pinning fixes nothing by itself, and
  `ubuntu-latest` flipping to 24.04 in January 2025 left breakage found months later. Recorded
  2026-08-20. [Full entry](research/backlog/aeh.md)
- **(aeg) CACHE PLAYWRIGHT'S SYSTEM LIBRARIES SO `--with-deps` STOPS INVOKING apt AT ALL.** The
  right long answer to `(aee)`'s hang - it removes the class rather than bounding an instance -
  and the largest consumer, at 43m33s on run 32295312064. ⚠ **Does NOT cover the `check` lanes**,
  which still need exiftool, so `ci_bounded.sh` stays either way. Recorded 2026-08-20. [Full
  entry](research/backlog/aeg.md)
- **(aef) THE BACKLOG CANNOT ANSWER "WHAT MUST SHIP BEFORE v1", AND 57 OF 64 ENTRIES ARE SILENT.**
  ⚠ **The title's figures are the 2026-08-19 reading and are kept as the dated measurement they
  were.** Re-counted 2026-08-22 with the command in the body: **81** entries, **7** matching a
  release marker - and the ratio the entry is about has got worse, not better, which is the
  argument for the ruling rather than against it.
  A decision about the backlog's SHAPE, not 57 small ones. ✅ **Ruled: option B** - a curated list
  in `PROJECT_STATUS.md`, guarded by the `test_backlog_references` pattern.
  ⚠ **Re-ranked live 2026-08-22: its gate fired and nobody re-read it.** *"The list is a ruling the
  maintainer makes after the first soak"* - **four soaks have run**, produced twelve entries and
  all twelve are closed, so the evidence it waited for now exists. It is the maintainer's ruling to
  make, and it is no longer blocked. ⚠ **The entry is ABOUT this failure and was an instance of
  it** - see its own new section. Recorded 2026-08-19. [Full entry](research/backlog/aef.md)
- **(aec) 62 FIXED WAITS IN THE BROWSER LANE, EACH ONE A COIN TOSS AGAINST A MEASURED LATENCY.**
  Recorded 2026-08-19. One was fixed; the class was not. [Full entry](research/backlog/aec.md)
- **(aea) TWO INTACT CATALOGS FOR ONE INSTALL, AND NOTHING RECONCILES THEM.** Recorded 2026-08-19.
  `DESTINATION_EXISTS` is now a dead end rather than a safeguard. [Full
  entry](research/backlog/aea.md)
- **(adz) A COMPATIBILITY PATH STATES ITS REMOVAL CONDITION WHEN IT IS WRITTEN.** Recorded
  2026-08-19. ⚠ **The window for free removal closes at the first `v*` tag.** [Full
  entry](research/backlog/adz.md)
- **(adx) A LIBRARY THAT MOVES IS HANDLED. WHAT IS MISSING IS THE DISCLOSURE.** Recorded
  2026-08-18. Three gaps, one user journey. [Full entry](research/backlog/adx.md)
- **(adt) TWO CATALOG WRITERS RACE INSIDE ONE PROCESS, AND THE 6558 ms THAT MADE IT BITE IS
  UNEXPLAINED.** Recorded 2026-08-15, retitled 2026-08-22 - the old title was not wrong, it just
  did not say which half is open. ⚠ **Its lead is dead twice over (2026-08-22) and the question is not.**
  `PERFORMANCE.md` §5.5 priced the per-open lock at **4-8 microseconds** with zero refusals in
  2,160 contended opens, and `(adu)` then removed it outright - re-measured, an open plus a
  settings write is **0.32 ms** against the **6558 ms** observed. Removing a falsified hypothesis
  answers nothing: **server-side instrumentation of the real lane is still the only instrument
  left.** ⚠ `(aaw)`'s lock deliberately does not cover this - settings writes do not go through
  `_start_drive_job` - so the window narrowed and the race did not close.
  [Full entry](research/backlog/adt.md)
- **(ads) THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION.** Recorded
  2026-08-15. [Full entry](research/backlog/ads.md)
- **(adm) `inspect_catalog` SKIPPED THE FIRST-RUN CASE - FIXED FOR THE APP, UNCHANGED FOR THE
  CLI.** Recorded 2026-08-14. [Full entry](research/backlog/adm.md)
- **(adn) NOTHING STOPS TWO APPS RUNNING, AND QUITTING THE SECOND DELETES THE WAY BACK INTO
  THE FIRST.** Recorded 2026-08-14, retitled 2026-08-22.
  ⚠ **Narrowed 2026-08-22 by `(aaw)`, and the title is now too broad**: two mutating operations on
  one drive can no longer overlap across processes, so *"two sets of in-flight writes"* is gone.
  **What remains is single-instance detection** - two apps, two ports, two sidecars, and
  `session-url.txt` naming one. ⚠ **`(vv)`'s residue was merged in the same day and `(vv)` closed**,
  so this is now the whole of the problem in one place, including the worst of it: quitting the
  second instance **deletes the link to the first, which is still running**.
  [Full entry](research/backlog/adn.md)
- **(adj) THE FREEZE IS NOT A REPRODUCIBLE TARGET: `truestill.spec` IS GITIGNORED.** [Full
  entry](research/backlog/adj.md)
- **(adi) REACT + SHADCN MIGRATION - PLANNED, GROUNDWORK LANDED, NOTHING MIGRATED.** [Full
  entry](research/backlog/adi.md)
- **(adh) TAURI SHELL + PYTHON SIDECAR - STAGE 1 MEASURED, THREE GAPS NAMED AND UNFIXED.** Recorded
  2026-08-13. [Full entry](research/backlog/adh.md)
- **(aed) THE METADATA BAKER STAGES EVERY BAKED FILE THROUGH THE SYSTEM TEMP DIRECTORY.** Recorded
  2026-08-19, split from `(adb)`. **Measure before changing anything.** [Full
  entry](research/backlog/aed.md)
- **(adg) THE VERIFY RESULT BLOCK MOVES `#bk-preview` BY +92.4px - a bigger mover than `(acw)`, and
  it cannot be reserved.** [Full entry](research/backlog/adg.md)
- **(ada) THE BACKUPS SCREEN NOW PUTS STATE BELOW THE FORMS, AND A ONE-COPY WARNING CAN FALL BELOW
  THE FOLD.** [Full entry](research/backlog/ada.md)
- **(act) AN UNNAMED ROOT IS LABELLED WITH THE LITERAL STRING `Library`, WHICH COLLIDES WITH
  ITSELF.** Recorded 2026-08-10. [Full entry](research/backlog/act.md)
- **(acy) THE NAMING LAYER - characterised across four rounds, measured against what already ships,
  and deliberately NOT built.** Recorded 2026-08-11. [Full entry](research/backlog/acy.md)
- **(acv) THE PRIVATE PATHS IN GIT HISTORY ARE ACCEPTED, NOT OVERLOOKED - and the repository goes
  private at launch.** [Full entry](research/backlog/acv.md)
- **(acu) POI LOOKUP FROM GPS - the strongest form of location naming, measured and NOT built.**
  Recorded 2026-08-11. [Full entry](research/backlog/acu.md)
- **(acp) GPS-DERIVED TIMEZONE - understood, costed, and deliberately NOT built.** [Full
  entry](research/backlog/acp.md)
- **(aco) A STILL WHOSE CAMERA WROTE UTC INTO `DateTimeOriginal` LANDS ON THE WRONG DAY.** Recorded
  2026-08-10. [Full entry](research/backlog/aco.md)
- **(acn) DOES A GPS FIX TIME COUNT AS CAPTURE EVIDENCE? A RULING, NOT A BUG.** [Full
  entry](research/backlog/acn.md)
- **(adf) A CLI-ORGANIZED LIBRARY LEAVES `path_hint.library` UNSET, so the app has no observed
  destination to prefill.** [Full entry](research/backlog/adf.md)
- **(aci) A DELETED DECISION BLOCKS DRIVE SAVES UNTIL A RESTORE RECONCILES THEM.** Recorded
  2026-08-09. [Full entry](research/backlog/aci.md)
- **(acg) ALBUM MEMBERSHIP CANNOT LEAVE THIS MACHINE - the same class as `(ack)`, waiting.**
  Recorded 2026-08-09. [Full entry](research/backlog/acg.md)
- **(acc) `write_decisions` exists with ZERO CALLERS, so no decisions document has ever been
  written.** ⚠ **Retitled 2026-08-22**: the old title asked about *finding* one, which understates
  it - nothing writes one either. The file format is built, atomic and tested; **the write trigger
  is not**, nor is the first-run-after-upgrade write aimed at the user most at risk. Corrected in
  the entry 2026-08-09 after *"Stages 1-3 landed"* proved to be half of Stage 3. Recorded
  2026-08-09. [Full entry](research/backlog/acc.md)
- **(aca) The app and the CLI disagree about when an organize run needs confirming.** [Full
  entry](research/backlog/aca.md)
- **(aby) Organize screen: copy that repeats itself or explains its own button.** [Full
  entry](research/backlog/aby.md)
- **(abz) Organize shows one population three ways and connects none of them.** [Full
  entry](research/backlog/abz.md)
- **(abw) An already-named trip is re-asked, and until this commit the answer was discarded.**
  ⚠ **Findings (1), (2) and (4) are closed; (3) is open and, since 2026-08-15, a FEATURE question
  rather than a defect** - an attempt at it is preserved unmerged under the tag
  `preserved/abw-finding-3` (peels to `66f6c22`; was a branch until 2026-08-15). [Full entry](research/backlog/abw.md)
- **(abs) The ghost-drive rule refuses REGISTRATION and warns nobody else.** [Full
  entry](research/backlog/abs.md)
- **(abt) The unhinted-residue prompt is CLI-only, because the app cannot ask mid-job.** Recorded
  2026-08-07. [Full entry](research/backlog/abt.md)
- **(abr) `rcRunArchives` passes no `onRefuse`, so a refused start would throw.** [Full
  entry](research/backlog/abr.md)
- **(abn) rescan, beyond the report. `truestill rescan` REPORTS; nothing acts on it yet.** Recorded
  2026-08-07. [Full entry](research/backlog/abn.md)
- **(abd) ONE CATALOG OR MANY - the question is unanswered, and it may be the wrong default.**
  Recorded 2026-08-05. [Full entry](research/backlog/abd.md)
- **(abe) CLI custody was fixed forward the same day; REPAIRING PRE-EXISTING ROWS IS THE OPEN
  HALF.** ⚠ **Retitled 2026-08-22** so the built half is not read as pending:
  `cli._register_destination` landed 2026-08-05 in `a0091cf`, gated on `--apply`. Rows written
  **before** that still carry no copy row, so they stay outside custody and invisible to
  `verify`, `status` and `where`. Recorded 2026-08-05. [Full entry](research/backlog/abe.md)
- **(abf) A fix does not retroactively clean what it prevented.** Recorded 2026-08-05. [Full
  entry](research/backlog/abf.md)
- **(abg) The reassured state has no notion of staleness - "Schrodinger's backup".** 📌 **read the
  entry first - a premise inside it was corrected.** **Stages 1-3 have shipped**; what remains open
  is the `GONE` state, which is unbuilt and unruled. Recorded 2026-08-05. [Full
  entry](research/backlog/abg.md)
- **(abm) Attach counts three things and shows none of them.** `unreadable`, `unmatched` and
  `unreadable_dirs` are all computed and tested, and not one of them reaches a screen. Recorded
  2026-08-06. [Full entry](research/backlog/abm.md)
- **(abk) The library has no per-folder view - "where is all this actually sitting".** [Full
  entry](research/backlog/abk.md)
- **(abj) Find matches one substring; a two-word query silently finds nothing.** [Full
  entry](research/backlog/abj.md)
- **(abc) `check_product_name.SUBCOMMANDS` should be derived, not transcribed.** [Full
  entry](research/backlog/abc.md)
- **(abb) The other capture-filename conventions.** `rule_camera_filename` shipped with ONE
  pattern, Android's `IMG_`/`VID_`; the other vendors' conventions are unbuilt. Recorded
  2026-08-03. [Full entry](research/backlog/abb.md)
- **(aba) Nothing reconciles the catalog's recorded location with where a file actually is.** [Full
  entry](research/backlog/aba.md)
- **(aaz) `ModifyDate < DateTimeOriginal` as a back-dating signal. RECORD ONLY - do not build.**
  [Full entry](research/backlog/aaz.md)
- **(aay) JPEG XL (`.jxl`) is classified as unrecognized. RECORD ONLY - do not build.** [Full
  entry](research/backlog/aay.md)
- **(aax) `time_known` is derived from provenance, not from the value. POST-LAUNCH.** [Full
  entry](research/backlog/aax.md)
- **(aan) A "verified against code" clause must still resolve.** Recorded 2026-08-01. [Full
  entry](research/backlog/aan.md)
- **(aas) An undated file cannot be assigned to an event the user knows it belongs to.** Recorded
  2026-08-02. [Full entry](research/backlog/aas.md)
- **(aau) A zero-warning test lane, and why it is not one today.** Recorded 2026-08-02. [Full
  entry](research/backlog/aau.md)
- **(aai) The plain copy path does not verify at write time.** Recorded 2026-07-31. [Full
  entry](research/backlog/aai.md)
- **(aaf) Persisted skip record - "show me what was skipped last week".** [Full
  entry](research/backlog/aaf.md)
- **(aag) Near-duplicate grouping and burst review.** A review surface over behaviour that is
  already correct - record only, do not build. Overlaps `(m)`. [Full entry](research/backlog/aag.md)
- **(aad) Desktop installers - LAUNCH-BLOCKING for the paid product.** [Full
  entry](research/backlog/aad.md)
- **(aac) Organize names unreadable source files; ONE RESIDUE REMAINS, and it is app-side.**
  ⚠ **Retitled 2026-08-22 - the bare title read as a whole unbuilt feature and two thirds is
  built.** Scan tier and residue 1: built 2026-08-02. **Residue 3 closed by `(aev)` on 2026-08-21**
  and nobody connected them - `FileHashes.perceptual_computed` plus `uncompared_photos` are exactly
  the *"readable but undecodable is indistinguishable from a video"* distinction it asked for.
  **What is left is residue 2 alone**: `unreadable_files` is built in `organize_preview` only, so
  the app's **run** completion cannot name a file the CLI names. [Full
  entry](research/backlog/aac.md)
- **(ss) Organize preview hashes every file before showing anything - slow on a network mount.**
  [Full entry](research/backlog/ss.md)
- **(xx) Absolute-path columns and hash-cache keys are not machine-portable.** [Full
  entry](research/backlog/xx.md)
- **(aap) Registering a folder does not mint a second identity - BUILT 2026-08-02, ONE SURFACE
  LEFT.** ⚠ **Retitled 2026-08-22.** The row sat under *"still to build"* while the entry's own
  first line said **BUILT 2026-08-02**; the guard that prevents the loss is shipped on the CLI.
  What remains is deliberate and named in the entry: **the app has no register screen**, so the
  protection has no app-side surface. [Full entry](research/backlog/aap.md)
- **(bbb) exiftool `_original` backups.** Mostly BUILT - safety 2026-07-30, recovery 2026-07-31;
  recovery item 4 is the PARTIAL remainder. [Full entry](research/backlog/bbb.md)
- **(nn) Prove destination timestamp parity against a live rclone remote.** [Full
  entry](research/backlog/nn.md)
- **(r) Analyze mode - the hash cache half is SHIPPED.** [Full entry](research/backlog/r.md)
- **(kk) Persist GPS at ingest - it is read and then thrown away.** 📌 **read the entry first - a
  premise inside it was corrected.** [Full entry](research/backlog/kk.md)
- **(ll) Sub-day event identity that survives a changing file set.** [Full
  entry](research/backlog/ll.md)
- **(aam) Sidebar reference: profile header, section labels, submenus.** [Full
  entry](research/backlog/aam.md)
## Settled technical stances (recorded so they are not re-litigated)

- **(aat) `(aar)` is forward-only, and `migrate-layout` will not carry it backwards.** [Full
  entry](research/backlog/aat.md)
## Product / strategy (parked decisions)

> **Settled stance these sit under:** a user's **photo data never leaves their machine** and
> there is no telemetry. Pro is gated by a **signed local token** obtained at a one-time account
> activation - `docs/DECISIONS.md` **D5**, which supersedes D1's no-accounts stance on the maintainer's
> ruling. Any Pro-tier item below inherits that constraint, and none of the licensing
> infrastructure is built yet.

- **Web dedup teaser.** A Pro-tier positioning idea (a lightweight web-facing "find your
  duplicates" hook); not started. Reference stack proven in PixSort's browser mode, all
  **client-side - nothing is uploaded**: `exifr` (image EXIF), `mediainfo.js` (WASM, video
  dates), `hash-wasm` (BLAKE3 hashing in the browser). PixSort's `lib/metadata.ts` and
  `lib/hash.ts` (present under both `frontend/` and `apps-platform/`) are the reference
  implementations to study when we build this.
- **Desktop UI: Tauri vs local-web.** Parked architecture decision. The Rust-backed Tauri path
  informed the SHA-256/no-BLAKE3 hashing choice; the event-review interaction is the feature
  that will ultimately force the decision.
  - **(o) Lessons from the PixSort audit** (`PixSort/AUDIT_REPORT.md`): whatever wraps the UI,
    **one process serves the real UI**, bound to **loopback only**, and there is **never a second
    framework runtime beside the Python core**. PixSort's Electron+Next.js shell ran a whole JS
    runtime alongside the backend - the coupling and bundle weight it caused is exactly what
    truestill's single-process, server-rendered, no-build local-web UI avoids. A native shell (if ever
    built) wraps that one process; it does not add a second app runtime.

## Converged programs (do not pick in isolation)

These are not duplicates to delete - they are **one job split across lettered items**. Anyone
picking one up must map the combined order before building.

- **Date provenance → honesty → rescue → optional `_original`.** Items: **`(n)`**, **`(ii)`**,
  **`(bbb)` recovery**, and **`(kk)`'s `GPSDateStamp`** (lat/lon on `(kk)` also serves
  places/map, but the stamp is this program's cross-check). **One program, now partly built -
  check each step before starting it:**
  **PROGRAM COMPLETE 2026-07-31**, with one clause carried out as `(aaj)` - see `(bbb)` item 4.
  **`(n)` and `(ii)` are built and now live in [`SHIPPED.md`](SHIPPED.md)**; `(bbb)` is still
  here because its recovery half is partial, and `(kk)` is still here because none of it landed.
  This block stays in `BACKLOG.md` because it is an instruction to whoever is about to build,
  and it is the one place the program is numbered end to end.

  1. ✅ **Done.** Persist a durable date-provenance column: `files.date_source` (**v13**) and
     `date_tag` (**v14**), written by `record_uploaded`, worded once in `date_explain.py`.
  2. ✅ **Done.** Honesty view (`(n)`): the provenance **mix** ships in `service/stats.py`, and
     since step 5 each tier drills down to the files in it, each carrying the sha256 the rescue
     is keyed on.
  3. ✅ **Done.** Rescue (`(ii)`): stored durably, survives every whole-disk operation
     (`date_confirmations`, **v15**; O4 tested by name), and **reachable** since step 5 -
     `POST /api/dates/confirm`, app-only by recorded deferral.
  4. ✅ **Done.** `_original` offer (`(bbb)` recovery): same surface, same `human-confirmed`
     tier, never a parallel tool and never a silent substitution. Item 4's "optionally note the
     embedded conflict" clause was **decided against** - see `(aaj)`, now out of scope.

  Also not started: **`(kk)`'s `GPSDateStamp`** - verified 2026-07-31, the catalog has no
  latitude/longitude columns and no `GPSDateStamp`, so no part of `(kk)` has landed.

  Building an unbuilt slice alone still builds half a screen; **starting a built one rebuilds a
  shipped schema.** Steps 1 and 2 read as unstarted in this file until 2026-07-31.

- **Empty-folder leftovers.** Already shipped as one capability - see **Empty-folder cleanup**
  (provenance `(rr)` / `(zz)` / `(eee)` Commit 4).

- **Walk-and-classify on a drive.** `(hh)` (`adopt`) shares machinery with shipped `clean-empty`;
  map that reuse when `(hh)` is chosen - do not invent a second walker.

- **Preview cost / progressive disclosure.** `(tt)` + `(u)` Built; remaining is measured
  `(ss)` work and `(r)` Analyze (richer dry-run report, not a cheaper pass).

- **Loud failure vs portability for absolute paths.** `(ww)` Built; `(xx)` / `(yy)` remain the
  portability + reconnect half of the same family.

- **LayoutScheme axes.** `(gg)` Built (adaptive day folders); `(y)` / `(z)` are further axes on
  the same seam - do not rebuild routing.

## Ideas / deferred

> **Sequencing note - several of these share machinery, and picking them one at a time is the
> expensive order.** See **Converged programs** first. `(n)` and `(ii)` (and `(bbb)` recovery /
> `(kk)` GPSDateStamp) are one date-provenance program; `(hh)` (`adopt`) shares the
> **walk-and-classify** machinery with shipped `clean-empty`. When the first of a cluster is
> chosen, map a combined order before building - the schema step and the UI surface are each
> worth paying for once.

- **(aal) How often is the machine wrong about dates, and about what?** Recorded 2026-07-31. [Full
  entry](research/backlog/aal.md)
- **(m) Duplicate-cleanup staging UX.** The visual side-by-side compare it describes IS `(aag)`'s
  subject - scope the two together or the same review surface gets designed twice. [Full
  entry](research/backlog/m.md)
- **(p) "Share safely" - metadata-stripping export. PRO TIER (behind the capability seam).** [Full
  entry](research/backlog/p.md)
- **(x) XMP sidecar export for user-generated context.** Trip and event names are the only
  user-created thing in a library, and the only thing lost on leaving truestill. Post-launch. [Full
  entry](research/backlog/x.md)
- **(hh) `truestill adopt` - bring stray media in an organized drive into the catalog.** [Full
  entry](research/backlog/hh.md)
- **(aao) Asset pairing: several files that are one photo.** Names the concept `(y)`, `(p)` and
  `(aag)` were each circling: several files that are one photo. Needs a design pass before any
  build. Recorded 2026-08-02. [Full entry](research/backlog/aao.md)
- **(aaq) `rule_software` reads a tag that is never requested, so it cannot fire.** [Full
  entry](research/backlog/aaq.md)
- **(y) Optional photo / video split - default TOGETHER, and pair-aware or not at all.** [Full
  entry](research/backlog/y.md)
- **(z) Optional source / device manifest - catalog-first, hash-keyed.** [Full
  entry](research/backlog/z.md)
- **(s) Source-folder names as event evidence.** A meaningful source folder name (`Olympics/`)
  becomes a pre-named event proposal instead of scattering by capture date. [Full
  entry](research/backlog/s.md)
- **(t) Reflink / copy-on-write fast path.** `FICLONE`/`clonefile` on APFS, btrfs, XFS, ReFS.
  Optimization, not correctness - `copy2` already takes `sendfile` fast paths today. [Full
  entry](research/backlog/t.md)
## App-surface deferrals

Copy / Move / Reorganize-in-place and `undo-organize` are **in the app** - see **`(eee)`**.
What remains CLI-only shares one reason: each is a **space-safe or irreversible** operation
whose failure mode is permanent, and GUI demand is still judged from soak / launch feedback
rather than assumed.

- **The date rescue (`confirm_file_date`) is APP-ONLY**, recorded 2026-07-31 when step 5 made it
  reachable. A rescue is review-shaped - look at a photo, judge it, correct it, with the evidence
  in front of you - which is what the honesty view already is. A CLI equivalent would need file
  addressing by hash or path and would be used for bulk correction: a different, more dangerous
  feature that wants its own design. **Written down explicitly rather than left implicit**,
  because `test_surface_parity.py`'s second blind spot is a surface that omits a key entirely,
  so an undocumented single-surface contract is indistinguishable from drift.

- **`truestill reclaim`** stays **CLI-only** until an app surface is explicitly approved. When
  one does get a surface, the pre-approved shape is advisory same-device detection plus a typed
  confirmation identical to the CLI's.
- **`{camera_model}` layout token** -- demand **re-confirmed by the user** during the soak
  era. Stays **deferred / Pro-tier candidate** as originally recorded in
  `org-structure-research.md` (§C1 "explicitly NOT v1 tokens"): it needs device metadata
  plumbed into the template render context. Recorded here so the re-confirmation is not lost
  the next time the token list is reviewed.

## Consciously out of scope (recorded with reasons)

- **A JavaScript FORMATTER, permanently. Ruled 2026-08-10 after measuring Biome 2.5.7.**
  Running it once would rewrite `app.js` wholesale - **3,733 source lines, 5,665 differing** - and
  `app.css` and `tokens.css` with it.
  - ⚠ **The cost lands on documentation that no test protects.** `docs/` carries **314**
    `file:line` references, of which **65 point into files the formatter would rewrite** (45 into
    `app.js` alone). Among them are `(abg)`'s, `(acd)`'s, `(acq)`'s, and several `ENGINEERING_STANDARD.md`
    §4 members written that week.
  - **Nothing would tell us.** Checked: **no test or guard asserts a line number.** Every
    `node.lineno` in the suite builds an error *message* (`test_absolute_imports`,
    `test_patch_targets_stay_aimed`, `test_subprocess_has_one_home`, `test_preview_gate_holds`);
    one docstring mentions `index.html:102`. So a reformat is green on every lane and silently
    invalidates 65 pointers.
  - **The benefit is consistency in a file one person edits**, and the cost includes routing every
    future `git blame` on `app.js` through one formatting commit. Not a close call.

- **Biome as a DEPENDENCY. Ruled 2026-08-10; the findings were taken, the tool was not.**
  A one-off `biome lint` run over `static/` and `templates/` found **90 diagnostics in 179 ms**:
  36 `useButtonType`, 16 `useOptionalChain`, 10 `noUnusedVariables`, 8 `noDescendingSpecificity`,
  6 `useTemplate`, and singles elsewhere. **Roughly 84 were opinions and 4 were real** - the four
  were fixed by hand in the commit that records this, with no Biome in the tree.
  - **Against adoption:** **63-80 MB per platform** (linux-x64 63.3, darwin-arm64 55.6, win32-x64
    79.6) across four CI lanes and three operating systems, as the **second** non-Python tool in a
    Makefile that has one; and our template **does not parse at all** without a committed
    `biome.json` enabling `html.parser.interpolation`, because Biome rejects `{{STALE_WARNING}}`.
    Adoption therefore starts with config, not with a binary.
  - **The 36 `useButtonType` findings stay unfixed, deliberately.** A `<button>` defaults to
    `type="submit"`, which only misbehaves inside a form - and there are **zero `<form>` elements
    in the app** (checked, not assumed: 0 in `index.html`, 0 in `app.js`). Inert today, real the
    day someone adds a form. **That check is the durable artifact here**, not the finding.
  - **Not a refusal of static analysis for the browser.** If it is revisited, the honest shape is
    a *small enabled rule set* - the a11y group, plus `suspicious/noDuplicateCustomProperties` -
    with `--formatter-enabled=false`, never the default 517 rules, which would mean fixing ~84
    non-defects or maintaining a suppression list as its own surface.

Not "not yet" -- decided **against**, so the question does not get re-litigated every time a
neighbouring product ships one. Each would be a reasonable feature in a different product.

- **A `warnings` field on `MigrationApplySummary`.** Found and **decided against 2026-07-31**,
  while closing the §9 gap where a missing exiftool degraded a migration silently. Recorded so
  it reads as a boundary someone chose, not a corner someone missed.
  - **What is still silent, precisely.** `migration_preview` surfaces the "folder names could
    not be checked against the files" warning through `warnings`, which the UI already renders,
    and the CLI prints it before the plan. `migration_apply` re-derives the same rules and has
    nowhere to put the reason, so a **direct apply without a preview** would degrade silently.
  - **No shipped flow performs that call.** The UI previews and shows the warning *before* the
    user confirms; `truestill migrate-layout` prints it in the same invocation that then
    applies. The silent path is reachable only by calling the service function directly, which
    is not a user flow.
  - **The cost is out of proportion to the case.** Closing it reaches the `TypedDict`, the
    payload construction, and the JS render - a public surface change, for a state nothing
    currently produces.
  - **What would make it worth doing:** *a caller that applies without previewing.* An API
    client, a scheduled or unattended migration, or a UI change that lets a user re-apply from
    a stored plan. Any of those turns this from unreachable into a real silent degradation, and
    the fix should land with that caller rather than in advance of it.

- **Cloud storage reached over a web API rather than a mounted filesystem `(aav)`.** Recorded
  2026-08-02. **A scope decision, not a limitation** - it follows directly from the product's
  promise that files stay readable without Truestill, in ordinary folders on the user's own disks.
  - **What works: anything the OS presents as a path.** Internal and external drives, NAS over SMB
    or NFS, and pCloud / Dropbox / OneDrive **mounted as a drive**. Truestill opens paths and does
    not care what is behind them, which is why the supported list needs no maintenance.
  - **What does not, and why it is a different product.** Google Drive API, S3, iCloud web. These
    are not filesystems: each needs a provider adapter, an OAuth flow, token refresh, rate
    limiting and its own failure taxonomy - and none of that makes anyone's photos more durable.
  - **Mounted is not local, in performance.** A FUSE or NAS path pays a round trip per file across
    tens of thousands of them. Projected from a measured 5 GB sample: for a 33,457-file library,
    network I/O dominates CPU by **3.6x to 36x** at every plausible transfer rate, so the mount
    decides the runtime and the pipeline does not. See `(ss)` and `PERFORMANCE.md` §3.0.
  - **Mounted is not always present, either.** A drive can vanish mid-run, which is what the
    `.truestill-drive.json` marker and `DriveReach.OFFLINE` exist for, and why identity is the
    marker uuid rather than a path.

- **Migrate verifying against the live copy hash instead of its journal snapshot `(aah)`.**
  Found 2026-07-31 while closing condition 3 of the date-provenance program. **Decided against
  2026-07-31**, after the analysis rather than before.
  - **Live catches no failure the snapshot misses.** On-disk corruption, a partial file from a
    crash, a half-finished relocate - the snapshot catches every one, and so does live, because
    corruption never updates the catalog. Every row where live "wins" is a **false alarm
    avoided, not a detection gained**.
  - **The snapshot is an independent second record; live collapses to self-consistency.** Two
    records that must agree catches a class one record checked against itself cannot - a catalog
    value that drifted from the bytes, or a row that now describes a *different* file after a
    re-organize. That is the same defect as `(aai)`: **a hash read from the thing it validates
    is not a check.** It is also what "a resume knows what it expected" buys - a resume finishes
    a plan made earlier, and must not silently re-derive one.
  - **Its entire benefit was already bought.** The only realistic source of the false alarm is a
    bake landing mid-migration, and condition 3 removes it at zero cost to the snapshot: the
    bake refuses while a migration is journalled and unfinished, re-checked before every file.
    `(aah)` would trade a real property away for something already secured.
  - **The hybrid is rejected too.** Accepting the on-disk hash if it matches *either* the
    journalled or the current value tolerates the bake and still catches corruption - but it
    reintroduces the self-consistency hole for exactly the case the snapshot exists to cover.
    *Two records must agree* beats a rule with an escape clause.
  - ⚠ **Reopening condition, deliberately specific:** evidence that the cross-process race
    actually bites - a soak run showing a real stall caused by a legitimate bake. Even then the
    fix is **the on-disk lock, not weakening the comparison**.
    ⚠ **Updated 2026-08-22: that lock now EXISTS.** This clause pointed at `(vv)`, which asked
    for it and has since closed; `(aaw)` shipped it - `flock`/`msvcrt`, per drive, mutating
    operations only. So the reopening condition is unchanged and its remedy is no longer
    hypothetical. The residual and its cost are recorded on `(aaw)`.

- **Noting an embedded-metadata conflict against a human-confirmed date `(aaj)`.** The
  "optionally note the embedded conflict" clause of `(bbb)` item 4. **Decided against
  2026-07-31**, after the design was worked out rather than before.
  - **The disagreement is already surfaced where it matters most**: the three-state card shown
    the moment someone confirms a date says exactly what the file still claims inside
    (*"The file itself still says 2014 inside"*), computed from the row being overwritten. What
    `(aaj)` would add is seeing that **later**, on the honesty view.
  - **Seeing it later needs the prior claim, and `confirm_date` destroys it.** It overwrites
    `captured_at` / `date_source` and sets `date_tag = NULL`; nothing else holds the old values.
    So the feature requires **storing a value the system has already decided is wrong** -
    forever, on every row, with every migration and every `record_uploaded` obliged to reason
    about it - whose only consumer is a line of explanatory text. *A column that exists only to
    be disagreed with* is the reason not to add one.
  - **The alternative was ruled out too.** Re-reading the file is live metadata, which the
    stated constraint forbids, and it inherits `(xx)`: with the drive disconnected it would read
    "cannot check" for most rows most of the time.
  - **The clause said "optionally".** That word was written by someone who already knew this was
    nice-to-have. The human-wins half of item 4 is built, tested by name against all five
    whole-disk operations, and is the half that carries the promise.
  - ⚠ **Do not reopen this to enable a *statistics* feature** - see `(aal)`. That is a different
    question with different requirements, and it is the use that would justify the column.

- **Face recognition / people albums.**
- **Semantic AI search** ("photos of a beach at sunset").
- **Auto-generated Memories / highlight reels.**

- **Per-camera or per-person subfolders inside an event.** It fragments **one memory by
  source** - the same error as an unconditional photo/video split. Four phones at one trip is
  precisely the case where everything should stay together, and splitting by device turns a
  shared afternoon into four partial accounts of it. Device identity is real and worth keeping;
  it belongs in the **catalog**, queryable, not carved into the folder tree - see `(z)`.

- **Conditional `Photos/` + `Videos/` subfolders ("create them only when both are present").**
  A structure must never rewrite itself because one file arrived: adding a single video to a
  618-photo day would force **619 files to move**. That is the same instability that rules out
  date-range folder names, and it is worse here because it triggers on an ordinary import. The
  optional, always-on, pair-aware split remains available as `(y)`.

**Why all three, together:** they are one class -- **ML infrastructure** -- and adopting any of
them changes what truestill *is*. Each needs models shipped or downloaded, a vector store or
embedding index beside the catalog, GPU-or-slow inference, and a retraining/refresh story; that
is a permanent tax on every install, and it lands squarely against the lean, local, no-network,
minimal-dependency identity recorded in `ENGINEERING_STANDARD.md` §1 and
`IMPLEMENTATION_STANDARDS.md` §7. It is also **Immich's and Ente's territory**, where they are
strong and mature: competing there means being a worse version of a server product, while the
thing truestill does that they do not -- custody of files you can still read without it -- goes
unfinished.

The honest framing for a user who wants these: run truestill for organizing and custody, and a
gallery server for browsing and search. They compose. That answer is better than a shallow
imitation of both.
