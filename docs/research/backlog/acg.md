# (acg) ALBUM MEMBERSHIP CANNOT LEAVE THIS MACHINE - the same class as `(ack)`, waiting.

*Body of backlog entry `(acg)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(acg) ALBUM MEMBERSHIP CANNOT LEAVE THIS MACHINE - the same class as `(ack)`, waiting.**
  Recorded 2026-08-09 from the schema while fixing `(ack)`. `file_albums` is
  `PRIMARY KEY (file_id, album_id)`: **both are catalog rowids**, and `file_id` is a rowid rather
  than a sha256, so album membership is **doubly** unresolvable on a machine that never saw this
  catalog. Not live only because `gather_decisions` takes album *names* and `apply_decisions`
  reports them under `not_applied` - the albums tables are empty today.
  - ⚠ **CORRECTION, 2026-08-26 (P103): "the albums tables are empty today" IS FALSE, and this
    entry is larger than it says.** `takeout.py:244` records an album per media file, `cli.py:2485`
    builds `IngestContext.albums` **unconditionally** on every ingest, and the rows land via
    `organizer.py:2121` -> `catalog.py:3113`. **`--map-albums` does not gate any of it** - it
    selects the event-naming prompt only (`cli.py:540`). So every Takeout user with album folders
    already has album names written to their drive on each save and **silently discarded on each
    restore**. `agy.md:65-68` flagged this sentence as worth re-checking and declined to; it is now
    checked. The entry stands, its premise does not, and the ranking should follow the corrected
    one. That a restore never *says* the section was dropped is `(ahx)`, filed separately.
  - **Whoever implements albums inherits `(ack)`'s bug** unless membership travels as content
    hashes. The rule is already written in `decisions.py`'s module docstring: identity travels
    inside the row it identifies. A sha256 does; a rowid does not.
  - **`file_id` is the sharper half.** Even a self-contained album key leaves membership pointing
    at rowids. The document must carry member **sha256s**, which is what the approved plan said
    (`albums: name + member sha256s`) and what the gather does not yet do.
