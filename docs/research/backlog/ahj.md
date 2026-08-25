# (ahj) §1b's FOURTH EXIT CONDITION IS CHECKABLE, AND IS CHECKED BY A CENSUS.

*Body of backlog entry `(ahj)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahj) §1b's FOURTH EXIT CONDITION IS CHECKABLE, AND IS CHECKED BY A CENSUS.** Filed
  2026-08-25 (P72).

  ## THE PROBLEM

  `PROJECT_STATUS.md` §1b's fourth condition - *"no mutating behaviour lives only in the app"* -
  was verified **by hand three times this month** and found three surfaces (bake, backup, trip
  apply). Nothing runs it. A condition nobody can test is a condition that drifts, and this one
  demonstrated that on itself: it named only bake, and stayed that way through two commits that
  changed the answer.

  ## IT IS DERIVABLE ON BOTH SIDES, MEASURED

  | inventory | source | count |
  |---|---|---|
  | mutating operations | `mutating=True` calls in `server.py`, AST | **9** |
  | CLI subcommands | `add_parser` names in `cli.py`, AST | **19** |

  **Four of the nine auto-join** by name: `backup`, `organize`, `clean empty` → `clean-empty`,
  `undo organize` → `undo-organize`. The other five do not - `set dates` is `bake`, `migrate` is
  `migrate-layout`, `undo` is `migrate-layout --undo`, `archive unpack` is part of `ingest`, and
  `trip apply` is two operations of which one is deferred.

  ## THE SHAPE, AND ITS HONEST COST

  A **nine-row declared table**, checked at both ends:

  * every `mutating=True` operation must have a row - so a new one cannot ship unlisted;
  * every row must name **either** a subcommand that exists in the parser **or** a deferral.

  ⚠ **Stated rather than implied: the join itself is prose and cannot be derived.** Nothing in the
  codebase declares that *"set dates"* is `bake`. What becomes mechanical is that no operation and
  no subcommand is **missing** from the table - which is the failure that actually happened, three
  times. Claiming more than that would be the guard-aimed-through-a-lens-that-cannot-resolve-it
  shape §4 keeps finding.

  This is `MUTATING_RUNS`' shape from P69, extended, and it would **subsume `(ahi)`**.

  ## ⚠ CORRECTED 2026-08-25 (P76 ruled it, P77 shipped the prerequisite)

  **It is a column on `_EXPECTED`, not a fourth table.** That table is already keyed by operation
  string, already holds every mutating operation, and already fails when a route is absent from it.

  **The `(ahi)` subsumption is withdrawn.** `MUTATING_RUNS` is keyed by service module; consolidating
  needs a second, different join.

  **What it pins, stated at the right size:**

  | | |
  |---|---|
  | condition 4, subcommand end | ✅ mechanical - the parser's `add_parser` names are AST-derivable |
  | condition 4, deferral end | ❌ the register is prose with no key; the row can declare `deferred`, a guard cannot check the register |
  | condition 1 | ⚠ **wiring only** - `_wires_a_record` proves a call exists in the code, not that it runs. `(agj)` is the defect it would miss |

  **Prerequisite, shipped P77**: `_declared()` read callee names and missed `jobs.claim`, so
  `clean empty` was in neither the derived inventory nor `_EXPECTED`. It matches the declaration
  now. `ENGINEERING_STANDARD.md`'s **seventy-second member** records the general rule.
