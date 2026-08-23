# (afz) `mutation_matrix.py` LEAKS A TEMPORARY DIRECTORY PER MUTANT, IN A SCRIPT NO GATE RUNS.

*Body of backlog entry `(afz)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afz)** Recorded 2026-08-23, found while measuring `(afy)`.

  ## The leak

  `scripts/mutation_matrix.py:539`:

  ```python
  report = Path(tempfile.mkdtemp()) / "r.xml"
  ```

  Bare `mkdtemp()`, **no cleanup on any path** - not a context manager, no `finally`, no
  `atexit`. `_pytest()` is called once per mutant inside the loop (`:673`) plus twice per run
  (`:647`, `:684`). The file defines **67 mutants** across three suites (`thumbnails`, `grid`,
  `parent-watch`), so a sweep of all three leaves **~73** `/tmp/tmpXXXXXXXX` directories, each
  holding one small JUnit XML. Three sweeps is the ~235 that were observed.

  ## ⚠ WHY IT ACCUMULATED INVISIBLY, WHICH IS THE PART WORTH KEEPING

  `mutation_matrix.py` appears in **no `Makefile` target, no pre-commit hook and no CI
  workflow** - checked, all three. That is correct and deliberate: `CLAUDE.md` says *"Not in
  `make check` - it costs minutes."* But it means the leak is invisible to every gate the repo
  has, and the directories are near-empty, so nothing runs out of anything. It is found by
  `ls /tmp`, which is not a step in any process.

  **The instrument that would have seen it does not exist**, and that is the finding rather than
  the line number. A tool run by hand, outside every lane, is where this class lives.

  ## 🔑 `:617` IS LEFTOVER BY DESIGN AND MUST NOT BE "FIXED"

  Recorded here, in the same entry, so nobody closing the one above closes this too:

  ```python
  backup = Path(tempfile.mkdtemp(prefix="mutation-matrix-"))
  ```

  This one is **deliberately never removed**. It holds the originals of every file the sweep
  mutates, and its own docstring gives the reason: *"The backup directory is printed, so even a
  `SIGKILL` leaves a one-command recovery."* A `TemporaryDirectory` here would delete the
  recovery at exactly the moment it is needed. It is **named** (`mutation-matrix-*`) rather than
  anonymous, which is what makes it identifiable later - the opposite of `:539`.

  **The distinction is the rule**: a leftover that is *evidence for recovery* is named and kept;
  a leftover that is *nobody's* is a defect. Anything proposed for `:539` must leave `:617`
  alone, and a remedy that unifies them is wrong.

  ## Also named, deliberately not fixed here

  - **`scripts/shoot_screens.py:170`** - `temp = tempfile.TemporaryDirectory()` held in a local
    with no `with` and no explicit cleanup. The finalizer removes it when `main()` returns, so it
    is clean on the ordinary path and **leaks on abnormal exit**. A smaller instance of the same
    class, in another hand-run script.
  - **`exif.py:265`** - `NamedTemporaryFile(delete=False)`, cleaned in a `finally`. Leaks a
    `.args` **file** only on `SIGKILL`. Listed so a later sweep does not re-derive that it is
    fine.
  - Clean and checked: `organizer.py:1249`, `profile_organize_preview.py:266`,
    `flake_report.py:179`, `benchmark_hashing.py:75` - all context-managed or `finally`-cleaned.
  - **No test in the repo calls `tempfile` at all.** Zero matches across `packages/*/tests` and
    `tests/`.

  ## ⚠ THE PREMISE THIS ENTRY CORRECTS

  The work was commissioned on the reasoning *"pytest cleans `tmp_path` itself, so leftovers mean
  `mkdtemp` without a `finally`, a subprocess making its own, or a test that creates and never
  removes"* - and the instruction was to **name the tests**.

  **The premise is false and it ruled out where the leak actually was.** `tmp_path_retention_count`
  defaults to **3** (`_pytest/tmpdir.py`): pytest *deliberately retains* the last three session
  roots and garbage-collects only what is older. So `/tmp/pytest-of-<user>` holding several
  `pytest-N` directories is the designed behaviour and is **not evidence of anything**. The
  inference from "there are leftovers" to "something leaked" does not hold, and following it
  pointed at the test suite - which is the one place in this repo that calls `tempfile` **zero**
  times. The leak was in a script the search had already excluded by assuming a gate would have
  caught it.

  **Recorded because a correct-looking inference that excludes the answer is worth more than the
  answer.** `ENGINEERING_STANDARD.md` §4's thirty-second member is the neighbour: a rule stated as
  a *machine state* ("pytest cleans up") expires in silence, while one stated as *intent* survives.

  ## What is not decided

  Whether the remedy is a `TemporaryDirectory` around `_pytest`'s report, writing the report
  inside the run's own backup directory, or a `--keep-reports` flag for the case where the XML is
  wanted after a failure. Not chosen here: the sweep's failure mode is *"which mutant survived"*,
  and whether that question ever needs the XML afterwards has not been asked of anyone who uses
  the tool.
