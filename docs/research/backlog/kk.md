# (kk) Persist GPS at ingest - THE CAPTURE HALF SHIPPED AT v17; `GPSDateStamp` did not.

*⚠ Retitled 2026-08-29. The old title, "it is read and then thrown away", was corrected inside this body on 2026-08-09 and outlived the correction by twenty days.*

*Body of backlog entry `(kk)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(kk) Persist GPS at ingest - THE CAPTURE HALF SHIPPED AT v17; `GPSDateStamp` did not.** Found while designing trip
  grouping (`trip-grouping-research.md` §5), and the scope is much wider than trips.
  - ✅ **CORRECTED 2026-08-09: THE CAPTURE HALF SHIPPED AT v17 AND THIS ENTRY WAS WRONG.**
    Traced end to end rather than assumed: `exif.py:72-73` requests `GPSLatitude`/`GPSLongitude`,
    `models.py:477` (`CaptureContext.from_metadata`) converts them, `catalog.py` writes
    `files.gps_latitude`/`gps_longitude`. Measured on the real catalog: of 395 files ingested
    after v17, **388 carry a camera and 138 carry coordinates**; the 2,300 ingested before it
    carry neither, because v17 deliberately does no backfill. `GPSDateStamp` is still not stored.
  - ⚠ **The paragraph below is the ORIGINAL 2026-07-31 finding and was true when written.** It is
    kept rather than edited because a record that is rewritten to stay correct stops being one -
    but read the correction above first: the catalog has had the columns since v17.
    Verified 2026-07-31: the catalog has **no latitude/longitude columns and no `GPSDateStamp`**.
    `(kk)` was split by ruling - the **`GPSDateStamp`** half belonged to the date-provenance
    program (as the cross-check for a suspect dead-clock date), the lat/lon half serves
    places/map and is separate. **The date-provenance program completed 2026-07-31 without the
    `GPSDateStamp` half**, so this is not "the rest of a mostly-done item": both halves are
    unstarted, and a reader should not have to infer that from the program's closure notes.
  - **The defect.** GPS is read live from exiftool during an organize run and used for the
    event-clustering jump cut (`event_review.py:80` builds `EventItem.gps`), and then it is
    **never written to the catalog**. `files` has no latitude/longitude column at all, and
    `camera_copies_for_events` selects `sha256, captured_at` and nothing else. The data is
    obtained, used once, and discarded.
  - **WHAT THIS MAINTAINER'S LIBRARY SAYS, AND WHAT IT DOES NOT.** Measured 2026-08-09 with
    exiftool over the real 2013-2014 source: **83 of 2,275 files carry GPS - 3.6%** - and they
    come from **one phone out of nine**. The Lumia 820 geotagged 83 of its 114 photos; the P780,
    the Canon IXY, the C5502, the Nexus 5 and four others recorded none at all. Location was off
    by default on that generation.
    **That is a fact about his files and not about the product.** A user arriving today with any
    modern phone has coordinates on nearly every photo, and for them GPS is not a 3.6% signal but
    the **primary** one - and the only naming evidence available to someone whose folders are all
    `DCIM`, which is most people and exactly the user the folder-name suggester has nothing to
    offer. A measurement of one library is a test bed, never a specification.
  - **PRODUCT-LEVEL CAUTION THAT DOES GENERALISE: dense-urban lookup is where this fails.** Both
    measured sets collapse into a handful of ~1.1 km buckets in one metro area - 4 buckets for
    the 83 source points, 7 for the 138 in the catalog. Offline reverse geocoding from GeoNames
    `cities500` gives each place a **single centre point**, so a lookup in a dense area is
    nearest-point and often wrong: Immich issue #8941 (neighbourhoods classified as cities) and
    discussion #12641 (one town's coordinates 12 km out; a 7,000-person district absent from
    `cities500` entirely) are real users hitting exactly this, open since April 2024. Taking the
    **modal place across a whole cluster** rather than tagging one photo is a genuinely safer
    design than theirs - but only if clusters have coordinates.
  - ✅ **CORRECTED 2026-08-10: THE BLOCKER BELOW IS TRUE OF THE INTEGRATION AND FALSE OF THE
    LOOKUP.** Reverse geocoding is a **pure function** - coordinates in, place name out - and is
    testable with a table of known coordinates and **no photos at all**. What needs clusters is
    taking a *modal place across a cluster*; that half is still blocked exactly as described.
    Conflating the two is what made this read as unbuildable. Measured the same day against a
    16-point fixture (Tamil Nadu across scale, a district, four continents, two adversarial
    points), all five GeoNames tiers, licence CC BY 4.0 throughout:
    - **The village case is a tier problem, not a GeoNames problem.** `cities500` misses every
      village under its threshold and answers with a neighbour 2-6 km away; `allCountries`
      filtered to class P (5,220,666 entries) returns `Mūngittoluvu` and `Ūrmenalagiyan` at
      **0 km**. On the 14 non-adversarial points, `cities500` scored 6 exact / 7 right-region /
      1 wrong; class-P scored 5 exact / 9 right-region / **0 wrong**.
    - **But class P is worse where it matters most**, and this is the finding: it answers Chennai
      with `Vepery` (a neighbourhood, population 0) and Paris with an arrondissement. More
      entries buys villages and loses cities, unless lookups are ranked by feature code and
      population - which is exactly what HoudahGeo does and what Immich issue #8941 is about.
    - ⚠ **`Wayanad` does not exist as a populated place.** One row in the whole dump, feature
      class **A** (`ADM2`), population 817,420. Every reverse geocoder filters to class P, so a
      district name is unreachable by construction. This is the motivating case and no tier fixes
      it; it needs admin polygons, which is a different dataset and a different problem.
    - **The name-form question is answered and it is not blocking.** The lookup returns the
      canonical long form (`Tiruchirappalli`, `South`), and `North` / `Tanjore` are both
      present in the `alternatenames` column **already inside the tier files** - 81.7% of
      `cities500` rows carry it. The separate `alternateNamesV2.zip` is 193 MB and is **not
      needed** for this. So a subtraction rule can fire on either form.
    - **Cost is not a constraint.** 150,000 lookups is 0.25 s on `cities500` and 0.39 s on
      class P; the index build is the whole cost (0.5 s versus 10.8 s).
    - ⚠ **Class P breached the 1 GB memory ceiling in this naive form: 1,682 MB peak RSS** to
      hold 5.2M points and a KD-tree, against 145 MB for `cities500`. Any use of it needs a
      packed on-disk index rather than "load it all", and that is a build, not a download.
    **Full record: `reverse-geocoding-research.md`** - tiers, accuracy, name forms, licence,
    and the two questions the design must answer. Nothing committed, no dependency added.
  - ✅ **P34, 2026-08-10: THE DISTRICT IS REACHABLE AS AN ATTRIBUTE, NOT AS A LOOKUP TARGET.**
    The maintainer's hypothesis, verified: every class-P row carries `admin1_code` and
    `admin2_code`, and the nearest populated place to the Wayanad fixture point (`Polacchikuni`,
    0.6 km) has **admin2 = `Wayanad`**. So the motivating case is solved by a **join**, not by a
    bigger dataset - `admin1CodesASCII.txt` (0.14 MB) and `admin2Codes.txt` (2.26 MB), 2.4 MB
    total. Measured with a streaming bounding-box filter at **38.7 MB peak RSS**, against the
    1,683 MB the full class-P load cost.
    - **Coverage:** admin1 on 100.0% of class-P rows, admin2 on **80.7%** globally but 98-99.5%
      for India, France, Japan, Australia and Brazil. Two of fourteen fixture points still came
      back with a **blank** admin2 - Tokyo and Oodnadatta - so a join cannot be assumed to
      resolve and needs a defined answer when it does not.
    - ⚠ **The name forms are the weak half, and the subtraction idea depends on them.** Of the
      eight district forms checked, six are reachable but **only via the admin2 entry's
      `alternatenames`, which `admin2Codes.txt` does not carry** - it has four columns and no
      alternates, so reaching them means joining its geonameid back into the 400 MB
      `allCountries.txt`. Raw, the file offers `Thoothukkudi` (not Thoothukudi), `Tiruppur` (not
      Tirupur), `Kanniyakumari` (not Kanyakumari), `Rāmanāthapuram` with diacritics, and 1,988 of
      47,549 names carrying a redundant `" district"` suffix. `Tirupur` is not among its
      alternates at all.
    - ⚠ **The admin names are not uniformly current, in BOTH directions, within one state.**
      `IN.25.628` is still `Tirunelveli Kattabo` - a form retired in 1997 - while `IN.25.733`
      `Tenkasi district` reflects a 2019 split. France's `FR.84` is still `Rhône-Alpes`, merged
      into Auvergne-Rhône-Alpes in 2016.
    - 📌 **And the finding neither of us anticipated: the era problem.** The Oormelalagiyan point
      returns **Tenkasi**, which is administratively correct *today* and was **Tirunelveli when a
      2013 photo was taken there**. Labelling an old photo with a current district is an
      anachronism the user may reasonably call wrong, and no dataset choice avoids it - the
      boundary moved, not the data. Any design has to decide whether a place name describes
      **where the camera was** or **what that ground is called now**, and say which.
  - **THE REAL BLOCKER: it cannot be BUILT next because it cannot be TESTED here.** *(Read the
    correction above first - this is true of the cluster integration only.)* The catalog
    holds **zero events**, so there is no cluster to take a modal place across, and the 138 points
    that exist sit in one metro area. Building against fixtures we invent is how the junk
    classifier came to be written and never once fired. §4's rule is that a fixture modelled on
    the current library inherits its blind spots; the inverse applies here - **a fixture modelled
    on nothing inherits nothing.**
  - **The cheap unblock, the maintainer's to provide:** a few dozen photos from a current phone
    with location on, taken in two or three different places. That makes the whole thing testable
    at once, including whether non-Western place names come back usably from `cities500`.
  - **Why it matters beyond trips.** A places / map view is a **high user expectation** in
    `org-structure-research.md`, and it is unbuildable without stored coordinates. The trip-edge
    case is only the symptom that exposed it: an arrival evening 80 km from home is trivially
    distinguishable from an evening at home, and truestill had that fact in memory and dropped it.
  - **It is permanently lost for already-organised libraries.** Every library placed before this
    lands has no stored GPS, and recovering it means re-reading every file. **We already pay the
    read cost** on every run - this is a column, not a pass.
  - **Scope:** persist latitude/longitude at ingest; persist `GPSDateStamp` alongside, since
    `date-layering-gap-check.md` §4(b) already ruled it the cross-check for a suspect dead-clock
    date and it is the same exiftool read. **`GPSDateStamp` is part of the date-provenance
    program** with `(n)` / `(ii)` / `(bbb)` recovery (see **Converged programs**) - the lat/lon
    columns also unlock places/map views, which are a separate product surface on the same write.
  - **Open question, deliberately not answered here:** whether existing libraries get a backfill
    pass. It is a re-read of the whole library, so it is opt-in work with a real cost, and it
    wants its own decision rather than being smuggled in with the column.
