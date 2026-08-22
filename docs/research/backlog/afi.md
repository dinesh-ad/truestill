# (afi) `clean-empty` CANNOT SEE THE FOLDERS `organize --in-place` EMPTIES, AND THE RUN PROMISES IT CAN.

*Body of backlog entry `(afi)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afi) FOUND BY SOAK FOUR, STEP D5, 2026-08-22.** ⚠ **Not a wrongful deletion - the inverse.**
  Nothing is removed that should not be; a folder the product emptied is invisible to the command
  that exists to remove it, after the run said it would be reported.

  ## MEASURED

  `organize --in-place --apply` over 166 real files. Its own banner:

  ```
  IN-PLACE - files will be MOVED on this drive, not copied.
    Empty folders left behind are reported, never deleted.
  ```

  It emptied `TCS M05 EA Mall` - 161 files moved out of it. Then:

  ```
  $ truestill clean-empty <drive>
  Drive 'lib': no migration leftovers recorded. Nothing to clean.

  catalog: inplace_moves      161 rows   (old_relative = 'TCS M05 EA Mall/...')
           migration_journal    0 rows
  on disk: TCS M05 EA Mall     exists, empty
  ```

  The run's own summary did not name it either. **Nothing reported it, and the banner said it
  would be.**

  ## CAUSE, AND IT IS ONE QUERY

  `Catalog.migrated_old_paths` reads **`migration_journal`** and nothing else:

  ```sql
  SELECT old_relative FROM migration_journal
   WHERE drive_uuid = ? AND completed_at IS NOT NULL
  ```

  `migration_journal` is written by `migrate.py`'s `record_migration_moves` - the `migrate-layout`
  path. `organize --in-place` writes **`inplace_moves`** and `inplace_runs` instead, and no reader
  in the cleanup path touches them. Both consumers go through that one function, so both are
  blind: `_cmd_clean_empty` (the command) and `_offer_cleanup` (the offer printed after a
  migration).

  ## THE CONTROL, so the scope is attributable rather than assumed

  Same drive, same catalog, immediately afterwards - a real `migrate-layout` of 75 files:

  ```
  migration_journal   75 rows
  offer after the run: "3 folder(s) are now empty. Review and remove them with: truestill clean-empty ..."
  clean-empty        : REMOVABLE - empty (3);  LEFT ALONE - something is in there (2), contents named
  apply              : Removed 3 folder(s) (3 to the trash).  0 files lost.  Exactly the 3 promised.
  ```

  ⚠ **`clean-empty` is not broken. It is correct, and it is pointed at one of the two journals.**
  `TCS M05 EA Mall` was still empty on disk and still unlisted after that run, standing beside
  three folders from the other journal that were found, offered and removed correctly.

  ## WHY IT MATTERS MORE THAN AN UNTIDY FOLDER

  - **The product made a promise in the imperative voice and did not keep it.** *"Empty folders
    left behind are reported"* is the sentence a user reads while deciding to type `move`.
  - `--in-place` is the mode where leftovers are **most** likely: every file moves out of a tree
    the user built by hand, so the entire old skeleton is left behind. `migrate-layout` reshuffles
    within a tree truestill already made.
  - ⚠ **The fifty-fourth member's shape**: an instrument silent in exactly the case it exists for.
    *"No migration leftovers recorded"* reads as *"there are none"*, not as *"I looked in the
    other journal"*.

  ## NOT DECIDED

  - **Whether the fix is one query or one journal.** `migrated_old_paths` could union
    `inplace_moves`, or the two journals could become one. The second is a data decision with
    `undo` on the other side of it - `inplace_runs` is what `undo-organize` reverses, and
    `(yy)` already recorded that rewriting undo records is its own decision.
  - **Whether `emptied_directories`' scope argument survives the union.** Its docstring is
    explicit that reading the journal rather than the filesystem is what stops this becoming a
    drive sweep. A union keeps that property; it is worth stating rather than assuming.
  - **Whether the banner's promise or the behaviour is the thing to change.** The promise is the
    better half - but if the union is not built, the sentence must stop claiming it.
