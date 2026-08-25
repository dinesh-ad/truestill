# (ahl) CONDITION 3 IS AT 34 FIELDS, NOT 2, AND ITS OWN CENSUS DISAGREES WITH ITSELF.

*Body of backlog entry `(ahl)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahl) CONDITION 3 IS AT 34 FIELDS, NOT 2, AND ITS OWN CENSUS DISAGREES WITH ITSELF.** Filed
  2026-08-25 (P81).

  ## THE METHOD, because the number is only as good as it

  AST-walk every `TypedDict` under `packages/truestill-app/src/truestill_app/`, then test each key
  name against three surfaces: `static/app.js` **with `//` and `/* */` comments stripped**,
  `frontend/src/**`, and `cli.py`. Derived twice, independently, same figures.

  ⚠ **Both declaration forms, and the second is not optional.** `service/backup.py:51` writes
  `TypedDict("BackupPreviewOk", {...})` in the functional form because it carries the reserved word
  `from` as a key. A class-body walk misses it entirely.

  ⚠ **AST rather than runtime introspection, and the repo already paid for that lesson.**
  `test_migrate_reports_its_stop.py:149` records a first draft asserting on `__required_keys__`
  that was **vacuous**: under `from __future__ import annotations` the annotations are strings, so
  `TypedDict` cannot see through `NotRequired[...]` and every key reads as required. Any guard
  built here inherits that constraint.

  | | |
  |---|---|
  | TypedDicts | **117** |
  | key slots declared | **579** |
  | distinct key names | **289** |
  | **no hit in `app.js` code and none in React** | **34** (**11.8%**) |
  | of those, no hit in `cli.py` either | **21** |
  | genuinely read by the React source | **0** |

  ## ⚠ 34 IS A FLOOR, NOT A COUNT

  **A key-name census cannot see a collided field.** `absent` is declared twice with opposite
  fates: `BakePreview.absent` (`service/bake.py:238`) **is** rendered at `app.js:4131`;
  `BakeSummary.absent` (`service/bake.py:166`, emitted `:217`) is not read by `bakeCompletion`
  (`app.js:4167`) at all. Because the name is *"read somewhere"*, it never enters the 34. So a bake
  run names what failed and stays silent about what it could not find, and this census is
  structurally blind to it.

  Getting the true figure needs **payload granularity** - knowing which JavaScript variable holds
  which route's response - and that is not mechanical. **`apollo-kotlin#991`, open since 2018, is
  the same limit in another language**: generated accessors mean code analysis cannot tell whether
  a client USES what it asked for, so a field stays undeprecatable because the client requests it
  and ignores it. Named here because it is the boundary, not a gap to close later.

  ## ⚠ STRIPPING COMMENTS MOVED THE ANSWER FROM 20 TO 34

  The naive grep certified **fourteen** dead fields as live. `matched_path`'s only `app.js`
  occurrence is a comment at `app.js:2643` saying the field *cannot* answer the question.

  **This exact failure has a published instance.** A Whatnot write-up (Dec 2025) describes an agent
  proposing to delete fields still referenced in web client code, because the web repo lacked the
  linter the mobile repos had. A text search that cannot tell code from prose is not a weaker
  version of the check; it is a different check that returns the wrong answer confidently.

  ## THE 34

  ⚠ **The LIST is derived; the REASON column is a human read of the surrounding code.** Said
  plainly rather than left to look uniform.

  ### Identity the browser was handed and never needs back (4)

  | key | declared | why nothing reads it |
  |---|---|---|
  | `run_id` | `migrate.py:340`, `:356`; `organize_undo.py:43`, `:49`, `:58` | the client posts back the handle it was given; the server resolves the run |
  | `uuid` | `drives.py:498`; `trips.py:344` | screens key on the label; `app.js:2999` says the server resolves the uuid |
  | `event_id` | `trips.py:459` | selection is echoed by position, not id |
  | `trip_id` | `trips.py:466` | as `event_id` |

  ### A path the client already knows, because it sent it (3)

  | key | declared | why nothing reads it |
  |---|---|---|
  | `dest_root` | `organize_undo.py:52`, `:60` | the browser holds the path it submitted |
  | `target_path` | `backup.py:150` | as `dest_root` |
  | `parent` | `fs_browse.py:31` | the browser derives the parent from the path it asked for |

  ### Preflight facts computed and never surfaced (6)

  | key | declared | why nothing reads it |
  |---|---|---|
  | `claimed_bytes` | `takeout.py:149` | the precheck refuses or proceeds; the arithmetic behind it is not shown |
  | `free_bytes` | `takeout.py:150` | as `claimed_bytes`. **36 test hits** and no renderer |
  | `oversized` | `organize.py:854` | the destination limit is reported as a refusal, not as a list |
  | `occupied` | `clean_empty.py:30` | the preview names folders it will not remove, not why |
  | `readable` | `clean_empty.py:22`; `fs_browse.py:45`, `:60` | unreadable is expressed by the absence of a result |
  | `can_register` | `drive_support.py:41`, `:51`; `drives.py:76` | three payloads carry it; the screens branch on the error code |

  ### A count a headline replaced (9)

  | key | declared | why nothing reads it |
  |---|---|---|
  | `dates_exif` | `takeout.py:62` | the ingest preview shows one total |
  | `dates_upload_approx` | `takeout.py:61` | as `dates_exif` |
  | `exact_duplicates_found` | `stats.py:95` | completeness is rendered as a percentage |
  | `redundancy_floor` | `drives.py:711` | its own comment says it exists to make a sentence safe to write; the sentence is written from `files_one_copy` |
  | `catalog_presence` | `drives.py:719` | the custody strip renders a tier, not this string |
  | `unplaced` | `organize.py:257` | its comment says *"a zero here is a fact and not an omission"* - and no surface states the fact |
  | `resumed` | `migrate.py:206` | the completion says how many moved, not how many were recovered |
  | `day_totals` | `trips.py:347` | the proposal renders groups, not per-day counts |
  | `pending_drives` | `migrate.py:84` | the preview warns per drive in prose |

  ### A mechanism or echo the UI derives another way (12)

  | key | declared | why nothing reads it |
  |---|---|---|
  | `modes` | `organize.py:649` | the mode list is rendered from the radio group's own markup |
  | `uses_rename` | `organize.py:788` | the screen branches on the mode name |
  | `requires_destination` | `organize.py:789` | as `uses_rename` |
  | `still_armed` | `organize_undo.py:64` | the screen re-fetches state instead of reading the echo |
  | `named_events` | `trips.py:475` | the apply result is rendered as one count |
  | `named_trips` | `trips.py:476` | as `named_events` |
  | `existing_names` | `trips.py:353` | collision avoidance happens server-side |
  | `source_hints` | `trips.py:355` | the suggestion is shown, not its provenance |
  | `missing_sidecar` | `takeout.py:48`, `:68` | the ingest summary does not distinguish this cause |
  | `distance` | `organize.py:154` | the duplicate sample shows the match, not how near |
  | `matched_path` | `organize.py:158` | ⚠ `app.js:2643` explains in a comment that this field **could never** answer the question the screen asks |
  | `operation` | `jobs.py:93` | the busy banner names the drive, not the job |

  ## ⚠ THIS DOCUMENT HAS AN EXPIRY DATE

  **Its value ends when `app.js` is deleted.** The census answers *"what does the current
  JavaScript read"*; once the React rewrite owns the screens, the question is answered by the
  types, mechanically, at both ends - which is `(ahn)`. A floor guard built on this list is
  therefore a **stopgap with a known end date**, and should be retired with `app.js` rather than
  inherited. A guard nobody retires is how a dead check outlives the thing it checked, keeps
  passing, and gets quoted as coverage.

  ## WHAT THIS IS NOT

  **Not a liveness proof, and no ecosystem offers one statically.** GraphQL is the only ecosystem
  that answers this question at all and it does so at **runtime**: Apollo GraphOS Insights reports
  which clients still query a deprecated field, and Hive's `deprecatedSchema(period:)` attaches
  usage over a window. REST has no equivalent. So the honest artefact here is a **declaration** -
  the 34 with their reasons - and a floor that goes red when a **35th** appears.

  ## RELATED

  `(abm)` (two of the fields, filed separately and confirmed), `(ahm)` (the run-record reader gap,
  ruled OUT of this condition), `(ahn)` (the mechanism that makes the consumed end mechanical),
  `(ago)` (the guard over citations in this file).
