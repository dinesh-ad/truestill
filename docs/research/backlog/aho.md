# (aho) THE JOB ENVELOPE IS THE ONLY SUCCESS PAYLOAD WITH NOTHING TO NARROW ON.

*Body of backlog entry `(aho)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aho) THE JOB ENVELOPE IS THE ONLY SUCCESS PAYLOAD WITH NOTHING TO NARROW ON.** Filed
  2026-08-25 (P93/P94), split out of `(ahn)` stage 4b because the fix is a **wire change** and
  belongs beside `(ahe)`'s and `(agk)`'s status-code rulings rather than inside a spec commit.

  ## THE MEASUREMENT

  Every arm of every response union in this app carries a `Literal`-tagged key. One does not.

  | arm | discriminator |
  |---|---|
  | `OrganizeUndoStateDisarmed` / `Armed` | `ok=Literal[True]` **and** `armed=Literal[False/True]` |
  | `SetLayoutOk` / `SetLayoutErr` | `valid=Literal[True/False]` |
  | `DriveBusyPayload` | `ok=Literal[False]`, `code=Literal['DriveBusy']` |
  | `BakeRefusal` | `ok=Literal[False]`, `code=Literal['MigrationUnfinished','NotConfirmed']` |
  | `DriveUnavailablePayload` | `ok=Literal[False]` |
  | `InvalidEventProposalPayload` | `ok=Literal[False]` |
  | **`JobStarted`** (`jobs.py`) | ⚠ **NONE** - one key, `job_id` |

  ## WHY IT MATTERS, AND IT IS NOT COSMETIC

  `_start_drive_job` returns **three** shapes from one route: a refusal Mapping, a
  `DriveBusyPayload`, and `JobStarted`. So **every one of the 15 job-start sites returns a union**,
  and `app.js` tells the arms apart at `app.js:244` with `started.ok === false` - which is false
  for `JobStarted` **only because `ok` is `undefined`**.

  🔑 **It is the one place in the app where narrowing rests on a key not being there.** It works,
  and it is the arm a generated TypeScript type would give a consumer no way to discriminate: a
  `oneOf` whose arms cannot be told apart is a type that helps nobody.

  ## THE FIX, AND WHY IT IS NOT A DETAIL

  Add `ok: Literal[True]` to `JobStarted`.

  ⚠ **It is additive and almost certainly safe** - `started.ok === false` stays false either way,
  so `app.js` is unaffected - **but it puts a new key on the body every job start returns**, and
  "almost certainly safe" on that response is a ruling rather than a detail. Fifteen call sites,
  one browser, and nine test files assert on the payload.

  **Not done in `(ahn)` stage 4b deliberately.** A spec commit that also changes the wire is two
  changes wearing one hat.

  ## RELATED

  `(ahn)` (the contract work this was found by), `(ahe)` and `(agk)` (the status-code rulings this
  sits beside), `(ahl)` (the census that works at key-name granularity and cannot see this).
