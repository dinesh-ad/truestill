# (aaq) `rule_software` reads a tag that is never requested, so it cannot fire.

*Body of backlog entry `(aaq)`, under **Rulings - decided, no work attached**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aaq) `rule_software` reads a tag that is never requested, so it cannot fire.** Recorded
  2026-08-02. **REDUCED 2026-08-12** (`SHIPPED.md`): the `SamsungModel` half is closed - deleted,
  not enabled - and the class now has a detector, `test_categorizer_tags_are_requested.py`, which
  fails if any tag `categorize.py` reads is absent from `REQUESTED_TAGS`. `Software` is its one
  documented exemption, and this entry is what the exemption names.
  **What remains is a product decision and needs the maintainer**, per the three ways out below.
  - ✅ **The `SamsungModel` fallback: CLOSED, deleted.** See `SHIPPED.md`. No evidence anywhere
    available justified requesting the tag, and requesting it invalidates every cached metadata
    row in every library.
  - **`rule_software`, the whole rule.** It reads `Software`, which is **not in `REQUESTED_TAGS`**
    either. Measured 2026-08-02: a JPEG stamped `Software=Adobe Photoshop 24.0 (Windows)` comes
    back from `read_metadata` with keys `DateTimeOriginal`, `FileType`, `ImageHeight`,
    `ImageWidth`, `MIMEType`, `SourceFile` - no `Software` - and categorises as `Saved` through
    `RuleName.FALLBACK`. Its own docstring calls it *"the main open-ended path: any application
    that stamps `Software` gets its own folder"*, and that path is unreachable. `_software_family`
    and `_GENERIC_SOFTWARE` exist only to serve it, and `layout.py`'s `RuleName.SOFTWARE` side-bin
    branch is only reachable through it. The module docstring's rule 3 describes behaviour the
    product does not have.
  - **THE DECISION, restated 2026-08-12 once the cost below was measured. It is three ways out,
    not two, and the middle one is new:**
    1. ***Request the tag as it stands.*** Now measurable and now clearly bad: 159 files with a
       working camera `Model` leave the timeline, and 3 folder labels become 97. Not a repair.
    2. ***Reorder `rule_software` below the device rule and constrain the label set, then request
       the tag.*** This is the option the entry did not have. It keeps the case the rule was
       written for - "everything I edited in Lightroom" - while a camera `Model`, which is real
       evidence of origin, outranks "was opened once in an editor". `_GENERIC_SOFTWARE`'s
       five-value exclusion list is the wrong shape for `Version` and `Binary data`; an allow-list
       or a plausibility test is.
    3. ***Delete the dead path*** and record why - costs nothing, discards whatever case it was
       written for.
    - Requesting the tag in options 1 and 2 also changes `tags_fingerprint`, invalidating every
      cached metadata row and forcing a cold exiftool pass, so it needs a reason beyond tidiness.
    - **This is now decidable in one sitting, which it was not before**: the cost of option 1 is
      a number, option 2 names what would have to change, and option 3 is unchanged.
  - **What "request the tag" would actually cost, measured 2026-08-12 rather than argued.** The
    entry called it a product decision without a number; here is the number. 1,258 media files
    across 78 camera makes (`metadata-extractor-images` + `exif-samples`), graded through the real
    `categorize`, production tag set versus the same set plus `Software`:

    | | production today | if `Software` were requested |
    |---|---|---|
    | filed as `Camera` (rule 4) | **461** | 302 |
    | filed by `rule_software` | - | **313** |
    | `Saved` (fallback) | 791 | 637 |
    | files carrying a real camera `Model` **not** filed as `Camera` | **0** | **159** |
    | distinct folder labels created | **3** | **97** |

    So requesting the tag takes **159 files that carry a working camera `Model` out of the
    timeline** and into an editor's folder - a Nikon D200 photo that was once opened in Photoshop
    files under `Adobe Photoshop/`, and `Pentax QS1.dng` (`Model: PENTAX Q-S1`) files under
    `PENTAX/` rather than `Camera/`. **Rule 3 sits above rule 4, so on any file carrying both it
    wins**, and "edited once" is not evidence of origin the way a camera model is.
    - **And the folder count is the sharper half: 3 labels become 97.** `_GENERIC_SOFTWARE`
      excludes five values, which is not the shape of the problem - the labels this produced
      include `Version`, `Binary data`, `Digital Camera`, `GLDPNG ver`, `Nikon Transfer` and
      `ImageMagick`. An open-ended folder-per-application rule inherits whatever junk vendors
      write into a free-text field.
    - Neither number argues for deletion by itself - a real "everything I edited in Lightroom"
      folder is a defensible product. They do say that requesting the tag **as it stands** would
      be a visible regression on ordinary camera libraries, so the decision is not "request or
      delete" but "reorder below rule 4 and constrain the label set, or delete".
  - **Worth checking first for `SamsungModel`: it may have been meant to come from
    `SamsungCaptureInfo`**, which **is** requested and is already used by the screenshot rule. If
    the Samsung model is derivable from that tag, the fix is a parse rather than a new request -
    and free.
  - **A dead rule still occupies a position in the chain.** `rule_software` sits between the
    filename conventions and the device rule, so anyone reasoning about `build_rules` is reading
    six rules when only five can fire - and any change to that ordering has to say what would
    happen the day `Software` is requested, not only what happens today. `(aar)`
    (`SHIPPED.md`) is the case that ran into it: it deferred within rule 2 rather than moving
    rule 2 below rule 4, **because a reordering would also hand messenger files to this rule**
    the day its tag is requested. So the dead rule already constrained a real design choice
    once, without ever executing.
