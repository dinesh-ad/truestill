# (adv) `TRUESTILL_DATA_DIR` IS SILENTLY OVERRIDDEN BY THE LEGACY CATALOG PATH.

*Body of backlog entry `(adv)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adv) `TRUESTILL_DATA_DIR` IS SILENTLY OVERRIDDEN BY THE LEGACY CATALOG PATH.** Recorded
  2026-08-18, found while checking whether `(ads)`'s overridden-data-directory arm was even ready
  to run. **Independent of `(ads)`**: a user who sets the variable can operate on a different
  catalog than the one they named, and the product never says the variable lost.
  - **The mechanism, and it is an ordering, not a bug in either half.** `default_catalog_path()`
    (`app_paths.py`) asks two questions in this order:
    1. `_working_directory_was_chosen() and LEGACY_CATALOG_PATH.exists()` - a **relative** path,
       `reports/catalog.sqlite`, resolved against the current working directory;
    2. `_data_dir() / CATALOG_FILENAME`, which is where `TRUESTILL_DATA_DIR` is honoured.
    **The legacy check wins**, so an explicit environment variable loses to a file that happens to
    sit under the process's CWD.
  - 🔬 **VERIFIED BOTH WAYS, 2026-08-18**, because "the override is ignored" and "the override is
    ignored *here*" are different findings:

    | `TRUESTILL_DATA_DIR` | working directory | `default_catalog_path()` resolves to |
    |---|---|---|
    | `.../Output/ovr` | the repo root (has `reports/`) | ⚠ `…/truestill/reports/catalog.sqlite` - **override ignored** |
    | `.../Output/ovr` | a directory with no `reports/` | ✅ `.../Output/ovr/catalog.sqlite` - **honoured** |

    Same process, same variable, same command; only the CWD differs. So the variable is not
    broken - it is **conditional on something the user did not state and is not told about.**
  - **How loud it is, measured rather than assumed - and it is louder than "silent".**
    `truestill status` with the variable set and shadowed prints
    `Catalog: /home/…/truestill/reports/catalog.sqlite (2695 files)`. **The resolved absolute path
    IS on screen**, which is `(aae)`'s startup banner doing exactly its job. What is absent is any
    statement that a variable was set and did not win: the banner reads identically whether the
    override was honoured, ignored, or never set. **A reader must already suspect the problem to
    see it in that line**, which is the difference between a signal and a disclosure.
  - **Why it is a defect rather than a documented precedence.** The legacy check exists to keep
    `(aae)`'s backwards-compatibility promise: an upgrade must not silently start writing to a
    different, empty catalog while the real one sits in `reports/`. That promise is about the
    **absence** of a stated intention. `TRUESTILL_DATA_DIR` **is** a stated intention, and a
    compatibility guess that beats an explicit instruction has the precedence backwards.
  - **Blast radius, stated rather than implied.** Writes go to whichever file wins, so a user who
    believes they are operating on a relocated catalog is organizing, baking and recording drives
    against a different one. Nothing is corrupted - both files are valid catalogs - which is what
    makes it survivable and also what makes it hard to notice.
  - **Who actually meets it.** Anyone running `truestill` from a checkout that has `reports/`,
    which is every developer and every test that does not redirect. `conftest.py` sets both
    `TRUESTILL_DATA_DIR` and `TRUESTILL_CACHE_DIR`, and the suite passes - so **the guard rail
    that would have caught this is the thing that hides it**: tests run with a `tmp_path` CWD, so
    the legacy path never exists and the override always wins.
  - **Not settled here, because it is a precedence decision rather than a fix:** whether an
    explicit `TRUESTILL_DATA_DIR` should outrank the legacy path outright, or whether the two
    should be reported when they disagree and the user asked to choose. ⚠ **Reversing the order
    silently is not obviously safe either** - someone with both a legacy catalog and the variable
    set in a shell profile would move libraries without asking. **Whatever is chosen, the case
    where they disagree must say so**, which is the half that is not a judgement call.
  - **Cross-references.** `(aae)` - why the legacy path is checked at all, and the promise it
    keeps. `(ads)` - where this was found; its overridden-data-directory arm cannot run on this
    machine for an unrelated reason (the only network filesystems are fenced), but it would have
    measured the wrong file if it had.
