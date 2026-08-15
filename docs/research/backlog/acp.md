# (acp) GPS-DERIVED TIMEZONE - understood, costed, and deliberately NOT built.

*Body of backlog entry `(acp)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(acp) GPS-DERIVED TIMEZONE - understood, costed, and deliberately NOT built.** Recorded
  2026-08-10 from the P41 date/timezone measurement. **This entry exists so the idea is not
  re-derived from scratch; the record is worth more than the feature.**
  - **It is a DIFFERENT CLASS of work from the place-name geocoding in
    `reverse-geocoding-research.md`, not a harder version of it.** Naming is a human question -
    Wayanad is a district and not a populated place, Chennai's nearest point is a neighbourhood,
    `Tiruchirappalli` or `Trichy` depends on who is asking - and there is no ground truth, only
    conventions. Timezone lookup asks **which polygon contains this point** and returns one IANA
    identifier: no synonyms, no administrative history, no phrasing expectation. Closed-form.
  - **Cost, for whoever prices it later.** `timezone-boundary-builder` is the standard source,
    **ODbL**, roughly 50-90 MB as GeoJSON and a few MB packed - against the 400 MB download and
    **1,683 MB peak RSS** that GeoNames class P cost. Point-in-polygon has an honest failure
    mode the place-name lookup lacked: a point at sea returns **no timezone**, where the
    nearest-neighbour place lookup confidently returned an island 920 km away.
  - **The asymmetry that would justify it:** a wrong place name is cosmetic and visible - the
    user reads it and shrugs. A **wrong timezone silently moves a photo to the wrong day**, and
    near midnight the wrong month, into a tree the user then trusts.
  - ⚠ **Two cautions, and together they are why this is filed rather than built.**
    1. **It inherits the anachronism problem in a WORSE form than place names had it.** Zone
       boundaries and DST rules change, so a 2013 photo needs the **historical** rule as of the
       capture instant, not today's. IANA `tzdata` provides that, but only if the lookup resolves
       the zone *and then* the rule for that moment - two steps, and skipping the second is the
       silent-wrong-day failure this would exist to prevent.
    2. **Coverage is small.** GPS is on **3.6%** of this maintainer's library and 1-20% of the
       public corpora, so it would answer the question for a minority of photos and still need a
       fallback for the rest.
  - ✅ **And the closing argument: we may not need it.** P41 measured six midnight-straddling
    fixtures end to end and **five of six land correctly**, because Truestill never converts -
    `parse_exif_datetime` strips any offset and keeps the naive local wall clock, which is what
    `DateTimeOriginal` actually means. Placement was **identical across four extreme machine
    timezones**. The one wrong case is `(aco)`, and a timezone dataset is not the cheapest way to
    close it. Reopen this only if `(aco)` is ruled to need correcting rather than reporting.
