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
that half is a human read.

---

## The short answer

**Five subcommands have no app route at all**, plus one write-half:

| | why it matters |
|---|---|
| `reclaim` | **deliberate.** `app.js:2179` - *"an irreversible removal is not a thing to reach for by accident"* |
| `restore` | the app can say a restore is needed (`service/drives.py:451-452`) and cannot perform one |
| `repoint-sources` | the library-moved remedy is CLI-only; `(adx)` owns the disclosure half |
| `rescan` | no route; `(abn)` is the open entry about what rescan should *do* |
| `self-check` | reachable only as a process flag, `__main__.py:285` |
| `catalog --move` | the read half is covered; `move_catalog_to_standard` has **zero** hits in the app package |

**And six more are partial**, mostly in flags rather than in whole features. The one that is
partial in a way a user would notice is **`ingest`: the app can preview an import and can never
apply one.**

---

## The table

`add_parser` line is where the subcommand is declared; the route column cites `server.py`.

| subcommand | CLI | app route | state |
|---|---|---|---|
| `organize` | `cli.py:434` | `/api/organize/{inventory,preview,run,settings}` `server.py:820-823` | **covered**, including `--move` / `--in-place` via `mode` (`service/organize.py:86`, `server.py:225`) |
| `undo-organize` | `cli.py:403` | `/api/organize/undo{,/preview,/apply}` `server.py:826-828` | **covered**, preview and apply |
| `migrate-layout` | `cli.py:662` | `/api/migrate/{preview,run}` `server.py:846-847`; undo `:852-854` | **covered**, including `--undo` |
| `verify` | `cli.py:599` | `/api/verify/run` `server.py:829` | **covered** |
| `where` | `cli.py:594` | `/api/where` `server.py:865` | **covered**; `--limit` becomes paging |
| `config` | `cli.py:629` | `/api/layout{,/preview}` `server.py:842-843` | **covered**; presets resolve client-side to a template |
| `status` | `cli.py:611` | `/api/drives` `:863`, `/api/library/{status,stats}` `:839,:841` | **covered**; same `single_copy_shas` query both sides |
| `clean-empty` | `cli.py:3660` | `/api/clean-empty/{preview,apply}` `server.py:837-838` | **partial** - `--permanent` deliberately absent (`service/clean_empty.py:71`), app refuses and points at the CLI |
| `ingest` | `cli.py:460` | `/api/ingest/{preview,archives/precheck,archives/run}` `server.py:830-832` | ⚠ **partial - preview only.** `service/takeout.py:204` returns `ingest_preview(...)`; there is no apply endpoint. `--tz`, `--prefer-takeout-dates`, `--map-albums` unimplemented |
| `drives` | `cli.py:509` | `/api/drives` `server.py:863` | **partial - list only.** Every marker-writing flag (`--init`, `--label`, `--uuid`, `--adopt-existing`, `--force-new-identity`, `--migrate-marker`) has no route |
| `analyze` | `cli.py:588` | `/api/organize/inventory` `server.py:820` | **partial** - same walk-and-stat tier; `--all-files` missing |
| `catalog` | `cli.py:620` | `/api/library/status` `server.py:839` | **partial - read half only.** `--move` has no route |
| `reclaim` | `cli.py:643` | **none** | deliberate |
| `restore` | `cli.py:559` | **none** | |
| `repoint-sources` | `cli.py:546` | **none** | |
| `rescan` | `cli.py:687` | **none** | |
| `self-check` | `cli.py:634` | **none** | process flag only |

### Flags missing from covered commands

Recorded because *"organize is covered"* is true and hides them: `--all-files`, `--by-device`,
`--no-rename`, `--no-timestamps`, `--phash-threshold`, `--pool` / `--workers`, `--report` (all
`_add_common_options`, `cli.py:331-398`), `verify --pool/--workers` (`cli.py:607-608`), and
`undo-organize --run-id` / `--list` (`cli.py:410-411`). `--rclone` is **out of scope by design**:
*"The app always writes to a local drive - there is no rclone path here"* (`service/organize.py:1030`).

---

## The other direction: app-only, no CLI subcommand

Worth knowing before anyone calls the CLI the complete surface. Backup (`server.py:867-868`), the
whole events and trips surface (`:845`, `:855-860`), date honesty and baking (`:848-851`),
thumbnails (`:866`), `reveal` (`:864`), the filesystem picker (`:833-836`), library root (`:840`),
and UI preferences (`:824-825`).

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
