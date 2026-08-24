# CLI and app: what each surface can do

**What this answers:** *"if the UI arc starts tomorrow, what is actually missing?"* Measured
2026-08-23 by reading both surfaces, so it is not re-derived from judgement every time it is asked
- which is `(aef)`'s finding about the release question, applied to a different question with the
same shape.

**What it is not.** Not a plan, not a priority order, and not a ruling that any gap should be
closed. Several are deliberate and say so in the code. It records *what is true*; what should be
built is a decision made against it.

⚠ **The counts below are a snapshot; the commands are not.** Run these rather than trusting the
prose, for the reason the document map gives about its own figures:

```sh
# CLI subcommands
grep -c 'add_parser(' packages/truestill-cli/src/truestill_cli/cli.py
# app routes
grep -c 'Route(' packages/truestill-app/src/truestill_app/server.py
```

On 2026-08-23 those read **17** and **50**.

`test_the_cli_app_parity_table_is_complete.py` fails when a subcommand exists that the table below
does not list, so a new command cannot ship and leave this silently stale. **It checks
completeness, not correctness** - it cannot tell whether the *route* column is still true, and
that half is a human read. ⚠ **Nor whether any `path:line` below still points at what it names**:
thirty-one had drifted by 2026-08-24. They are repointed and the class is ruled on at the end of
this file - read that before trusting a number here.

---

## The short answer

**Five subcommands have no app route at all**, plus one write-half:

| | why it matters |
|---|---|
| `reclaim` | **deliberate.** `app.js:2200` - *"an irreversible removal is not a thing to reach for by accident"* |
| `restore` | the app can say a restore is needed (`service/drives.py:487-488`) and cannot perform one |
| `repoint-sources` | the library-moved remedy is CLI-only; `(adx)` owns the disclosure half |
| `rescan` | no route; `(abn)` is the open entry about what rescan should *do* |
| `self-check` | reachable only as a process flag, `__main__.py:285` |
| `catalog --move` | the read half is covered; `move_catalog_to_standard` has **zero** hits in the app package |

**And six more are partial**, mostly in flags rather than in whole features. The one that is
partial in a way a user would notice is **`ingest`: the app can preview an import and can never
apply one.**

---

## The table

The CLI column names the `add_parser` call rather than a line - grep it. The route
column cites `server.py` by line, and those are re-resolved by hand.

| subcommand | CLI | app route | state |
|---|---|---|---|
| `organize` | `cli.py` `add_parser("organize"` | `/api/organize/{inventory,preview,run,settings}` `server.py:878-881` | **covered**, including `--move` / `--in-place` via `mode` (`service/organize.py:93`, `server.py:230,253`) |
| `undo-organize` | `cli.py` `add_parser("undo-organize"` | `/api/organize/undo{,/preview,/apply}` `server.py:884-886` | **covered**, preview and apply |
| `migrate-layout` | `cli.py` `add_parser("migrate-layout"` | `/api/migrate/{preview,run}` `server.py:904-905`; undo `:910-912` | **covered**, including `--undo` |
| `verify` | `cli.py` `add_parser("verify"` | `/api/verify/run` `server.py:887` | **covered** |
| `where` | `cli.py` `add_parser("where"` | `/api/where` `server.py:923` | **covered**; `--limit` becomes paging |
| `config` | `cli.py` `add_parser("config"` | `/api/layout{,/preview}` `server.py:900-901` | **covered**; presets resolve client-side to a template |
| `status` | `cli.py` `add_parser("status"` | `/api/drives` `:921`, `/api/library/{status,stats}` `:897,:899` | **covered**; same `single_copy_shas` query both sides |
| `clean-empty` | `cli.py` `add_parser("clean-empty"` | `/api/clean-empty/{preview,apply}` `server.py:895-896` | **partial** - `--permanent` deliberately absent (`service/clean_empty.py:71`), app refuses and points at the CLI |
| `ingest` | `cli.py` `add_parser("ingest"` | `/api/ingest/{preview,archives/precheck,archives/run}` `server.py:888-890` | ⚠ **partial - preview only.** `service/takeout.py:206` returns `ingest_preview(...)`; there is no apply endpoint. `--tz`, `--prefer-takeout-dates`, `--map-albums` unimplemented |
| `drives` | `cli.py` `add_parser("drives"` | `/api/drives` `server.py:921` | **partial - list only.** Every marker-writing flag (`--init`, `--label`, `--uuid`, `--adopt-existing`, `--force-new-identity`, `--migrate-marker`) has no route |
| `analyze` | `cli.py` `add_parser("analyze"` | `/api/organize/inventory` `server.py:878` | **partial** - same walk-and-stat tier; `--all-files` missing |
| `catalog` | `cli.py` `add_parser("catalog"` | `/api/library/status` `server.py:897` | **partial - read half only.** `--move` has no route |
| `reclaim` | `cli.py` `add_parser("reclaim"` | **none** | deliberate |
| `restore` | `cli.py` `add_parser("restore"` | **none** | |
| `repoint-sources` | `cli.py` `add_parser("repoint-sources"` | **none** | |
| `rescan` | `cli.py` `add_parser("rescan"` | **none** | |
| `self-check` | `cli.py` `add_parser("self-check"` | **none** | process flag only |

### Flags missing from covered commands

Recorded because *"organize is covered"* is true and hides them: `--all-files`, `--by-device`,
`--no-rename`, `--no-timestamps`, `--phash-threshold`, `--pool` / `--workers`, `--report` (all
`_add_common_options`, `cli.py:350-417`), `verify --pool/--workers` (`cli.py:627-628`), and
`undo-organize --run-id` / `--list` (`cli.py:429-430`). `--rclone` is **out of scope by design**:
*"The app always writes to a local drive - there is no rclone path here"* (`service/organize.py:1045`).

---

## The other direction: app-only, no CLI subcommand

Worth knowing before anyone calls the CLI the complete surface. Backup (`server.py:925-926`), the
whole events and trips surface (`:903`, `:913-918`), date honesty and baking (`:906-909`),
thumbnails (`:924`), `reveal` (`:922`), the filesystem picker (`:891-894`), library root (`:898`),
and UI preferences (`:882-883`).

---

## What this cost, and why it is written down

⚠ **Three of four expectations held by the maintainer before the read were wrong**, in the
direction that inflates the arc: `migrate-layout`, `clean-empty` and `undo` were all assumed to
have no route and all three are covered. The one assumed-missing that was missing is `reclaim`,
and the real gap next to it - `catalog --move` - was not on anyone's list.

**That is the argument for the document.** The question was being answered from memory, the memory
was wrong in both directions at once, and each answer would have sized the work differently.
`(aef)` records the same failure about the release question: *"it is not stored anywhere - it is
RECOMPUTED from judgement every time it is asked, which is why it comes out different."*

⚠ **One finding fell out of the read and is not an inventory item:** `(agg)` - the archive ingest
route writes to the destination while declaring `mutating=False`, so the drive lock never engages.
Filed separately; it is a defect, not a gap.

---

## The line numbers drifted, and the ruling is to carry fewer of them

**Repointed 2026-08-24 (P40), from the code rather than by adding an offset.** Thirty-one
citations were re-resolved. Fifteen of the table's seventeen `cli.py` cites pointed at something
other than the `add_parser` they named, as did the `status` row's three route cites, the whole
app-only paragraph, and four ranges in the flags section.

**What actually happened, because the shape matters more than the fix:**

- The table was **correct on the day it was written** (`f3e35b0`, 2026-08-23 09:23). Four commits
  moved `cli.py` the same afternoon and the column was never re-resolved.
- ⚠ **`(ago)`'s guard ran over this document that evening and fixed exactly two of them** - the
  `where` and `self-check` rows, from lines 576 and 616 to 594 and 634. *(Written as prose rather
  than as citations on purpose: `test_live_documents_cite_code_that_exists.py` cannot tell a
  quoted old number from a live one, and it failed this paragraph's first draft. Same shape as
  the `<space>` spelling in `IMPLEMENTATION_STANDARDS.md` §6.2 - a document about a sweep must not
  be written in the form the sweep acts on.)* Those two are the **only two still correct today**.
  That is not luck: `(ago)` detects a citation pointing at a **blank line**, and those two had
  landed on one. The other fifteen drifted onto other real code and were invisible to it - which
  is the limit `(ago)` states about itself, demonstrated on the document it was auditing.
- ⚠ **`219359c` then re-resolved the route column and left the CLI column beside it**, in the same
  table, in the same commit. **A half-refreshed table is worse than a stale one**: it reads as
  freshly checked, and the half nobody touched inherits that credibility. *(Recorded 2026-08-24 as
  a variant of `ENGINEERING_STANDARD.md` §4's fifty-sixth member - a note there rather than a
  member of its own, because this is its only instance. A second one earns it a number.)*
- ⚠ **AND THE RULING'S TRIGGER FIRED THE NEXT DAY, 2026-08-24 (P42).** A **six-line** change to
  `cli.py` - wiring `(agl)`'s cancel - moved every declaration below it and invalidated all
  seventeen citations again, one day after they were repointed. So the column below **no longer
  carries line numbers**: it names the `add_parser` call, which is greppable, is what a reader
  actually wants, and cannot drift. That is this file's ruling applied to the column that earned
  it, and it is deliberately narrower than the whole-corpus change the ruling still defers.
- ⚠ **The offsets were not uniform, so "add 18" would have been wrong.** Fourteen of the fifteen
  had moved by 18 lines; `clean-empty` had moved by **51**. An offset is a guess about a diff, and
  a citation repaired from a guess is a citation nobody has read.
- One citation was **wrong when written** rather than drifted: `service/takeout.py` has not changed
  since `f3e35b0`, and its `return ingest_preview(...)` was cited two lines high.

### The ruling: fewer numbers, not a guard

**A citation guard is the wrong instrument here, and `(ago)` already contains the reason.** Its
blank-line signal cannot see a line that moved onto other real code, which is this whole class; a
guard that instead pinned the number exactly would go red on every commit touching `cli.py` - five
did in one day - and a guard that goes red on ordinary work is switched off within a week, taking
its real signal with it (`ENGINEERING_STANDARD.md` §4).

**So the honest answer is that this column will always drift, and the fix is to stop carrying the
number.** A subcommand is declared as `sub.add_parser("organize", ...)`, so the **name is already
in the call** and `grep -n 'add_parser("organize"' packages/truestill-cli/src/truestill_cli/cli.py`
answers the question the line number was standing in for - exactly, from the code, and it cannot
rot. The route column is the same shape: `Route("/api/drives", ...)` carries its own path.

**Not built here, and named rather than smuggled in** - which is the form `(ago)` asked for when it
declined the same change. Converting the columns means deciding what a citation is *for* across
every living document, not just this one. Until that is decided, the numbers above are current as
of 2026-08-24 and the map row's warning stands: **only completeness is pinned; the route column is
a human read.**
