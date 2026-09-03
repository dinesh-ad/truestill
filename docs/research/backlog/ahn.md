# (ahn) THE PAYLOAD CONTRACT STOPS AT THE PYTHON BOUNDARY, AND REACT IS BEING BUILT AGAINST NOTHING.

*Body of backlog entry `(ahn)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahn) THE PAYLOAD CONTRACT STOPS AT THE PYTHON BOUNDARY, AND REACT IS BEING BUILT AGAINST
  NOTHING.** Filed 2026-08-25 (P81).

  ## THE GAP

  ⚠ **NO TYPEDDICT COUNT IS CARRIED HERE (2026-09-02, P193).** The figures below were true when
  filed and stale three ways by P193: 128 class-form in the tree, 133 by import, 140 components
  once nesting is followed - and the AST census misses the three that inherit another TypedDict,
  `OrganizeDoneSummary` among them, the largest completion payload. **The count is derived at
  emission**, by stage C, and nowhere else. The original sentence follows as the record of P81.

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

  ⚠ *(Corrected 2026-09-02, P191: that sentence is this entry's own - `react-migration-plan.md` names
  no payload contract and does not cite `(ahn)`; its only "contract" is the e2e selector set.)*
  *"Rewriting the UI against a contract nobody has declared reproduces every one of these in a new
  language."* `app.js` is the only thing
  that currently knows which fields are real, and it is scheduled for deletion.
  `test_surface_parity.py`'s own docstring says it does not cover this - it *"protects the REPAIR,
  not the contract."*

  **`(ahl)`'s census expires when `app.js` does. This is what replaces it**, and it replaces it
  with something mechanical at both ends rather than a list somebody maintains.

  ## STAGES 1-3 SHIPPED. WHAT STAGE 4 NEEDS, AS A LIST

  Stage 1 (`JobTarget[T]`, 11 factories then, **13** on 2026-09-02) and stage 2 (the route resolver,
  47 of 50 then, **49 of 52** on 2026-09-02) made the
  **declared** end exact. Stage 3 asked whether that turns `(ahl)`'s 34 into a count. **It does
  not** - it turns three specific hidden fields into named ones and proves the method's limit.

  ⚠ **These five are prerequisites, not stage 4 itself.** Recorded so the next turn starts from a
  list rather than a survey.

  1. **The seven literal payloads must be typed.** A dict literal has no schema, so each is a hole
     *in* the spec rather than a note beside it. `_start_drive_job`'s `{"job_id"}` first: one key,
     **15 call sites**, and the envelope every job route returns.
  2. ⚠ **CORRECTED 2026-09-02 (P191): THE NARROWING DESCRIBED BELOW WAS NEVER COMMITTED.** The
     resolver in the tree is the reference-based one (`test_every_route_names_its_payload_type.py`,
     *"looks for the reference to `service.X` anywhere in the handler"*); run today it yields **12**
     multi-type routes and `JobTarget[BackupRunSummary]` for `/api/backup/run`. The 25 lives in
     `c6845d1`'s message and here. `_start_drive_job` has **17** call sites (4 direct, 13 pooled),
     not 15; and prerequisite 1 above is already discharged by 4a (`jobs.py:JobStarted`). The
     paragraph below is what P94 measured in a working tree and did not keep.
     ⚠ **THIS SAID "TWELVE ROUTES RESOLVE TO 2-3 TYPES, 35 OF 47 TO EXACTLY ONE", AND BOTH
     FIGURES WERE BUILT ON A RESOLVER ANSWERING A DIFFERENT QUESTION.** Corrected 2026-08-25 (P94)
     by narrowing it to **what reaches a `JSONResponse`** - returns, not references - and
     re-deriving before any row was written. **The count did not fall to three. It rose to 25.**

     **The prediction failed because the thing it was correcting was worse than measured**, in two
     ways found only by the narrowing:

     * ⚠ **For the job routes the old resolver named the wrong type entirely.** `/api/backup/run`
       resolved to `JobTarget[BackupRunSummary]` - **the factory's callable type, which is never a
       response.** The route returns a job envelope. So stage 2's *"47 of 50 name a payload type"*
       is true as written and the type named is not the payload, for every job route.
     * ⚠ **`_start_drive_job` returns THREE shapes** - a refusal Mapping, `DriveBusyPayload` and
       `JobStarted` - so **all 15 job-start sites are genuine unions**, and the old resolver saw
       inside that helper for only **4** of them (it followed `_start_drive_job(...)` and not
       `run_in_threadpool(_start_drive_job, ...)`, the `(agu)` hole its own docstring disclaimed).
       `expired_session`'s `ExpiredSessionPayload` was invisible the same way.

     🔑 **So 25 is more accurate than 12, not less**, and the shape of the work changes with it:
     the job envelope is **one reusable union component** shared by 15 routes, not 15 rulings. Six
     routes remain `GET`+`POST` on one `Route` object and are **two operations**, not unions.

     ⚠ **The narrowed resolver is NOT yet precise**: it reads a local's declared annotation without
     applying branch narrowing, so `jobs.start`'s `str | DriveBusyPayload` survives where only the
     `DriveBusyPayload` arm is ever sent. That must be fixed before rows are written, or the
     declaration encodes the resolver's remaining mistakes.

     **Nothing was declared this turn.** The gate was *"re-derive before writing any row; if the
     count is wrong, stop and report"*, and it is reported here rather than worked around.
  3. **A Python-type to JSON-Schema mapping** for every TypedDict (derived at emission), including the **29** that are
     nested-only and the `X | Y` unions.
  4. ✅ **RULED 2026-08-25 (P91), and it is no longer a blocker.** It was filed as *"OpenAPI has
     no place for an event stream, so the job summaries have no home"*. **That framing was too
     pessimistic and the derivation says why**: the summaries were never the problem - they are
     component schemas either way - and the stream's own contract is **three fixed shapes**:
     `progress` (6 keys), `done` (`type`/`status`/`summary`) and `error` (`type`/`message`/`code`) -
     all three built inside `jobs.py:JobManager.start` (corrected 2026-09-02; this cited `claim` and
     `_abandon`, which build no frame), plus `: ping` comment frames that carry no
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
     `{ok: !failed, ...d}` at `app.js:streamJob`, so the `d` every `runJob` handler reads is a
     **browser-side adapter**, not the server's contract. A spec written from what the handlers
     read would **freeze that adapter into the contract** and hand React a type for a shape the
     server never sends. Whoever writes stage 4d must describe `jobs.py`'s three envelopes, not
     `app.js`'s `d`.
     ⚠ **And the browser is the only consumer**, checked: `/api/` matches **0 files** under
     `packages/truestill-cli/src/`, and there is one `EventSource` call site. The spec is a
     **codegen input, not a public contract** - which is what makes the one-frame inaccuracy cost
     nothing and AsyncAPI's ceremony unjustified.
  5. **`NotRequired` must map to optional, read from the AST.**
     `test_migrate_reports_its_stop.py:test_the_app_summary_carries_the_stop_and_the_refusals` records that runtime `__required_keys__` is **vacuous**
     under `from __future__ import annotations` - every key reads as required. A generator using it
     would be wrong about every optional field, and `elapsed_seconds` is on nearly all of them.

  ## STAGE 4b, RE-DERIVED 2026-09-02 (P191) - AND WHERE IT STOPS

  `payload_contract.py:response_types` (moved from the resolver test in stage D) is the narrowed resolver. The rule,
  written down: **the response is the first positional argument of every `JSONResponse(...)`
  reachable from the handler**; a helper the handler returns through - `_start_drive_job`, directly
  or via `run_in_threadpool` - contributes every one of its responses; a local reads as its declared
  annotation or the type of what was assigned to it, in source order. Run over the tree:

  | | count |
  |---|---|
  | routes | 52 |
  | resolve to more than one type | **29** (stage 2's resolver says 12 for the same tree) |
  | of which: job-start routes sharing one envelope - `JobStarted` / `DriveBusyPayload` / the refusal Mapping | 17 |
  | of which: `GET`+`POST` on one `Route`, two operations not a union | 6 |
  | of which: genuine unions of payloads (events propose, apply, merge, split; clean-empty apply; bake run) | 6 |
  | unresolved expressions, kept under `?` | 1 - `clean_empty_apply`'s `jobs.claim(...)` refusal |

  ⚠ **Not precise yet, and the imprecision is measured rather than hidden**: no branch narrowing,
  so `result: str | DriveBusyPayload` reads as its declared union and `dict(target)` reads as
  `target`'s whole parameter annotation, `JobTarget[object] | Mapping[str, object]`. A row written
  from this resolver would encode both. **No row is written.** P94's 25 was measured in a working
  tree that was never committed; 29 is what the tree holds now, and the difference is the routes
  added since (`(aix)`'s rename pair, `clean-empty/apply`).

  ## TWO RULINGS FOR THE MAINTAINER, WITH THE PROPOSAL AND ITS COST

  1. **The emission shape.** The table above lists three and chooses none. The tree suggests a
     fourth it does not list, and it is the proposal: **components from the TypedDicts, the
     route-to-payload join from the narrowed resolver.** The extraction half exists
     (`test_no_thirty_fifth_dead_payload_key.py:_declared`, every TypedDict in under a second); the
     join half now exists (`_response_types`); what is missing between them is the Python-type to
     JSON-Schema mapping (4c: every TypedDict, derived at emission, 29 nested-only, `X | Y` unions, `Literal` tags,
     `NotRequired` read from the AST per 4e) and one script that writes `openapi.json` from the
     two. **Cost**: 4c is mechanical and sizeable, about the size of `_declared` again; the script
     is one function; a contract test that regenerates and diffs is one file. Hand-writing 579
     slots is refused for the reason the table gives; emitting from routes alone cannot name a
     component. Branch narrowing (the imprecision above) is a second, smaller ruling inside this
     one: either accept the union as declared, or hand-write the two narrowings as `TypeGuard`s the
     way `server.py:_is_not_confirmed` already does for `BakeRefusal`.
  2. **The node dependency.** `openapi-typescript` is not in `frontend/package.json`. Types only,
     no runtime, MIT, milliseconds; the alternatives generate clients and hooks the project does not
     need or are unmaintained. Adding it is `(agc)`'s kind of decision and is not taken here.

  Stage 5 then is one generated file imported at `main.tsx`'s cast, and `main.tsx:37`'s
  `Record<string, unknown>` is deleted - the whole point.

  ## RULED 2026-09-02 (P193): THE SHAPE, THE DEPENDENCIES, AND WHAT MSGSPEC PROVED

  **Ruling 1**: components from the TypedDicts, the route join from the narrowed resolver; the
  spec is **committed** and CI is red on drift. **Ruling 2**: `openapi-typescript` is a frontend
  dev dependency. **Prior art**: `airbytehq/airbyte-python-cdk#751` - a CI check that the
  committed OpenAPI spec is current whenever the API models change. ⚠ **A cited example the
  advisor supplied could not be found** (a write-up attributed to *mcalthrop*, April 2026;
  searched by name and by phrase, nothing carrying it) and was replaced rather than kept. Same
  class as the four entries wrong about their own subject, and it came from the maintainer.

  **msgspec, tried on every TypedDict in a throwaway environment, 2026-09-02**:

  | | evidence |
  |---|---|
  | as shipped | `TypeError Literal may only contain None/integers/strings - typing.Literal[False] is not supported` on **35 of 133** - every `ok: Literal[True]`/`Literal[False]` tag; and `Type unions may not contain more than one TypedDict type`, which is every multi-type route |
  | `NotRequired` at runtime | on 3.14 under `from __future__ import annotations`, `IngestPreviewEmpty.__optional_keys__ == []` while `get_type_hints` reads `NotRequired[str]` - msgspec would emit all **25** optional fields as required, silently |
  | with a rebuild pass (TypedDicts rebuilt from `get_type_hints`, boolean `Literal` → `const`) | `ok 133 failed 0 in 30 ms`; 140 components; **0** of 25 `NotRequired` fields wrongly required; `openapi-typescript` 7.13.0 consumed the result in 135 ms with `ok: false` preserved |
  | the inventory is not the wire | seven components are **dataclasses** (`ReviewCard`, `TripProposal`, ...) reached through `EventProposalSuccessPayload` and `MergeReviewCardsResult`, which are internal session objects; the wire shape is `ReviewCardsPayload` and the resolver already names it |

  **So msgspec replaces the type-to-schema half of 4c** with a library call plus that pass, and
  the pass is where prerequisite 5 lives. It is a **dev** dependency: 0.21.1, BSD-3, zero
  dependencies, 48 wheels including cp314 and cp314t, ~220 KB, never imported at runtime. The
  Pydantic ruling (`packages/truestill-app/pyproject.toml`, *"disallowed for our models"*) is
  about a model layer; this defines no model and touches no request path.

  ⚠ **THE RULE STAGE C'S SCRIPT MUST CARRY IN ITS OWN TEXT: emit the closure of what the
  resolver names per route, never the TypedDict inventory.** Emitting from the inventory puts
  the seven dataclasses and two session objects into the spec describing nothing the server
  sends. Whoever reads `emit_openapi.py` meets that there or repeats it.

  ## THE STAGES, SMALLEST FIRST, EACH MAKING THE NEXT SAFE

  | stage | proves | status |
  |---|---|---|
  | **A · close 4b** - the busy arm and the clean-empty arm bound to annotated locals (the `dates_bake_run` convention); the resolver binds a helper's first parameter to the caller's argument and drops `JobTarget[...]` members, so the refusal arm is named per route | the join is exact; every later row reads it | ✅ **`bc484fc`, 2026-09-02**: 52 routes, 17 job-start, **0 unresolved**; 29 multi-type by type-string, **40 by member**. Backup's envelope is `JobStarted \| DriveBusyPayload` with no refusal arm; the bake's carries `BakeRefusal` and `DriveUnavailablePayload`. Four mutants, four caught |
  | **B · type the SSE frames** - `progress`/`done`/`error` are dict literals on `queue.Queue[dict[str, Any]]`, plus a hand-written `event: error` for an unknown job; `done.summary` is the union of the 13 factories' `T` | the stream has a schema to reference; 4a for the stream | ✅ **`7d4a0b5`, 2026-09-03**: `ProgressFrame`, `DoneFrame`, `ErrorFrame`, and a **fourth**, `UnknownJobFrame`, the hand-written bytes no queue census could see; there is no fifth (two puts, four yields, one a comment). `DoneFrame.summary` is `object` and its union is **derived** - 13 factories, 16 types - never listed. The literal census now reads the stream: **five** unnamed on the old file, none on the tree. Four mutants, four caught |
  | **C · the rebuild pass + msgspec**, guard first: every AST `NotRequired` absent from `required`, every `ok:` tag a `const`, no component the resolver does not reach | 4e proved before 4c is trusted | ✅ **`adf2a2e`, 2026-09-03**: `scripts/emit_openapi.py`, the inventory rule in its own text. **128 components from 74 roots**, derived; the inventory reads 135 in the app plus two in core reached by nesting. A fourth root source the derivation found: the exception handler's `CatalogBusyPayload`, which no route walk reaches. Lowered: 36 boolean tags to `const`, 27 optional fields correct against the AST; refused: a dataclass, a bare `object` outside `DoneFrame.summary`, a union of two TypedDicts in a field. Floor in `test_the_contract_components_are_derived.py`. Five mutants, five caught |
  | **D · the join + emission** - `oneOf` of `$ref`s per route, `GET`+`POST` as two operations, the events route as `text/event-stream`; `openapi.json` committed; a Python-only regenerate-and-diff test in `make check` | the spec is the artefact and drift is red, in the lane with no Node | open |
  | **E · stage 5** - `openapi-typescript`; `api.d.ts` generated and committed with the spec's sha256 in its header; `make frontend` regenerates and diffs; a Python test checks the header hash; `main.tsx`'s cast deleted | a read is a type reference | open |

  **The contract test**: (1) `openapi.json` equals what the tree emits - Python, `make check`;
  (2) `api.d.ts` was generated from this spec - header hash in `make check`, full diff in
  `make frontend`; (3) every response property is referenced from `frontend/src` by the
  TypeScript compiler's reference search - the Node lane, and **what replaces `(ahl)`'s
  `DEAD` table**, still not liveness and said so. **Neither census goes at stage 5**: the
  job-summary guard retires row by row per island; the dead-key census goes when `app.js` does.

  ## RELATED

  `(ahl)` (the census this makes obsolete, deliberately), `(adi)` (the React migration, by island),
  `(abm)` (two fields that would never have shipped unread under a declared contract).
