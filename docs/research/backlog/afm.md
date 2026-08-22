# (afm) UNCAPPED PER-ITEM LISTS ARE THE RULE, NOT THE EXCEPTION - AND THE BIGGEST FIRES ON SUCCESS.

*Body of entry `(afm)`. **SHIPPED 2026-08-22** - the index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## HOW IT CLOSED, AND WHAT THE ENTRY HAD WRONG

**None of A, B or C.** The last of this entry's own *"NOT DECIDED"* bullets turned out to be the
question - *"whether the `--dry-run` preview and the `--apply` report should differ here at all"* -
and the other two answers follow from it. `_print_report` served **two documents**: a decision
sheet read before typing a word, and a listing scrolled past after the run was already authorised.
Every option above adjusts the **volume** of a block that should not be one block.

So both per-file listings take `listing=not args.apply`. A preview keeps the whole argument -
nothing else can serve it, and the record cannot, being written after execution. An authorised run
keeps the counts, and `listing=False` prints **nothing** rather than a tally: `_print_summary` runs
two lines later with every count these headers carried, and a second copy is the `(abl)` shape.

⚠ **B was refused as premature, but B's premise was the one that held.** It wanted the detail
behind a verbosity level and needed `(afl)` first. `(afl)` shipped as a **record rather than a
flag**, and that is what made this cheap: what may be dropped is only what something else still
holds. **`(afd)`'s cap was uncomfortable for the opposite reason** - there the elided lines were
the only copy.

⚠ **Considered and refused: making stdout terminal-aware**, as stderr already is at
`cli.py:1779-1783`, whose docstring carries a measured justification (*"127 KB of unreadable
scrollback on a real 32,628-file run"*). **The precedent did not transfer.** A run's output would
stop being reproducible from its command line, which is too much to give up, and the asymmetry is
defensible on its own terms: **progress is chrome, a decision sheet is content.** Measured before
ruling: piping stdout changes nothing today - 2,154 lines piped against 2,155 on a tty - because
there is no `isatty` check on stdout at all.

⚠ **Refused: summarising by category and date source.** Deciding which decisions deserve a
person's eye is the judgement the current block declines to make, and it must not be made inside a
volume fix. Its own entry if it is wanted.

## THREE CORRECTIONS TO THE MEASUREMENTS ABOVE

1. **FOUR sites scale, not five.** `uncompared.files` is capped **at the source** -
   `organizer.py:544`, `files=tuple(named[:FOLDER_PREVIEW])`, with `total` carrying the true
   count. It is the shape this fix copies, not an instance of the defect.
2. **`undated` is uncapped but gated** on `--skip-undated`, so it is not on the default path.
3. **~7 lines per entry is a floor, measured on a minimal resolution.** Real files with a date
   source cost **9**: 37 lines for 5 files against 262 for 30.

## THE COVERAGE THAT HAD TO GO FIRST

Counted before anything changed, and it is why the fix is one commit behind its tests:

* the `unique`/`near`/`exact` listing had **no test**. Two files call `_print_report` and both
  assert tally lines and duplicate origins - counts in headers, never the listing under them.
* `organizer.py`'s `FOLDER_PREVIEW` cap was untested.
* ⚠ **no suite asserted output VOLUME anywhere** - no `len(out.splitlines())` assertion existed in
  the repo. That is the measurement this entry is about, and it was the one nobody had.
* ⚠ **`_print_skipped_undated` had no *direct* reference, which is not the same as no coverage** -
  `test_config_cli.py:75` exercised it end to end and asserted *"named, never silent"*. A grep for
  the symbol missed it, and the full suite caught what the grep did not. Its guarantee was
  **relocated, not weakened**: the test now asserts the count on screen and the name in the
  record, which outlives the scrollback that prompted `(afl)`.


- **(afm) SPLIT OUT OF `(afd)` ON 2026-08-22**, whose title claimed the failure list was *"the one
  uncapped list in the product"*. Measuring it falsified that, so the general case gets its own
  letter and `(afd)` keeps the two lists it was filed about.

  ## MEASURED, ON A RUN WHERE NOTHING WENT WRONG

  2,110 real files organized successfully to an empty destination:

  ```
  stdout                     15,128 lines
  the NEW UNIQUE block       15,082 lines   for 1,953 entries, ~7 lines each
  ```

  ⚠ **That is 7.5x the entire output `(afd)` was filed over, on the success path.** A user who
  organizes a normal folder gets fifteen thousand lines and no way to ask for fewer - which is
  `(afl)`.

  ## THE SCAN

  An `ast` walk over `cli.py` finds **49** `for` loops that print per item with no slice and no
  `_STATUS_PREVIEW`. ⚠ **Most are bounded by construction** and are not defects: a literal tuple
  of three media groups, `PRESETS.items()`, a fixed list of reasons. The number is a starting
  point, not a finding.

  **Five scale with the corpus**, and these are the entry:

  | site | list | what it prints |
  |---|---|---|
  | `cli.py:1937` | `unique` | `_format_new` - ~7 lines each. **The 15,082.** |
  | `cli.py:1946` | `near` | `_format_new` - same shape, near-duplicates |
  | `cli.py:1956` | `exact` | `_format_exact` per duplicate |
  | `cli.py:1969` | `undated` | one line per undated file |
  | `cli.py:2827` | `uncompared.files` | one line per file that could not be compared |

  ## WHY THIS IS NOT JUST "APPLY THE CAP FIVE MORE TIMES"

  ⚠ **The preview's job is different from the failure list's.** `(afd)`'s list repeated one fact
  2,096 times; `NEW UNIQUE` repeats a *different* fact 1,953 times - each entry names its own
  category, date, provenance and hashes, and that is the product explaining its decisions before
  a user commits to them. Capping it hides decisions rather than noise.

  **So the honest options differ from `(afd)`'s**, and none is obviously right:

  - **A. Cap, like the rest.** Cheapest, consistent - and a preview that shows 20 of 1,953
    decisions is arguably no longer a preview.
  - **B. Summarise instead of listing.** Counts by category and date source, with the per-file
    detail behind `(afl)`'s verbose level. Needs `(afl)` first.
  - **C. Leave the preview alone and cap only the incidental lists** (`exact`, `undated`,
    `uncompared`). Smallest defensible change; leaves the 15,082.

  ## NOT DECIDED

  - Which of the five are noise and which are the product's argument for what it is about to do.
  - Whether this waits on `(afl)`. **B needs it; A and C do not.**
  - Whether the `--dry-run` preview and the `--apply` report should differ here at all - today the
    same block is printed by both.

  ---

  ## ⚠ WHAT `(afl)` COST THIS ENTRY, 2026-08-22

  This entry's option **B** was *"summarise instead of listing, with the per-file detail behind
  `(afl)`'s verbose level"*, and it said *"needs `(afl)` first"*.

  **`(afl)` closed without a verbosity flag.** It found that nothing in the product could answer
  *"which photos failed?"* after the terminal scrolled, and shipped a run **record** instead - a
  file beside the catalog, written automatically. The right destination for detail turned out to be
  a file rather than a flag, and of the twelve elision sites only the failure list was the record
  of an irreversible act.

  ⚠ **So B has nothing to hide behind.** 15,082 lines on a *successful* run is now a
  **default-output question**: what should an ordinary run print, with no verbosity control to
  demote the rest to. That is a harder question than the one this entry was filed with, and it is
  the honest one - the previous framing let the volume be somebody else's flag to add.

  What does not change: the record covers this. A user who wants the per-file detail of a
  successful run already has it in `last-run.json`, which is an argument **for** summarising the
  preview rather than against it.
