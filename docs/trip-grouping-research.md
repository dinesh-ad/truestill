# Trip grouping: multi-day events, and the router that has to carry them

Status: **The trip arc is COMPLETE, end to end (2026-07-29).** Design approved (2026-07-28,
`b5cba4a`, rulings `fb60c10`); 2a the router refactor (`1247055`), 2b detection (§11), 2c
persistence, catalog v12 (§12). Backlog `(mm)` resolved (`1ed021e`) unblocked 2d, planned as
sub-stages 13.0-13.4 (§13): **13.0** (verification spike, §13.6), **13.1** (the
detection-to-persistence join, §13.1), **13.2** (`Placement.TRIP_DAY` and the render seam, §13.2),
**13.3a** (reveal in file manager, §13.3a), **13.3b** (the proposal-card redesign, §13.3b) and
**13.4** (migration wiring, §13.4, `db5e517`) are all built. 13.4 also subsumes what the original
design called **Stage 2e** (adoption for existing libraries), since it rides the same
`plan_migration` the CLI's `migrate-layout` already calls - no separate 2e work was needed.
Nothing in this arc remains open; see `PROJECT_STATUS.md` §2.2 for what is next.

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
**Answered and FIXED, 2026-07-29 - see §13.6 (the finding) and §13.7 (the fix). It side-binned
`Camera`, including named events; it now routes through `label_routes`/`rederive_rules` exactly
as the CLI does.**
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

**13.1 - Detection-to-persistence join, catalog-only. BUILT 2026-07-29.**
- **Shipped:** `truestill_core.trip_review` (`propose_trips_from_catalog` / `TripDecision` /
  `commit_trips`), the trip equivalent of `event_review.propose_from_catalog` / `commit_catalog`,
  one layer up - a sibling module to `trips.py`, for the same reason `trips.py` is a sibling to
  `events.py` (§11): `trips.py`'s own docstring scopes it to pure detection, so persistence code
  does not belong inside it. `propose_trips_from_catalog` reads a drive's dated camera copies and
  runs `detect_trips` (2b) unchanged; `commit_trips` takes `TripDecision`s (a proposal, a name or
  `None` to decline, and optional `confirmed_days`) and persists them.
  - **Name-once semantics, resolved as *refresh via `update_trip_days`*, not a bare skip** - a
    deliberate refinement of this sub-stage's original wording, flagged here rather than silently
    diverging from it. Every day in a decision already claimed by the *same* trip calls
    `update_trip_days` with the confirmed set: idempotent when nothing changed (a pure re-ask),
    an edge adjustment when it did, and identity-preserving either way since `update_trip_days`
    never touches `id`/`name`/`slug`. This subsumes "skip without re-asking" (the observable
    result - no duplicate, no rename - is identical) while also correctly handling "re-ingest one
    more photo into an already-active day," which a bare skip would not: that day's count changes
    but its claim does not, so refreshing (not skipping) is what keeps the row accurate.
    **Mixed claims** (some days already claimed by an *other* trip, alongside unclaimed days) are
    not reachable by any fixture built here - flagged in the function's own docstring as
    out-of-scope, not silently handled.
  - **The Wayanad-shaped (31/635/737/654) fixture was not reproduced here.** That exact shape is
    already the acceptance fixture for `detect_trips` itself (§11,
    `test_the_real_wayanad_run_is_one_full_proposal_no_trim`); re-deriving it at this layer would
    re-assert detection, which this sub-stage does not touch. Built instead: smaller synthetic
    multi-day fixtures (two and three consecutive active days) that exercise the *persistence*
    guarantees - name-once, edge-trim, decline - the real shape's job is to prove detection, and
    this stage's job is to prove what a caller does with whatever detection returns.
- **Did not touch:** `layout.py`, `migrate.py`, `organizer.py`, `RenderContext`, `Placement`, any
  HTTP route, any template. No file was placed or moved; only `trips`/`trip_days` rows.
- **Fixtures, each proven to fail against its named mutation first** (`ENGINEERING_STANDARD.md`
  §4):

  | Fixture | Mutation | Result before restoring |
  |---|---|---|
  | Re-ingest one photo into a named trip, no re-ask, id/name stable | the already-claimed check removed (always `create_trip`) | `sqlite3.IntegrityError` - `trip_days.day`'s primary key refused the second claim |
  | Confirmed edges (a 3-day proposal trimmed to 2) are what get stored | `confirmed_days` ignored, raw `proposal.days` used | the trimmed day was claimed anyway - the trim silently did not take |
  | A declined run (span over `DEFAULT_MAX_SPAN_DAYS`) persists nothing | none needed - a decline cannot become a `TripDecision` by construction, so this is a type-level guarantee confirmed at the catalog boundary rather than a mutation test |

  The re-ask fixture reuses the identity-stability discipline `test_edge_adjust_keeps_trip_id_
  and_name_stable` (§12) already needed: a decoy trip created *after* the trip under test, so a
  delete-then-reinsert bug cannot land back on the same id by SQLite's rowid-reuse coincidence.
  - **A fixture-design pitfall worth recording**: an early version of the re-ask fixture seeded
    the re-ingested photo as a second, separate synthetic burst late at night. On this library's
    small synthetic scale, that burst's large gap to the existing cluster did not clear the
    relative-density cut threshold (`events-clustering-research.md` §1-2's own lesson, hit again
    here), merging two days into one cluster and silently changing which day the fixture actually
    exercised. Fixed by seeding the re-ingested photo immediately after the existing cluster's
    last member instead, which is also the more faithful shape for "re-ingest one photo."
- **Complexity:** `O(days)` per decision for the name-once lookups (one indexed `trip_for_day`
  read per day) plus `O(days)` for whichever of `create_trip` / `update_trip_days` fires - both
  already `O(days)` per Stage 2c (§12). No table scan.
- **STOP point:** a drive's catalog can hold named, edge-adjusted trips. Nothing renders
  differently and nothing on disk moves. `Placement.TRIP_DAY` does not exist yet - 13.2 next.

**13.2 - `Placement.TRIP_DAY` and the render seam, pure. BUILT 2026-07-29.**
- **Shipped:** the `TRIP_DAY` member on `Placement`. `RenderContext` gains `trip: tuple[datetime,
  str] | None` and `trip_name: str | None`, mirroring `event`/`event_name` exactly, and its
  `date` property resolves a trip's **start** date first (a trip stays one object, filed under
  its own start month - §3d - the same way an event's cross-month member already did; sharing
  one property rather than re-deriving the rule a second time). `classify()` is extended per
  the precedence decision below; `LayoutScheme.of` gains an optional `trip_day` parameter,
  **defaulting to `timeline_evented` itself** - "the trip shape is the day-event shape plus one
  dated level" (§2) argues for deriving the template rather than adding a fourth
  independently-configurable Settings knob; every existing scheme-construction call site
  (`Preset.scheme()`, `scheme_from_string`, `DEFAULT_SCHEME`) needed no change and now also
  produces a valid `TRIP_DAY` template for free. `LayoutTemplate._render`'s single auto-append
  branch gains a sibling, `_trip_segments`, appending **two** synthesized levels instead of one:
  the trip's own header folder (via `event_folder`, unchanged - a trip header is a dated, named
  folder exactly like an event's, so it reuses the same naming/sanitization/disambiguation-shape
  logic rather than a second copy of it), then the individual day in full ISO form (§3b) -
  always the file's **own** capture date, never the trip's start, which the base segments above
  already used.
  - **Precedence, resolved as recommended**: `classify()` checks `context.trip` before
    `context.event` and returns unconditionally when it is set - `context.event` is never
    consulted once a trip claims the day, so a caller cannot get §2's "a trip day claims every
    photo taken that day" rule wrong by omission.
  - **No `{trip}` token** - §8 already rejects one (a conditional inside a template is the DSL
    the one-seam rule forbids), so the two-segment append is the *only* way a trip renders,
    unconditionally, exactly like the event append it sits beside.
  - **The (mm) collision-scoping boundary, baselined here, widened in 13.4 (built).** A test at
    this stage constructs a scheme where `TRIP_DAY`'s naming genuinely diverges from
    `EVENT_DAY`'s (bypassing the derived default via the `trip_day=` override - no shipped
    preset does this yet, exactly as no shipped preset ever made `EVENT_DAY` diverge from
    `EVERYDAY` before `(mm)`), and pins that the render seam can express the divergence -
    render-level only, not yet `migrate.py`'s grouping, which this sub-stage does not touch. 13.4
    later widened the grouping itself; see its own note for what that found.
  - **A stale cross-reference in this document's own earlier draft, fixed in place**: this
    section's "shape TBD" note pointed at "§13.3's precedence decision," but two different
    sections in this document are both informally "13.3" - the *sub-stage* bullet (review UI,
    below) and the *load-bearing decisions* subsection further down. The precedence and
    template-derivation guidance actually being referenced lived in the latter (decisions 1 and
    2); both are now resolved, above, rather than left to be found by guessing which "13.3" was
    meant. Not renumbered further than this fix - a wholesale renumbering is out of scope for a
    pure-render sub-stage and risks breaking other already-committed cross-references.
  - **The year-split case (§3e) was not built as a render-level fixture, and does not belong
    here.** `_split_at_year_boundary` (Stage 2b, `trips.py`) already guarantees no `TripProposal`
    crosses a year boundary before it ever reaches persistence or rendering - splitting into two
    *rows* is a detection-time decision, not something the renderer decides or could decide from
    a single `RenderContext`. What the renderer *does* guarantee, and what start-month filing
    (§3d) already tests: a trip entirely within one year files under that year via `context.date`
    resolving to the trip's start, whichever year that is.
- **Did not touch:** `migrate.py`, `organizer.py`, 13.1's catalog join (`trip_review.py`), any
  HTTP route, any template file. Nothing supplies `RenderContext.trip` from real data yet.
- **Fixtures, each proven to fail against its named mutation first** (`ENGINEERING_STANDARD.md`
  §4):

  | Fixture | Mutation | Result before restoring |
  |---|---|---|
  | mypy exhaustiveness: `LayoutScheme.of` must name `TRIP_DAY`'s template | the `case Placement.TRIP_DAY` arm removed (member added, arm not) | `mypy --strict` failed at the `assert_never` line: `Argument 1 to "assert_never" has incompatible type "Literal[Placement.TRIP_DAY]"; expected "Never"` |
  | `TRIP_DAY` derives `EVENT_DAY`'s template, not `EVERYDAY`'s | the derivation fallback changed from `timeline_evented` to `timeline` | rendered under a bare `{yyyy}` base instead of `{yyyy}/{yyyy}-{mm}` - `AssertionError` |
  | Equality: the existing three placements are unperturbed | none needed - the pre-existing golden-master `test_every_preset_renders_its_known_paths` (pinning all three shipped presets' `SAMPLE_ROWS` output) passed unchanged, which *is* the Stage-2a-style equality proof; there is no separate "old scheme" object left to diff against now that `TRIP_DAY` is additive to the one `LayoutScheme` implementation | - |

  Direct render tests (not run against a bug, since nothing existed to regress against): the
  exact Wayanad shape (§2), start-month filing across a month boundary (§3d), trip-before-event
  precedence, and the naming-divergence baseline above.
- **Complexity: unchanged - `O(1)` per file.** `classify` is still a constant number of
  comparisons (one more branch, not a loop); `template_for` is still a dict lookup;
  `_trip_segments` is two more `event_folder`/`strftime` calls, not a function of file count.
- **STOP point:** given a `RenderContext` carrying trip data, the scheme renders the right path.
  No caller builds that context from real data yet.

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

**13.3a - Reveal in file manager on the apply-to-disk result. BUILT 2026-07-29.** A small,
independent slice, done ahead of the rest of 13.3 because it stands on its own: the aggregate
"Moved N photos into trip folders." line on the *existing* day-event screen (real multi-day
Trips have no UI yet - this is the day-event "Trips & events" screen the naming-collision item
below already flags) is replaced by one row per named+applied event/trip this run, each with its
real destination folder and a working "Open in file manager" link.

- **No new endpoint.** `/api/reveal` (`service.reveal_in_file_manager`) already ships, already
  used on the Backups screen's drive cards (`app.js:639`), with the same `LocalGuard` every other
  route has. The frontend reuses the exact `[data-open]` pattern unchanged.
- **The originally-specified root-restriction was proposed, researched, and withdrawn** - it
  does not defend a threat in scope. `SECURITY.md`'s own model is that an attacker who is
  already the machine's own user is out of scope; the real threat `LocalGuard` defends against
  (a web page reaching the local API via token/Host/Origin) is unaffected by which directory a
  legitimate same-origin request names. Checked first that no existing filesystem endpoint
  (`fs_dirs`, `fs_validate`, `fs_create`) restricts to a root either - `path.resolve()` there is
  symlink/`..` normalization, not a boundary check - and confirmed restricting `reveal` alone
  would have broken the already-shipped Backups reveal, which points at drive paths outside any
  organize-library root by design.
- **The originally-specified disabled-for-not-yet-applied-card state was also withdrawn** -
  there is no per-trip card with a path anywhere in the shipped UI to attach it to. The only
  existing cards are pre-name, pre-apply proposal cards (`cluster_json`: `start`/`end`/`count`/
  `location`, no path, no applied-state), and the post-apply view was a single aggregate summary
  with no per-trip breakdown at all. Reveal only ever makes sense once a real folder exists, so
  it landed on the one surface that provably has one: the apply-to-disk result, after the files
  have actually moved there.
- **The one backend touch**: `Catalog.sample_relative_for_event` (one indexed lookup, `O(1)`) and
  `service.migration_apply` gaining an optional `named_events` parameter - unused by the plain
  Settings-screen migration, which keeps behaving exactly as before.
- **Fixture, proven against the defect first**: two trips named and applied in one run must
  produce two result rows, not one collapsed aggregate. Confirmed failing when `events_apply_to_
  disk` is changed to always pass an empty event list (`KeyError: 'trips'` - the aggregate-only
  shape), passing after restoring.

**13.3b - Proposal-card redesign: the inversion, split/merge as a pair, EVENT vs TRIP labelling.
BUILT 2026-07-29.**

Supersedes 13.3's originally-planned edge-trim/extend interaction model (the bullet above,
written the same planning pass) - flagging the divergence rather than silently overwriting the
earlier plan. The instruction that actually built this sub-stage required mirroring the shipped
day-event handlers (`events_propose`/`events_merge`/`events_split`/`events_apply`) exactly, not
inventing a new "adjust an edge" gesture. Trimming/extending a day off either end of a proposed
run is **not** built; splitting a run at a day boundary and merging two runs the detector did not
join **are**, because those are the operations day-events already have muscle memory for
(`events.split_candidate`/the old `merge_candidates`), and reusing that interaction shape for
trips - rather than inventing edge-nudging - is what "do not invent a new interaction model" meant
in practice. §13.3's other decisions (items 1-4 below) are unaffected; only the interaction shape
changed.

- **THE INVERSION.** Before this stage, every Stage-1 day-cluster rendered as its own review card
  regardless of whether it was part of a longer run; a user reassembled a trip by hand with a
  merge checkbox, redoing by hand what `detect_trips` (2b) already knew. `trip_review.
  assemble_trip_review` now runs detection first: a genuine multi-day proposal renders as ONE
  card (span, photo total, per-day breakdown); a standalone active day still renders as its own
  (unchanged) day-event card. Detection assembles up; the user adjusts down (split) or joins
  across a gap detection left alone (merge).
- **LABELLING.** Resolves 13.3's item 5 naming collision (below): a card's `kind` ("trip" |
  "event") is a **display** label computed from day count (`ReviewCard.kind`), decoupled from
  which of `trip`/`event` the card actually carries - a multi-day run is a TRIP, a standalone day
  is an EVENT, and the screen's copy and per-card badge both say so.
- **CONTROLS, kept as a pair.** SPLIT is primary: breaks a wrongly-joined run at a day boundary
  (`trip_review.split_trip`, the direct trip-shaped inverse of merge) for a trip card, or by file
  count (`events.split_candidate`, unchanged) for an event card. MERGE is secondary (visually
  demoted - a small `.k`-styled checkbox beside the card, not its own prominent control) and
  combines two or more cards the detector did not join (`trip_review.merge_review_cards`), always
  producing a `TripProposal` - never a raw concatenated `EventCandidate` - because a manual merge
  must obey the same two locked rules detection does:
  - **§3e year boundary**: refuses with a stated reason rather than fabricating a cross-year trip.
  - **§3f max-span**: declines with the exact message format (`trip_review.decline_message`,
    composed here per §12's deferral) rather than silently splitting or truncating.
  Both refusals surface to the HTTP caller as `{"error": "..."}` (never a silent no-op) and leave
  the session's cards untouched.
- **Nothing is auto-applied.** `assemble_trip_review`'s declines (over-span runs `detect_trips`
  itself declined) are surfaced as messages too (`decline_message`), not folded into silence. A
  trip is written to the catalog only on explicit name + confirm, through the same `commit_trips`
  join 13.1 built.
- **A consequence, flagged rather than silently absorbed:** the old `events_merge` concatenated
  raw cluster items into one `EventCandidate` (no year/span check possible on a bag of items with
  no calendar structure). Because every merge must now obey §3e/§3f, merging two gap-separated
  day-events - even when neither looks like a "trip" on its own - always produces a `TripProposal`.
  **At this stage** a trip did not yet reach `migrate.py`/apply-to-disk (that was 13.4's job, then
  unbuilt); naming such a merge persisted it to the catalog but did not relocate its files, where
  the pre-13.3b merge-then-apply-to-disk flow did, and the app said so honestly rather than
  reporting a false "nothing to move." **Resolved in 13.4 (built):** a merged trip now previews
  and applies exactly like a named event always has - the honesty banner this stage added was
  removed once it had something true to say instead.
- **A narrow, deliberate labelling edge case:** `split_trip` can split a 2-day trip (the smallest
  a proposal can be) into two 1-day pieces. Each remains a `TripProposal` under the hood - still
  confirmed through `commit_trips` like any other trip - but is *labelled* "event" (`ReviewCard.
  kind`'s day-count floor), for the same reason `detect_trips` itself never proposes a 1-day trip.
  Not reconciled into a genuine cluster-based `EventCandidate`, since that would need member items
  this function is never given.
- **Fixtures, proven against the defect first (`ENGINEERING_STANDARD.md` §4):**
  - A multi-day detected run must render as ONE card, not one per day: mutating `assemble_trip_
    review`'s claimed-days set to empty reproduced the pre-13.3b bug exactly (`4 == 2`, every
    cluster rendering separately); restored.
  - A manual merge across a year boundary must refuse: disabling the year check (`if False:`)
    made the core-level fixture fail with "DID NOT RAISE TripMergeError"; restored. Reproduced
    again at the HTTP layer (dropping `events_merge`'s `except TripMergeError` lets the exception
    surface as an unhandled 500 instead of `{"error": ...}`); restored.
  - A manual merge past `max_span_days` must decline, not split/truncate: same mutation pattern
    on the span check, same failure, same restore.
  - A standalone day is labelled "event", never "trip" - proven directly against `ReviewCard.kind`
    and again over HTTP against the serialised `kind` field.
  - `split_trip`/`merge_review_cards` round-trip correctly, including that a merged-in solo
    cluster's partial count is superseded by the day's full total (§2's day-claim rule).
- **Complexity.** Detection is unchanged: O(N) over camera items + O(D log D) over active days
  (§11). `assemble_trip_review` adds one O(N) day-total pass over the same items already read for
  detection (no extra I/O - one query feeds both) and O(P) to build cards from P proposals/
  clusters. Each merge/split/decline-message call is O(days involved) - a handful of dates, never
  a function of the whole library.
- **Not built here, on purpose:** 13.3's originally-planned edge-trim/extend interaction (above);
  13.4's migration wiring (a confirmed trip does not move files); the CLI fresh-organize path for
  trips (§13.3 item 6, unchanged recommendation).

**13.4 - Migration wiring: TRIP_DAY-aware `plan_migration`. BUILT 2026-07-29 (`db5e517`).**
- **Prerequisite cleared:** 13.0 found a real gap (the app's migrate path side-binned `Camera`)
  and it is fixed - §13.7. This sub-stage no longer waits on it.
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

**BUILT 2026-07-29 - the trip arc is now complete end to end (detect -> review -> apply).**

`copies_for_migration` gained a day-keyed `LEFT JOIN` against `trip_days`/`trips` (no schema
change - `trip_days.day`'s existing primary key); `plan_migration` sets `RenderContext.trip` per
row, gated on that row's own rule resolving to the timeline (a trip's day-claim, unlike an
event's, is not safe-by-construction against a same-day non-Camera file, since the join is
day-keyed, not category-keyed - guarded explicitly, and a day a trip claims but an event does not
survive on is fully dissolved into the trip, never left as a phantom disambiguation candidate).
Rides the exact `migration_preview`/`migration_apply` path an event's migration already used -
no new endpoint, no looser confirm gate.

**The `(mm)` widening**, decided: event and trip headers are disambiguated in one pass, grouped by
their *resolved naming* rather than by placement - the mechanism that already made two same-day
events collide correctly now covers a trip header for free. Proven, not assumed: under this
schema's day-claim exclusivity (`trip_days.day` is a primary key, and a day a trip claims
dissolves any event on it), an event and a trip header can **never** actually collide - collision
requires an identical date, and an identical date always means dissolution. The grouping is still
the right general mechanism (and the regression fixture below proves it does not break the
existing event-vs-event case now that trips share its dict); the one case it does not
cross-check - `TRIP_DAY` deliberately configured with a naming that diverges from `EVENT_DAY`'s
(13.2's escape hatch, no production caller sets it) - cannot collide on the rendered string in
the first place, and is alarmed (once, on the run that crosses it, the `dedup.LINEAR_SCAN_ALARM`
pattern) rather than assumed away.

**Complexity:** the added join is `trip_days.day`'s primary key, `O(1)` per row; `plan_migration`
stays `O(rows)` overall, unchanged from before this stage.

**Fixtures, proven against the defect first:** the §10 worked example (Aug 15-16 plans the header
then each day beneath it); a Camera photo in a trip inherits §13.7's routing (still side-binned
without a route decision, correctly timelined with one - mutation: dropping the row-level
`rule == TIMELINE_RULE` guard let a WhatsApp file on a trip's day get pulled into the trip folder,
confirmed failing, restored); an event sharing a trip's day is fully dissolved, not
double-planned (mutation: dropping the dissolved-event exclusion produced a spurious collision
warning for a folder nothing would ever use, confirmed failing, restored); the `(mm)` alarm
(mutation: disabling it, confirmed silent, restored); preview alone moves nothing, apply relocates
exactly what preview showed.

### 13.3 Load-bearing decisions 2d forced - all now settled

1. **Trip-vs-event precedence when a day has both - RESOLVED, built 13.2.** `classify()` checks
   `context.trip` before `context.event` and returns unconditionally when it is set, exactly the
   recommended option: a caller cannot get this wrong by omission, since `context.event` is
   never consulted once a trip claims the day.
2. **How much of the `TRIP_DAY` template is configurable vs. derived - RESOLVED, built 13.2.**
   `LayoutScheme.of` derives `TRIP_DAY`'s default from `timeline_evented` itself; no new
   independently-configurable field was added. An explicit `trip_day=` override exists as a
   construction-time escape hatch (used by 13.2's own (mm)-boundary baseline test), but no
   production caller uses it.
3. **The `(mm)` collision-scoping widening - RESOLVED, built 13.4.** Event and trip headers are
   disambiguated together, grouped by resolved naming rather than placement. Proven there, not
   assumed: under this schema's day-claim exclusivity, an event and a trip header can never
   actually collide - see 13.4's own note for the full finding.
4. **Schema - CONFIRMED, built 13.4 exactly as predicted.** No new version was needed for the
   join. `trip_days.day` (PK, already v12) answers "is this day claimed" for any date; a
   day-keyed SQL join against `f.captured_at`'s date is what `copies_for_migration` uses to
   attach trip membership, the same way it already joins `events` by `f.event_id`.
5. **The "Trips & events" naming collision** (§13.1) - **RESOLVED, built 13.3b.** A card's `kind`
   ("trip" | "event") is a display label computed from day count, decoupled from the underlying
   `ReviewCard` payload; the screen's copy and per-card badge now say TRIP for a genuine multi-day
   run and EVENT for a standalone day, never "trip" for both.
6. **Which surface 2d targets - RESOLVED as recommended.** The app's review-in-place pattern
   (13.1, 13.3b, and the migration step in 13.4) is the built surface; the CLI's fresh-organize
   path (`apply_events`/`run_event_stage`-equivalent for trips) remains **not built** - it has no
   trip-flavoured language today and nothing in the soak record asks for it.

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

**Confirmed with evidence, then FIXED the same day (2026-07-29) - see §13.7. Soak-class defect:
outranked 13.1, landed before any trip build resumed.**

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

---

## §13.7 Fixed (2026-07-29): option 1, with the (a)/(b) history that justified it

**Determination: (a), an oversight - not a deliberately-deferred interactive step.** Checked
before fixing, per instruction, rather than assumed:

- The app's trip/event migrate wiring (`ad34fd6`, 2026-07-26 15:30, "make named trips reach disk")
  was written when `Camera/YYYY/MM/YYYYMMDD_slug/` genuinely **was** the correct destination - its
  own commit message says so: "relocating the copies into `Camera/YYYY/MM/YYYYMMDD_slug/`."
  Category-first was still the default; `Placement` and the side-bin/timeline distinction did not
  exist yet.
- The year-first default flip (`c0ae0c8`) landed 2026-07-28 12:14, **two days later**.
- `label_routes`/`rederive_rules` were introduced in `6676617`, 2026-07-28 12:40 - 26 minutes
  after the flip, and explicitly because of it: "2,224 of 2,269 copies in the real soak catalog
  carry the label `Camera`. That is not an edge case." That commit added 100+ lines wiring both
  functions into the CLI's `_cmd_migrate_layout`.
- **The same commit touched `service.py`** - its whole diff there is two one-line changes
  adapting `run_migration`'s call shape from `scheme.timeline` to `scheme` (a signature change
  happening in the same commit), never adding `routes=`/`rules_by_sha=`. No comment, no backlog
  entry, nothing in `server.py`/`app.js`/any template suggests an interactive app-side review
  step was ever planned - the mechanical adaptation kept the app compiling under the new
  signature and stopped there.

### The fix

`service.py` gains `_resolve_migration_routes(catalog, drive_uuid, path)`, calling
`label_routes` + `rederive_rules` exactly as `cli._cmd_migrate_layout` does (no `--by-device`
equivalent, since the app has no such toggle - re-derivation runs with the plain device rule,
matching what the app can actually express). Both `migration_preview` and `migration_apply` now
pass the resolved `routes`/`rules_by_sha` to `run_migration`, so a `Camera` photo an organize run
would place on the timeline migrates to the same place - migrate and organize are the same
placement decision, routed through the same seam, the same principle `(mm)` enforced one layer
up.

### Complexity

`label_routes` is `O(files)` for the tally, `O(labels)` after. `rederive_rules` is
`O(ambiguous files)` - one batched exiftool read (~2.2 ms/file at 12 MP, header reads only) plus
an `O(1)` rule evaluation per file - and **zero when nothing is ambiguous**. This is the exact
cost the CLI has already paid on every `migrate-layout` run since `6676617`; the app now pays the
same bounded cost, not a new one.

### Fixtures, proven against the defect first (`ENGINEERING_STANDARD.md` §4)

`test_migrate_preview_routes_a_camera_photo_by_its_own_evidence`
(`packages/truestill-app/tests/test_settings_http.py`) seeds two `Camera`-labelled files with
opposite evidence in one fixture: `resolvable` carries metadata a faked `read_metadata` returns
as the device rule (the same technique `test_rederivation_degrades_instead_of_failing_when_
exiftool_is_missing` already uses to control `rederive_rules` deterministically); `unresolvable`
has none. **Confirmed failing against the pre-fix code first** (`git stash` on `service.py`
alone): the resolvable file reproduced §13.6's exact result,
`Camera/2023/2023-08/2023-08-20 - Goa Trip/resolvable.jpg` instead of the timeline. After
restoring the fix: `resolvable` lands at `2023/2023-08/2023-08-20 - Goa Trip/resolvable.jpg` (the
timeline, under its named event, exactly as organize would place it) and `unresolvable` still
lands at `Camera/2023/2023-08/unresolvable.jpg` (the conservative default, correctly preserved
for a label re-derivation genuinely cannot resolve).

**`test_migrate_preview_lists_moves` needed no change and was left exactly as it was.** Checked
first: its file is a dummy byte string with no real capture metadata at all, so `rederive_rules`
cannot resolve it either before or after this fix - it is the "genuinely unplaced photo" case the
task asked to distinguish, not the bug. Its own comment already said so ("no camera evidence ->
side bin"); it still does, and it still passes unchanged.

**Not in scope, unchanged by this fix:** the app still has no UI for a label re-derivation
*cannot* resolve (option 2 from §13.6's list) - it silently keeps the conservative side-bin
default there, identically to the CLI absent an interactive prompt. That remains a separate,
smaller gap, not addressed here.

`make check` (483 tests, ruff/mypy/dash-check) green. 13.0's table entry above and
`PROJECT_STATUS.md` §2.1 both record this as resolved.

---

## 14. Stage 3.2 - largest-first review and one small-event disclosure

**BUILT 2026-07-29.** Proposal presentation now follows the correction cost: the largest groups
come first, because overlooking a 2,057-photo trip costs more than overlooking an 8-photo burst.
`ReviewCard.count` is the single count seam and `order_review_cards` applies one descending sort
after detection and after every merge or split.

**Small is derived from the configured floor, not a fixed photo count.** The first implementation
used two doublings (`count < 4 * min_files`), but review rejected it: at the default 8 it hid
everything below 32, including the unverified secondary-survey claim's 23-photo average. That
inverted the intent by treating a typical memory as noise. The retained rule is the **first
doubling**, `count < 2 * min_files`: default 8 hides threshold-adjacent 8-15-photo events and keeps
23 visible. A detected event already meets the lower floor; a manually split event may fall below
it and remains small. The rule still scales when a heavy shooter raises the floor. A card backed
by `TripProposal` is never eligible, even if a split has reduced it to one day and its display
label therefore says EVENT.

All eligible events sit behind **one** disclosure. Its summary carries the number of groups,
minimum and maximum photo counts, and the full date span, so opening it is optional rather than
required to understand what was hidden. There is no second collapsed tier. Split remains the
per-card correction; the existing merge checkbox stays small and the global Merge checked action
uses the existing ghost-button style, visually below Split without inventing another control.

**Reuse and boundaries:** the existing `ReviewCard` and session card list remain authoritative;
there is no second proposal model or persistence path. `ReviewCardPayload` and the collapsed
summary are typed API payloads. No dependency was added.

**Complexity:** ordering is `O(P log P)` time and `O(P)` output space for `P` proposal cards.
Collapse classification and summary are each `O(P)` time; the summary stores only scalar
aggregates. No catalog setting is re-read and no work is performed per media file.

**Fixtures:** the existing HTTP fixture first reproduced date ordering (`[8, 10]` instead of
`[10, 8]`). The presentation fixture now pins the corrected exclusive boundary (15 hidden,
16 shown), keeps 23 visible, and proves trip immunity. Before the correction it failed directly:
`small_event_limit(8)` was 32 rather than 16. The earlier mutation replacing the exclusive,
event-only rule with inclusive count-only logic also failed by hiding the boundary and a trip.

## 15. Stage 3.3 - active-day duration and kind-preserving results

**BUILT 2026-07-29.** The reported "3 days" on a Sep 13-16 proposal was not an off-by-one error:
the proposal carries three active dates (Sep 13, 15 and 16) across four inclusive calendar dates.
The count was correct but the label was ambiguous. `ReviewCardPayload.active_days` now carries
the explicit typed count and the card says **3 active days**, while the visible Sep 13 -> Sep 16
span continues to show the calendar extent.

The screen's completion seam also stopped calling every applied group a trip. Named day-events
and multi-day trips had both been appended under the backend key `trips`, and the frontend helper
was consequently named `tripResultCards` even though it rendered both. The typed
`AppliedReviewGroupPayload.kind` now survives through the job result as `groups`; each completion
row renders EVENT or TRIP from that value. Proposal badges, name placeholders, named counts,
move-preview copy and completion copy now use the same two nouns.

**Reuse and complexity:** active-day count reuses the proposal's existing `days` mapping; no
calendar walk or second count was added. Computing `len(days)` is `O(1)`. Kind is already known
when each result row is assembled and adds `O(1)` time and space per named result. Detection,
catalog I/O and layout are unchanged; no dependency was added.

**Fixtures:** the exact Sep 13/15/16 bridge is pinned over HTTP as start Sep 13, end Sep 16,
three active days. The shipped-copy guard failed first on the old
`plural(c.days.length, "day")` text. Completion fixtures pin EVENT and TRIP independently;
mutating a trip result's kind to EVENT failed with the expected `event != trip`.
