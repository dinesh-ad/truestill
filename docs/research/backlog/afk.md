# (afk) JUNK DELETED BEFORE AN `rmdir` REFUSAL IS NOT REPORTED, SO A PARTIAL REMOVAL READS AS NONE.

*Body of backlog entry `(afk)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afk) FOUND BY SOAK FOUR, STEP D7, 2026-08-22.** Small, and the same shape as `(aez)`: a
  destructive action that partly happened and reports as though it did not happen at all.

  ## MEASURED

  `_remove_permanently` unlinks the planned junk **first**, then calls `rmdir`. When `rmdir`
  refuses, the unlinks have already happened:

  ```
  Removed 2 folder(s) (2 deleted permanently).
    ! 2013/2013-09/2013-09 - Everyday: [Errno 39] Directory not empty

  folder survives?      YES
  unexpected file?      YES
  .DS_Store (the junk)? REMOVED  -- and nothing said so
  ```

  The failure line names the folder and the errno. A reader concludes the folder was left alone.
  Its `.DS_Store` is gone.

  ## WHY IT IS SMALL, AND WHY IT IS STILL WORTH A LETTER

  The junk was **named in the preview** - `[.DS_Store, Thumbs.db]` beside the folder - and
  `JUNK_NAMES` is a deliberately conservative list, so nothing of value is at risk. This is not
  about the bytes.

  ⚠ **It is about a report that is wrong in the direction of "nothing happened".** `(aez)` was
  exactly this: `run_reclaim` raised mid-loop *after earlier candidates had already been deleted*,
  and the run ended in a traceback rather than a count. Here there is no traceback and the count
  is right about folders - but the same class of statement, *"this one failed"*, is standing in
  for *"this one partly succeeded"*.

  ## THE FIX IS A SENTENCE, NOT A REORDER

  ⚠ **Do not "fix" this by calling `rmdir` first.** The order is load-bearing: the junk must go
  before the folder can be empty, and `_remove_permanently`'s whole safety argument is that
  `rmdir` is the last word. The remedy is to say what was removed:

  > `! <folder>: not removed (directory not empty); its .DS_Store was removed`

  ## NOT DECIDED

  - Whether the same reporting gap exists on the trash path. It does not today, because the trash
    path moves the folder whole - but `(afj)` option **A** would introduce an unlink-then-check
    step there and would inherit this exactly.

  ---

  # CLOSED 2026-08-22, inside `(afj)`, and this entry predicted that.

  The section above ends: *"`(afj)` option **A** would introduce an unlink-then-check step there and
  would inherit this exactly."* It did. The fix that stopped `clean-empty` handing whole folders to
  the trash made this reporting gap **mandatory to close rather than optional**, because the partial
  state it produces is larger than the one recorded here: junk in the trash **and** the folder still
  present, where before it was junk destroyed and the folder still present.

  Neither ordering of the two entries was available. Shipping `(afj)` alone gives every ordinary run
  a partial state its own report cannot describe; fixing this first fixes the reporting of a code
  path `(afj)` replaces.

  **The remedy is the sentence this entry asked for**, in `cleanup._partial_removal_reason`, and it
  now covers both dispositions:

  ```
  ! 2013/2013-09/2013-09 - Everyday: not removed (directory not empty); its .DS_Store is in the trash
  ```

  Measured on the real race. Under `--permanent` the same line reads *"its .DS_Store was removed"*.

  ⚠ **The order was not touched**, per this entry's own instruction: the junk still goes before the
  `rmdir`, because the folder cannot be empty otherwise and `rmdir` being last is the whole
  guarantee. Pinned by `test_junk_already_in_the_trash_is_named_when_the_rmdir_refuses`.
