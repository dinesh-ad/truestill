# (ajt) THE JOB ENVELOPE HAS NO TAG, SO EVERY JOB ROUTE'S RESPONSE IS A BARE UNION.

*Body of backlog entry `(ajt)`, under **Ideas / deferred**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ajt)** Filed 2026-09-03 (P199), at `(ahn)`'s closure.

  ## THE FACT, DERIVED

  `test_the_committed_spec_is_current.py:test_which_unions_can_be_discriminated_is_derived_and_said`
  prints the census on every run: **0** unions share a string-valued fixed property, **13**
  two-member unions share a boolean one (`ok`, `valid`, `armed`, `created`), **10** share nothing.
  The ten are the job envelopes (`JobStarted | DriveBusyPayload | ...`), the `GET`+`POST` settings
  routes' state-or-result pairs, and the four frames on the event stream, where `UnknownJobFrame`
  carries only `message`.

  ## WHAT IT COSTS TODAY, AND WHAT A TAG WOULD COST

  Today: `openapi-typescript`'s shape and this repo's emitter both render a bare `oneOf` as a union
  of the exact component types, and TypeScript narrows it with `"job_id" in body`. Strictly more
  than the `Record<string, unknown>` the island carried until stage E.

  A tag: `JobStarted` would gain `ok: Literal[True]` (the convention twenty-four payloads already
  use), which changes the body **seventeen** job-start routes return and every reader of it in
  `app.js`. The emitter then emits a `discriminator` for nothing, since the tag is boolean and
  OpenAPI requires a string; the gain is TypeScript narrowing on a literal instead of `in`.

  ## NOT DECIDED

  Whether the gain is worth a wire change. Nothing blocks on it.
