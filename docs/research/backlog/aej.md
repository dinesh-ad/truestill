# (aej) SOAK: FOUR CUSTODY SURFACES STATE SOMETHING TRUE OF ONE POPULATION AS IF IT WERE TRUE OF ANOTHER.

*Body of backlog entry `(aej)`, under **Shipped**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aej) SOAK: FOUR CUSTODY SURFACES STATE SOMETHING TRUE OF ONE POPULATION AS IF IT WERE TRUE OF
  ANOTHER.** Found 2026-08-20 by the first soak. **All four are the `(abg)` class** - history
  reported as state, or one set's number printed under another set's sentence - and they are filed
  together because the fix for each is the same kind of thing: say which set you mean.

  ## ✅ THREE FIXED 2026-08-20; THE FOURTH SPLIT OUT AS `(aem)`

  **The split is itself the finding, and it answers "one defect or four".** (1) and (2) are one
  defect - the same line of `cli.py`, the same row object, both numbers already returned by
  `list_drives` and neither read. (3) is its own, a scope label that does not carry down. (4) is
  its own **and is a different kind**: there is no record that a copy-mode run started, so no
  wording repairs it. It is `(aem)` and needs a design.

  They shared a **symptom** - a true statement about one population read as a statement about
  another - never a mechanism. Filing them together was right for reporting and wrong for fixing.

  ## (1) `LAST VERIFIED: never`, SIXTEEN SECONDS AFTER A VERIFY THAT FOUND THE PROBLEM ** sharpest **

  Deleted 7 organized files by hand, ran `verify`. It reported `verified 4098 / MISSING 7` and
  **named all seven paths correctly**. Then `drives` said:

  ```
  D3   4105   11649.2   connected   2026-08-20T09:06:46   never
  ```

  ⚠ **"never" is the one word that is not true.** The underlying rule is right and deliberate -
  `refresh_drive_verified` leaves NULL unless *every* copy is confirmed, so the drive cannot claim
  a date it has not earned (`(abg)` Stage 2, "structurally incapable of over-claiming").
  **The defect is the rendering:** `(d['last_verified'] or 'never')` collapses two states into one
  word - *no check has ever run* and *a check ran and could not confirm everything*. The second
  needs attention; it is displayed as the first, which needs none.
  ⚠ Same shape as `(aeb)`: a null meant two things and the surface chose the reassuring reading.

  ## (2) THE CLI `drives` TABLE DROPS A SHORTFALL IT ALREADY COMPUTES

  `list_drives` returned `D3 | 4105 | missing_count=7 | missing_at=2026-08-20T09:06:46`. Its own
  docstring states the intent: *"a drive reads '2,269 recorded, 2,269 not found on 11 Aug'"*.
  ⚠ The CLI's columns are LABEL / FILES / SIZE(MB) / STATUS / LAST SEEN / LAST VERIFIED - **no
  missing column**. Seven files are known gone and `drives` prints only `4105`. The app has this as
  `driveNotFoundNote`; **the CLI never got it**, so the surface whose entire job is the per-drive
  summary is the one that omits the shortfall.

  ## (3) "none of these files carries a capture date" - FALSE, AND SELF-CONTRADICTORY

  Re-organizing an already-organized source printed, verbatim:

  ```
    date sources (organized files):
    capture dates      : none of these files carries a capture date
        undated x0
  ```

  4,111 files were analysed and they **do** carry dates - the same set reported `exif 3793`,
  `inferred_local 2`, range 2013-08-30 to 2020-12-31 on the first run.
  ⚠ Two defects in three lines: the sentence is **false** about *"these files"*, and it
  **contradicts `undated x0` directly below** - if none carried a date, undated would be 4,111.
  The scoping label *(organized files)* sits on the line above and does not carry down, and the
  block mixes scopes throughout: `files analysed 4111` and `largest files 4,111 sized` are the
  analysed set; the date lines and `folders derived 0` are the organized set (which was empty).

  ## (4) AN INTERRUPTED, HALF-POPULATED LIBRARY READS AS AN ORDINARY HEALTHY ONE

  A `kill -9` mid-organize left 340 of 4,105 files. Between the kill and the restart, `drives` said
  `D3  340  611.4  connected` and `status` reported normally. **Nothing said a run had been
  interrupted**, that 3,765 files were missing, or that this was half a library. The catalog was
  internally consistent and therefore serene.
  ⚠ Every number was true. The reader's question - *"is this backup finished?"* - is not one any
  surface answers, and `340 files, connected, never checked` is indistinguishable from a small
  library that is complete.
  ⚠ **The restart was silent too:** it printed `3765 organized / 346 duplicate, skipped`, the shape
  of an ordinary run, and never mentioned the interruption or the `.partial` file it cleaned up.
  Correct outcome, no record - against §9's never-silent rule, a recovered partial write is exactly
  the sort of event that should be counted and named.

  ## UNCONFIRMED, RECORDED SO IT IS NOT LOST

  ⚠ Progress output interleaved mid-sentence into the summary prose:
  `VID_20140817_102145.mp4  04:54:24 -> 10:21:45  (+05:30, filename)  organizing: 769/4111`.
  **Observed with stdout PIPED only**; not reproduced on a terminal, where carriage-return progress
  may render cleanly. Do not treat as confirmed without a tty check.
