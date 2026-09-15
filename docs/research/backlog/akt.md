# (akt) `/api/drives` SENT EVERY AT-RISK FILE TO A SCREEN THAT NAMES THREE.

*Body of backlog entry `(akt)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## THE DEFECT

`at_risk` was `list[AtRiskRow]` - **one entry per at-risk file** - and the browser used
**`rows.length` as the count**. So the number in *"83 files exist in only one place"* was the
length of an array that had to carry every file for the headline to stay true.

Measured on a catalog whose files all sit on one drive (the worst case, and a new user's case):

| one-copy files | payload | of which `at_risk` | build |
|---|---|---|---|
| 2,574 | 159,954 B | 99.8% | 9.4 ms |
| **300,000** | **18,600,370 B** | **100.0%** | **1,198.7 ms** |

⚠ **Structural, not slow.** The payload grows with the library; the screen has never shown more
than **three names per drive** (`app.js`'s `atRiskSampleLine`, `names.slice(0, 3)`).

## THE CENSUS - every field on this payload that grows with the library

Asked because a second instance had turned up twice in one week. `DrivesPayload` holds three keys:

| field | grows with | verdict |
|---|---|---|
| `drives: list[DriveRow]` | the number of **drives** | a handful; `DriveRow` is otherwise scalars |
| `DriveRow.decisions.stale` / `.awaiting_restore` | **sections** (`trips`, `events`, `albums`, `settings`) | a fixed six-word vocabulary, not library-sized |
| `cannot_name_library: str` | nothing | one sentence |
| **`at_risk`** | **files** | **the defect** |

**One instance, and it is the one that was reported.** Recorded so the next reader does not re-run
the census.

## THE RULE

🔑 **CAP THE NAMES, NEVER THE COUNT.** The band, the banner title and the chip all rest on the
number - it is the product's central custody claim and may never be a sample. The names exist only
to make the claim actionable.

`OrganizedSample` is the same shape one surface over and its docstring is the rule already:
*"tiles plus the count they were taken from, so truncation is never silent."* The completion grid
caps at `GRID_SAMPLE_LIMIT = 48` and says so; this is that decision at the size this job needs.

**The shape:**

```json
{"total": 300000,
 "drives": [{"drive": "BackupA", "reach": "connected", "total": 300000,
             "shown": ["IMG_000000.jpg", "…"]}]}
```

`total` is exact and summed from exact per-drive totals. `shown` is capped at
`AT_RISK_SAMPLE_LIMIT = 6` - twice the three the screen prints, so the copy can grow a name
without a contract change. `total - len(shown)` is what renders as *"and N more"*.

## WHAT THE SCREEN SAYS ABOUT WHAT IT DOES NOT NAME

⚠ **"and 299,997 more" is a number with no way to reach it, unless the remedy's SCOPE is stated.**
A reader could reasonably think the button copies the three files just listed. Neither surface has
a way to *enumerate* every at-risk file - the CLI's `status` caps at `_STATUS_PREVIEW` and says
*"... and N more"* with the same gap - so inventing a route was not on offer.

**Chosen: the action is the route, and it is said out loud.** The here-line now ends *"Copying to
another drive covers 300,000 files, not only the ones named here."* You do not need to see three
hundred thousand filenames; you need to know that one button covers all of them. The away-line
keeps its existing route - connect the drive first, because there is nothing to copy from until
you do.

## THE RESULT

| one-copy files | payload before | after | build before | after |
|---|---|---|---|---|
| 2,574 | 159,954 B | **553 B** | 9.4 ms | 10.1 ms |
| 300,000 | 18,600,370 B | **561 B** | 1,198.7 ms | 1,267.5 ms |

Constant, bounded by drives. Plus the browser half, which is larger and not in that table:
`JSON.parse` of the old array measured **117.6 ms** against **0.0018 ms**, before the 300,000 JS
objects it left resident.

## ⚠ THE FIRST IMPLEMENTATION MEASURED FASTER AND WAS SLOWER

A single windowed query - `COUNT(*) OVER (PARTITION BY ...)` with `ROW_NUMBER()` - is the obvious
shape and was written first. On a **warm** connection it won: **1,156 ms against 1,181 ms** for the
two-step. The route opens a **fresh** catalog per call, and measured that way it loses badly:
**1,587 ms against 1,262 ms** - the window functions must materialise and sort every partition
while a `GROUP BY` count sorts nothing. **Measure the shape the caller uses**, not the one that is
convenient to put in a loop. The two-step shipped; `PERFORMANCE.md` §7.2 carries both readings.

## WHAT DID NOT CHANGE

**The scan.** The predicate is `GROUP BY ... HAVING COUNT(*) = 1` over every copy - a question
about the whole table by construction, and no index removes it. What this entry removed is
**building and sending** 300,000 rows to render twelve names.

**`single_copy_shas`.** Still used by `cli.py:_cmd_status`, which caps in Python for a terminal
rather than for a payload. Its in-memory cost at 300,000 is real and is **not** addressed here.

## RELATED

`(akp)` (`reach` on the at-risk remedy - the field this preserves), `(aes)` (`was_checked`, the
other Backups payload correction), `(ahl)` (dead payload keys - the opposite failure, a field
computed and never read), `(abk)` (seeing the whole library, which is the feature an enumeration
route would belong to).
