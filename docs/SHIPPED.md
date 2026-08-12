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
  - **The open questions are answered.** `platformdirs` **is** justified in writing, at the top
    of `app_paths.py`, against the stdlib alternative as `ENGINEERING_STANDARD.md` §4 requires.
    An existing `reports/catalog.sqlite` is **adopted, never orphaned**. The filename stayed
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

- **(aaq) PARTLY CLOSED 2026-08-12: the `SamsungModel` half deleted, and the class given a
  detector. The `rule_software` half is the maintainer's and stays open.**
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
