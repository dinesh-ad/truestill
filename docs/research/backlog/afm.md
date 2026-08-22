# (afm) UNCAPPED PER-ITEM LISTS ARE THE RULE, NOT THE EXCEPTION - AND THE BIGGEST FIRES ON SUCCESS.

*Body of backlog entry `(afm)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
