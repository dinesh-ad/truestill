# Trip grouping: multi-day events, and the router that has to carry them

Status: **Design approved (2026-07-28, `b5cba4a`, rulings `fb60c10`). Stages 2a-2c are built**:
2a the router refactor (`1247055`), 2b detection (§11), 2c persistence, catalog v12 (§12). Backlog
`(mm)` is resolved (`1ed021e`), which unblocked 2d. **2d is now in planning** (§13, 2026-07-29) -
not yet built. 2e (migration adoption) remains after it.

Read [`events-clustering-research.md`](events-clustering-research.md) §7 first: it is the reason
this document exists.

---

## 1. Why this stage exists

Stage 1 made segmentation correct and, in doing so, made it **within-day only**. Every overnight
gap exceeds the 60-minute boundary floor, so no cluster can span midnight. All 15 proposals on the
real library are inside a single day. That was accepted deliberately - but it leaves a real thing
unrepresented:

> A four-day trip to Wayanad is currently ten separate day-events with the same name typed ten
> times, or one name typed once and nine days left un-evented.

Multi-day grouping therefore happens **above** clustering, as an explicit second layer, not by
loosening the boundary rule. Loosening it would re-import the exact failure Stage 1 removed: a
threshold that spans midnight also spans a sparse tail, and the 5.6-year cluster comes back.

**A trip is a named span of days. A day event is a named span of hours.** They are different
objects, and the day layer stays untouched.

## 2. The shape

```
{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd} - Trip Name/{yyyy}-{mm}-{dd}/
```

Rendered for the real candidate (assuming Dinesh names Aug 15–17 "Wayanad"):

```
2014/
└── 2014-08/
    └── 2014-08-15 - Wayanad/
        ├── 2014-08-15/     635 photos
        ├── 2014-08-16/     737 photos
        └── 2014-08-17/     654 photos
```

### A trip day claims every photo taken that day

**Intended behaviour, stated rather than left to be inferred.** Once a day belongs to a trip, the
day folder holds *all* of that day's photos:

- **Sub-day clusters merge.** 2014-08-16 produced two clusters, 565 and 157. Inside a trip they
  do not become two folders - the day is the unit, and `565 + 157 = 722`.
- **Un-clustered stragglers are included.** The photos that fell outside every cluster are still
  photos from that day of the trip. This is why the folder counts above (635 / 737 / 654) exceed
  the cluster sums (631 / 722 / 651): **35 stragglers across the active days**, measured.

The alternative - a trip day holding only its clustered files, with the remainder going to
`Everyday` - would scatter one day of one trip across two places in the tree. Nobody looking for
"the Wayanad photos" would accept that. The rule is therefore: **a day is in a trip, or it is
not; there is no partial day.** This is the layout consequence of `trip_days.day` being a primary
key (§6), and it is what makes a trip folder complete enough to copy away on its own.

Against today's shipped year-first shapes:

| | Un-evented | Day event | **Trip (new)** | Side bin |
|---|---|---|---|---|
| | `{yyyy}/{yyyy}-{mm}/{yyyy}-{mm} - Everyday` | `{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd} - Name` | `{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd} - Name/{yyyy}-{mm}-{dd}` | `{category}/{yyyy}/{yyyy}-{mm}` |

The trip shape is the day-event shape **plus one dated level**. That is deliberate: a trip is
recognisably the same kind of thing as a day event, one level deeper, so a user who understands
one understands the other without being told.

## 3. The rules, and why each is what it is

**(a) Named by start date.** The folder is `2014-08-15 - Wayanad`, never a range. The start date
is the only date about a trip that cannot change: a later ingest can extend a trip's end, and
re-scanning a forgotten card can add days in the middle, but the first day is fixed once
confirmed. Naming on anything mutable means renaming folders on the user's disk after the fact,
which is the one thing a copy-only tool should never do.

**(b) Dated day subfolders, in full ISO form.** `2014-08-16/`, not `16/`. Two reasons, both
concrete: a trip crossing a month boundary would sort `28, 29, 30, 31, 01, 02` under bare days,
and a day folder lifted out of its parent by a file manager, a search result or a backup listing
is meaningless without the date. Every folder in truestill's tree says what it is; the day level
is not an exception.

**(c) No year suffix in the name.** "Wayanad", not "Wayanad 2014". The `{yyyy}` parent already
carries the year, and (e) guarantees that the same name never appears twice under one year.

**(d) Filed in the start month.** A trip running 2016-11-28 → 2016-12-02 lives entirely under
`2016/2016-11/`, including the December days. A trip is one object; splitting it across two month
folders to satisfy a filing rule would put half of it where nobody looks for it. The month folder
answers "when did this start", which is how people remember trips.

**(e) A year boundary always splits.** This is [`IMPLEMENTATION_STANDARDS.md`] R2, unchanged and
not negotiable here: nothing may be filed outside its own year. A trip running
2016-12-28 → 2017-01-03 becomes **two** trips:

```
2016/2016-12/2016-12-28 - Goa/{2016-12-28, 2016-12-29, 2016-12-30, 2016-12-31}
2017/2017-01/2017-01-01 - Goa/{2017-01-01, 2017-01-02, 2017-01-03}
```

Both named "Goa", no suffix, no collision - different year parents. (c) and (e) are the same
decision seen from two sides: because the year splits, the name never needs the year.

The split is **structural, not a proposal**: the user names one trip and gets two folders, and
the UI must say so at confirm time rather than let it be discovered on disk.

**(f) Max span is a setting, default 30 days.** A run of consecutive active days is not bounded by
anything intrinsic - someone who photographs daily for a year has one 365-day run, and calling
that "a trip" is meaningless.

*Honest limit:* **this library cannot validate the number.** Its longest active-day run is 4 days
(§4), so 30 is chosen on principle, not fitted: it is long enough for any real holiday, short
enough that a habitual daily shooter never trips it. It is a setting precisely because the
default is unvalidated.

*On exceeding the cap, decline - do not split.* **Ruled and settled.** A run past the cap produces
**no trip proposal**; its days remain individually offerable day events. Splitting at day 30 would
fabricate a boundary the data does not contain - the same error class as the `00`-day date
convention rejected in §8: inventing a value to satisfy a structure.

**The message is part of the ruling, not decoration.** Declining silently would look like a bug,
so the message must name the run length and point at the setting that governs it:

> 62 consecutive days of photos (2018-06-03 to 2018-08-03) - too long to propose as one trip.
> Raise `trips.max_span_days` (currently 30) if this really was one trip.

Both numbers are required: the run length is the evidence, and the setting name is the action.
This is `IMPLEMENTATION_STANDARDS.md` §9 (never-silent) applied to a decision *not* to act.

**(g) Name once, keyed on the day.** See §6 - this is the rule with a real implementation
consequence, and it is not the one the existing code would give us.

## 4. What the rule proposes on the real library

Trip candidacy = a run of **≥ 2 consecutive active days**, where an *active day* is one that
produced at least one cluster proposal under the Stage 1 rule.

Measured, not asserted:

```
active days                     : 10   (2013-09-13 .. 2014-08-17)
consecutive-active-day runs ≥ 2 :  2

  2013-09-15 .. 2013-09-16    2 days,    32 photos
  2014-08-14 .. 2014-08-17    4 days, 2,035 photos
```

**Gating on clusters rather than on "days with any photo" is load-bearing.** The permissive rule
also finds `2023-08-20 .. 2023-08-21`- a two-day run of **2 photos total**. Under cluster-gating
it never appears, because neither day clears `min_files = 8`. A trip proposal for two photos would
be the kind of thing that teaches a user to stop reading proposals.

The 32-photo run (2013-09-15/16, evening clusters of 13 and 19) is a genuine judgement call and is
exactly why proposals are proposals. It is offered; it costs one keystroke to skip.

## 5. Addition 1 - the proposal is the run; the edges belong to the user

**The rule proposes the whole consecutive active-day run. It never silently trims it and never
silently pads it.** The start and end are adjustable before the trip is named, and the confirmed
edges are what get stored.

This is not a general principle looking for an example - it is forced by the one real candidate:

| Day | Clusters | In clusters | All photos | |
|---|---|---|---|---|
| 2014-08-14 | 2 | **31** | **31** | 19:46–21:22 (n=23) and 22:22–22:25 (n=8) |
| 2014-08-15 | 2 | 631 | 635 | |
| 2014-08-16 | 2 | 722 | 737 | |
| 2014-08-17 | 3 | 651 | 654 | |

("All photos" is what the day folder would hold, per §2 - the trip claims the whole day.)

Ground truth from Dinesh: **the trip was Aug 15–17.** The rule proposes **Aug 14–17.**

Both readings are defensible from the data alone. An evening burst of 31 photos immediately before
three heavy days is precisely the shape of an arrival evening - and it is also precisely the shape
of an unrelated evening at home. **Nothing in the timing distinguishes them.**

A GPS cross-check would settle it - an arrival evening is 80 km from home - and **it is not
available on this path.** GPS is read live from exiftool during a fresh organize
(`event_review.py:80`), but the catalog never persists it: the query that feeds review on an
already-organised drive selects `sha256, captured_at` and nothing else
(`catalog.camera_copies_for_events`), and `files` has no GPS column at all. So for exactly the
population that matters here - a library already placed on disk - the one signal that could judge
an edge automatically has been discarded upstream. That is a further argument for the persisted
provenance column `(n)`/`(ii)` already want, and, for now, a reason the user decides.

So the two tempting automatic rules are both wrong:

- *Trim a day whose count is under some fraction of its neighbours* → silently deletes the arrival
  evening from the trip whenever the arrival evening is quiet, which is most of the time.
- *Include any adjacent active day* → silently annexes the evening before departure at home.

Either would be a confident answer to a question the data does not answer. The design's position
is that **the rule is good at finding candidate spans and bad at judging edges**, so it does the
first and hands the second to the person who was there. The proposal shows per-day photo counts
and time ranges so the trim is an informed one - a user seeing `31 / 631 / 722 / 651` can decide
in a second.

*To confirm at build time:* was Aug 14 evening the drive up to Wayanad, or an evening at home?
Either answer is fine; the design does not depend on it. It becomes the acceptance fixture.

## 6. Name-once, and a latent defect it exposes

Trips must not re-ask. Two mechanisms are available, and the obvious one is wrong.

**The existing mechanism does not generalise.** `EventCandidate.signature` is
`packages/truestill-core/src/truestill_core/events.py:109`- a SHA-256 over the sorted member
`sha256`s - and `events.signature` is the `UNIQUE` key that `event_by_signature` looks up
(`catalog.py:940`). Membership *is* identity. For a trip that is explicitly user-adjustable (§5)
and that grows when the next card is ingested, that is exactly backwards: **trimming Aug 14 off
the trip, or ingesting one more photo from Aug 16, produces a different signature, so the named
trip is not recognised and is offered again as new, with the old name orphaned.**

**Proposed: a trip's identity is the trip, and name-once is keyed on the *day*.**

```sql
CREATE TABLE trips (                      -- schema v12
    id         INTEGER PRIMARY KEY,       -- identity: the row, not the membership
    name       TEXT NOT NULL,
    slug       TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL
);
CREATE TABLE trip_days (
    day     TEXT PRIMARY KEY,             -- a day belongs to at most one trip
    trip_id INTEGER NOT NULL REFERENCES trips(id)
);
```

A re-run asks one question per candidate day: *is this day already claimed?* If yes, it is silent.
Adjusting edges is an update to `trip_days`, not a new identity. Extending a trip on the next
ingest adds a row. The name survives all of it, which is what "name once" has to mean.

`trip_days.day` as the primary key also states an invariant the layout depends on and makes it
unviolatable: **a day is in one trip or none**, so a file has exactly one destination.

**Nearby shortfall, flagged and not fixed** (per the standing code bar): the same membership-hash
identity means an existing *day event* is re-proposed whenever its file set changes - ingest one
more photo from an already-named day and the signature moves, so the name is asked for again. That
is a real defect in shipped behaviour, not a hypothetical. Backlogged, not fixed here.

**The cause is shared; the fix is not.** An earlier draft of this document suggested day events
could take the same day-key remedy. **That is wrong, and the correction matters enough to state
in place so nobody applies it later.**

`trip_days.day` works as a primary key for exactly one reason: **a day belongs to at most one
trip.** Day events do not have that property - *they are not days*. 2014-08-16 alone produced
**two** clusters (565 files and 157 files), and 2014-08-17 produced **three**. Keying day events
on the date would collapse a morning outing and an evening one into a single identity, silently
merging two separately-named events into whichever was written last.

Sub-day events therefore need a **different** key - one stable under a changing file set but still
able to distinguish several events within one day. A time-anchored identity (the day plus the
cluster's start, tolerance-matched) is the obvious candidate, but it needs its own design pass and
its own evidence, which is precisely why it is a backlog item and not a footnote to this one.

## 7. The architectural flag, answered honestly

**Does `LayoutScheme` still hold at five shapes? No - and the strain is in the router signature,
not in the idea.**

Route-then-render is right and stays. What does not scale is *how* the route is expressed.
Today (`layout.py:510`):

```python
def template_for(self, rule: str, *, evented: bool) -> LayoutTemplate:
    if rule != TIMELINE_RULE:
        return self.side_bin
    return self.timeline_evented if evented else self.timeline
```

Three shapes, three named fields, one string test and one boolean. It reads perfectly. Now project
the two shapes already in the queue:

- Stage 2 adds trips → `template_for(rule, *, evented, in_trip)`
- backlog `(gg)` adds heavy-day buckets → `template_for(rule, *, evented, in_trip, heavy)`

That is **three booleans and eight combinations, of which five are meaningful**. `in_trip and not
evented` is unreachable; `heavy and in_trip` needs an arbitration nobody has written down; `rule
!= TIMELINE_RULE` makes every other flag moot. None of that is expressible in the signature - it
survives only as an ordering of `if`s that the next reader has to re-derive. Adding the fifth shape
to this router means the router becomes the thing that needs a design document.

**Prerequisite refactor: name the placements.** Replace the boolean axes with one enum and one
mapping - mechanically, with no behaviour change:

```python
class Placement(StrEnum):
    SIDE_BIN = "side_bin"  # non-timeline category
    EVERYDAY = "everyday"  # timeline, un-evented
    EVENT_DAY = "event_day"  # timeline, named single-day event
    TRIP_DAY = "trip_day"  # timeline, a day inside a named trip     [Stage 2]
    DAY_BUCKET = "day_bucket"  # timeline, un-evented heavy day          [(gg)]


@dataclass(frozen=True)
class LayoutScheme:
    templates: Mapping[Placement, LayoutTemplate]

    def render(self, placement: Placement, context: RenderContext) -> PurePosixPath:
        return self.templates[placement].render(context)


def classify(rule: str, context: RenderContext) -> Placement:
    """The one router. Every shape decision in the product is made here, exactly once."""
```

**This is more route-then-render, not less.** The classifier decides once and returns a name;
templates stay dumb structural descriptions with zero conditionals; the token grammar remains a
description, never a language. The one-seam rule is satisfied more strictly than today, because
today the decision is smeared across a signature and a branch order.

What it buys:

- **Exhaustiveness.** `match placement: ... case _ as unreachable: assert_never(unreachable)`-
  mypy `strict` fails the build when a sixth shape is added and a site is missed. Booleans give no
  such check.
- **The vocabulary is the product's.** "Trip day" is a thing Dinesh can say; `evented=True,
  in_trip=True, heavy=False` is not.
- **Impossible states stop being expressible.** There is no `Placement` for "side bin that is also
  a trip day", so no code has to exclude it.
- **Config, `preview_scheme` and Settings enumerate placements** instead of hard-coding three
  field names - the preview grows a row per shape for free.
- **Adding a shape is a member plus a mapping entry**, and the compiler lists every site.

Cost: one mechanical commit across `layout.py`, `config`, `service.py`, `migrate.py` and their
tests. **Provably behaviour-preserving**: render every `SAMPLE_ROWS` case through the old and new
schemes and assert path-for-path equality, so the refactor lands green before trips exist.

**Recommendation: sequence it as Stage 2a, before trips - not after.** Piling the fifth shape onto
the boolean router and refactoring later means doing the trip work twice and reviewing it twice.
This is the cheapest it will ever be, because today there are three shapes to move, not five.

## 8. Rejected alternatives

| Rejected | Why |
|---|---|
| **Date-range names**- `2014-08-15 to 2014-08-17 - Wayanad` | The folder name encodes mutable state. Every trim, extension or late ingest renames a directory on the user's disk. A copy-only tool does not rename what it already placed. |
| **The `20161100_Name` zero-day convention** | Fabricates a date that is not a date. Day `00` parses nowhere, sorts before day 01, and would have to be excluded by hand from every date-reading path we own. Directly against "dates are never guessed"- it just moves the guess into the folder name. |
| **Year suffix in the trip name**- `Wayanad 2014` | Redundant under a `{yyyy}` parent, and after a year split (e) the same trip would carry two different names. |
| **Flat trip folder, no day subfolders** | The Wayanad trip is 2,026 photos. One folder of 2,026 files is the problem `(gg)` exists to solve; creating it here to solve a different problem is a trade in the wrong direction. |
| **A `{trip}` token, or `{event}` behaving differently when a trip exists** | Requires a conditional inside a template. That is the DSL the one-seam rule forbids. The distinction is a *route*, and routes live in the classifier. |
| **Loosening the clustering boundary to span midnight** | Re-creates the Stage 1 defect exactly (`events-clustering-research.md` §2). Multi-day grouping is a separate layer for a reason. |

## 9. Complexity

Trip detection runs on the **already-computed** cluster list - no new I/O, no additional exiftool
pass, no re-read of any file.

- Group clusters by date: `O(C)` over clusters, hash-keyed.
- Sort the distinct active days: `O(D log D)`, `D ≤ C` and in practice `D ≪ C` (10 days from 15
  clusters here).
- One linear scan for consecutive runs, one span check per run: `O(D)`.
- Name-once lookup: one indexed `trip_days` read per candidate day, `O(1)` each.

**Total `O(D log D)` on top of clustering, dominated by a sort of the distinct-day list.** Layout
rendering is unchanged in cost: the classifier is one dict lookup and a constant number of tests
per file, replacing the current constant number of boolean tests.

## 10. Build plan, on approval

**Stage 2a - the placement refactor** (prerequisite, no behaviour change).
Equality harness over `SAMPLE_ROWS` old-vs-new before anything else lands.

**Stage 2b - trip detection**, pure, in `events.py` or a sibling: candidate runs, the max-span cap
with its decline path, the year-boundary split.

**Stage 2c - persistence**, schema v12 (`trips`, `trip_days`), day-keyed name-once.

**Stage 2d - the review stage and the layout wiring**: proposals with per-day counts and adjustable
edges, the `TRIP_DAY` template, the year-split notice at confirm time.

**Stage 2e - adoption for existing libraries.** `migrate-layout` already re-derives rules per file
and plans moves under the preview-then-confirm gate; trips add a route label, not a mechanism.
Naming Aug 15–17 on an already-organised drive plans:

```
2014/2014-08/2014-08-15 - Wayanad/           ->  2014/2014-08/2014-08-15 - Wayanad/2014-08-15/
2014/2014-08/2014-08-16 - Everyday-ish/...   ->  2014/2014-08/2014-08-15 - Wayanad/2014-08-16/
```

Nothing about the migration machinery changes: same journal, same `migration_runs`, same v11
reversibility, same preview and confirm word. **No move happens without the preview being shown
and confirmed.**

### Validation - and it must be run against the bug

Per [`ENGINEERING_STANDARD.md`](ENGINEERING_STANDARD.md) §4, every regression fixture below is
worthless until it has been *seen to fail*. Each is listed with the defect it must fail against:

| Fixture | Must fail when |
|---|---|
| Trip crossing 2016-12-31 | the year-split is removed → asserts two trips, not one |
| Trip 2016-11-28 → 12-02 | start-month filing is removed → asserts all days under `2016-11` |
| Two-day, 2-photo run | cluster-gating is replaced by any-photo days → asserts no proposal |
| 40-day active run | the max-span cap is removed → asserts *no* trip and no fabricated split |
| Edge adjustment | edges are auto-trimmed by count ratio → asserts the full run is proposed |
| Re-ingest one photo into a named trip | identity is membership-hashed → asserts no re-ask |

The last one is the direct regression test for §6, and it is the fixture that would fail today
against the existing signature scheme. That is the point of writing it.

---

## Open rulings needed before build - **all four now resolved**

*Fixed 2026-07-28: item 4 was left dangling at the end of this file by an earlier edit that
inserted §11 in the middle of this list. Restored to its place; all four are answered below.*

1. **Stage 2a first?** Refactor the router before adding the fifth shape, as recommended - or
   proceed with trips on the boolean router and consolidate later. **Resolved: yes** - built as
   `1247055`.
2. **Aug 14** - part of the Wayanad trip or not? Becomes the acceptance fixture either way.
   **Resolved: yes**, the drive up - see §11.
3. **Max span on exceed** - decline and explain (recommended), or split at the cap. **Resolved:
   decline and explain** - see §11's max-span mutation and §3f's message contract.
4. **The day-event re-ask defect** (§6) - backlog entry, as recommended, or fold into Stage 2c.
   **Resolved: backlog entry** - `(ll)`, carrying the correction that the trip day-key fix must
   NOT be applied to day events.

---

## 11. Built: Stage 2b, detection only (2026-07-28)

`detect_trips` lives in **`packages/truestill-core/src/truestill_core/trips.py`**, a sibling
module to `events.py` rather than an addition to it: `events.py`'s own docstring scopes it to
within-day clustering, and a trip is explicitly a second, separate layer above that (§1). One new
module keeps that separation legible rather than growing `events.py` past its stated scope.

**Aug 14 is confirmed: the drive up.** The acceptance fixture
(`test_the_real_wayanad_run_is_one_full_proposal_no_trim`) feeds the real cluster shape and the
real day counts (31 / 635 / 737 / 654, per §2's day-claim rule) and asserts exactly one proposal,
Aug 14-17, untrimmed. Ground truth and the detector agree.

### The signature grew a parameter the design doc did not anticipate

`detect_trips(all_items: Sequence[EventItem], clusters: Sequence[EventCandidate], ...)`, not
`detect_trips(clusters, ...)` alone. The reason is the acceptance fixture itself: its counts
(635/737/654) are **all photos that day**, and `EventCandidate` cannot supply them.
`cluster_camera` silently drops any segment under `min_files` (`events.py`) - the members of a
too-small segment are not returned as a smaller candidate, they are simply gone. Once clustering
has run, no `Sequence[EventCandidate]` can recover what fell outside every cluster. `all_items` is
the same population the clusters were built from, which both existing callers
(`event_review.gather_camera_items`, `event_review.propose_from_catalog`) already hold before they
call `cluster_camera` and currently discard on return.

`all_items` is used **only** to total each already-active day. Gating which days are active still
reads `clusters` alone - a day with entries in `all_items` but no cluster in `clusters` cannot
start, join, or bridge a run. This preserves the load-bearing rule in §4 exactly: the two-day,
2-photo fixture proves it (below).

### `max_gap_days`, the parameter §3f's max-span sibling needed

A run bridges an interior dead day (no cluster) up to `max_gap_days` calendar days wide - a travel
day or a rained-out day does not end a trip. **Default 1**, chosen the same way `max_span_days`
was: on principle, not fitted. Trip-mining literature and prior art (e.g. Canon US10318816) bridge
small gaps for exactly this reason - a single quiet day inside an otherwise continuous outing is
evidence of a lull, not of two separate trips. **Unvalidated on this library**: the one real
multi-day run (Aug 14-17) has no interior dead day to measure the default against, the same honest
limit §3f already recorded for the span cap.

A bridged day sits **inside** `[start_date, end_date]` but has **no entry** in `TripProposal.days`
- the fixture `test_a_bridged_interior_day_stays_inside_the_span_but_absent_from_days` pins this
exactly, including that it is absent, not present at zero.

### Fixtures, and the mutation each was run against

Per `ENGINEERING_STANDARD.md` §4, every fixture below was proven to *fail* against its named
defect before being trusted - not merely written to pass:

| Fixture | Mutation | Result before restoring |
|---|---|---|
| Real Aug 14-17, no trim | reintroduced a relative-count edge trim (drop a day under 10% of the run's peak) | proposal became Aug 15-17 - Aug 14 (31 vs. a 737 peak) was trimmed exactly as the mutation predicts |
| Year boundary splits into two | disabled `_split_at_year_boundary` | one Dec 28-Jan 2 proposal instead of two |
| Two-day/2-photo run never proposes | active-day gating read from `all_items` instead of `clusters` | a trip was proposed from two lone, uncluster-able photos |
| 40-day run declines, no split | `max_span_days` widened to remove the cap | the 40-day run became one proposal, zero declines |
| Bridged interior day, present in span, absent from `days` | `max_gap_days` dropped to 0 | one 5-day proposal became two 2-day proposals |

All five pass against the real code; each was confirmed to fail first. The source was restored and
diffed byte-for-byte against the pre-mutation copy after every test.

### Complexity, as measured against the stated bound

**O(N) to total `all_items` by date + O(D log D) to sort the distinct active-day set + O(D)** for
the run scan, the year split and the span check - `D` = active days, `N = len(all_items)`,
`D ≤ C ≤ N`. The `O(N)` term is additional to the `O(D log D)` asked for, and it is unavoidable:
correctness requires the per-day *all-photos* total, and that total has no source but a single
pass over `all_items`. Neither sequence is walked more than once, and no pass is nested inside
another - flagged here rather than left for a reader to notice the bound was not quite what was
specified.

### Deferred, not silently dropped

Two fixtures from §10's table belong to later stages and were not built here, because they test
things `detect_trips` does not do:

- **`Trip 2016-11-28 → 12-02`, start-month filing.** Filing is a layout/rendering concern
  (Stage 2d's `TRIP_DAY` placement), not a detection concern. `detect_trips` returns dates; nothing
  in it decides which month folder a date renders under.
- **Re-ingest one photo into a named trip, no re-ask.** Name-once is `trip_days.day` as a primary
  key against **persisted** state (§6) - Stage 2c. `detect_trips` is pure and stateless between
  calls; there is nothing here yet to re-ask against.

### A flagged edge case, not exercised by any fixture

A cluster is assumed to fall entirely within one calendar day. `events.py` states this as an
empirical property of the real library (every overnight gap exceeds `MIN_BOUNDARY_GAP_S`), not a
structural guarantee of `cluster_camera` itself - a cluster whose members straddle midnight without
a qualifying gap is possible in principle. Checked against the real 2,238-file library: **zero**
clusters span more than one calendar day. `detect_trips` takes a cluster's first member's date as
its sole contribution to `active_days` if this were ever violated; not tested, because nothing in
the real data exercises it.

### Two consequences of composing already-ruled rules, recorded so they are not mistaken for bugs

- **A two-day run split exactly at Jan 1 can vanish.** Splitting at the year boundary (§3e,
  structural) followed by discarding any single-day piece (§4, a lone day is never a trip) can
  compose to leave a genuine two-day active run - one day in each year - with neither a proposal
  nor a decline. Both rules are individually correct and separately approved; this is their
  faithful intersection, not a new judgement call.
- **`migrate.py`'s naming trap (backlog `(mm)`) is now load-bearing, not latent.** It was harmless
  while every placement shared one naming default; `TRIP_DAY` is the first placement whose
  template Stage 2d will genuinely need to differ. Resolving `(mm)` is a prerequisite for 2d, not
  an optional cleanup beside it.

---

## 12. Built: Stage 2c, persistence only (2026-07-28)

Schema **v12**: `trips` and `trip_days`, exactly as designed in §6 - identity is the row (`id`),
never a membership hash. `create_trip`, `trip_for_day`, `update_trip_days` live on `Catalog`
(`packages/truestill-core/src/truestill_core/catalog.py`). `detect_trips` (§11) is wired to
**nothing** here - it stays pure; the join to persistence is Stage 2d's job.

### The first schema-level down-migration in this codebase, and why it is safe here

`downgrade_v12_to_v11` reverses `_add_trip_tables` - drop `trip_days`, drop `trips`, reset
`PRAGMA user_version` to 11. Every migration before v12 (`_MIGRATIONS`) is forward-only; "reversible
migrations" elsewhere in this codebase (`IMPLEMENTATION_STANDARDS.md`, the v11 entry) means an
*undoable file move* (`migration_journal`/`migration_runs`), not a *schema* undo - there was no
DDL-reversal precedent to match, so this is new. It is safe to add narrowly, for v12 only: v12
*adds* two self-contained tables and alters nothing v11 already had, so dropping them back is exact
rather than an approximation. **Testing/rollback only** - no CLI path calls it, nothing in `Catalog`
wires it in.

### The first declared foreign key in this codebase

`trip_days.trip_id REFERENCES trips(id)` is the schema's first `REFERENCES` clause. SQLite disables
foreign-key enforcement by default, per connection, unless `PRAGMA foreign_keys = ON` is set - and
nothing in `Catalog.__init__` ever had reason to before now. Without setting it, the fixture proving
the FK would have passed for the wrong reason (nothing to enforce, nothing to catch), so it is now
set on every connection. Checked for blast radius first: no other table in the schema declares a
`REFERENCES`, so enabling enforcement changes nothing else's behaviour.

### `update_trip_days` also refreshes the trip's own `start_date`/`end_date`

Not in the original method list, added because leaving them stale is a real correctness bug, not a
hypothetical one: a trip row whose `start_date` still names a day just trimmed off is a row lying
about its own span. The identity (`id`, `name`, `slug`) is untouched - only membership and the
row's own recorded range change, in the same transaction.

### Fixtures, and the mutation each was run against

Per `ENGINEERING_STANDARD.md` §4, proven to fail against its named defect before being trusted:

| Fixture | Mutation | Result before restoring |
|---|---|---|
| Up v11→v12, down v12→v11, byte-equivalent | `downgrade_v12_to_v11` forgets to drop `trips` | schema fingerprints differed by exactly the leftover table |
| `trip_days.day` PK rejects a second trip on the same day | PK dropped from the column | a second `create_trip` on an already-claimed day succeeded instead of raising |
| Edge adjust keeps `trip_id` and `name` stable | `update_trip_days` rewritten to delete-then-reinsert the trip row | the trip vanished under its original id (see below - the first version of this fixture did not catch this) |
| `trip_days.trip_id` FK requires a real trip | `PRAGMA foreign_keys = ON` removed | inserting a `trip_days` row with a nonexistent `trip_id` succeeded instead of raising |

**The identity-stability fixture needed a second attempt to actually discriminate.** The first
version created only the trip under test; a delete-then-reinsert mutation happened to land back on
the *same* id, because plain `INTEGER PRIMARY KEY` (no `AUTOINCREMENT`) assigns the next rowid as
`max(existing) + 1` at insert time - with the table otherwise empty, deleting id 1 and reinserting
produces id 1 again, by coincidence rather than correctness. The fixture now creates a second,
higher-numbered trip *before* the edit under test, so a genuine delete-and-recreate lands on a
visibly different id. This is exactly the discipline `ENGINEERING_STANDARD.md` §4 asks for - a
fixture that cannot fail against the bug is not a regression test - applied one level deeper:
the first mutation attempt revealed the fixture itself needed strengthening, not just the code.

### Complexity

`create_trip`: one insert plus one insert per claimed day, **O(days)**. `trip_for_day`: one
`PRIMARY KEY`-indexed lookup, **O(1)**. `update_trip_days`: one delete, one insert per day, one
row update, **O(days)**. No table scan anywhere in the CRUD surface.

### Not built here, on purpose

No layout wiring, no `TRIP_DAY` template, no UI, no `migrate-layout` adoption - those are Stage 2d
and 2e. `detect_trips`'s output (`TripProposal`) is not yet converted to `create_trip` calls
anywhere; that conversion, and the decision of what "silence" means when `trip_for_day` reports a
day already claimed, belong to whichever stage first has a caller to write it for.

---

## 13. Stage 2d planning (2026-07-29) - a plan, not a build

Requested because 2d is the largest stage in this arc (layout wiring + review UI) and over-scoping
a stage this size has caused reverts before. **Nothing below is built.** No `Placement.TRIP_DAY`,
no template, no route, no UI. This section exists to be approved sub-stage by sub-stage, the same
discipline 2b/2c were built under.

### 13.1 What the codebase actually does today, verified before planning on top of it

Three things this plan depends on, checked directly rather than assumed:

- **`disambiguate_event_folders` is called from exactly one place: `migrate.plan_migration`.**
  `organizer.apply_events` (the CLI's fresh-organize path) never calls it - a fresh organize run
  has no cross-file collision check for event names at all today. Whatever 2d builds for trips
  inherits this asymmetry unless it deliberately changes it, which is out of scope here.
- **The web app's entire trip/event story is "review an already-organized drive, then migrate" -
  never "propose during a fresh import."** `event_review.propose_from_catalog` clusters from
  `catalog.camera_copies_for_events` (an already-placed drive's rows), `commit_catalog` only
  writes `files.event_id`, and the app's own comment is explicit about the split: `events_apply`
  "changes only the catalog; the on-disk placement is a separate, previewed, journalled migration
  (`events_preview` / `events_apply_to_disk`)." Those two routes call
  `service.migration_preview` / `migration_apply`, which call **`migrate.plan_migration` /
  `run_migration` directly** - the identical function `(mm)` just fixed. The CLI's
  `apply_events`/`run_event_stage` path (fresh-organize-time naming) is a **separate, parallel**
  mechanism that the app never uses for events at all, and grepping the CLI source for the word
  "trip" returns nothing - the CLI has no trip-flavoured language anywhere.
- **A discovered risk, not a defect I've fixed or fully diagnosed: `service.migration_preview` /
  `migration_apply` never call `label_routes` or `rederive_rules`, and pass no `routes` or
  `rules_by_sha` to `run_migration`.** `rule_for_row` then defaults every unmapped label to
  `ROUTE_SIDE_BIN` - and `Camera` is *always* unmapped (`label_routes` marks it
  `ROUTE_AMBIGUOUS` by construction, same as any device-rule label). `resolve_scheme` never
  overrides the side-bin template either (`scheme_from_string` never passes `side_bin=`, so it is
  always the fixed `{category}/{yyyy}/{yyyy}-{mm}` shape) - so today, migrating through the app
  (Settings screen **or** the events/trips screen) puts `Camera` files under `Camera/...`, not the
  timeline, unless something resolves the ambiguity that I could not find anywhere in
  `service.py`. `test_migrate_preview_lists_moves` confirms this is the app's *current* behaviour
  and even names it in a comment ("no camera evidence -> side bin") - so it is not a test gap, it
  is the shipped answer for an un-re-derived label. **I have not verified whether this is a live,
  user-visible defect in the already-shipped day-events screen, an intentional gap nobody has hit
  yet, or something a mechanism I haven't traced resolves.** It matters here because 2d's most
  natural path (mirroring day-events exactly, per the point above) would build trips on the *same*
  call path. Flagging rather than fixing - it is not `(mm)`, and diagnosing or fixing it is not
  this planning task's job. **Recommend a short, dedicated verification spike before or as 2d's
  sub-stage 0**, below.
- **The existing "Trips & events" screen already calls a single-day named event a "trip" in its
  own copy** (`templates/index.html`: "Trips & events", "name the trips, then move them into trip
  folders"; `static/app.js`: `plural(r.events, "trip")`). The CLI never uses this word. Once a
  genuinely multi-day `TripProposal` exists, the product will have **two different things called
  "trip"** in the same screen - see §13.3.

### 13.2 Sub-stages, smallest-safe-first

Each lands green independently, in this order. **13.0 is a spike, not a build stage** - it produces
an answer, not code that ships.

**13.0 - Verification spike: does the app's migrate path route `Camera` correctly today?**
**Answered 2026-07-29 - see §13.6. No: it side-bins `Camera`, including named events, today.**
- **Builds:** nothing. Runs the app's existing `/api/migrate/preview` (or `events_preview`) against
  a realistic fixture (a `Camera`-labelled, dated file, year-first layout, no `--by-device`) and
  reads the actual proposed path.
- **Must NOT touch:** any source file. Read-only, using what already ships.
- **Acceptance:** a written answer - "yes, `Camera` lands on the timeline via the app today"
  (meaning I've misread something above and should say exactly what) or "no, it lands in
  `Camera/...` via the app today" (meaning the gap in §13.1 is real and live, and it is a
  **prerequisite fix**, not a 2d task, since it predates trips and already affects shipped
  day-events).
- **STOP point:** the answer, reported. No code changes either way - this is recon, not a fix.

**13.1 - Detection-to-persistence join, catalog-only.**
- **Builds:** the trip equivalent of `event_review.propose_from_catalog` / `commit_catalog`: a
  function that reads a drive's dated camera copies, runs `detect_trips` (2b), and for each
  confirmed decision (name + confirmed edges, or skip) calls `create_trip` / `update_trip_days`
  (2c). Silence semantics for an already-claimed day (`trip_for_day` returns non-`None`): **skip
  it without re-asking**, mirroring day-events' `skipped_signatures` pattern - the specific
  decision `trip-grouping-research.md` §12 left open for "whichever stage first has a caller to
  write it for."
- **Must NOT touch:** `layout.py`, `migrate.py`, `organizer.py`, `RenderContext`, `Placement`, any
  HTTP route, any template. No file is placed or moved by this sub-stage; it only writes
  `trips`/`trip_days` rows.
- **Acceptance fixture:** the deferred fixture from §10's original table, finally buildable now
  that persistence exists - *"re-ingest one photo into a named trip, no re-ask"* - plus a
  Wayanad-shaped fixture (31/635/737/654) asserting one confirmed trip claims all four days, and
  an edge-trim fixture (§5: user narrows the proposed Aug 14-17 run to Aug 15-17) asserting
  `update_trip_days` reflects exactly the confirmed edges, not the raw proposal. Each proven to
  fail against its named mutation first, per `ENGINEERING_STANDARD.md` §4.
- **STOP point:** a drive's catalog can hold named, edge-adjusted trips. Nothing renders
  differently and nothing on disk moves.

**13.2 - `Placement.TRIP_DAY` and the render seam, pure.**
- **Builds:** the `TRIP_DAY` member on `Placement`; `RenderContext` gains a field carrying trip
  membership for a file's day (shape TBD - see §13.3's precedence decision); `classify()` is
  extended to return `TRIP_DAY` under the resolved precedence; `LayoutScheme` gains a template
  slot for it (independently configurable or derived - §13.3); `LayoutTemplate._render`'s
  single auto-append mechanism is extended to append **two** synthesized segments (the trip's own
  header folder, then the individual day) instead of one - today's mechanism assumes exactly one
  synthesized segment per file, and a trip day needs two.
- **Must NOT touch:** `migrate.py`, `organizer.py`, 13.1's catalog join, any HTTP route, any
  template file. This sub-stage proves the *router and renderer* can produce the §2 shape given a
  `RenderContext` - nothing supplies that context from real data yet.
- **Acceptance fixture:** a Stage-2a-style equality harness (render every existing `SAMPLE_ROWS`
  case through old and new `LayoutScheme`s, assert path-for-path equality - proving the new member
  changes nothing for files with no trip context) **plus** direct render tests for the exact
  shapes in §2-§3: Wayanad rendering to
  `2014/2014-08/2014-08-15 - Wayanad/2014-08-15/2014-08-16/2014-08-17/` day subfolders, the
  year-split case (§3e: one trip crossing Dec 31 renders as two, never one folder crossing the
  boundary), and start-month filing (§3d: a Nov 28 - Dec 2 trip files entirely under `2016-11`).
  Each proven to fail against a named mutation (e.g., reverting the two-segment append back to
  one collapses the day level and produces §8's rejected "flat trip folder" shape).
- **STOP point:** given a `RenderContext` carrying trip data, the scheme renders the right path.
  No caller builds that context from real data yet - `mypy --strict`'s exhaustiveness check
  (`assert_never`) is what proves every existing `LayoutScheme.of()` call site was forced to
  answer the new member, the same proof Stage 2a used.

**13.3 - Review UI: propose, adjust edges, name, skip. Catalog only, no relocation.**
- **Builds:** the app-side surface mirroring `events_propose` / `events_merge` / `events_split` /
  `events_apply` for trips - **new interactions, not a relabelled reuse**, since adjusting a
  trip's edges (trim/extend a *day* off either end of a proposed run, per §5) is a different
  operation from merging or splitting day-event clusters. Proposals render per-day counts (per
  §5's `31 / 631 / 722 / 651` table) so a user can judge an edge in one glance. Confirming calls
  13.1's join. The year-split notice (§3e) is shown **at confirm time**, not discovered on disk,
  per §3's "structural, not a proposal" rule.
- **Must NOT touch:** `migrate.py`, or the existing day-event routes/templates, except to
  disambiguate UI copy (§13.3's naming-collision item below) - this sub-stage does not relocate
  a single file.
- **Acceptance fixture:** an HTTP-level test proposing the Wayanad-shaped fixture, adjusting the
  edge from Aug 14-17 to Aug 15-17, confirming a name, and asserting the persisted `trips`/
  `trip_days` rows match the *adjusted* edges, not the raw proposal - the same distinction 13.1's
  fixture proves at the catalog layer, now proven end-to-end through the HTTP surface.
- **STOP point:** a user can name and edge-adjust a trip through the app. No file has moved.

**13.4 - Migration wiring: TRIP_DAY-aware `plan_migration`, gated on 13.0's answer.**
- **Only proceeds once 13.0's spike is answered and, if it found a real gap, that gap is fixed
  first** - building trip-aware migration on top of a migration path that already misroutes
  `Camera` would compound rather than isolate the defect.
- **Builds:** `copies_for_migration` (or a sibling) supplies each row's trip membership (a
  day-keyed join against `trip_days` - no schema change needed, §13.3's schema question below);
  `plan_migration`'s per-row `RenderContext` construction sets the trip field per the precedence
  decision; **widens `(mm)`'s collision-scoping boundary**, flagged explicitly in the Shipped note
  as this stage's job - today's fix groups disambiguation by *naming value*, so two placements
  that happen to share a naming (both `READABLE`, say) are already caught correctly even across
  `EVENT_DAY`/`TRIP_DAY`, but two placements with *different* namings are not cross-checked. This
  sub-stage must decide: cross-group scoping, or an explicitly accepted, alarmed limitation (the
  `dedup.LINEAR_SCAN_ALARM` pattern) - not silently left as today's narrower, single-placement-safe
  scoping.
- **Must NOT touch:** `organizer.py` (the CLI fresh-organize path) - per §13.1's finding, the app
  never uses it for events, and there is no evidence trips need to either, until demand says
  otherwise.
- **Acceptance fixture:** the §10 Stage 2e worked example itself - naming Aug 15-17 on an
  already-organized drive plans the two-line relocation shown there, through the *same* preview
  gate, same journal, same typed-confirm word as every other migration. Plus a same-naming and a
  differing-naming collision fixture (mirroring `(mm)`'s two-sided proof) to pin whichever
  collision-scoping decision this sub-stage makes.
- **STOP point:** a confirmed trip, previewed and confirmed, actually relocates files on a
  connected drive. This is functionally what the design doc called "Stage 2e" (§10) - see §13.4's
  own note below on why the line moved.

### 13.3 Load-bearing decisions 2d forces, not yet settled

1. **Trip-vs-event precedence when a day has both.** §2's rule ("a trip day claims every photo
   taken that day... sub-day clusters merge") means a day inside a confirmed trip must render as
   `TRIP_DAY`, never `EVENT_DAY`, even if that day also has a named cluster. `classify()`'s
   *order* of checks must encode this (trip checked before event), and whichever caller builds
   `RenderContext` must not set `event=` for a trip-claimed day - or `classify()` must ignore
   `context.event` once `context.trip` is set. Not decided which; recommend the latter (classify
   ignores `event` when `trip` is set) so a caller cannot get this wrong by omission.
2. **How much of the `TRIP_DAY` template is configurable vs. derived.** §2 states "the trip shape
   is the day-event shape plus one dated level" - which argues for *deriving* `TRIP_DAY`'s
   template from `timeline_evented` mechanically (no new Settings knob) rather than adding a
   fourth independently-configurable field to `LayoutScheme.of()`/`Preset`. Recommended, not
   decided: fewer knobs, and it makes the "one level deeper" relationship structural rather than
   a convention two settings could drift apart from.
3. **The `(mm)` collision-scoping widening** - named above in 13.4. Real, and this plan places it
   in 13.4 (migration wiring), not 13.2 (pure render) or 13.3 (review UI, no relocation) - it only
   matters once two placements' names can actually collide on disk, which nothing before 13.4
   does.
4. **Schema:** no new version needed for the join itself. `trip_days.day` (PK, already v12) answers
   "is this day claimed" for any date; a day-keyed SQL join against `f.captured_at`'s date is
   sufficient for `copies_for_migration` to attach trip membership, the same way it already joins
   `events` by `f.event_id`. Flag if 13.1's real build surfaces a reason this is insufficient -
   none is evident from the design alone.
5. **The "Trips & events" naming collision** (§13.1). Recommend, not decided: the existing
   single-day screen's copy is disambiguated to "Events" (or similar) as part of 13.3, before or
   alongside introducing genuine multi-day Trips under that name - shipping both concepts as
   "trip" in the same screen is exactly the kind of user-facing-truth defect
   `IMPLEMENTATION_STANDARDS.md` §9 exists to catch, even though neither individual string is
   presently false.
6. **Which surface 2d targets.** Recommend the app's review-in-place pattern (13.1 and 13.3, and
   the migration step in 13.4) as the built surface; the CLI's fresh-organize path
   (`apply_events`/`run_event_stage`-equivalent for trips) is **not built** unless demand says
   otherwise - it has no trip-flavoured language today and nothing in the soak record asks for it.

### 13.4 Stale or contradicted against what actually shipped

- **`IMPLEMENTATION_STANDARDS.md` §2's "One layout seam" bullet still describes the pre-2a
  router** ("routes on `CategoryMatch.rule`... then on whether the file belongs to a named
  event") - it never mentions `Placement`, `classify()`, or the `EVENT_DAY`/`EVERYDAY`/`SIDE_BIN`
  vocabulary Stage 2a (`1247055`) actually shipped. Not fixed here (planning only); worth a small
  docs-only pass before or alongside 13.2, since that sub-stage is exactly where a fourth
  `Placement` member is added to a contract that doesn't yet name the mechanism at all.
- **This document's own §10 assigns "migration renders through the same seam" to Stage 2e**
  ("migrate-layout already re-derives rules per file... trips add a route label, not a
  mechanism"), while the *day-event* precedent already shows the app's entire review flow is
  migrate.py-based end to end (§13.1). The two framings aren't contradictory so much as
  differently grained: §10 is right that migration *machinery* doesn't change, but making trips
  *usable* through the app (the whole point of this arc, per `PROJECT_STATUS.md` §2.2's tab-tour
  origin) needs *some* migrate.py wiring, which is why 13.4 exists inside this plan rather than
  being deferred wholesale to a later stage. Flagging the reframing rather than silently
  relabelling §10.
- **Nothing else checked here contradicts what 2a/2b/2c/`(mm)` actually built** - the shape in
  §2-§3, the fixtures in §11-§12, and the `(mm)` Shipped note all still hold.

### 13.5 Recommended first sub-stage

**13.0 (the verification spike), then 13.1.** 13.0 costs nothing to build and its answer changes
the shape of 13.4 materially - better to know now than to plan 2d's last sub-stage around an
assumption. 13.1 is the smallest genuinely additive slice after that: it only extends Stage 2c's
already-built, already-tested CRUD, touches nothing 2a/2c didn't already touch, and its acceptance
fixture (the re-ask test §12 deferred) is exactly the piece of evidence this arc has been missing
since Stage 2c shipped. 13.2 (the render seam) is independently buildable in parallel once 13.1 is
approved, since neither depends on the other's output yet - but building both before either is
reviewed is exactly the over-scoping this planning pass exists to avoid, so they are proposed as
separate approvals, not a batch.

---

## §13.6 Stage 13.0 spike, answered (2026-07-29): the app's migrate path side-bins `Camera` today

**Confirmed, with evidence. No code changed - this is a read-only finding.**

### The answer

**The app's migration path (`service.migration_preview` / `migration_apply`) does NOT route a
`Camera` photo to the timeline. It side-bins it, and it side-bins a NAMED event's folder along
with it.** This is not a hypothetical edge case: it is the app's actual, currently-shipped,
already-tested behaviour, on the exact two buttons the Settings screen and the "Trips & events"
screen both use to physically move a file.

### The trace, with the real lines

`service.migration_preview` and `migration_apply`
(`packages/truestill-app/src/truestill_app/service.py:976-1023`) both call `run_migration(...)`
with neither `routes` nor `rules_by_sha` supplied:

```python
outcome = run_migration(catalog, LocalDestination(path), marker.uuid, scheme, apply=False)
```

Grepping the whole file for the mechanism that would resolve them turns up nothing:

```
$ grep -n "label_routes\|rederive_rules\|routes=\|rules_by_sha" packages/truestill-app/src/truestill_app/service.py
(no output)
```

`run_migration` -> `plan_migration` -> `rule_for_row`
(`packages/truestill-core/src/truestill_core/migrate.py:203-212`) then does exactly what its
signature promises when both are absent:

```python
def rule_for_row(row, routes, rules_by_sha=None):
    if rules_by_sha:
        ...
    decided = routes.get(str(row["category"]), ROUTE_SIDE_BIN)
    return TIMELINE_RULE if decided == ROUTE_TIMELINE else "fallback"
```

With `routes={}` (the `plan_migration` default), `{}.get("Camera", ROUTE_SIDE_BIN)` is always
`ROUTE_SIDE_BIN` - `Camera` is *always* ambiguous by construction
(`label_routes`, `migrate.py:102-147`: only screenshot/messenger/fallback labels are
deterministic; `Camera` is the device rule's own default label). `rule_for_row` therefore always
returns `"fallback"`, and `classify("fallback", context)` (`layout.py:515-524`,
`TIMELINE_RULE = "device"`) always returns `Placement.SIDE_BIN`, regardless of `context.event`.

The frontend has no resolution mechanism either - `app.js` and every template have zero mentions
of "ambiguous", "rederive", or "by_device"/"by-device".

**Contrast with the CLI**, which does not have this gap: `cli._cmd_migrate_layout`
(`cli.py:1364-1387`) calls `rederive_rules` **unconditionally**, before any user confirmation:

```python
routes = label_routes(catalog, marker.uuid)
rules_by_sha = rederive_rules(catalog, marker.uuid, args.path, routes, by_device=...)
decided = {r.label: (ROUTE_SIDE_BIN if r.needs_decision else r.route) for r in routes}
plan = plan_migration(catalog, marker.uuid, scheme, routes=decided, rules_by_sha=rules_by_sha)
```

`rule_for_row` checks `rules_by_sha` **first** - so any file `rederive_rules` can positively
re-derive (a real exiftool re-read against the actual rule chain, bounded to ambiguous labels
only) routes correctly regardless of what the label-level default says. The app skips this whole
step. It is not a missing interactive prompt; it is a missing automatic re-derivation the CLI
does not even ask permission for.

### Confirmed against the existing test

`test_migrate_preview_lists_moves` (`packages/truestill-app/tests/test_settings_http.py:72-99`)
already asserts this as the app's real, intended behaviour, and names it in its own comment:

```python
assert r["moves"][0]["new"] == "Camera/2023/2023-08/x.jpg"  # no camera evidence -> side bin
```

This is not a test gap - it is the shipped, tested answer for an unresolved ambiguous label. The
gap is that the app never attempts to resolve it, not that the fallback itself is wrong.

### Empirical confirmation (a throwaway script, not committed, no source touched)

Seeded a catalog exactly as a real organize run would: a `Camera`-labelled file already sitting at
`2023/2023-08/x.jpg` (the pure year-first timeline), named as an event via `record_event` +
`set_event_id` - the identical mechanism `event_review.commit_catalog` uses when a user clicks
"Save names" on the Trips & events screen. Then compared what a fresh organize run would answer
for the same file against what the app's actual `migration_preview` answers, using
`resolve_scheme()` - the same layout resolution both paths use:

```
organize (rule=device, TIMELINE_RULE) would place it under: 2023/2023-08/2023-08 - Everyday/x.jpg
organize, as a named event, would place it under:            2023/2023-08/2023-08-20 - Goa Trip/x.jpg
app migration_preview moves: [{'old': '2023/2023-08/x.jpg',
                                'new': 'Camera/2023/2023-08/2023-08-20 - Goa Trip/x.jpg'}]
```

The app's own migration path takes a file **already correctly placed on the timeline**, already
named via the app's own review screen, and relocates it **off** the timeline into
`Camera/...` the moment "Preview" or "Move photos into trip folders" is clicked.

**Not verified: whether this has actually been exercised against the real production drives.**
Dinesh may have used the CLI (`truestill migrate-layout`, which does not have this gap) for the
real year-first migration described in §2.0, in which case this is a live gap that has not yet
been hit through the app specifically, rather than one that has silently mis-filed real photos.
That distinction matters for urgency but not for the finding itself: the code path is real, it is
reachable from two shipped buttons, and it is reproducible on demand.

### Consequence for 13.4 (and for day-events, today, independent of trips)

- **This predates trips entirely and already affects shipped day-events.** Any name given through
  the "Trips & events" screen and applied via its own "apply-to-disk" button lands under
  `Camera/...`, not the timeline, today - with or without Stage 2d. It is not caused by `(mm)`
  and `(mm)`'s fix does not touch it (confirmed above: `rule_for_row` returns `"fallback"` before
  `classify()` ever sees the event).
- **13.4 must not build trip-migration wiring on top of this unresolved.** A confirmed trip,
  applied through the same `migration_preview`/`migration_apply` path, would be relocated under
  `Camera/2023/2023-08/2023-08-15 - Wayanad/...` instead of the timeline shape §2 specifies -
  compounding the existing gap with a second, newer feature built on the same broken assumption.
- **This is a candidate prerequisite fix, not a 2d task**, per 13.0's own acceptance criterion.
  Options, none built here:
  1. Have `service.migration_preview`/`migration_apply` call `label_routes` + `rederive_rules`
     unconditionally, exactly as the CLI does - no interactive step needed, since re-derivation is
     automatic and only the *unresolved* remainder needs a decision (which the app has no UI for
     either, a second, smaller gap this option would also expose).
  2. Surface the ambiguity in the app instead of silently defaulting - closer to
     `label_routes`'s own intent ("surfaced for a decision, never guessed") but is new UI, not a
     one-line service fix.
  3. Do nothing here and treat it as a pre-existing, independent defect to fix on its own schedule,
     accepting that 2d's app-based trip review (§13.3-§13.4) inherits it until it is.
  **Recommend option 1** as the minimal fix that makes the app's behaviour match the CLI's already-
  settled answer to the exact same question, but this is a recommendation, not a decision - it
  affects day-events today and should probably be judged on its own, separately from whether or
  when Stage 2d proceeds.
