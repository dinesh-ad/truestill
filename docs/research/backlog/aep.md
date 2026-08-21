# (aep) THE WRITE SIDE HAS NO `unreadable_label`: "upload" AND A RAW errno REACH THE USER.

*Body of backlog entry `(aep)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aep) A FAILED COPY LEAKS BACKEND VOCABULARY AND A RAW `errno`.** Split out of `(aek)` on
  2026-08-21, where it was the third finding and the only one not about setup.

  ## WHAT A USER READS, VERBATIM

  Reproduced 2026-08-21 on a destination that refused the write:

  ```
  FAILED: IMG_0001.png: cannot upload to 'Saved/Undated/IMG_0001.png': [Errno 13] Permission denied: '/.../dest3/Saved'
  ```

  Two rule violations in one line, and both are §9's.

  **1. "upload" is backend vocabulary.** `IMPLEMENTATION_STANDARDS.md` §9: *"No backend vocabulary
  reaches a user. 'Uploaded' is honest inside the code and false on screen."* The string is built
  at `destinations/local.py:67` and `:125`. ⚠ **The rule is stated at the site that breaks it**:
  `cli._print_execution`'s own comment says *"'uploaded' is backend vocabulary ... and never
  reaches a user"* (`cli.py:2137-2138`), eighteen lines above the `print` that emits
  `failure.detail`.

  **2. The raw errno reaches the user.** `_upload_failure` deliberately strips it for `EFBIG` and
  is pinned for that - `test_destination_errors.py:77` asserts *"the raw errno leaked into a
  user-facing sentence"* - and the fall-through branch passes `{exc}` through untouched.

  ## THE SHAPE OF THE REMEDY, WHICH ALREADY EXISTS ON THE OTHER SIDE

  Reads have `models.unreadable_label` and `UnreadableReason`, whose comment states the rule:
  *"no `errno` name or raw enum value ever reaches a user"* (`models.py:194-197`). **Writes have
  no equivalent.** `(aek)` added `drive_unwritable.explain_unwritable_drive` for the two writes
  that reach a user's own drive, which is a start and is deliberately scoped to those - extending
  it to the copy path is this entry.

  ## ⚠ WHY THE EXISTING GUARD DID NOT CATCH IT

  `test_status_labels_cover_every_outcome` (`test_organizer.py:425-434`) asserts that every
  `ActionStatus` has a user-facing **label**. It says nothing about `detail`, which is the free
  string that carries the leak. A guard aimed at the right subject through a lens that cannot
  resolve part of it - `ENGINEERING_STANDARD.md` §4, fifty-fourth member.

  ## NOT DECIDED

  - **What the sentence should say.** "Could not copy X to Y" plus a worded reason is the obvious
    shape, but the FAT32 branch above it is already a worked example of a reason worth naming
    specially, and there may be others.
  - **Whether `detail` should be structured rather than a string.** Today every surface renders it
    verbatim, so a leak anywhere reaches every screen at once.
