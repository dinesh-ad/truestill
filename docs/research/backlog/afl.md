# (afl) THE PRODUCT HAS NO VERBOSITY CONTROL AT ALL - NO `--verbose`, NO `-q`, NO LEVELS.

*Body of backlog entry `(afl)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afl) FOUND WHILE FIXING `(afd)`, 2026-08-22.** ⚠ **Not a missing flag - a missing dimension.**
  It is the reason two other entries have nowhere to put what they must not print.

  ## MEASURED

  ```
  truestill --help          : no --verbose, no -v, no -vv, no --quiet, no -q, no --debug
  every subcommand          : the same
  ```

  Every line the product prints is printed unconditionally. There is one output level, and it is
  whatever each call site decided.

  ## WHY IT SURFACED, AND WHY IT IS NOT COSMETIC

  `(afd)` asked whether a failure list's raw `OSError` text should go behind `--verbose`.
  [clig.dev](https://clig.dev) puts developer-only detail exactly there. **The option did not
  exist to reject** - so the raw text had to be capped away instead of demoted, and the most
  specific evidence a user has when a copy fails is now elided rather than moved.

  `(aep)` has the same problem from the other side: it must stop a raw errno reaching a user, and
  the natural home for an errno is a verbose level nobody can ask for.

  ## PRIOR ART, WHICH IS UNUSUALLY SETTLED FOR A CLI QUESTION

  - **Unix convention**: `-v` / `-vv` to add detail, `-q` to remove it.
  - **[clig.dev](https://clig.dev)**: `-q, --quiet` - *"Display less output. This is particularly
    useful when displaying output for humans that you might want to hide when running in a
    script."* And `-d, --debug` for debugging output. ⚠ clig warns `-v` is ambiguous - *"can often
    mean either verbose or version"* - and suggests `-d` for verbose, which is a decision this
    entry has to make rather than inherit.
  - **[.NET](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet)**: five named levels -
    `quiet`, `minimal`, `normal`, `detailed`, `diagnostic` - with `-v` as the alias. A worked
    example of *levels* rather than a boolean, which is the shape a product with this much output
    probably needs.

  ## NOT DECIDED

  - **Boolean or levels.** `--verbose` alone is cheap; five levels is what a run producing 15,000
    lines actually calls for, and `(afm)` is about that volume.
  - **`-v` or `-d`.** clig's ambiguity warning versus the Unix habit. `truestill --version` exists,
    which is exactly the collision clig names.
  - **What each level contains.** ⚠ This is the real work, and it is a per-call-site decision
    across the whole CLI - not a flag definition. Doing it badly means a `--quiet` that hides
    something a user needed.
  - **Whether `--quiet` may hide a failure.** It must not hide a non-zero exit; whether it may
    hide the *reason* is a §9 question.

  ---

  # CLOSED 2026-08-22, RE-RANKED RATHER THAN DEFERRED.

  ⚠ **The right destination for verbose detail turned out to be a FILE, not a FLAG.** This entry
  was filed as "the product has no verbosity control"; the read-only pass found something that
  outranks it, and the fix that follows leaves almost nothing of the original.

  ## What the investigation found

  **After the terminal scrolls, nothing in this product could answer *"which photos failed?"***
  Every candidate checked:

  | candidate | why not |
  |---|---|
  | `--report PATH` | built from `resolutions`, **before** execution - records what was *decided*. Measured: `status`, `detail`, `final_relative` all absent. And opt-in. |
  | logging | **none**: zero `logging.` calls in either package |
  | `files.upload_status` | only ever holds `'uploaded'` - a row exists only for a file that **succeeded** |
  | `ActionStatus.FAILED` | appears nowhere outside `cli.py` and `organizer.py`. No persistence at all. |

  So `(afd)`'s cap did not hide the failure list behind a missing flag: **the elided lines were the
  only copy**. That is the finding, and it is why this became a record.

  ⚠ **The prior art is a null result rather than a gap in the search.** Every current backup guide
  treats this as the operator's job - `>> /var/log/backup.log` from cron. Those tools assume
  somebody wiring up logging. This product has no cron, no operator, and a user who will not read
  a man page. The convention does not transfer.

  ## What ships

  One rolling `last-run.json` beside the catalog, written automatically on every applied run, built
  from `results`. `--report PATH` stops deciding *whether* a record exists and now says only
  *where* it goes.

  Verbatim, from the `(afe)` reproduction - the run that could not say what it did:

  ```json
  {
    "format": 1,
    "run": {
      "source": "/data/aflrun/src",
      "destination": "/data/aflrun/dest",
      "intended_total": 27,
      "attempted": 6,
      "stopped": {
        "never_attempted": 21,
        "reason": "The library catalog could not be written, so the run stopped rather than copy files it could not record. 5 files organized and recorded before this. ... Diagnostic: SQLITE_READONLY_DIRECTORY."
      }
    }
  }
  ```

  ```
  files[] entries: 27
    ..._2053977145_n.jpg   status=uploaded        landed_at=Camera/2013/10/...
    ..._293394388_n.jpg    status=failed          landed_at=None
    ..._1092238818_n.jpg   status=not attempted   landed_at=None
  ```

  ## Rulings, each with its reason

  **Beside the catalog, always** - the sibling half of `cache_path_for`'s rule **without the
  split**. A cache is redirected to the OS cache directory because losing one costs nothing; a
  record is data and belongs with the catalog wherever it is.

  **Rolling, not per-run** - one file has no expiry policy. A file per run reintroduces the
  "who decides when these go" commitment that ruled out the catalog.

  **From `results`, not `resolutions`** - strictly more information. `ActionResult` carries the
  whole resolution plus status, detail, where it landed, and a `sha256` *richer* than the plan's.

  **Automatic** - the user who most needs the record is the one who did not know to ask.

  **The stop is carried, not inferred by the reader.** A record silent about what was never tried
  reads as complete and is not - `(afa)`'s shape. `intended_total` against `attempted` shows the
  gap even to a reader who ignores the `stopped` block.

  ⚠ **The reason is read from the last result and never asserted.** `execute` stops in three
  places; the cancel at `organizer.py:1977-1978` **records nothing**, and the CLI passes no
  `cancel` - so that one is unreachable from this surface. The record's stop handling therefore has
  **one live case and one only the app path can exercise**, and where the reason is not there it
  says so rather than inventing one from whichever file happened to be last.

  ## ⚠ THE HONEST LIMIT: it survives a stop, not a kill

  The record is written **after** execution, so a hard crash or `SIGKILL` between the last file and
  the write loses it entirely. **The thing this exists to survive is a run that ends badly, and
  this design survives one kind of bad ending and not the other.**

  Not a reason to change it: per-file writes are their own performance question, and `(aem)`'s
  `organize_runs` already covers the killed run from a different angle - `unfinished_organize_run`
  derives it as `achieved < intended_total`, which is where this record's vocabulary comes from.
  **But a limit stated is the difference between a design and an assumption.**

  ## The behaviour change, recorded rather than discovered

  **A preview now writes nothing**, where `--report` used to produce a plan report. The plan
  answered *"what would happen"*; the record answers *"what happened"*; one file cannot honestly be
  both. It also resolves a contradiction that was already there: the DRY RUN banner says *"nothing
  was written or recorded"* while `--report` wrote a file. The banner is now true in every case.

  If a plan-preview artefact turns out to be wanted, it gets **its own entry and its own name**,
  never a second meaning for this flag.

  ## What is left of this entry: one sentence

  With the record, `(afd)`'s cap is **legibility rather than loss**, and `(aep)`'s raw errno has a
  home that is not the terminal. Of the 12 elision sites, the other 10 are previews and status
  listings - none is the record of an irreversible act, and `--limit 0` already exists for the one
  where a user genuinely paginates. What survives is that **the run names where the record went**,
  which this delivers unconditionally.

  ⚠ **`(afm)` pays for this**, and it is recorded there too: it was leaning on a verbosity flag
  that will now not exist.
