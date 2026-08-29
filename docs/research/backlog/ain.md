# (ain) A REFUSED TIMESTAMP AFTER A COMMITTED RENAME LEAVES A FILE ON THE DRIVE WITH NO CATALOG ROW.

*Body of entry `(ain)`, **SHIPPED 2026-08-29 (P143)** - its index row is in
[`SHIPPED.md`](../../SHIPPED.md), not [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared between the two.*

> ⚠ **This body was filed as a SOURCE READING and said so. It was reproduced before it was
> touched, and every clause held** - three files on the drive, zero catalog rows, exit 1 - **with
> one correction the reading could not have made**: `(afe)`'s *"exits 0"* is true only once the
> refusal clears. While the mount keeps refusing, each run exits 1 **and still writes the
> duplicate**, so the exit code is not the tell. The measurement, the ruling and the census the
> fix produced are in `SHIPPED.md`'s row; this body is left as the reading it was.

- **(ain) A REFUSED TIMESTAMP AFTER A COMMITTED RENAME LEAVES A FILE ON THE DRIVE WITH NO CATALOG
  ROW.** Filed 2026-08-29 (P141), from code. **`(aie)`'s mirror image on the same mount, and
  worse** - filed separately because it has a different fix, and burying it inside `(aie)` would
  mean it ships when `(aie)` does or not at all.

  ## THE MECHANISM

  `organizer._upload_and_stamp` runs `destination.upload(...)` and **then**
  `destination.set_timestamp(...)`. `LocalDestination.set_timestamp` is a bare `os.utime` with no
  guard. On a mount that refuses `utime` - FUSE/cloud, SMB/CIFS, NFS with `root_squash`, or any
  destination where the caller does not own the file - the sequence is:

  1. `upload` **completes and commits by rename**. The file is on the drive, whole and correct.
  2. `set_timestamp` raises.
  3. The exception propagates; the file is reported **`FAILED`**.
  4. **The rename is never rolled back**, and no `file_copies` row is written.

  🔑 **So the drive holds a photograph the catalog has never heard of.** That is exactly the state
  [`afe.md`](afe.md) measures as **self-worsening**: the next `organize` finds no row for the sha,
  `_already_at_target` is a `samefile` check that is false in copy mode, `_free_relative` allocates
  a suffix, and the run writes `…_1.jpg` **and exits 0**. One refused timestamp becomes a
  duplicate library, silently, on every subsequent run.

  ## WHY IT IS WORSE THAN `(aie)`, AND WHY THE FIX DIFFERS

  | | `(aie)` | `(ain)` |
  |---|---|---|
  | what the drive holds | **nothing** - the staged copy is discarded | **a committed file** |
  | what the catalog holds | nothing | nothing |
  | is the pair consistent? | ✅ yes - nothing, nothing | ❌ **no - the drive and the catalog disagree** |
  | on the next run | the same failure again | **a duplicate is written, exit 0** (`(afe)`) |
  | the fix | keep the verified copy instead of discarding it | **make the stamp non-fatal, or record before stamping** |

  ⚠ **`--no-timestamps` escapes THIS one and not `(aie)`**, which is the clearest proof they are
  different defects. `set_timestamps=False` (`cli.py`) gates precisely this call in
  `_upload_and_stamp` - so the flag prevents `(ain)` entirely. It cannot help `(aie)`, because
  `safe_copy` never sees `set_timestamps` (zero occurrences) and `copy2`'s internal `copystat`
  has already raised inside `upload` before the guard is reached.

  ## WHAT IS NOT ESTABLISHED

  - **Not measured.** `(aie)` was reproduced by injecting `EPERM` at `os.utime`; the same injection
    would reach this path, but it has not been run. **This entry is a source reading**, and
    `(aid)`/`(aie)` are the precedent for what that is worth until someone runs it.
  - **Which repair is right is unruled**: making the stamp non-fatal (the file is already correct;
    a wrong mtime costs nothing the product uses, since `models.DateSource` has no mtime tier), or
    writing the catalog row before stamping so the drive and catalog cannot disagree. The second is
    the stronger invariant and the larger change.
  - **Whether `bake` and `migrate` share it** - both reach `set_timestamp`-shaped calls; not traced.

  ## RELATED

  `(aie)` (the same mount, the opposite direction), `(afe)` (the self-worsening orphan this
  produces), `(aim)` (the summary that reports it as `FAILED` while the plan said organized),
  [`soak-eight-record.md`](../../soak-eight-record.md).
