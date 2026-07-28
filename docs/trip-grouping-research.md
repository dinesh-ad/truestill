# Trip grouping: multi-day events, and the router that has to carry them

Status: **Design approved (2026-07-28, `b5cba4a`, rulings `fb60c10`). Stage 2a (`1247055`) and
Stage 2b (detection only) are built; §11 records what shipped and what remains open.** Stages
2c-2e (schema, layout wiring, migration) are still to come.

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

## Open rulings needed before build

1. **Stage 2a first?** Refactor the router before adding the fifth shape, as recommended - or
   proceed with trips on the boolean router and consolidate later.
2. **Aug 14**- part of the Wayanad trip or not? Becomes the acceptance fixture either way.
3. **Max span on exceed**- decline and explain (recommended), or split at the cap.

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
4. **The day-event re-ask defect** (§6)- backlog entry, as recommended, or fold into Stage 2c.
