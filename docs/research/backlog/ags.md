# (ags) INGEST EXTRACTS A WHOLE ARCHIVE INTO THE USER'S TEMP, WHICH IS OFTEN RAM.

*Body of entry `(ags)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

> ## ⚠ THE PREMISE IS FALSE - read this before building anything here (2026-08-24, P40)
>
> **Both halves of the headline are wrong against today's code, and were wrong on the day the
> entry was filed.** Recorded rather than deleted, because the entry below is the evidence for how
> it happened. **Not closed here** - whether a letter filed on a false premise is closed or struck
> is the maintainer's call, and this note is what stops it being built in the meantime.
>
> **Archive extraction does not use the OS temp.** `extract_archive_set`
> (`archive_extract.py:303`) extracts *"into one merged staging tree **under `destination`**"*;
> `_write_journal` (`archive_extract.py:213`) builds it as `destination / STAGING_DIRNAME`, where
> `STAGING_DIRNAME = ".truestill-staging"` (`archive_extract.py:57`). Both callers go through it -
> the CLI at `cli.py:1667` and the app at `service/takeout.py:201` - and `server.py:424` says so in
> a comment: *"into a staging tree ON THE DESTINATION DRIVE"*.
>
> ⚠ **That is this entry's own recorded fix-shape**, *"extraction scratch should live beside the
> DESTINATION it is being ingested toward"* - already true, and true since the feature's **first**
> commit (`346135c`, 2026-08-01), three weeks before the entry was filed on 2026-08-23.
>
> **And `organizer.py:1251`, the line the entry cites, is a different mechanism.** It is
> `_MetadataBaker`, which stages the **next `WRITE_BATCH_SIZE` files** - 100 (`exif.py:238`) - and
> calls `self.close()` to remove the previous chunk before staging the next
> (`organizer.py:1243-1251`). It is bounded at a hundred photos, never *"a 20 GB Takeout
> archive"*, and it is the chunked bake `IMPLEMENTATION_STANDARDS.md` §1 describes.
>
> **How it happened**: the first function looked at answered the question truthfully -
> `organizer.py` does open a `TemporaryDirectory` named `truestill-ingest-` - and the reading
> stopped there rather than reaching the function that actually extracts archives.
> `ENGINEERING_STANDARD.md` §4's sixty-ninth member, and the seventh instance of the
> false-when-written class in a week. **Found by grepping every `tempfile` use in
> `packages/*/src/` before believing the citation**, which is what that member asks for: the whole
> shipped tree has three, and `exif.py:265`'s argfiles are the only other one - which this entry
> already excluded.

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
