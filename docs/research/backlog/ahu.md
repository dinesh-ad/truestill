# (ahu) A RELATIVE DESTINATION SILENTLY DISABLES THE DECISIONS BACKUP, FOR THE LIFE OF THE DRIVE.

*Body of backlog entry `(ahu)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahu) A RELATIVE DESTINATION SILENTLY DISABLES THE DECISIONS BACKUP, FOR THE LIFE OF THE
  DRIVE.** Filed 2026-08-26 (P103). **The only durable copy of every name a human typed, never written.**

  ## MEASURED, BOTH ARMS, SAME 353 FILES

  353 photographs from `Input/IV Bangalore`, ext4, 16 cores / 30 GiB. One trip and three events
  named through the app's **HTTP routes** (`/api/events/propose`, `/api/events/{s}/apply`) - a
  product, not a service function.

  | destination as typed | `path_hint.drive.<uuid>` | `.truestill-decisions.json` |
  |---|---|---|
  | `dest-a` (relative) | `dest-a` | **absent.** `decisions.problem.<uuid>` = *"a drive root must be a full path"* |
  | `/data/tmp/.../dest-b` (absolute) | the absolute path | **written**, carrying all four names |

  One variable, opposite outcomes. The names existed in both catalogs; only one drive got them.

  ## THE CHAIN

  `cli.py:2606` takes `Path(args.destination)` **unresolved**, and `cli.py:2616` stores it
  verbatim as the hint. `write_decisions` then refuses on every save:
  `decisions.py:741` `if not root.is_absolute():` -> `decisions.py:746`. Nothing retries and
  nothing rewrites the hint, so **the refusal is permanent for that drive**.

  🔑 **The guard is right and its stated premise is wrong.** `decisions.py:741-746` reasons that
  *"A drive root is always absolute in practice; requiring it turns a silent misfile into a
  reported refusal."* It is not always absolute in practice: `truestill organize src dest` is the
  natural way to type the command.

  ## WHY NO TEST CAUGHT IT

  **Every `set_setting(drive_path_hint(...))` in the repo is in a test, and every one passes an
  absolute `tmp_path`** - `str(root)`, `str(gone)`. Checked:
  `grep -rn "set_setting(drive_path_hint" packages/` returns test files plus four production
  sites (`cli.py:1225`, `cli.py:2616`, `service/organize.py:1114`, `service/drives.py:388`,
  `service/verify.py:96`). No test drives `main()` with a relative destination.

  That is `handoff-2026-08-25.md` §1's *"a test constructing its input differently from the real
  caller"*, the `(ahp)` class, on a second path - and `(ahp)`'s own DO names the remedy:
  **for anything reachable from a command line, drive `main()` end to end.**

  ## AND THE REFUSAL'S OWN VISIBILITY IS UNTESTED

  Found while checking whether a user would notice. The outcome **is** recorded and **is**
  rendered - `catalog_session.py:87-89` calls `_record` unconditionally before consulting the
  report callback, so the app surfaces it at `service/drives.py:549` -> `app.js:2937-2939` even
  though all 40 app `open_catalog` sites pass no report. The CLI prints it to stderr at
  `cli.py:862-865`.

  ⚠ **But no test asserts either.** `_report_decision_saves` (`cli.py:850-869`) is exercised by no
  assertion for **any** outcome; the rendered-text tests use a `FAILED` detail string, never this
  one; and no test drives a refusal through `open_catalog` to the recorded setting. The only
  `WOULD_LOSE` test asserts the enum, which proves the branch and not the visibility.

  ## THE FIX, AND WHAT IT MUST NOT BE

  Resolve at the boundary - `Path(args.destination).resolve()` at `cli.py:2606` - and audit the
  other four hint writers for the same. **Not** relaxing `decisions.py:741`: the guard is what
  turned this from a silent misfile into a reported one, and it is the reason this entry exists.

  ⚠ **Existing catalogs carry the bad hint already** and no code path rewrites it. A repair pass
  is part of the fix, not a follow-on - otherwise every drive registered before the fix stays
  broken forever, which is this entry restated.

  ## RELATED

  `(ahp)` (the same class), `(ahv)` (what is lost when the document does not exist),
  `(afu)`, `(acc)`, [`soak-six-record.md`](../../soak-six-record.md)'s dated correction.
