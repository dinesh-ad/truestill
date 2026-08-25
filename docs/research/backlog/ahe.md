# (ahe) THE BAKE'S TYPED CONFIRMATION WAS NEVER ENFORCED WHERE THE WRITE HAPPENS.

*Body of backlog entry `(ahe)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared between the two.*

- **(ahe) THE BAKE'S TYPED CONFIRMATION WAS NEVER ENFORCED WHERE THE WRITE HAPPENS.** Found
  2026-08-25 by P64, while ruling on whether the bake should stay app-only. It was not the
  question being asked.

  ## WHAT WAS WRONG

  `CONFIRM_WORD = "set dates"` lived in `service/bake.py`, was shipped to the browser inside the
  **preview** payload, was compared by `typedConfirm` in `app.js`, and **never left the browser**.
  `dates_bake_run` read exactly one body key, `path`. `bake_run(path, db)` had no confirmation
  parameter to pass it to.

  So the typed field was a UI gesture with nothing behind it. Any local process holding the
  session token could POST `{"path": "..."}` and rewrite every confirmed file on that drive.

  ⚠ **This is the operation that deserved the guard most.** `exif.py`'s `_WRITE_FLAGS` are
  `("-overwrite_original", "-m")` - **no sidecar is kept**. Organize moves files and
  `undo-organize` reverses it; migrate journals the whole plan before touching disk and resumes;
  clean-empty reports and never removes. The bake overwrites the bytes inside a photograph and the
  date it used to carry is gone.

  ## WHERE THE CHECK WENT, AND WHY NOT THE ROUTE

  In `bake_run`, with **no default** on `confirmation`.

  The route is **one** caller. `PROJECT_STATUS.md` §1b commits to a second - the engine finishes
  first, and the CLI carries every behaviour. A check in `server.py` would have to be written a
  second time, correctly, by whoever adds that surface. That is `(afu)`'s shape exactly: a
  builder that worked, guarded at the caller, and was **unreachable** from the package that needed
  it next.

  No default is the ruling `MigrationStop.kind` and `jobs.start`'s `mutating` already carry:
  defaulting it either way is a decision nobody made.

  ## THE STATUS CODE IS SPENT ON THE RIGHT OUTCOME

  A missing word answers **400**, not the 200 every other refusal on that route takes. `(agk)` and
  P24 both ruled this: a refusal a person should read is a 200 with a payload the UI renders; a
  request that arrived malformed is not that. `drive_label` is **empty** on the refusal, so a
  caller's mistake never reads as a fault of the user's hardware.

  ## WHY IT SURVIVED

  ⚠ **It was the only mutating run with no route-level test.** Checked:
  `grep -rn "dates/bake" packages/truestill-app/tests/` returned nothing. `bake_preview` and
  `bake_cancel` were covered; the seam where an HTTP request becomes a write to a user's
  photographs was not.

  ## THE CENSUS - this is a class

  Six `typedConfirm` call sites in `app.js`:

  | site | word | enforced server-side? |
  |---|---|---|
  | migrate apply | `move` | **no** |
  | migrate undo apply | `undo` | **no** |
  | organize | (per mode) | **no** |
  | organize undo | `undo` | **no** |
  | clean-empty | `clean` | **no** |
  | **bake** | `set dates` | **fixed here** |

  Established by reading every `mutating=True` handler in `server.py` and by
  `grep -rn 'confirm' server.py` - **no route reads a confirmation key**. For contrast, the CLI
  checks at the handler in eight places via `_typed_confirmation`.

  **Only the bake is fixed**, deliberately. It is the irreversible one; the other five are
  recoverable, and each has different semantics. A blanket change to five confirmation paths is
  not a fix, it is one guess repeated five times. They are recorded here so the next reader finds
  a census rather than an instance.
