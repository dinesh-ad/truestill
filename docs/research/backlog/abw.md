# (abw) An already-named trip is re-asked, and until this commit the answer was discarded.

*Body of backlog entry `(abw)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abw) An already-named trip is re-asked, and until this commit the answer was discarded.**
  Three findings, recorded 2026-08-08 while checking a premise for folder-name suggestions. The
  first two are **closed here**; the third is **open and deliberately not fixed**.
  - **(1) CLOSED. Already-named trips are re-offered as cards.** `assemble_trip_review` never
    consults `trip_for_day` - its `claimed_days` set means "claimed by a proposal in THIS run".
    `trip_for_day` is called in exactly two places, both at commit time. Proven against the real
    catalog: it holds `('Wayanad', 2014-08-14, 2014-08-17)` and the card is offered anyway.
  - **(2) CLOSED. The screen could not tell.** `ReviewCardPayload` carried no name, so the card
    rendered an empty box indistinguishable from an unnamed one. It now carries `existing_name`,
    from `Catalog.named_trip_days()` (one read, O(claimed days), keyed by DAY so it survives the
    reordering merge and split do). The card shows the name as **text, not a field**, and says
    renaming is not available there - a question that is asked must be answerable.
    - **`existing_name`, not `name`, and the distinction is load-bearing.** The browser already
      uses `card.name` as its own store for what the user has typed (`syncEvNamesFromDom`,
      carried across merge/split by `takeEvNamesByKey`). A catalog name in that field would be
      indistinguishable from something the user wrote, and would be sent back as their answer.
      The plan for this work called that branch "dead"; it is not.
  - **(3) OPEN, AND SINCE 2026-08-15 A FEATURE QUESTION RATHER THAN A DEFECT.** `commit_trips`
    discards a new name for an already-claimed trip.
    `decision.name` is never read on the `update_trip_days` branch, and `update_trip_days`
    documents that name and slug are untouched. Downstream, `apply_event_review_names` reports
    `"name": name.strip()` - what the user typed - so the reveal row would have named a trip the
    catalog had not renamed. Finding (2) removes the way to reach it from the screen; the code
    path is unchanged.
    - **Why it was not simply fixed.** The discard is deliberate and pinned by
      `test_re_ingest_one_photo_into_a_named_trip_does_not_re_ask`, whose docstring says a
      differing name proves "it is ignored, never used to rename". That pins
      `trip-grouping-research.md` §6 *"Trips must not re-ask"*, which exists so a re-proposal -
      recomputed from a fresh scan, knowing nothing about the name - cannot overwrite a name the
      user chose.
    - **The §6 threat model has no instance today, recorded so it is not re-derived.**
      `commit_trips` has exactly one production caller, `service/trips.py`'s
      `apply_event_review_names`, whose names come straight from the screen's `names[]` array and
      are always user-typed. There is no CLI trips path at all - neither `commit_trips` nor
      `assemble_trip_review` appears anywhere in `truestill-cli`. A re-offered card renders an
      empty box, so doing nothing already sends `null`. Every name that reaches the branch is a
      deliberate keystroke. A folder-name suggestion would not change that: the suggestion is
      never prefilled into `value=` and requires a click.
    - 🔬 **ANALYSED 2026-08-15 AGAINST AN ACTUAL ATTEMPT, AND FINDING (3) IS NO LONGER A
      DEFECT - IT IS A FEATURE QUESTION.** A stashed attempt at this fix surfaced after seven
      days and was analysed rather than merged. **It is preserved and pushed as branch
      `wip/trip-rename-finding-3` at `66f6c22`**, named here so it is not rediscovered from
      scratch or found again as an anonymous stash. **It stays unmerged.**
      - **The attempt is coherent and well-guarded, not a sketch.** 148 lines: a
        `Catalog.rename_trip` whose `WHERE id = ? AND name <> ?` makes "did anything change" the
        same statement that changes it, the `commit_trips` branch, and a **106-line test**. Its
        strongest case is the **cry-wolf** one - *a blank reply must never erase a stored name*,
        because a re-offered card arrives empty, so opening the screen and pressing Save would
        otherwise strip every trip in the library of its name. The author guarded the worse
        defect first.
      - ✅ **§6's threat model verified to have NO INSTANCE, 238 commits after this entry claimed
        it.** Re-checked rather than trusted: `commit_trips` has **exactly one** production
        caller (`service/trips.py:502`, inside `apply_event_review_names`), there is **no CLI
        path** (neither `commit_trips` nor `assemble_trip_review` appears anywhere in
        `truestill-cli`), and names arrive as the screen's `names[]` array via `server.py:739`.
        Every name reaching the branch is still a deliberate keystroke.
      - ⚠ **The pinning test conflates two things, and nobody has separated them - not this
        entry, and not the attempt.** `test_re_ingest_one_photo_into_a_named_trip_does_not_re_ask`
        exists, by its own docstring, to catch *"a mutation that skips the 'already claimed' check
        and always re-creates"* - **identity stability**, which is real and must not be weakened.
        The **name-overwrite** assertion is one line inside it, reached by passing a name **no
        production caller can produce**. Those are separable concerns in one fixture; treating the
        whole test as "the §6 rule" overstates what it protects.
      - 🔑 **DECISIVE: THE NEVER-SILENT VIOLATION WAS ALREADY FIXED, THE OTHER WAY.** The attempt
        argues the box was editable so editing it must work. **That box no longer exists.**
        `3ffb8d5` - *"a trip that already has a name says so instead of asking again"*, finding
        (2) above - landed **47 minutes after the attempt's base commit** (`fe5a9ae` 18:12:33,
        `3ffb8d5` 18:59:53, same day) and renders the name as **text, never a field**, labelled
        *"already named - renaming is not available here"*. **Two valid repairs of one defect -
        remove the question, or honour the answer - and one shipped.** So §9 never-silent is
        satisfied today, and finding (3) is no longer a live defect. It is the **feature
        question**: should the screen be able to rename at all?
      - **And `3ffb8d5` was a deliberate reaffirmation, not an oversight.** Its own docstrings say
        *"honouring a rename here is recorded as open rather than assumed safe"* and *"Whether it
        should still hold now that the only caller passes user-typed names is `(abw)`'s open
        question, and it is not settled here."* Someone documented the rule while the attempt sat
        unmerged, knowing both.

    - **THE OPEN QUESTION, which decides the cost rather than the staleness.** ⚠ **Re-checked
      2026-08-15: this is EXAMINED BY BOTH SIDES AND COSTED BY NEITHER**, which is a different
      thing from unexamined and is the state to act on. This entry raises it below; the attempt
      addresses it directly in `rename_trip`'s docstring (*"Renaming does not move files... exactly
      as it does after a layout-template change or after `record_event` renames an event on
      re-commit"*) and names the reconcile path - `copies_for_migration` selects
      `t.name AS trip_name`, **verified at `catalog.py:901`**, so the next migration renders the
      new name and offers the moves. **What no one has done is cost it.** Trips own folder names
      in the layout, so a rename changes the catalog and not the disk, and until a migration runs
      **the screen and the filesystem disagree about what a trip is called**. That must be
      answered before any rename ships. A trip already
      placed on disk spells its old name in every folder path (`2014-08-14 - Wayanad/...`), so
      renaming leaves the catalog and the disk disagreeing until a migration. That is the same
      forward/reconcile split a layout-template change already uses, and `record_event` already
      renames an event on re-commit with exactly this consequence - but it has not been costed,
      and it is what must be answered before the invariant is broken.
    - **(4) CLOSED. The event half of the screen defect.** `existing_name` is now answered for
      event cards from `Catalog.named_event_signatures()`, so an already-named event shows its
      name as text instead of an empty box, exactly as trips do. **"Already named" turned out to
      be two questions**, and deciding which one is asked was the whole job:
      - **Same signature** - the identical file set, already named. The trip bug again: show the
        name, invite nothing.
      - **Different signature** - membership changed, so this is a NEW cluster that merely
        *overlaps* a named one. It is not that event, and it must still be offered a name.
      Collapsing them silences every cluster that ever grew, or claims named-ness for something
      unnamed. Both are pinned, and a mutation that collapses them fails the second case - the
      difference in behaviour is the feature, not an edge of it. `ExistingNames` carries the two
      keyings side by side (day for trips, signature for events) because the two identities
      genuinely differ; it is one object rather than two loose maps so a third does not arrive as
      a third parameter.
    - **EVENTS HAVE THE IDENTICAL DISCARD, AND THERE ARE FAR MORE OF THEM.** This is the larger
      half of the finding, not a footnote to it. `event_review.commit_catalog` reads
      `event_by_signature` first and, when a row exists, takes its id and **never looks at
      `decision.name`** - exactly what `commit_trips` does. `record_event` would have renamed it
      (`ON CONFLICT(signature) DO UPDATE SET name = excluded.name`); it is simply not called on
      that branch. A library has one trip for every several events - the maintainer's own has 1
      trip against 21 clusters - so by volume this is where the discard actually bites, and it is
      **still live**: `ReviewCardPayload.existing_name` is hardcoded `None` for event cards, so
      an already-named event still renders an empty box exactly as trips did before this commit.
      Fixing the event half needs its own reproduction, because event identity is a membership
      hash (`events.signature`) rather than a day: adding one photo changes the signature, so a
      re-offered event is not always the same object. The SCREEN half of that is now closed by
      (4) above; what remains open is the same thing that remains open for trips - `commit_catalog`
      still discards a name for an existing signature, and nothing on the screen reaches it.
    - Work in progress exists for this and is preserved, not discarded: a `Catalog.rename_trip`
      that decides "did anything change" in its own `WHERE` clause, plus five tests including the
      one that matters - a blank reply must never erase an existing name, or a bare Save would
      strip every named trip in the library.
