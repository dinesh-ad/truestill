# Event clustering: why the current rule is inverted, and what replaces it

Status: **Design deliverable, awaiting approval. No code changed.** This document is the review
gate for item 4.5, which is sequenced before backlog `(gg)` because `(gg)` partitions on
evented-vs-un-evented and therefore needs the evented set to be right first.

---

## 1. The defect

`events._boundary_after` cuts where a gap exceeds the **median of its ±10 neighbours by 4.0 in
log-seconds**. Nothing else. A segment then survives only if it has ≥ 8 files **and** spans
≥ 2 hours.

Because the threshold is *purely relative to local density*, it behaves **inversely at both
extremes**. Measured on the real 2,238-file camera library:

| Day | Photos | Span | Median gap | A cut therefore needs |
|---|---|---|---|---|
| 2014-08-14 | 31 | 2.7 h | 27.5 s | > 25.9 min |
| 2014-08-15 | 635 | 17.4 h | 10.0 s | > 10.0 min |
| 2014-08-16 | 737 | 20.0 h | 10.0 s | > 10.0 min |
| 2014-08-17 | 654 | 15.5 h | 7.0 s | **> 7.3 min** |

A steadily-shot day gets cut every few minutes and shatters into fragments, almost all of which
then fail the 2-hour span filter. The whole library produced **4 clusters**, three of them
2-hour shards of 08-15/08-16 — and one of them this:

```
2014-08-19 00:00 -> 2024-03-24 12:45   n=11   span=49,068 h
```

**A 5.6-year "event" of 11 photos.** In that tail the median gap is 109 days, so a cut would
need a gap of *years*. Sparse data never splits; dense data always does.

**Why 08-15 and 08-16 were offered and 08-14 and 08-17 were not** is therefore not a rule anyone
would recognise: all four days clear `min_files` easily, and the difference is only whether some
fragment happened to survive 2 hours uncut. It is luck of internal rhythm, not a judgement about
events.

## 2. The generalisable lesson

**A threshold defined relative to local density is inverted at both extremes**, and the failure
is symmetric: what is "unusually large" in a burst is ordinary in a sparse tail, and vice versa.
Any purely relative rule has this shape.

**The synthetic fixtures validated it precisely because they lacked real density variation.**
`scripts/tune_events.py` generates scenarios with roughly uniform intra-event spacing, which is
the one condition under which a relative threshold is well-behaved. The tuning note — "4.0 is
the lowest value that keeps a multi-day trip whole" — is *true on those fixtures* and wrong on a
real library. The fixture was not too small; it was the wrong **shape**.

This is why §4 of the build plan adds fixtures derived from real density profiles: a regression
test for this class has to vary density, not volume.

## 3. The proposed rule

Four changes. The relative test is **kept** — it is what recognises a natural break — and simply
stops being the *only* thing that decides.

**(a) Absolute floor.** A cut requires the gap to beat the local median **and** be at least
`MIN_BOUNDARY_GAP`. A boundary shorter than a coffee break is not a boundary.

**(b) Hard cap on the GAP.** Any gap beyond `MAX_WITHIN_EVENT_GAP` cuts unconditionally,
regardless of local median. **The cap is on the gap, never on the segment span** — capping span
would chop a genuine two-week trip, whose internal gaps are hours. This is what kills the
5.6-year class.

**(c) Remove `min_duration_s`.** A 45-minute birthday with 60 photos is a real event and is
currently unofferable at any sensitivity. `min_files` does the useful work.

**(d) Keep the GPS-jump cut**, unchanged: a >50 km relocation is real evidence.

### Parameters, chosen from a sweep on the real library

| floor | clusters | 08-14 | 08-15 | 08-16 | 08-17 | longest |
|---|---|---|---|---|---|---|
| none | 39 | 2 | 10 | 6 | 12 | 2.2 h |
| 30 min | 24 | 2 | 6 | 2 | 7 | 5.8 h |
| **60 min** | **15** | **2** | **2** | **2** | **3** | **11.8 h** |
| 90 min | 12 | 1 | 1 | 1 | 3 | 18.2 h |

**Recommended: `MIN_BOUNDARY_GAP = 60 min`.** Below it, days still shatter (30 min leaves 08-17
in seven pieces); above it, distinct outings merge (90 min collapses 08-15's morning and evening
into one). 60 keeps a day as two or three recognisable outings, which is what those days
actually were.

**Recommended: `MAX_WITHIN_EVENT_GAP = 48 h.** The sweep shows 24/36/48 h are *identical* on this
library — no real gap falls between them — so the value is chosen on principle rather than fit:
48 h lets a trip survive a full quiet day (a travel day, a rained-out day) without splitting,
which matches the forum consensus that multi-day trips stay whole. Isolating it confirms it is
load-bearing:

```
floor only    : 16 clusters, longest span  49,068.8 h
floor + cap   : 15 clusters, longest span      11.8 h
```

`min_files` stays **8**. Raising it to 15 drops 2014-08-14 (31 photos) entirely, and a 31-photo
evening is an event.

## 4. What the rule proposes for the real library — **for Dinesh to check**

This is the ground truth that matters: these should correspond to things that actually happened.

```
2014-08-15 07:34 -> 19:21   n=618   11.8h
2014-08-17 06:25 -> 15:57   n=594    9.5h
2014-08-16 09:27 -> 15:18   n=565    5.8h
2014-08-16 16:46 -> 20:01   n=157    3.3h
2013-09-30 11:49 -> 13:09   n=59     1.3h
2014-08-17 18:54 -> 20:11   n=42     1.3h
2014-01-05 18:12 -> 20:44   n=30     2.5h
2014-08-14 19:46 -> 21:22   n=23     1.6h
2013-09-16 18:12 -> 18:58   n=19     0.8h
2013-09-13 17:45 -> 18:02   n=18     0.3h
2014-08-17 21:45 -> 21:53   n=15     0.1h
2013-09-15 19:48 -> 20:12   n=13     0.4h
2014-08-15 20:27 -> 21:52   n=13     1.4h
2013-09-21 14:14 -> 14:41   n=8      0.4h
2014-08-14 22:22 -> 22:25   n=8      0.0h
```

**All four August days now appear**, as mornings/afternoons/evenings rather than arbitrary
2-hour shards, and the 5.6-year cluster is gone.

**Two judgement calls to confirm:** the last two entries (8 photos over 0.0 h and 0.4 h) are
bursts, not outings. They are offered because `min_files = 8` with no duration filter. Options
if they are noise: raise `min_files` to ~10-12, or reinstate a *small* duration floor (~10 min)
purely to exclude single bursts — deliberately not 2 hours. **I would leave them**: they are
*proposals* a user names or skips, and a burst that is genuinely a moment is cheap to skip and
expensive to have missed.

## 5. Complexity

Unchanged and linear. One sort (`O(n log n)`), one pass computing gaps, one pass over gaps with
a **fixed ±10 window** for the local median, one pass forming segments: **O(n)** after the sort,
with `O(window)` work per gap where window is a constant. The floor and cap are two scalar
comparisons per gap and add nothing asymptotically. No I/O.

## 6. Build plan, on approval

1. `MIN_BOUNDARY_GAP` and `MAX_WITHIN_EVENT_GAP` as named constants with the reasoning above;
   `min_duration_s` removed.
2. **Real-data-shaped fixtures**: density profiles derived from the actual library — a dense
   700-photo day, a sparse multi-year tail, a 45-minute burst — so this class of failure cannot
   pass again. Regression tests assert the *shape* (a dense day is not shattered; a sparse tail
   is not one event), not exact counts.
3. Both `min_duration_s` settings tested, per the ruling, so removing it is evidenced rather
   than assumed.
4. Re-run against the real library and diff against §4 before and after.

**Not doing without a separate decision:** changing `sensitivity` (4.0) or the `window` (10).
The sweep shows the floor and cap do the work; touching the relative test as well would make it
impossible to attribute any change.
