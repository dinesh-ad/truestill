# (abm) Attach counts three things and shows none of them.

*Body of backlog entry `(abm)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abm) Attach counts three things and shows none of them.** Recorded 2026-08-06 while fixing
  the walk that produced the third.
  - `DriveAttachment.unreadable` (files), `.unmatched` (on the drive, unknown to the catalog) and
    now `.unreadable_dirs` (folders that could not be listed) are all computed, tested, and read
    by nobody: `service/backup.py` uses `src.linked + tgt.linked` for `will_read` and **discards
    the return value entirely on the run path**. So a drive can attach with folders skipped and
    the screen says only how many files were linked.
  - **Deliberately not fixed with the walk.** The walk fix stops the fact being *destroyed*;
    showing it is a payload key plus a render plus a browser test, and doing one of the three
    siblings would leave the other two - which is how they got here.
  - **`service/fs_browse.py:188` rides along.** Its `rglob` undercounts a locked subfolder in the
    browse dialog's media estimate. Left as `rglob` on purpose: that number is already advisory
    and already truncated by `cap` (`media_capped`), which distorts it more than a locked folder
    does, and there is nowhere on a file-picker row to name a folder. Swapping the walk without a
    surface would recreate exactly the computed-and-dropped value this entry exists to close.
