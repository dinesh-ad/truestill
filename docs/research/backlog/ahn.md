# (ahn) THE PAYLOAD CONTRACT STOPS AT THE PYTHON BOUNDARY, AND REACT IS BEING BUILT AGAINST NOTHING.

*Body of backlog entry `(ahn)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahn) THE PAYLOAD CONTRACT STOPS AT THE PYTHON BOUNDARY, AND REACT IS BEING BUILT AGAINST
  NOTHING.** Filed 2026-08-25 (P81).

  ## THE GAP

  **117 TypedDicts, 579 key slots, 289 distinct key names** describe what every route returns, in
  Python, and **nothing carries any of it across the wire**. `(ahl)` measured the consequence from
  the other side: **34** key names reach no consumer, and the React source consumes **zero** payload
  keys of any kind.

  ⚠ **THE LIVE INSTANCE IS ALREADY IN THE TREE, BEFORE A SINGLE SCREEN EXISTS.**
  `frontend/src/main.tsx:37`:

  ```ts
  type OrganizeSummary = Record<string, unknown>;
  ```

  A 2026 write-up names this exact failure: the wrapper casts the error away, so generated types
  can update without complaint, the pull request goes green, and the frontend reads a shape that no
  longer exists. `Record<string, unknown>` is that cast, written by hand, and it is the **first**
  payload type the React rewrite has.

  ## THE MECHANISM, which is a field standard rather than an invention

  **The backend emits an OpenAPI spec; `openapi-typescript` generates the TypeScript types; the
  frontend imports them.** That is mechanical at **both** ends - and the second end is precisely
  the one `(ahl)`'s census cannot reach, because it is reduced to grepping JavaScript for key names
  and cannot tell code from a comment.

  ## ⚠ WHY THIS PROJECT DOES NOT GET IT FREE, and the reason is a recorded decision

  FastAPI derives the spec from Pydantic models at no cost. This app is **Starlette**, and not by
  accident - `packages/truestill-app/pyproject.toml:17` records the choice and its reason:

  > *"not FastAPI (wraps Starlette+Pydantic; Pydantic is disallowed for our models and unneeded for
  > one user)"*

  Checked: **`pydantic` appears in no `pyproject.toml` in this workspace.** So the cheapest route to
  the mechanism is closed **by a decision that is still standing**, and this entry does not propose
  reversing it. That is what makes the design a separate turn rather than an obvious step.

  ## THE THREE SHAPES, and what is measurable about each today

  ⚠ **This entry does NOT choose between them.** It records the gap and the mechanism.

  | shape | measured cost | measured? |
  |---|---|---|
  | **hand-write the spec** | **579 key slots** to transcribe and then keep in step by hand - a second list beside the TypedDicts, which is the failure mode this repo files entries about | ✅ derived |
  | **generate from the TypedDicts** | the extraction half **already works**: one AST pass yields 117/579/289, both declaration forms, in well under a second. What is missing is Python-type to JSON-Schema mapping, and the route-to-payload join below | ✅ the extraction; ❌ the mapping, not estimated |
  | **emit from the routes** | ⚠ **the join does not exist.** `server.py` declares **50** `Route(...)`s and **all 50** handlers are annotated `-> JSONResponse`, never the TypedDict they return. Nothing anywhere declares which route returns which payload | ✅ derived |

  🔑 **That last row is the finding.** Whichever shape wins, something has to state
  route-to-payload for 50 routes, and today **no artefact does** - which is also why `(ahl)` had to
  work at key-name granularity and could not see `BakeSummary.absent`.

  ## WHY THE TIMING MATTERS

  `react-migration-plan.md` already carries the argument: *"Rewriting the UI against a contract
  nobody has declared reproduces every one of these in a new language."* `app.js` is the only thing
  that currently knows which fields are real, and it is scheduled for deletion.
  `test_surface_parity.py`'s own docstring says it does not cover this - it *"protects the REPAIR,
  not the contract."*

  **`(ahl)`'s census expires when `app.js` does. This is what replaces it**, and it replaces it
  with something mechanical at both ends rather than a list somebody maintains.

  ## STAGES 1-3 SHIPPED. WHAT STAGE 4 NEEDS, AS A LIST

  Stage 1 (`JobTarget[T]`, 11 factories) and stage 2 (the route resolver, 47 of 50) made the
  **declared** end exact. Stage 3 asked whether that turns `(ahl)`'s 34 into a count. **It does
  not** - it turns three specific hidden fields into named ones and proves the method's limit.

  ⚠ **These five are prerequisites, not stage 4 itself.** Recorded so the next turn starts from a
  list rather than a survey.

  1. **The seven literal payloads must be typed.** A dict literal has no schema, so each is a hole
     *in* the spec rather than a note beside it. `_start_drive_job`'s `{"job_id"}` first: one key,
     **15 call sites**, and the envelope every job route returns.
  2. **Twelve routes resolve to 2-3 payload types and each needs a ruling.** 35 of 47 resolve to
     exactly one. A `oneOf` is a legitimate answer, but it must be **decided** - a resolver
     returning a set cannot tell a real union from an extra reference it happened to find.
  3. **A Python-type to JSON-Schema mapping** for 117 TypedDicts, including the **29** that are
     nested-only and the `X | Y` unions.
  4. ✅ **RULED 2026-08-25 (P91), and it is no longer a blocker.** It was filed as *"OpenAPI has
     no place for an event stream, so the job summaries have no home"*. **That framing was too
     pessimistic and the derivation says why**: the summaries were never the problem - they are
     component schemas either way - and the stream's own contract is **three fixed shapes**:
     `progress` (`jobs.py:356`, 6 keys), `done` (`jobs.py:379`, `type`/`status`/`summary`) and
     `error` (`jobs.py:429`, `type`/`message`/`code`), plus `: ping` comment frames that carry no
     payload. All the variability lives in `done.summary`.
     **The ruling**: the event payloads are OpenAPI **component schemas**, and
     `/api/jobs/{job_id}/events` **references** them as `text/event-stream` with a `oneOf` over the
     three envelopes - so the link is mechanical rather than the prose the field pattern settles
     for, and nothing is left unreferenced. The document states its own limit: the schema is **one
     frame**, the body is a sequence of them. AsyncAPI is refused on `(agc)` - a second spec and a
     second toolchain is a second authority that can disagree - and a documented exclusion is
     refused because it would leave the run summaries untyped at the consumer, preserving exactly
     the cast stage 5 exists to delete.
     ⚠ **THE FINDING, WHICH OUTLIVES THE RULING: `ok` IS NOT ON THE WIRE.** `streamJob` synthesises
     `{ok: !failed, ...d}` at `app.js:166`, so the `d` every `runJob` handler reads is a
     **browser-side adapter**, not the server's contract. A spec written from what the handlers
     read would **freeze that adapter into the contract** and hand React a type for a shape the
     server never sends. Whoever writes stage 4d must describe `jobs.py`'s three envelopes, not
     `app.js`'s `d`.
     ⚠ **And the browser is the only consumer**, checked: `/api/` matches **0 files** under
     `packages/truestill-cli/src/`, and there is one `EventSource` call site. The spec is a
     **codegen input, not a public contract** - which is what makes the one-frame inaccuracy cost
     nothing and AsyncAPI's ceremony unjustified.
  5. **`NotRequired` must map to optional, read from the AST.**
     `test_migrate_reports_its_stop.py:149` records that runtime `__required_keys__` is **vacuous**
     under `from __future__ import annotations` - every key reads as required. A generator using it
     would be wrong about every optional field, and `elapsed_seconds` is on nearly all of them.

  ## RELATED

  `(ahl)` (the census this makes obsolete, deliberately), `(adi)` (the React migration, by island),
  `(abm)` (two fields that would never have shipped unread under a declared contract).
