# (aai) The plain copy path does not verify at write time.

*Body of backlog entry `(aai)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aai) The plain copy path does not verify at write time.** Recorded 2026-07-31, and
  **re-scoped 2026-07-31 after the original reasoning was found to be wrong.** **DEFERRED with
  the cost stated - not an open item awaiting work.**
  - ⚠ **The original entry was wrong, and its "fix" would have been a regression.** It said the
    path records "the hash of what was sent, not what landed", and proposed re-reading the
    destination so the recorded hash described the bytes that actually arrived. That is
    backwards. `verify` compares **the file on disk against the recorded hash**, so:
    - recording the **source** hash (what ships) means a truncated or half-flushed copy
      **fails** verify - the user is correctly told that copy is bad;
    - recording **what landed** would have `verify` compare a file against a hash taken from
      *that same file*. It would **pass**. A corrupted copy would be blessed VERIFIED, forever.

    So the change would have made verify **tautological on the copy path** and destroyed the
    protection it exists to give. It is recorded here rather than quietly replaced because it
    would have looked like an obvious improvement to whoever picked it up - and because it is
    the bake's reasoning applied where it does not belong: a bake needs the landed hash
    *because it deliberately changes the bytes and no source-truth claim survives*; a plain copy
    has a source, and the source is the truth.
  - **THE INVARIANT THIS ENTRY IS REALLY ABOUT, stated positively 2026-08-12 because the entry
    argued the negative and the positive is the stronger case: every path that DESTROYS a source
    re-reads the destination first, and copy mode destroys nothing.**
    - `organizer._move_source` - "delete a source only after its destination copy re-verifies.
      Never deletes on doubt": `destination.checksum(final_relative) == copy_sha`, and any failure
      keeps the source.
    - `reclaim.run_reclaim` - "re-verify fresh, immediately before deleting: never delete on a
      stale check", through `reclaim._verify`, which re-hashes the file on the drive.
    - Plain copy leaves the source where it is. **So the asymmetry is correct rather than merely
      tolerable**, and it is the answer to "why does move verify and copy not": verification is
      the price of destruction, and copy does not destroy. Nothing is at risk during the
      detection window, which is why the latency below costs nothing.
  - **What the real gap is: detection latency, not correctness.** `organizer._upload_copy`
    writes and returns nothing, and `copy_sha` is the source hash. Nothing re-reads the
    destination, so §1's `copy -> record -> re-verify` ordering - which `_move_source` really
    does perform for `--move` - has no equivalent on the plain copy path. A bad write is
    reported as `organized` and is discovered **at the next `verify`, rather than never**. The
    copy is protected either way; what is missing is catching it at the moment it happens.
  - **Why it is deferred rather than open.** Two measured constraints, both of which make this a
    design exercise rather than a fix:
    - **Cost:** a full re-read of every written file. **Measured directly 2026-08-12, replacing
      the proxy below, and it is worse than the proxy said.** On 1.50 GB of the real library: the
      copy itself 0.96 s, the re-read **2.22 s**. So verifying takes the write phase from 0.96 s
      to 3.18 s - **3.3x, not the 30-50% estimated here** - paid always, on every organize.
      (Superseded proxy, kept because it is what the deferral was originally argued on: ~6.3 s
      per 6.2 GB local, ~22 s on a cloud FUSE mount, from the attach work.)
      - **And the re-read is from the DESTINATION, which is usually the slowest device present** -
        a USB drive or a cloud mount, not the NVMe these numbers came off. At the 3.9 MB/s
        measured for cloud-mount content reads, verifying a 6.3 GB organize would add ~27 minutes.
      - **If it is ever built, do not use a second read.** A chunked copy that hashes as it writes
        was measured on the same 1.50 GB at **1.99 s** - 2.1x the bare copy, but **37% cheaper
        than copy-then-verify** and one pass over the destination instead of two. The cost is
        giving up `shutil.copy2`'s in-kernel fast path. Recorded so it is not re-derived.
    - **It cannot be unconditional:** `RcloneDestination` has **no `checksum`** and the base
      raises `DestinationError`. So a post-write verify either skips silently on rclone - a new
      silent hole, which is worse than the one being closed - or needs its own
      UNVERIFIABLE-style outcome plumbed through the organize report. That is design.
  - **If it is ever built**, the recorded hash must **stay the source hash**; the verify step is
    an additional check, never a replacement for what is stored.
