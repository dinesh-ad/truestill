# (aan) A "verified against code" clause must still resolve.

*Body of backlog entry `(aan)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aan) A "verified against code" clause must still resolve.** Recorded 2026-08-01 while
  moving `(aae)` and `(jj)` into the built section. **Record only - needs its own
  measured-scope pass before it is built.**
  - **The failure it prevents.** `(aae)` sat in the wrong section asserting a *"Current state,
    verified against code 2026-07-31"* that named `DEFAULT_CATALOG_PATH`, `catalog_startup.py`,
    `cli.py` and `server.py` line numbers. The symbol had been deleted and the line numbers had
    moved. **A document saying it was code-verified is not evidence**, and a cold start has no
    way to tell which of those citations still means anything.
  - **Why the obvious guard is the wrong one, measured before proposing it.** A check keyed on
    completion vocabulary appearing in the section for open work **misses `(aae)` entirely**,
    because that entry carried none of it - it said *record only*. It also cry-wolfs
    immediately on `(bbb)` and `(r)`, which are legitimately partial, say so, and are licensed
    by this section's own preamble. So the discriminator is not status vocabulary. It is
    whether the entry's factual claims about code still hold.
  - **The check that fits:** every backticked **symbol** inside a verified-against-code clause
    must exist under `packages/*/src`. Symbols, never line numbers -
    `IMPLEMENTATION_STANDARDS.md` already states that symbols are cited over line numbers
    because line numbers drift by design.
  - **The cry-wolf surface, which is why this is recorded and not built.** A backtick in these
    documents holds a Python symbol, a table name (`file_copies`), a column
    (`files.date_source`), a CLI flag (`--apply`), a setting key
    (`layout.everyday_day_threshold`), a typed confirm word (`delete forever`) and a filename.
    Only the first is checkable this way and no regex separates them by shape. Whatever rule is
    chosen needs the measured before/after row this repo asks of every guard - the worked
    example is `test_backlog_references.py`, scoped against the real file rather than a
    plausible phrase list.
  - **A second instance of the same class, in case the guard should generalize.**
    `scripts/benchmark_hashing.py` says `TRUESTILL_CORPUS` is *"named by environment variable
    (`docs/PROJECT_STATUS.md` §6)"*. §6 exists and documents nothing of the kind - the variable
    appears nowhere in that file. A live citation to a real section that does not carry the
    claim, which an anchor-existence check would not catch either.
  - **A third instance, and this one landed in the BINDING CONTRACT.** `956953f` deleted
    `dedup.LINEAR_SCAN_ALARM`; `IMPLEMENTATION_STANDARDS.md` §8 went on naming
    `dedup.LINEAR_SCAN_ALARM = 10_000` as live machinery until it was swept a commit later, and
    `dedup.py`'s own docstring pointed at `BACKLOG.md (v)` after `(v)` had moved to
    `SHIPPED.md`. **Both were found by a manual grep that only happened because someone asked
    "why was it built this way?"** - which is not a process. Two things this instance settles
    about the guard's design: the contract needs to be in scope (it is the document a conflict
    resolves *toward*), and a backticked `Module.SYMBOL` is the highest-value shape to check
    first, since it is unambiguous where a bare word is not.
  - **Related, not the same.** `test_backlog_references.py` already guards the opposite
    direction - a settled item described as pending elsewhere - and deliberately scans only
    settled sections. Noted while here: its `_SETTLED` markers do not match
    `## Shipped (kept for provenance)`, so that section is currently outside its scope.
