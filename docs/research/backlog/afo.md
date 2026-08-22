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
