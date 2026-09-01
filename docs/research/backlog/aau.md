# (aau) A zero-warning test lane, and why it is not one today.

*Body of backlog entry `(aau)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aau) A zero-warning test lane, and why it is not one today.** Recorded 2026-08-02 after two
  cleanup commits took the suite from **36 `ResourceWarning`s to 1**. **Record only - the lane
  cannot land until the last warning is either owned or proven un-ownable.**
  - **A gate that cannot pass on the day it is added is a broken gate.** One warning survives, and
    a lane that fails on its own first commit teaches everyone to ignore it.
  - ⚠ **RE-MEASURED 2026-08-22: THE COUNT MOVED THE WRONG WAY, AND THE SURVIVOR IS NO LONGER
    UN-OWNABLE.** `uv run pytest` over 2,849 tests reports **7 warnings**, not 1. More usefully,
    the suite now names an allocation site the entry says was unknown:
    `truestill_core/layout.py:LayoutTemplate._render_segment.substitute`, *"ResourceWarning: unclosed database"*, attributed to
    `test_the_run_argues_only_while_it_can_be_stopped.py` and others - a collector-timed warning
    landing on whichever test is running, exactly as described, but with the **allocating module
    now visible without `tracemalloc`**.
    **This makes the entry more actionable, not less**: its own bar is *"the last warning is either
    owned or proven un-ownable"*, and one of the seven now has an owner to look at. It also means
    the 36-to-1 figure is a **dated reading** rather than a standing state - count it rather than
    quote it. ⚠ And the growth is the argument for the lane, not against it: nothing noticed six
    new warnings arriving, because nothing was watching.
  - **The survivor, described rather than blamed.** An unclosed `sqlite3.Connection` is collected
    during `test_layout.py::test_parse_rejects_empty_and_empty_segments`, reported against stdlib
    `inspect.py`. **That test opens no catalog, and `test_layout.py` constructs no `Catalog`
    anywhere** - the connection was allocated by something else and merely finalised there. That
    is the whole difficulty: a collector-timed warning lands on whichever test happens to be
    running. Without `tracemalloc` the allocation site is unknown, and enabling it across the
    suite costs more than the warning does.
  - **The existing policy stays, for its recorded reason.** `pyproject.toml` exempts
    `ResourceWarning` from `filterwarnings = ["error"]` because it is about *when* the collector
    runs, not about an API: *"turning a real deprecation gate into a flaky one is how gates get
    switched off."* A zero-warning lane sits beside that policy; it never replaces it.
  - **The shape it should take if the survivor proves un-ownable:** assert **no warning
    attributable to our code** - keyed on whether any frame under `packages/` appears - rather
    than a raw count of zero. A count gate fails on someone else's finalizer; an attribution gate
    fails on ours, which is the only one worth waking up for.
