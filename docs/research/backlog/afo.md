# (afo) A FOLDER THAT REFUSED IS REPORTED AS ONE WITH SOMETHING IN IT.

*Body of backlog entry `(afo)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afo) SPLIT OUT OF `(afa)` ON 2026-08-22.** Small, self-contained, and **worse than silence**:
  the other two sites in `(afa)` said too little, this one asserts something false.

  ## MEASURED, VERBATIM

  A folder whose parent refuses, in a `clean-empty` plan:

  ```
  LEFT ALONE - something is in there (1):
    Camera/2013   []
  ```

  Two contradictory claims on one line. The heading says **something is in there**; the bracket
  says **nothing is**. The truth is neither: Truestill could not look.

  ## CAUSE

  `cleanup.py:185-186` classifies a refused folder as `Tier.OCCUPIED` with `contents=()`, and
  `cli.py:3553-3555` renders every occupied candidate as `{relative}   [{contents}]`.

  ⚠ **The classification is right and the rendering is what is wrong.** `OCCUPIED` is exactly the
  correct *decision* - the folder is not removable, and the comment at `cleanup.py:178-183` argues
  it well: *"a folder that is gone was dealt with; a folder that will not answer was not"*. The
  tier carries two meanings - *"I looked and something is there"* and *"I could not look"* - and
  the report renders only the first.

  ## NOT DECIDED

  - **A third tier, or a flag on the candidate.** A tier means every `match` over `Tier` must be
    revisited; a flag means `OCCUPIED` keeps one meaning and gains an adjective.
  - **What the line should say.** *"could not be read"* is the obvious shape and matches the
    vocabulary `(aer)` settled for folders - which is a reason to prefer it over inventing another.
  - ⚠ **Whether the empty bracket should ever print.** `[]` beside any folder is noise; it reads as
    a fact about contents even when contents are unknown.

  ---

  # FIXED 2026-08-22. A field, not a fourth tier.

  ## What a user now reads

  ```
  LEFT ALONE - something is in there (1):
    Camera/2023/10   [loose-photo.jpg]

  LEFT ALONE - could not be opened (1):
    Camera/2023/09
  ```

  Two headings, because one could not be true of both. **No bracket on the second**: there are no
  contents to name, and an empty one reads as a claim that there are none - which was half of the
  original defect.

  The wording is `(aer)`'s, not a fourth phrase for one fact: `models.py` already says *"folders
  that could not be opened"* and `cli.py` already prints *"folder, could not be opened"*.

  ## ⚠ A FIELD, AND THE REASON IS A TRAP IN `removable`

  `Candidate.removable` is defined **negatively** - `tier is not Tier.OCCUPIED` - so **any tier
  added later is removable by default**. A fourth member for "unreadable" would have put a folder
  that refused into `plan.removable` and handed it to `run_cleanup`: the exact inversion this entry
  exists to prevent, introduced by the fix for it.

  `OCCUPIED` was already the right *decision*, argued at `cleanup.py:178-183`. What was missing was
  the *reason*, and a tier cannot carry it without carrying the decision too.

  **Pinned**: `test_a_refused_folder_is_never_removable_however_the_tiers_change` asserts the
  property rather than the tier, so it fails the day a member is added without editing `removable`
  - the only moment anyone would find out.

  ## ⚠ NOT INFERRED FROM `contents == ()`

  It is exact today: every other `OCCUPIED` return builds its contents from a non-empty list, so
  `OCCUPIED and contents == ()` means *could not look*, precisely. **By accident.** A sentinel
  carrying a second meaning is the shape `(afa)` was filed about, and it would have made every
  future reader re-derive the invariant instead of reading it.

  ## Two producers, and neither test covers the other

  * `plan_cleanup` - the folder itself will not `stat` (`reach` returns `REFUSED`).
  * `_classify_with` - it stats and `iterdir` raises. A folder with `--x`: traversable, not
    listable.

  ⚠ **The second had NO test - only a mention in the other file's prose.** It has one now, and the
  two were mutation-proved separately: regressing producer 1 kills one test, regressing producer 2
  kills a different one, so a fix at either alone cannot make the other pass.

  **The causes are deliberately not distinguished.** Same fact, same action, same sentence - and an
  enum of causes invites a third member, which re-enters the `removable` trap above.

  ## The app carries the field although nothing reads it yet

  `clean_empty.py` already shipped `contents` for every occupied candidate, and `app.js` has no
  reference to `occupied` - so the falsehood was CLI-only. The payload now carries `readable`, so
  the day a screen renders that list it cannot inherit *"something is in there"* beside an empty
  one. **No browser lane**: nothing a renderer reads was removed or renamed, and no surface reads
  the list today.
