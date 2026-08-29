# (ail) A ROUTE TO `find --duplicates` - RETIRED 2026-08-29, unbuilt.

*Body of entry `(ail)`, **RETIRED 2026-08-29** - recorded in [`BACKLOG.md`](../../BACKLOG.md) under *Consciously out of scope*; the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

⚠ **Briefs called this `(aim)`. It is filed at `(ail)`, the letter that was actually free**, so the
namespace stays dense; `(aim)` was never allocated and remains free. Recorded here because a
reader hunting `(aim)` needs to land somewhere.

- **(ail) A ROUTE TO `find --duplicates` - RETIRED 2026-08-29, unbuilt.** Proposed 2026-08-29 as *"`find --duplicates` already
  returns exact groups; nothing points at it - add the route on each surface."* **Retired the same
  day, unbuilt: every clause of the premise is false.**

  ## THE FIVE CHECKS

  | claim | check | result |
  |---|---|---|
  | a `find` subcommand exists | argparse | **absent** - it lists the 19 that exist and rejects `find` |
  | a `--duplicates` flag exists | `grep` over `cli.py` | **absent** |
  | a `dedup` subcommand exists | `grep '"dedup"'` | **absent** |
  | a Duplicates card exists | `grep` over `static/app.js` | **absent** |
  | anything returns exact-duplicate **groups** | `grep 'def .*duplicate'`, core + app service | **none** - the nearest are `duplicate_explain.explain_duplicate` (pairwise), `catalog.stats_near_duplicate_flagged_count` (a count), `insights.duplicate_bytes` (a byte total) |

  🔑 **AND IT COULD NOT SIMPLY BE BUILT EITHER, WHICH IS THE PART WORTH KEEPING.** A route cannot
  point at data nobody kept. `stats.py` reports `"exact_duplicates_found": None` because
  **exact-duplicate skips are not stored in the catalog**, and `dedup.DedupIndex._by_sha` is
  `dict[str, str]` - one path per content, written with `setdefault` - so no group survives the run
  that skipped it. Soak eight measured the consequence: a **52-way group** rendered as 51 pairwise
  sentences, existing only in the transcript.

  **Persisting the skips is the prerequisite, and it is `(aii)`'s subject, not a routing job.**
  Anything that revives this idea starts there.

  ## RELATED

  `(aii)` (owns the ground: no durable trace, no group concept, no query),
  [`soak-eight-record.md`](../../soak-eight-record.md) §6.
