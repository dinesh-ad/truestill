# (afd) THE FAILURE LIST IS UNCAPPED AND PRINTS RAW `OSError` TEXT.

> ⚠ **TITLE CORRECTED IN PLACE, 2026-08-22.** It read *"THE ONE UNCAPPED LIST IN THE PRODUCT IS
> THE FAILURE LIST"*, and that is false - measured, not argued. `cli.py:1934` and `:1943` are
> uncapped too, and on an **ordinary successful run** of 2,110 real files the `NEW UNIQUE` block
> alone printed **15,082 lines**: 7.5x the entire output this entry was filed over, with nothing
> wrong. The failure list is the worst-behaved list, not the only one. The general case is
> `(afm)`; this entry keeps the two lists it was filed about.

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

  ---

  # FIXED 2026-08-22. Q1 = C, Q2 = A, Q3 = shared.

  ## The number, re-measured on the real library rather than carried from the soak

  `Input/2014`, 2,110 real files, destination denied after ten had landed:

  ```
  BEFORE                          AFTER
  stderr lines   2,101            25
  FAILED lines   2,096            20  + "... and 2,074 more FAILED (all the same reason)."
  distinct reasons   1             (unchanged - it was always one fact)
  EXECUTED says  "2096  failed"   unchanged: the total was never in doubt
  ```

  The soak's 233/2,004 was a small corpus. The real worst case is ~9x that, and the shape is what
  matters: **2,096 lines carrying one reason, printed beside a summary that already stated the
  count.**

  ## Q1 - the cap is `_STATUS_PREVIEW`, and the constant's own comment was wrong

  It is the one that already exists (20, six sites, the shared `... and N more` idiom). ⚠ Its
  comment read *"how many single-copy files `truestill status` lists before eliding"* while five
  other lists already borrowed it - a shared constant documented as one command's setting, which
  is how the next reader concludes it may be tuned for `status` alone. Corrected.

  **Capping alone would have been half the fix.** With one reason behind 2,096 failures, a bare
  cap shows 20 identical lines and hides 2,076 identical lines - tidier, no more informative. So
  the elision names the reason count: *"all the same reason"*, or *"N distinct reasons in total"*
  when the tail is mixed. ⚠ The mixed case is the one that matters: eliding is only safe because
  the tail said one thing, and if it said three, that count is all that stands between the reader
  and a hidden second cause.

  **`_reason_key` is text normalisation and is labelled as such.** A detail names its own source
  and target, so the 2,096 failures carry 2,096 *distinct* strings; counting them verbatim would
  report 2,096 reasons for one fact. Stripping quoted fragments collapses them and keeps
  `[Errno 13]` apart from `[Errno 28]`, because the differing part is not quoted. **A real key
  belongs to `(aep)`**, which asks whether `detail` should be structured at all.

  ## Q2 - volume only, and the reason the other options do not exist

  Rewording is **`(aep)`**, not adjacent to it: that entry's worked example is literally this line,
  and it names both violations - *"upload"* is backend vocabulary, and the raw errno passes
  through. This entry does not touch the words.

  ⚠ **And `--verbose` was not rejected - it does not exist.** clig.dev puts developer-only detail
  behind verbose mode, and this product has **no verbosity control at all**: no `--verbose`, no
  `-v`/`-vv`, no `--quiet`, against a Unix convention and .NET's five documented levels
  (quiet / minimal / normal / detailed / diagnostic). So there is nowhere to put the raw text, and
  that absence is why `(aep)` has nowhere to put the errno either. Filed as **`(afl)`**.

  ## ⚠ The stream was never the defect

  clig.dev puts errors and messaging on `stderr` **on purpose** - moving a failure report to
  `stdout` would feed it into whatever the run was piped into. What clig also says is *"don't
  treat `stderr` like a log file, at least not by default"*, and 2,096 lines is exactly that.

  So the capped list **stays on `stderr`**. This also answers why `organize ... > log.txt` never
  helped: the flood was on the other stream, and 2,101 lines reached the terminal regardless.
  Twenty-five do not.

  ## A pager was considered and REJECTED, which is different from not considered

  clig.dev recommends one for large output and `git diff` is the worked example. It is wrong here:

  - **`organize` runs non-interactively and in scripts.** clig's own rule is *"use a pager only if
    `stdin` or `stdout` is an interactive terminal"* - so a pager would do nothing in exactly the
    case this defect was measured in, a redirected run.
  - **clig itself warns that *"using a pager can be error-prone, so be careful with your
    implementation such that you don't make the experience worse for the user."*** A dependency on
    `less` and on terminal detection, to hide output that should not have been produced.
  - **It treats the symptom.** 2,096 lines of one fact are not better paged; they are better not
    printed.

  ## Q3 - one fix, two sites, and one of them stays unmeasured

  `MOVE KEPT` (`cli.py:2250-2252`) and `FAILED` (`:2254-2259`) were the same six lines twice, two
  lines apart: same uncapped loop, same raw `.detail`, same `stderr`. One `_print_capped` now
  serves both.

  ⚠ **`MOVE KEPT`'s worst case is UNMEASURED.** It needs a per-file removal failure after a
  verified copy, which a whole-destination refusal does not produce - my run had **zero**. So the
  two are identical in *shape*, and the volume claim is only made for `FAILED`.
