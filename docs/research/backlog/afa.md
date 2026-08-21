# (afa) A PATH THE PRODUCT KNOWS WAS REFUSED IS STILL NOT REPORTED TO ANYONE.

*Body of backlog entry `(afa)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afa) "WE DETECTED IT AND SAID NOTHING" IS A DIFFERENT STATE FROM "WE COULD NOT TELL".**
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
  `folder_skip_remedy` and `UNCOMPARED_LABEL` already are - and not three separate wordings
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
