# (afd) THE ONE UNCAPPED LIST IN THE PRODUCT IS THE FAILURE LIST, AND IT PRINTS RAW `OSError` TEXT.

*Body of backlog entry `(afd)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afd)** Found 2026-08-21 by **soak three, step R3** - a destination that refuses **after**
  preflight has passed.

  ## MEASURED

  244 files, a destination flipped to `EACCES` once ten had landed:

  ```
  233 FAILED lines, 2,004 lines of output, one "... and N more" (belonging to a different list)
  ```

  A representative line, unedited:

  ```
    FAILED: Canon EOS 100D.jpg: cannot upload to '2013/2013-04/.../20130407_200009_Canon EOS 100D.jpg':
    [Errno 13] Permission denied: '/.../soak3/r3/src/Canon EOS 100D.jpg' ->
    '/.../soak3/r3/mnt/2013/2013-04/2013-04 - Everyday/20130407_200009_Canon EOS 100D.jpg.partial'
    3,981,312 bytes of it are still at /.../.partial, and could not be removed.
  ```

  ## TWO DEFECTS IN ONE LINE

  **1. It is the only uncapped list.** `_print_execution` (`cli.py:2177-2183`) loops
  `for failure in failures:` with no slice and no *"and N more"*. `_STATUS_PREVIEW` appears
  **16 times** elsewhere in the same file - `_print_unreadable`, `_print_folder_groups`,
  `_print_uncompared` all elide at 20 and say how many they hid. ⚠ **The truncation rule is
  applied everywhere except the case that generates the most rows**, and a failure mode that
  affects every remaining file generates one line per file by construction.

  **2. It prints raw `OSError` text and two absolute paths.** §9 rules that no backend vocabulary
  reaches a user, and `models.unreadable_label` exists so *"no `errno` name or raw enum value ever
  reaches a user"*. `[Errno 13] Permission denied: '<src>' -> '<dst>.partial'` is the exception -
  including the internal `.partial` suffix and the `->` of a `rename` the user never asked about.

  ⚠ **This is arguably deliberate and that is why it needs a decision rather than a patch.**
  `_print_unreadable`'s docstring says the FAILED line is *"the better line of the two - later, and
  more specific"*, so the specificity is wanted. What is not wanted is the errno spelling, the
  temp-file mechanics, and 233 repetitions of them.

  ## ⚠ AND THE REMEDY EXISTS ONLY ON THE PREVIEW - measured in R1, same three files, one run

  Three source files at `chmod 000`, the same command with and without `--apply`:

  ```
  preview:  Files that were not organized:
              files not organized: 3
                permission denied: 3
                  Canon_40D.jpg  ...
                (not organized; check the file's permissions and try again)

  --apply:  FAILED: Canon_40D.jpg: [Errno 13] Permission denied: '/.../src/Canon_40D.jpg'
  ```

  **The worded reason and the remedy - the whole of `(aew)` - are on the preview only.** A user
  who runs `--apply` directly, which is the ordinary case once they trust the tool, gets the raw
  errno and no next step. §9's one-source-of-wording rule, broken across preview and run rather
  than across CLI and app - the same family as `(aer)`.

  ## A THIRD, SMALLER: THE EXIT CODE DISAGREES WITH ITSELF (R2)

  An unreadable **file** exits **1** - `_print_unreadable`'s own comment argues for it, so that
  `organize && next_step` cannot chain past a library Truestill could not account for. An
  unreadable **folder** holding twelve photos exits **0**, while reporting the folder correctly.
  Same run, same class of ignorance, opposite codes.

  ## WHAT WAS **NOT** WRONG - the safety properties all held

  R3 existed to ask whether a mid-run refusal corrupts state. It does not:

  - **The catalog matched the disk exactly**: 10 files landed, 10 `file_copies` rows. No row for a
    file that never arrived.
  - `.partial` was used throughout, so no truncated file ever wore a real name, and the **one**
    left behind was cleaned up by the next run.
  - **A re-run resumed**: it recognised *"10 already on this drive"* as exact duplicates and
    copied only the remaining 233.
  - **Full accounting** (§1): 244 sources, 243 recorded, and the one difference was a byte-identical
    duplicate **named in the report** as `[SKIP: exact duplicate]`.
  - Exit code **1**, and every failed file named.

  ## NOT DECIDED

  - **What the cap should be, and what the elided lines become.** 233 identical failures are one
    fact, not 233; a cap alone would hide the shape. *"231 more, all the same reason"* may be the
    honest form.
  - **Whether the raw text belongs behind a flag** (`--verbose`, a log file) rather than deleted -
    it is genuinely the most specific evidence available when a copy fails.
  - **Whether `MOVE KEPT` (`cli.py:2173-2175`) has the same two problems**, since it is the same
    shape immediately above and was not exercised by this step.

  ---

  ## ⚠ CONFIRMED IN A SECOND COMMAND - soak four, step D6, 2026-08-22

  This entry was found in `organize`'s failure list. `clean-empty`'s is the same shape and adds a
  detail worth having: **a Python `bytes` repr reaches the user.** A real trash refusal, staged by
  denying `/data/.Trash-1000/files` and `info`:

  ```
  Removed 0 folder(s).
    ! 2013/2013-08/2013-08 - Everyday: [Errno 13] Permission denied: b'/data/.Trash-1000/info/2013-08 - Everyday 2.trashinfo'
  ```

  The `b'...'` is `send2trash` handing back a bytes path, printed through `str(exc)` unchanged. So
  the remedy this entry is about is **not one list's formatting**: two commands reach it
  independently, and the second leaks a language artefact on top of the raw errno.

  ⚠ **The refusal behaviour itself was correct** and is not what this note reports - 0 folders
  removed, all three left in place, each named. §1 condition **(d)** held. Only the wording is at
  issue.
