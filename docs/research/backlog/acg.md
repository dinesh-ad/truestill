# (acg) ALBUM MEMBERSHIP CANNOT LEAVE THIS MACHINE - the same class as `(ack)`, waiting.

*Body of backlog entry `(acg)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(acg) ALBUM MEMBERSHIP CANNOT LEAVE THIS MACHINE - the same class as `(ack)`, waiting.**
  Recorded 2026-08-09 from the schema while fixing `(ack)`. `file_albums` is
  `PRIMARY KEY (file_id, album_id)`: **both are catalog rowids**, and `file_id` is a rowid rather
  than a sha256, so album membership is **doubly** unresolvable on a machine that never saw this
  catalog. Not live only because `gather_decisions` takes album *names* and `apply_decisions`
  reports them under `not_applied` - the albums tables are empty today.
  - ⚠ **CORRECTION, 2026-08-26 (P103): "the albums tables are empty today" IS FALSE, and this
    entry is larger than it says.** `takeout.py:scan_takeout` records an album per media file, `cli.py:_print_duplicate_space`
    builds `IngestContext.albums` **unconditionally** on every ingest, and the rows land via
    `organizer.py:_record_then_stop_if_it_will_recur` -> `catalog.py:Catalog.record_uploaded`. **`--map-albums` does not gate any of it** - it
    selects the event-naming prompt only (`cli.py:_build_parser`). So every Takeout user with album folders
    already has album names written to their drive on each save and discarded on each restore.
    `agy.md:65-68` flagged this sentence as worth re-checking and declined to; it is now
    checked. The entry stands, its premise does not, and the ranking should follow the corrected
    one. That a restore never *says* the section was dropped is `(ahx)`, filed separately.
  - ⚠ **CORRECTION TO THE CORRECTION, 2026-09-01 (P184): "SILENTLY discarded" WAS WRONG BY A WHOLE
    SURFACE, and the entry carried it for a week.** The CLI **does** say so.
    `decisions.py` sets `not_applied=("albums",) if decisions.albums else ()`;
    `decisions.py:withheld_count` walks `REPORT_FIELD_NOTE` so a new omission field joins the
    count without anyone remembering it; and `cli.py:_print_restore_plan` looks up
    `REPORT_FIELD_NOTE[field.name]` to name the section. **The app does not**:
    `grep -rn not_applied packages/truestill-app/src` returns **0 files**.
    🔑 **So the true claim was "reported in the terminal, and no screen restores at all"** -
    ⚠ **and even that sentence needed one more correction, made 2026-09-01 (P185).** It first read
    *"silent on every screen"*, which implies a screen that stays quiet. **There is no such
    screen**: `grep -rn apply_decisions packages/*/src` finds **no app caller**, and
    `cli-app-parity.md` already records it - *"`restore` | the app can say a restore is needed
    (`service/drives.py:DriveDecisions`) and cannot perform one"*. `(ahx)` shipped and owns the CLI;
    the app half is not an unowned gap but a **route that does not exist**, which is the parity
    arc's work and neither entry's.
  - ✅ **SHIPPED 2026-09-01 (P185).** Membership travels as `{"name": …, "members": [sha256, …]}`,
    built by `catalog.Catalog.album_members` and applied by `decisions._apply_albums`.
    🔑 **NO SCHEMA CHANGE, so no migration on a published product** - `albums.name` and
    `files.sha256` are already `UNIQUE`, so the rowids stay local and the document names what they
    point at. That is `(ack)`'s method rather than a second ruling: *"Fixed at the gather, because
    apply cannot repair what the document discarded [...] No schema change was needed."*
    ⚠ **The premise in this entry was wrong about the mechanism.** Membership did not travel in a
    form that failed to resolve - **it did not travel at all**:
    `albums=tuple({"name": name} for name in catalog.all_album_names())` carried the vocabulary and
    nothing else. Rowids are a local storage detail and were never the transport.
    ⚠ **Merged by UNION, not first-wins**, which `_merge_albums` records: two drives hold different
    partial views of one album, so first-wins would drop members - this entry's own harm one layer
    up. Safe because membership is append-only, checked rather than assumed (two `INSERT OR IGNORE`
    writers, zero `DELETE`). **If a remove ever ships, that merge must be revisited in the same
    commit.**
    A member whose content the catalog does not hold is counted into `awaiting_content` and **kept
    in the document**, never dropped. `not_applied` no longer names albums.
    ⚠ **Not fixed here, and filed separately**: `forget_organized` deletes a `files` row without
    touching `file_albums`, there is no foreign key, and the schema has no `AUTOINCREMENT` - so a
    reused rowid can attach a different photograph to the old one's album. That is wrong today
    independent of portability.
  - **Whoever implements albums inherits `(ack)`'s bug** unless membership travels as content
    hashes. The rule is already written in `decisions.py`'s module docstring: identity travels
    inside the row it identifies. A sha256 does; a rowid does not.
  - **`file_id` is the sharper half.** Even a self-contained album key leaves membership pointing
    at rowids. The document must carry member **sha256s**, which is what the approved plan said
    (`albums: name + member sha256s`) and what the gather does not yet do.
