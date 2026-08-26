# (ahw) THE APP'S EVENT QUERY TESTS A LABEL WHERE A RULE WAS MEANT, AND THE TRIPS SCREEN GOES DEAD.

*Body of backlog entry `(ahw)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahw) THE APP'S EVENT QUERY TESTS A LABEL WHERE A RULE WAS MEANT, AND THE TRIPS SCREEN GOES
  DEAD.** Filed 2026-08-26 (P103).
  **A rule with a named violator**, and the census is the entry's real subject.

  ## THE RULE, VERBATIM

  `layout.py:530-532` already forbids exactly this test:

  > routing keys on the **rule, not the label**: under `--by-device` the label is the hardware
  > name, so a label test would send a whole library into a side bin.

  And `layout.py:535-545` names the consequence: *"missing one would put a file on the timeline
  while silently excluding it from event naming or trip placement."*

  ## THE VIOLATOR

  `catalog.py:1286-1289`, `camera_copies_for_events`:

  ```sql
  WHERE fc.drive_uuid = ? AND f.category = 'Camera' AND f.captured_at IS NOT NULL
  ```

  A hardcoded label literal. The CLI asks correctly, by rule - `event_review.py:68`, against
  `TIMELINE_RULES` (`layout.py:549`). The app's path (`server.py:800` -> `service/trips.py:362` ->
  `trip_review.py:197`) asks by label.

  **Under `--by-device` the label is `Samsung SM-A546B`, the SQL matches zero rows, and the Trips
  screen proposes nothing.** `rule_camera_filename` survives it only by emitting the same label
  string (`categorize.py:440`) - luck, not design.

  ## WHAT THE USER SEES

  Not an error. Not an empty state with a reason. **A screen that proposes nothing and looks like
  a library with no trips in it.** The user concludes their photos do not group; the product has
  simply asked the wrong question. That is why this outranks the record corrections it was filed
  beside.

  ## THE CENSUS P104 MUST RUN

  **Every place a category LABEL is tested where a RULE was meant.** Three definitions of one
  concept exist and none derives from another:

  | | site | kind |
  |---|---|---|
  | 1 | `TIMELINE_RULES` (`layout.py:549`) | the rule set |
  | 2 | `CAMERA_LABEL` (`categorize.py:65`) | the label constant |
  | 3 | the SQL string literal (`catalog.py:1289`) | **does not import #2** |

  A fourth module handles the same hazard correctly and says so -
  `packages/truestill-core/src/truestill_core/migrate.py:218-233`: *"The catalog records a
  **label**, not the rule that produced it (`files.category`), and an organize run routes on the
  rule -- so this is the bridge."*

  ⚠ **Nothing guards it.** Checked: `grep -rn "TIMELINE_RULES" packages/` reaches only Python
  identifiers, and a grep for the constant **cannot see inside a query string**, which is exactly
  why `layout.py:535-545` did not catch `catalog.py:1289`. **So one instance found by a soak is
  not evidence of one instance existing** - that is the census's whole justification.

  ## CAN THE CENSUS BE GUARDED, OR ONLY RUN ONCE?

  **Guarded**, and the design turns on one inversion: key on the label **VALUE** inside string
  literals, not on the constant's name.

  - **Derived**: walk `packages/*/src` `.py` (`ast`) and `.js`, collecting every string literal
    containing a known category label as a whole word; docstrings excluded. The label set is read
    from `categorize.py`, not re-listed, so a new label joins without touching the guard.
  - **Declaration**: a short allowlist of sites permitted to name a label literally.
  - **Assert**: every derived hit is in the allowlist - the DERIVED inventory looped and asserted
    into the DECLARATION, never the reverse.

  **Prove it bites**: `scripts/mutate_once.py` on `catalog.py:1289`. It must go red on today's
  tree before the fix lands, which makes it a regression test as well as a census.

  ⚠ **Two blind spots, stated rather than implied.** It cannot see a label assembled at runtime -
  and `--by-device` labels are exactly that, `sanitize_label(f"{make} {model}")`
  (`categorize.py:404-407`) - so the dynamic labels are out of scope by construction. And it
  cannot catch the inverse error, a rule test where a label was meant.

  **The census and the guard are one piece of work.** A census with no guard is a snapshot.

  ## THE SAFETY CONDITION, BEFORE ANYONE BUILDS THE FIX

  ⚠ **It is not a one-line swap, because the rule is not persisted.** `files` carries
  `category TEXT NOT NULL` and no rule column (`catalog.py:83-108`, the column at `:92`). Three
  shapes, and the third must be refused with a reason rather than tried:

  1. persist the routing **decision** at organize time (an `on_timeline` column) - cheapest query;
  2. persist the **rule** (a `category_rule` column) - most general;
  3. map label -> rule at query time - **fails under `--by-device` by construction**, the labels
     being unenumerable in SQL.

  A backfill can re-derive the device rule for existing rows: `camera_make` and `camera_model` are
  persisted (`catalog.py:103-104`).

  🔑 **AND THE TWO SELECTIONS PROVABLY DIVERGE - the fix is not a strict repair.**
  `categorize.py:216-224` says it outright: *"`software` names a folder after whatever an app
  stamped"*, and `packages/truestill-core/src/truestill_core/migrate.py:229-231` says
  ``Camera`` *"is the device rule's default label **and** a perfectly possible ``Software``
  value"*. So `f.category = 'Camera'` selects **more** than `rule in TIMELINE_RULES`: a file
  labelled `Camera` by `rule_software` is on the Trips screen today and the rule-based fix would
  **remove** it. On ordinary libraries, not only `--by-device`.

  **So every fix carries its own before/after set comparison**, and a site whose label and rule
  select differently is a **separate ruling**, not a mechanical repair. Only provably-identical
  sites are mechanical. That is what stops a census becoming one large behaviour change presented
  as tidying.

  ⚠ **The diff has its own catch**: the rule-based selection cannot be run against today's catalog
  at all, there being no rule column, so the comparison must be made at organize time in memory or
  by re-deriving from the persisted camera fields. Any other way is measuring the instrument.

  ## RELATED

  `(ahv)` (the signature this query feeds), `(afa)`, `(adi)`,
  [`cli-app-parity.md`](../../cli-app-parity.md).
