# (ags) INGEST EXTRACTS A WHOLE ARCHIVE INTO THE USER'S TEMP, WHICH IS OFTEN RAM.

*Body of entry `(ags)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ags) INGEST EXTRACTS A WHOLE ARCHIVE INTO THE USER'S TEMP, WHICH IS OFTEN RAM.** Filed
  2026-08-23 out of the P30 tmpfs investigation - **a product defect found while chasing a
  development one, and deliberately not fixed in that turn.**
  - **The mechanism.** `organizer.py:1251` extracts an archive into
    `tempfile.TemporaryDirectory(prefix="truestill-ingest-")`, which follows `TMPDIR` - in
    production, the user's `/tmp`. On many Linux desktops (Fedora since 34, Arch, this
    machine) `/tmp` is **tmpfs**: a 20 GB Takeout archive ingested there is 20 GB of RAM and
    swap before a single file reaches the library. The exact failure the development side
    just measured - 26 GB peak, swap 98%, desktop lag - handed to a user by the product.
  - **The corroborating half**: `exif.py:265`'s argfiles also follow `TMPDIR` but are tiny
    and unlinked in `finally` - named so nobody widens this entry onto them; they are fine.
  - **The shape of a fix, not designed here**: extraction scratch should live beside the
    DESTINATION it is being ingested toward (same volume, so the final move is a rename and
    the free-space check is honest), never in the OS temp. `suite_scratch.py` records the
    same ruling for the test suite; this entry is that ruling reaching the product.
  - **Not the same defect as the P30 finding**: that was development scratch (the session
    scratchpad on tmpfs); this is what the shipped product would do to a user's machine.
