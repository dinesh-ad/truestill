# (afa) `unreachable` MEANS FOUR THINGS, AND THE TOOLTIP ASSERTS ONE OF THEM.

> ⚠ **NARROWED AND RETITLED 2026-08-22, after a read-only pass that falsified this entry's own
> thesis.** It read *"A PATH THE PRODUCT KNOWS WAS REFUSED IS STILL NOT REPORTED TO ANYONE"* and
> covered three sites. Two are now their own letters, and one of the three claims below was simply
> untrue. What remains is `date_rescue` alone. See **"THE CENTRAL GUESS, FALSIFIED"** at the end -
> that section is worth more than the fix.

*Body of backlog entry `(afa)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afa)** "WE DETECTED IT AND SAID NOTHING" IS A DIFFERENT STATE FROM "WE COULD NOT TELL".
  Filed 2026-08-21 while closing `(aey)`, from the sites that were in front of us.

  ## WHAT CHANGED, AND WHY THIS IS NOW A GAP RATHER THAN A LIMIT

  Before `(aey)`, two sites could not reliably distinguish a refused path from an absent one - the
  stdlib handed them one answer. After it, `path_reach.reach` returns `Reach.REFUSED` and both
  sites **branch on it explicitly** and then say nothing:

  - `service/date_rescue.py` - a sidecar on an unreadable mount is skipped. Correct: reporting
    *"no original"* would be false. But the user is told nothing at all about that photo.
  - `drive_adoption.py` - a refused sample is not counted as evidence. Correct, and it is why the
    presence tally cannot be quietly poisoned. But the resulting verdict does not say how much of
    the sample it could not look at.

  A limitation became a decision, and the decision is currently *stay silent*.

  ## ⚠ THIS IS `(aer)`'s SHAPE, AND THAT IS NOW THREE INSTANCES

  A fact the product holds and does not render:

  1. `(aac)` - unreadable **files**, whose reason was destroyed by `FileHashes(None, None)`.
  2. `(aer)` - hidden and unreadable **folders**, named by `analyze` and dropped by `organize`.
  3. **this** - refused **paths** at two more surfaces.

  Three is a pattern rather than a coincidence, so the fix is probably **one decision about how
  refusal is reported everywhere** - a single vocabulary, worded once in `models` the way
  `folder_skip_remedy` and `uncompared_remedy` already are - and not three separate wordings
  invented at three call sites. Starting from the wording would be a mistake here; starting from
  *what a person does about it* is what made `(aer)` work.

  ## ⚠ WHY IT WAS NOT FOLDED INTO `(aey)`

  `(aey)` is a defect fix: 3.14 made five sites answer a question they were written to refuse to
  answer. Restoring that is the whole job. Surfacing refusal is a **user-facing change** with a
  payload field, wording and a browser render, and folding it in would put a defect fix and a
  feature in one diff, so a revert takes both.

  **`drive_adoption` is the specific reason to hold.** Its verdict is something a user acts on -
  *is this drive my library?* - and adding an `unreadable` count beside a presence tally changes
  what that decision looks like on screen. That deserves its own wording ruling, not a paragraph
  inside a pathlib fix.

  ## NOT DECIDED

  - **Whether one vocabulary can serve all three instances**, or whether a file, a folder and a
    sample are different enough that one sentence would be vague at all three.
  - **Whether `drive_adoption` should refuse to offer a verdict at all** past some proportion of
    refused samples, rather than reporting a number beside it. A tally the user has to interpret
    may be worse than an honest *"I could not see enough of this drive to say."*
  - **Where the count rides.** `(aer)` established `SkippedFolderGroup` and `(aev)`
    `UncomparedPhotos`; a third structure of the same shape is a hint that the shape itself wants
    naming.


  ---

  # READ-ONLY, 2026-08-22. The entry survives only in its third.

  ## ⚠ 1. `date_rescue` IS NOT SILENT - this entry's own claim was wrong

  It said *"the user is told nothing at all about that photo"*. Measured: `continue` at
  `date_rescue.py:original_candidates` leaves the value **pre-seeded at `:272`** as `{"status": "unreachable"}`,
  and `app.js:startMigrateRun` renders that as **"could not check"**, with the tooltip *"The folder this
  was imported from is not reachable, so no backup file could be checked"*.

  **What is actually wrong is narrower and different.** `unreachable` is produced by four distinct
  paths:

  | line | cause |
  |---|---|
  | `:277` | no catalog row for that sha |
  | `:277` | a row with no `source_path` |
  | **`:286`** | **the sidecar's path refused** - the `(aey)` case this entry was filed about |
  | `:289` | the source's parent is not a directory |

  and the tooltip asserts **one** of them for all four. For the refused-sidecar case it names the
  wrong thing: it is the sidecar that would not answer, not necessarily the folder.

  ⚠ The class docstring at `:234-238` is careful that `none` and `unreachable` must not collapse -
  *"Collapsing them would let a screen tell a user their photo has no backup when the truth is that
  nobody checked."* **Nothing applies that same care one level down**, to the four causes inside
  `unreachable`.

  ## 2. `drive_adoption` was never a reporting problem - `(afn)`

  A refusal above half the sample converts *"this is your library"* into *"this is a new drive"*,
  silently, and the guard against a second drive id is bypassed rather than triggered. A
  data-integrity defect. Split out; it outranks this entry.

  ## 3. A third site nobody had named - `(afo)`

  `cleanup.py:plan_cleanup` prints `LEFT ALONE - something is in there (1):` above `Camera/2013   []`.
  Not silence: a false assertion. Split out.

  ## ⚠ THE CENTRAL GUESS, FALSIFIED

  This entry said the fix was *"probably **one decision about how refusal is reported everywhere**
  - a single vocabulary, worded once in `models`"*, and that it was `(aer)`'s shape for the third
  time. **Both halves are wrong, and the measurement is what shows it.**

  `(aer)`'s shared home worked because its sites answered **the same question**: *which folders did
  this run not enter?* One wording, one payload field, one render served all of them.

  These three do not answer the same question:

  | site | what it actually needs |
  |---|---|
  | `date_rescue` | a **cause**, among four already conflated into one word |
  | `cleanup` `(afo)` | a **tier or flag** that means *unknown* rather than *occupied* |
  | `drive_adoption` `(afn)` | a **denominator decision**, and a verdict that can be surfaced at all |

  **One vocabulary would have fixed none of the other two.** Only the first is a wording problem at
  all; `(afn)` is arithmetic and control flow, and `(afo)` is a type. A single `models` constant
  would have sat unused beside both.

  ⚠ **The general lesson, which is the reason to write this down.** Three sites sharing a *cause*
  (the stdlib stopped distinguishing refused from absent) is not the same as three sites sharing a
  *remedy*. `(aer)` earned its shared home by having one question behind it; this entry inherited
  the expectation of one from the family resemblance and never checked. **"Three instances, so one
  fix" is a hypothesis, and it is cheap to test by asking each site what it would do with the
  shared thing.** Asked here, two of the three had no use for it.
