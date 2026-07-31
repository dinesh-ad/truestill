# Adaptive day-folder threshold for Everyday photos (backlog gg)

Status: **built 2026-07-30** (default threshold **40**). This document records the
research behind that default and the placement rules the implementation follows.

The soak finding: a heavy un-evented day (the maintainer's 2014-08 Everyday bucket held 2,057 photos)
drowns the monthly `{yyyy}-{mm} - Everyday` folder - the problem the year-first layout was
meant to solve one level up.

---

## 1. The rule

Un-evented timeline photos on a capture day whose **un-evented count** exceeds a threshold get
their own folder:

```
{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd} - Everyday
```

Days under the threshold stay in the monthly bucket:

```
{yyyy}/{yyyy}-{mm}/{yyyy}-{mm} - Everyday
```

Events are unaffected. On a day that has both a named event and un-evented leftovers, the
leftovers never mix into the event folder: they take the day folder if over threshold, else the
month bucket. Trip-claimed days never enter this branch (`classify` returns `TRIP_DAY` first).

Mechanically this is a third `Placement` on the `LayoutScheme` seam (`DAY_BUCKET`), chosen by
route-then-render - never a conditional inside the template DSL
(`trip-grouping-research.md` §7 already named the member).

---

## 2. Why peers do not supply the default

Surveyed products choose a **fixed** folder shape; none adapt by day count:

| Product | Default habit | Adaptive by count? |
|---|---|---|
| PhotoPrism | year/month; day folders via external rename + reindex | No |
| Immich | storage template; documented default is year / year-month-day | No |
| digiKam | optional date-based sub-albums for all same-date images | No |

The default therefore cannot be copied from a peer constant. It has to come from how many
photos a typical person produces, with the constraint that the monthly Everyday bucket remains
the **common** case for an average library - not tuned to a 600+/day shooter.

Sources for the peer survey:

- [PhotoPrism discussion #3357](https://github.com/photoprism/photoprism/discussions/3357)
- [Immich storage template docs](https://docs.immich.app/administration/storage-template)
- [digiKam advanced import](https://docs.digikam.org/en/import_tools/advanced_import.html)

---

## 3. Survey anchors for the number

**Mean daily take ≈ 20.** Photutorial / Matic Broz figures reported for 2024: the average person
in the US takes about 20 photos a day
([Letem svetem Applem summary](https://www.letemsvetemapplem.eu/en/2024/04/19/v-letosnim-roce-bude-94-vsech-fotografii-porizeno-pomoci-smartphonu-v-usa-prumerne-vyfoti-clovek-20-fotek-denne/)).

**Mean photos per named occasion ≈ 23.** OnePoll survey for Mixbook, random double-opt-in of
**2,000** US adults, 15-16 August 2023: respondents take nearly 23 pictures per occasion at
graduations, weddings, vacations and sporting events
([Talker News](https://talker.news/2023/10/09/average-american-takes-this-many-photos-per-day/),
[StudyFinds](https://studyfinds.org/taking-pictures-camera-roll/)).

This is the same "~23" figure that `events-clustering-research.md` §3 once carried as an
unverified secondary claim. Attribution is now recorded; the mean alone still does not imply a
distribution (half below 23 is not established). Event `min_files = 8` remains justified by the
measured library, not by this survey.

**BACKLOG candidate band:** 30-50 / day, to validate rather than invent (`BACKLOG.md` `(gg)`).

---

## 4. Default: 40

Approved 2026-07-30.

- Above mean daily (~20) and mean occasion (~23), so a normal phone day does not earn a day
  folder.
- Inside the recorded 30-50 band.
- Roughly ~2× mean occasion - clear of typical occasion size without pretending the parallel to
  `2 * min_files` is a theorem.
- A 600+/day or 2,057-photo Everyday dump clears any value in the band; the default is for the
  average library. The setting stays editable.

Catalog key: `layout.everyday_day_threshold`. Missing / invalid → 40.

---

## 5. Determinism and reconcile

**When evaluated:** once per file at placement time (organize preview/run and migrate plan),
through the shared `classify` → template → render seam. Not on browse or settings save alone.

**Count set:** un-evented, timeline-rule files for that capture calendar day from
**(catalog already placed ∪ this run's planned un-evented members)**. Event members and
trip-claimed days are excluded.

**Later imports can change a day's deserved folder.** New organize runs place *new* files under
the current classification; already-placed files stay until a migrate reconciles.

**Reconcile is both directions:** month→day when over threshold; day→month when under.
`migrate-layout` / Settings migrate re-classifies with current counts.

**Never-silent on reconcile:** the preview must state the reason **per affected day**, e.g.
"2014-08-17 now has 47 photos, over your threshold of 40 - moving to its own day folder" and
the reverse under-threshold coalesce. A bare move list is not enough - the user did not
directly request this placement change.

**Gate:** preview, then typed `move` on apply. The CLI already requires it; the app Settings
migrate path must use the same `typedConfirm` helper (closing the one-click gap is in scope for
this work, not deferred).

**Settings warning:** changing the threshold must warn that existing files do not move until a
migrate is run - the same forward/reconcile split already used for layout template changes. A
setting that silently only affects future files reintroduces the split-era problem.

---

## 6. Router shape

```text
SIDE_BIN → TRIP_DAY → EVENT_DAY → DAY_BUCKET | EVERYDAY
```

`RenderContext` carries a pure `heavy_day: bool` set by the caller after the day-count pass.
`LayoutScheme.of` gains `Placement.DAY_BUCKET`; `assert_never` fails the build if a new member
is added without a template.

Day-bucket template (product shape, not a user DSL branch):

```text
{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd} - Everyday
```
