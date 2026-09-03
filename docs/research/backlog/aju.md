# (aju) CONDITION 3'S CONSUMED END WAITS ON THE REACT MIGRATION, AND §1b CANNOT ORDER IT BEFORE.

*Body of backlog entry `(aju)`, under **Blocked - do not build yet**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aju)** Filed 2026-09-03 (P199), at `(ahn)`'s closure.

  ## WHERE CONDITION 3 STANDS

  `PROJECT_STATUS.md` §1b's third exit condition, *"no route computes a field no consumer reads"*,
  has two ends. The **declared** end is finished: every route's response is derived
  (`payload_contract.py:response_arms`), the spec is committed (`emit_openapi.py`), the types are
  generated (`emit_api_types.py`), and `make check` is red on drift at both. The **consumed** end
  is still `test_no_thirty_fifth_dead_payload_key.py`: a regex over `app.js` and the hand-written
  React source, which holds **34** keys with a reason each, and which reads `src/generated/` as
  nothing - a declaration names every key and reads none.

  ## THE ORDERING PARADOX, STATED

  §1b orders *engine, then contract, then UI*, and lists this condition under *the engine
  finishes first*. It cannot: a field is unread until something reads it, and the thing that will
  read it is the UI. Stage E of `(ahn)` (2026-09-03) made the consumed end **checkable by a
  compiler** - once a React island reads a payload through `api.d.ts`, a key it reads is a
  reference the compiler resolves and a key it does not is a compiler fact, not a regex's. It did
  not tick the condition, and could not.

  ## WHAT RETIRES THE TABLE, EVENT BY EVENT

  - Each React island that owns a screen replaces that screen's reads; **the replacement census is
    a compiler-resolved reference search over the generated types**, run in the Node lane, and each
    `DEAD` key that screen owns is decided there: read on the screen, or deleted from its payload.
  - `test_job_summaries_are_read_where_they_are_delivered.py` retires row by row as the islands that
    own job screens land; `test_no_thirty_fifth_dead_payload_key.py` retires when `app.js` is
    deleted, its last reader.
  - The condition ticks when the table is empty. Blocked on `(adi)` by construction.
