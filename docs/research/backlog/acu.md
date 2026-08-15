# (acu) POI LOOKUP FROM GPS - the strongest form of location naming, measured and NOT built.

*Body of backlog entry `(acu)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(acu) POI LOOKUP FROM GPS - the strongest form of location naming, measured and NOT built.**
  Recorded 2026-08-11. Take a photo's coordinates, ask what named buildings are nearby, and a
  folder called `EA Mall` gets `Express Avenue`. The technique is standard - OpenStreetMap's
  Overpass API returns named POIs within a radius - and it is the strongest version of this idea
  **because it RETRIEVES a fact instead of asking a model to recall one.** That is the same
  instinct as splitting place-identification out to a gazetteer: a lookup cannot invent a mall,
  and every model size measured invented one (`Emaar Mall`, `Chennai International Trade City`,
  `Eco Park Mall`, `East Avenue Mall`; the answer is Express Avenue, and not one said it did not
  know).
  - ✅ **It would have worked, and that is measured rather than assumed.** One Overpass query,
    400 m around Express Avenue's coordinates, returned the way `Express Avenue Mall` and two
    nodes named `Express Avenue` / `Express avenue`.
  - ⚠ **But it returns CANDIDATES, not an answer**, which is the part a design has to own. The
    same query returned **60 named features** in that radius - `Royapettah`, `Melody` (cinema),
    `Lifestyle` (clothes), `Escape Cinemas`, a clock tower, a church. Choosing among them, and
    matching the user's `EA Mall` to `Express Avenue Mall`, is a separate decision that the
    lookup does not make. OSM's own naming is inconsistent here (three entries, two spellings),
    so an exact string match is not the bridge either.
  - **The offline cost, as numbers rather than an adjective** (measured 2026-08-11): the full
    planet extract is **94.2 GB** (`Content-Range` on `planet-260803.osm.pbf`), the India-only
    extract **1.6 GB**, against **12.9 MB** for the `cities500` gazetteer. The density is the
    reason, and it is measurable directly: in one Chennai bounding box OSM holds **11,053 named
    POIs against 64 `cities500` rows - 173x**. A name-and-coordinate-only index derived from a
    POI extract would be far smaller than the raw file; **that derived size was not measured**,
    and is stated here as a gap so it is not mistaken for a finding.
  - ⚠ **Three things block it here, and none of them is the technique.**
    1. **There are no coordinates for the case it would solve.** `(kk)` measured GPS on **3.6%**
       of this library - 83 of 2,275 files, from one phone of nine - and the `EA Mall` photos are
       2013-2015, when location was off by default. The evidence this feature runs on is absent
       exactly where the motivating example lives.
    2. **An online lookup sends COORDINATES, which is a location history**, and a far larger
       exception than the folder-name hole §1 was just narrowed to permit. A folder name is a
       word the user typed; a coordinate is where they physically were, per photo. Verified
       2026-08-11: Nominatim's policy is *"no heavy uses (an absolute maximum of 1 request per
       second)"* and *"periodic requests from apps are considered bulk geocoding and as such are
       strongly discouraged"*; Overpass asks for **under ~10,000 requests and under 1 GB per
       day**, shared across ~30,000 daily users. Neither is a production dependency, and neither
       refusal is about our volume - it is what those services are for.
    3. **A self-hosted instance is the server this product does not have.** §2 and §3 are built on
       there being none; standing one up for naming would be a larger commitment than the
       licensing server, which is itself unbuilt and needs its own design pass.
  - ⚠ **Licence, unread and therefore not cleared:** OSM data is **ODbL** (verified on
    `openstreetmap.org/copyright`), the same share-alike family `(acp)` records for timezone
    boundaries. It must be read before any commercial tier ships data derived from it. Recorded
    as a question, not an obstacle.
  - ✅ **Why this is kept rather than refused, and it is the whole reason for the entry.** For a
    user arriving today with a modern phone, GPS coverage is near-total, and for someone whose
    folders are all `DCIM` this is **the best naming evidence that exists** - better than the
    folder name, because there is no folder name. That user is real even though this maintainer is
    not one. §4's twenty-first member is the rule being applied: one library is a test bed, never
    a specification, and `(kk)` already records the same asymmetry for place names. **Do not read
    "3.6%" as a verdict on the feature; it is a fact about a 2013-2014 library.**
