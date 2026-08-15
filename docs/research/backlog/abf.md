# (abf) A fix does not retroactively clean what it prevented.

*Body of backlog entry `(abf)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abf) A fix does not retroactively clean what it prevented.** Recorded 2026-08-05.
  - Row **id=1** in the maintainer's catalog has a `source_path` under a pytest temp directory -
    `/tmp/pytest-of-<user>/pytest-81/test_skip_undated_names_skippe0/src/…` - naming the test that
    created it. A **test run** wrote into a real catalog. (The username is elided here on
    purpose; the load-bearing part is the tmpdir and the test name.)
  - **`(aae)` is recorded as fixed and it was** - `TRUESTILL_DATA_DIR` / `TRUESTILL_CACHE_DIR`
    honoured on every platform, a root `conftest.py` redirecting both for the session, and
    `default_catalog_path` resolved per call so a test can isolate it. Nothing here reopens it.
  - **The point is the general one, and it is why this has its own letter:** a prevention fix
    leaves its own history behind. `(aae)`'s entry describes the stray file it found and deleted;
    this row is a *different* survivor, in a different catalog, still counted today - it is one
    of `(abe)`'s 31. **When a fix stops a class of damage, ask separately whether existing damage
    is being carried**, and record the answer either way. The two questions look like one.
