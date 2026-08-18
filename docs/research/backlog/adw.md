# (adw) THE LEGACY CATALOG PATH IS RELATIVE, SO THE SAME INSTALL FINDS A DIFFERENT CATALOG DEPENDING ON WHERE IT WAS LAUNCHED.

*Body of backlog entry `(adw)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adw) THE LEGACY CATALOG PATH IS RELATIVE, SO THE SAME INSTALL FINDS A DIFFERENT CATALOG
  DEPENDING ON WHERE IT WAS LAUNCHED.** Recorded 2026-08-18, split out of `(adv)` while fixing it,
  because it is **the deeper defect and it outlives that fix**.
  - **The mechanism, and it is one word.** `LEGACY_CATALOG_PATH` is `Path("reports/catalog.sqlite")`
    - **relative**. `_legacy_catalog()` asks `LEGACY_CATALOG_PATH.exists()`, which is a question
    about the **current working directory**, not about the installation. So `truestill status` run
    from one directory and from another, by the same user on the same machine with the same
    install, can name two different catalogs - and both answers are "correct" by the rule as
    written.
  - **`(adv)` did not fix this and was never going to.** `(adv)` fixed the *precedence* between an
    explicit `TRUESTILL_DATA_DIR` and the legacy path. This is about the legacy path having no
    fixed meaning at all. **They are independent**: even with no environment variable anywhere,
    `cd` changes which library you are working in.
  - 🔬 **MEASURED CONSEQUENCE, and it is inside this repo's own test suite.** `conftest.py` sets
    `TRUESTILL_DATA_DIR` per test expressly for hermeticity - *"without an override the default
    catalog resolves into the developer's real home"*. It does **not** change the working
    directory, and pytest runs from the repo root, which has a `reports/`. So:

    | | `default_catalog_path()` inside a test resolves to |
    |---|---|
    | before `(adv)` | ⚠ `…/truestill/reports/catalog.sqlite` - **the maintainer's real catalog** |
    | after `(adv)` | ⚠ the same path, now with `reason="legacy"` and a note saying why |

    **`(adv)` made it disclosed. It did not make it prevented**, and for a test suite a disclosure
    is not protection: hermeticity still rests on every such test remembering to `chdir`.
  - ✅ **EXPOSURE, NOT DAMAGE - checked rather than assumed, so nobody reads this as an incident.**
    The real catalog's mtime is **2026-08-15 16:24**, unchanged across many `make check` runs on
    2026-08-18. Nothing has written to it; the tests that could reach it either pass an explicit
    `--db` or `chdir` first. **What is missing is the guarantee, not the good outcome so far.**
  - **Why it has survived.** The relative path is `(aae)`'s backwards-compatibility promise
    working exactly as designed for the case it was designed for - a developer in a checkout, who
    genuinely does mean *this* `reports/`. `app_paths` already documents the awkwardness
    (`_working_directory_was_chosen` exists because a double-clicked app has no meaningful CWD and
    the question is *"undefined"* there). What was never decided is what the path means for
    someone who **does** have a working directory but did not intend it to select a library.
  - **The shape of the decision, stated so it is not answered by reflex.** Making it absolute is
    not one change but a choice among at least three, and none is obviously right:
    - **anchor it to the install** - but a pip install has no single home, and a frozen bundle's
      directory is read-only;
    - **resolve it once at process start and keep it** - removes the mid-run surprise, keeps the
      launch-directory surprise;
    - **retire the legacy path on a schedule** - honest, and it needs a migration story for anyone
      still holding one, which is exactly what `(aae)` promised not to force.
    ⚠ **No route is recommended and none has been tested.** What is established is that the
    current behaviour is not a decision anybody made.
  - **What would close it cheaply and is not the fix**: a guard that fails if the suite's own
    `default_catalog_path()` resolves outside the test's temporary root. That protects this
    repository and leaves every user's `cd` doing the same thing. Worth having; not a substitute.
  - **Cross-references.** `(adv)` - the precedence defect found alongside this, now fixed.
    `(aae)` - why the legacy path exists and the promise it keeps.
