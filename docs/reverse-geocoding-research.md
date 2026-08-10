# Reverse geocoding: what the offline datasets actually answer

> **MEASUREMENT RECORD, 2026-08-10. Nothing is built and nothing is recommended.**
>
> This exists so the next person does not re-measure it. Every number below was taken on this
> machine on this date against a 16-point fixture with stated provenance; the datasets are
> versioned by download date and will drift. Where a conclusion is an inference rather than a
> measurement it says so.
>
> **Two things it deliberately does not do:** choose a tier, and propose a design. The measured
> facts rule some options out on their own, and the remaining choice depends on decisions nobody
> has made yet - both are recorded at the end as *questions the design must answer*.

Raised by `(kk)`. The trigger was a correction: `(kk)` said GPS "cannot be BUILT next because it
cannot be TESTED here". That is true of taking a **modal place across a cluster** - the catalog
holds zero events - and false of the lookup, which is a **pure function**: coordinates in, place
name out, testable with a table of known coordinates and **no photos at all**. Conflating the two
made the whole item read as unbuildable for nine days.

---

## 1. The fixture

Sixteen points, each carrying its provenance, because a fixture whose truth came from the dataset
under test measures nothing.

* **MAINTAINER** - five Tamil Nadu villages with Census of India 2011 populations and
  coordinates, supplied independently of GeoNames: Mappilaiurani (Thoothukudi, 26,802),
  Moongiltholuvu (Tirupur, 3,030), Oormelalagiyan (Tirunelveli), Vellicode (Kanyakumari),
  Wooster Nagar.
* **PUBLISHED** - widely-published centroids: Chennai, Tiruchirappalli, Thanjavur, Wayanad
  (district), Paris, Rochefourchat (a near-empty French commune), Tokyo, São Paulo, Oodnadatta.
  *Caveat stated rather than glossed:* GeoNames and Wikipedia cross-pollinate for large cities,
  so agreement on a metro proves less than agreement on a village.
* **CONSTRUCTED** - two adversarial points with no correct answer: mid-North-Atlantic
  (35.0N 40.0W) and the Sahara interior (23.5N 12.5E). The measurement there is the *distance*.

Nearest neighbour is computed on the **unit sphere** with a KD-tree. A Euclidean metric over
degrees is wrong everywhere but the equator, and every Indian point sits at 8-13N where a degree
of longitude is ~2% shorter than a degree of latitude - getting that wrong would bias every
Indian result in one direction and read as a dataset fault.

## 2. The tiers

All five GeoNames tiers, downloaded 2026-08-10. `allCountries` filtered to feature class P
(populated places) yields **5,220,666** of its 13,455,006 rows.

| tier | entries | download | on disk | load | index build | peak RSS | per lookup |
|---|---:|---:|---:|---:|---:|---:|---:|
| cities15000 | 34,080 | 3.2 MB | 8.0 MB | 0.08 s | 0.01 s | 78 MB | 1.02 µs |
| cities5000 | 69,585 | 5.3 MB | 14.3 MB | 0.14 s | 0.02 s | 90 MB | 1.49 µs |
| cities1000 | 170,603 | 10.2 MB | 29.6 MB | 0.31 s | 0.06 s | 124 MB | 1.30 µs |
| cities500 | 235,206 | 12.9 MB | 38.8 MB | 0.42 s | 0.09 s | 145 MB | 1.64 µs |
| **allCountries class P** | **5,220,666** | 400.5 MB | 634.9 MB | 8.20 s | 2.63 s | **1,683 MB** | 2.57 µs |

⚠ **Class P breaches this repo's 1 GB working ceiling at 1,683 MB peak RSS**, in the naive
"load it all and build a tree" form measured here. That rules it out on memory before any
accuracy argument. A packed on-disk index would change the number, and that is a build rather
than a download - it has not been costed.

**Lookup cost is not a constraint at any tier.** 150,000 photos costs 0.25 s on `cities500` and
0.39 s on class P. The index build is the entire cost: 0.51 s against 10.83 s.

## 3. Accuracy, and the trade nobody escapes

Fourteen non-adversarial points:

| tier | exact | right region, wrong place | wrong |
|---|---:|---:|---:|
| cities15000 | 6 | 6 | 2 |
| cities5000 | 6 | 7 | 1 |
| cities1000 | 6 | 7 | 1 |
| cities500 | 6 | 7 | 1 |
| allCountries class P | 5 | 9 | **0** |

**More entries buys villages and loses cities.** Class P is the only tier that answers the
villages - `Mūngittoluvu` and `Ūrmenalagiyan` at **0 km**, where `cities500` offers a neighbour
2-6 km away - and Rochefourchat improves monotonically with tier size (39 → 23 → 16 → 9 → **0
km**). But class P answers **Chennai with `Vepery`**, a neighbourhood with population 0, and
**Paris with an arrondissement**.

**Neither end is correct without ranking by feature code and population.** That is what HoudahGeo
does with a 30 MB offline dataset, and it is what Immich issue #8941 (neighbourhoods classified
as cities) is about. **We have not costed it.** It is the obvious next measurement and it was not
taken.

## 4. Wayanad: unreachable as a place, reachable as an attribute

**`Wayanad` does not exist as a populated place.** One row in the entire 13.4M-row dump: feature
class **A**, code `ADM2`, population 817,420. Every reverse geocoder filters to class P, so a
district name is unreachable **by construction** - and no tier fixes it, because the problem is
the feature class and not the size.

**The rescue, verified.** Every class-P row carries `admin1_code` and `admin2_code`. The nearest
populated place to the Wayanad point - `Polacchikuni`, 0.6 km - has **`admin2 = Wayanad`**. So the
district is an attribute of the nearest place rather than a lookup target, joined through
`admin1CodesASCII.txt` (0.14 MB) and `admin2Codes.txt` (2.26 MB): **2.4 MB total**. Measured with
a streaming bounding-box filter at **38.7 MB peak RSS**.

Every Tamil Nadu point resolved to its correct district. **But:**

* **Coverage is not total.** admin1 is present on 100.0% of class-P rows; admin2 on **80.7%**
  globally, 98-99.5% for India, France, Japan, Australia and Brazil. **Two of fourteen fixture
  points returned a blank admin2** - Tokyo and Oodnadatta. The join cannot be assumed to resolve
  and needs a defined answer when it does not.

## 5. The name forms, plainly

This decides whether a subtraction rule (strip the place name a folder already implies) can ever
fire, and it is separate from whether the lookup is correct.

**For settlements it is solved and costs nothing extra.** The lookup returns the canonical long
form - `Tiruchirappalli`, `Thanjavur` - and `Trichy` and `Tanjore` are both present in the
`alternatenames` column **already inside the tier files**, populated on 81.7% of `cities500` rows
(50 and 66 alternates respectively). The separate `alternateNamesV2.zip` is **193 MB** and is
**not needed** for this.

**For districts it is the weak half.** Six of eight human forms are reachable, but **only through
the admin2 entry's `alternatenames`, which `admin2Codes.txt` does not carry** - it has four
columns and no alternates - so reaching them means joining its geonameid back into the **400 MB
`allCountries.txt`**: the file the 2.4 MB join existed to avoid. Raw, the admin2 file says:

| what a person types | what the file says | reachable via alternates? |
|---|---|---|
| Thoothukudi | `Thoothukkudi` | yes |
| Tirupur | `Tiruppur` | **no - absent entirely** |
| Kanyakumari | `Kanniyakumari` | yes |
| Chengalpattu | `Chengalpattu district` | yes |
| Tirunelveli | `Tenkasi district` | **no - see §7** |
| Wayanad | `Wayanad` | yes |

Plus **1,988 of 47,549** admin2 names carry a redundant `" district"` suffix, and **12,994**
contain diacritics (`Rāmanāthapuram`, `Drôme`), so any matching needs normalisation.

**The names are not uniformly current, in both directions, inside one state.** `IN.25.628` is
still `Tirunelveli Kattabo`, a form retired in 1997, while `IN.25.733` `Tenkasi district` reflects
a 2019 split. France's `FR.84` is still `Rhône-Alpes`, merged into Auvergne-Rhône-Alpes in 2016.

## 6. Licence

**CC BY 4.0 for every GeoNames dump**, one licence across all tiers and the admin files
(`readme.txt`, retrieved 2026-08-10). Attribution required. Commercial redistribution permitted.
Supplied **"as is" without warranty or any representation of accuracy, timeliness or
completeness** - which matters for a product making a claim about where a photo was taken.

## 7. What the design must answer

Recorded as open questions rather than limitations, because each changes what gets built.

### 7.1 A refusal distance

**A nearest-neighbour lookup returns an answer at any distance, and nothing says "nothing".**

| point | tier | answer | distance |
|---|---|---|---:|
| open sea, N Atlantic | cities500 | `Lajes das Flores` | **920 km** |
| open sea, N Atlantic | class P | `Lajedo` | 916 km |
| Sahara interior | cities500 | `Al Qaţrūn` | 271 km |
| Sahara interior | class P | `Anāy` | 128 km |

A photo from a boat, a plane, or empty desert would be confidently labelled with a place
hundreds of kilometres away. **This is a shippable defect, not a curiosity.** Any design needs a
distance beyond which the answer is *nothing*, and that threshold is a product decision: it
trades silence against confident error, and the right number differs between a metro and a
desert.

### 7.2 The anachronism, and it outranks the rest

**Oormelalagiyan returns `Tenkasi`** - administratively correct today, and **`Tirunelveli` when a
2013 photo was taken there.** Tenkasi was carved out of Tirunelveli in 2019; both districts exist
in the file. `Rhône-Alpes` merged in 2016. **The boundary moved, not the data**, so no dataset
choice and no tier avoids this.

It matters here more than it would elsewhere. **Truestill is built on the premise that a capture
date is a fact about the past** - dates are never guessed, mtime is never trusted, `Undated/`
exists rather than an invented year. A place name that silently describes the **present** sits in
the same folder name as a date that describes the **past**, and contradicts it.

> **The design must answer whether a place name means WHERE THE CAMERA WAS or WHAT THAT GROUND IS
> CALLED NOW - and say which on screen.** Both are defensible. Neither is defensible unstated,
> because the user cannot tell them apart from the folder name and will assume the first.

Answering "where the camera was" needs historical boundaries, which GeoNames does not carry and
which would be a different dataset and a much larger problem. Answering "what it is called now"
is free and needs a sentence on screen saying so.

---

## Appendix: what was not measured

Stated so the gaps are not mistaken for findings.

* **Feature-code and population ranking** - the thing that would make either tier correct. Not
  costed.
* **A packed on-disk index** for class P, which is the only route past the 1,683 MB ceiling.
* **Accuracy outside the fixture.** Sixteen points, weighted to Tamil Nadu by design. The
  per-tier scores are not population-weighted and should not be read as global hit rates.
* **The modal-place-across-a-cluster half of `(kk)`**, which remains blocked on the catalog
  holding zero events - the original blocker, still true for that half.
* **Any non-GeoNames source.** OpenStreetMap/Nominatim extracts and commercial datasets were not
  examined.
