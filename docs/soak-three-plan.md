# Soak three - what the product does when the filesystem says no

**Status: written 2026-08-21, NOT RUN.** Soaks one and two organized a healthy library at scale.
This one does not: every step makes something refuse, and reads what the product then says.

## Why refusal, and why now

From the stock-take beside [`soak-two-record.md`](soak-two-record.md): **eleven of the twelve
entries closed or filed in the three days after soak two live in code that only runs when the
ordinary case did not hold.** The single exception is `(aeu)`. Three were **live delete-path
defects** - `(aez)` and `(afb)` both raised an uncaught `PermissionError`, and `run_reclaim`'s did
it *mid-loop, after earlier candidates had already been deleted*. None was found by running the
product; they were found by reading, provoked by a pin ordered for something else.

⚠ **Soak two's own thesis already named this class** - *"SEQUENCE defects need control, not scale.
Interruption, **refusal**, undo, resume"* - and then scheduled **no step that refuses anything**.
No soak step anywhere `chmod`s a thing. That is the gap this plan fills.

## The five refusals are five different errnos, and the product may confuse them

Measured on this machine, on 2026-08-21, before writing the steps:

| what happens | errno | staged by |
|---|---|---|
| permission denied | `EACCES` | a real `chmod 000` |
| read-only media | **`EROFS`** | a FUSE mount with `ro=True` |
| media full | `ENOSPC` | a FUSE filesystem that refuses `create` |
| drive unmounted cleanly | *(no errno)* - **the path becomes an empty directory** | `fusermount3 -uz` |
| drive vanished uncleanly | **`ENOTCONN`** | `SIGKILL` the FUSE daemon |

⚠ **`EROFS` is not `EACCES`, and the difference is the point of two of these steps.** A permission
problem is the user's to fix; read-only media cannot be fixed at all, only used differently. A
product that says *"check the folder's permissions"* about a write-protected SD card is sending
someone to a dialog that will not help. `models.unreadable_remedy` has five reasons and **none of
them is read-only**, which is a prediction this soak is designed to falsify.

⚠ **The clean-unmount row has no errno at all**, and that is the one worth being frightened of:
the path still exists, still stats, is still a directory, and is **empty**. Every file on that
drive reads as *gone* rather than *unreachable* - the exact `(aac)`/`(aer)`/`(aey)` conflation, at
the scale of a whole drive.

## Staging - what this machine can and cannot do

**No passwordless `sudo`, and `unshare -Ur` is refused** (`write failed /proc/self/uid_map`), so
**no loopback filesystem and no `mount` of any kind is available.** Verified rather than assumed.

**But `fusermount3` is setuid root and `/dev/fuse` is world-writable**, and a `fusepy` filesystem
mounts unprivileged. Every errno in the table above was produced that way here, today. So all five
refusals are stageable **without root**.

⚠ **A FUSE filesystem is NOT a monkeypatch, and the distinction is the reason this plan is
runnable at all.** Reason 2 of the stock-take is that a simulation freezes an assumption about how
a failure presents - which is how `_deny` survived a stdlib change and how the first
`_swallowing_predicates` fixture walked past its own refusal. A FUSE mount freezes nothing: the
process makes a **real syscall**, the **kernel** returns a **real errno**, and the product runs
**unmodified**. What is synthetic is only *when* the failure fires. Prefer a real `chmod` wherever
`chmod` can express the case - it is simpler and needs no harness - and use FUSE only for the four
refusals `chmod` cannot express.

**What cannot be staged here at all:**

- **A genuinely full block device.** `ENOSPC` from FUSE is a real errno on a real syscall, but the
  filesystem is not really full - no partial write, no fragmentation, no metadata exhaustion. S11
  keeps its `⚠ needs a loopback` marking from soak two and **stays unrun on this machine**.
- **Windows and macOS refusal semantics.** `chmod 000` does not deny the owner on Windows, and
  neither `EROFS` nor `ENOTCONN` arrives by the same route. Every step here is **Linux only**, and
  a green run says nothing about the two platforms that only CI sees.
- **Real removable media** - an actual write-protected SD card, an actual USB pull. FUSE
  reproduces the errno, not the hardware.

---

# The steps

Each step: what to **do**, what to **read**, and what would count as **the app saying something
untrue**. `corpus: subset` is soak two's `Input/2013` - 166 files, 289 MB - because these are
sequence defects and a large corpus is actively worse (soak two §"The corpus, therefore").

## R1 - A source file that cannot be read. `corpus: subset` · `chmod` · **no root**

| | |
|---|---|
| **Do** | `chmod 000` **three files** in the source, then `organize` (preview, then `--apply`). Restore afterwards. |
| **Read** | The preview's counts, the *Files that were not organized* block and its per-reason remedy, the exit code, the destination tree, and `status`. |
| **Untrue if** | the three are absent from every report · the preview count and the applied count disagree · they are reported under a reason that is not `permission denied` · the remedy sends the user somewhere that cannot help · **exit 0** on a run that could not read three of the user's photos · they are silently counted as *organized*. |

## R2 - A source whose PARENT cannot be read. `corpus: subset` · `chmod` · **no root**

| | |
|---|---|
| **Do** | `chmod 000` a **folder** containing ~20 files, then `organize`. This is the case `(aey)` was about: the files are fine, the way in is not. |
| **Read** | The skipped-folder block (`(aer)`'s), the folder count, whether the folder is **named**, and the remedy. |
| **Untrue if** | the folder is reported as **hidden** rather than unreadable · a **file count** appears beside it - `c027dd3`'s rule, the walk never entered it · it is described as *missing* or offered as creatable (`(aey)`'s shape, end to end) · the 20 files are silently absent from the totals · the run reports success. |

## R3 - A destination that refuses **mid-run**, not at the start. `corpus: subset` · **FUSE** · no root

⚠ The step this whole plan exists for. Preflight checks the destination **once, at the start**;
every defect in this family lived in what happens after that.

| | |
|---|---|
| **Do** | Mount a FUSE destination that is writable, start `organize --apply`, and flip it to `EACCES` after ~30 files. Then a second pass: flip to `EROFS` instead. |
| **Read** | Per-file statuses, the failure block, the catalog afterwards, `verify`, and whether a **re-run resumes** or starts over. |
| **Untrue if** | the run reports success · files that never landed are recorded in the catalog as copies (`file_copies` rows with no file) · the two refusals produce the **same** wording, when one is fixable and one is not · a partial file is left at the destination with no `.part` suffix and no journal row · `verify` afterwards disagrees with what the run said it wrote · the re-run re-copies what already landed instead of resuming. |

## R4 - A drive that unmounts while a job is running. `corpus: subset` · **FUSE** · no root

| | |
|---|---|
| **Do** | Organize onto a FUSE drive, then **mid-run**: (a) `fusermount3 -uz` - clean unmount, path becomes an **empty directory**; (b) in a second pass, `SIGKILL` the daemon - path returns **`ENOTCONN`**. Then run `verify` and open the Backups screen **while it is still gone**, and again after remounting. |
| **Read** | The job's outcome, `verify`'s missing count, `drives` custody lines, the Backups screen wording, and `status`. |
| **Untrue if** | ⚠ **the empty-directory case reports every file as *missing* rather than the drive as unreachable** - the whole-drive form of `(aac)` · custody claims one copy for content that has two, one merely unplugged · anything **destructive** keys off that verdict: a reclaim offer, an adoption `NO_MATCH`, or any reconciliation that forgets copies it cannot currently see · `ENOTCONN` escapes as a raw `OSError` to a screen · `LAST VERIFIED` updates from a verify that could not read the drive. |

## R5 - The catalog's directory becomes unwritable after the run began. `corpus: subset` · `chmod` · **no root**

| | |
|---|---|
| **Do** | Start `organize --apply`, and `chmod 555` the directory holding `catalog.sqlite` once files are landing. SQLite needs to create `-wal` and `-journal` **beside** the database, so this refuses writes without touching the file itself. |
| **Read** | Whether the run continues, what it says, the catalog's contents afterwards, and `verify` against the destination tree. |
| **Untrue if** | files are copied and **not recorded**, with the run reporting success - the state `rescan` exists to repair, reached silently · the failure surfaces as a raw `sqlite3` message (§9) · the catalog is left **corrupt** rather than unchanged · a retry after restoring permissions does not reconcile · the run claims a number of organized files the catalog cannot substantiate. |

## R6 - Read-only media as a **source**. `corpus: subset` · **FUSE** · no root

| | |
|---|---|
| **Do** | Mount the subset read-only (`EROFS`) and `organize` **from** it - the ordinary "import from a write-protected card" case. Then `organize --in-place` against it, which must refuse before doing anything. |
| **Read** | The run's outcome, and specifically what `--in-place` says when it cannot write to the source. |
| **Untrue if** | a copy-mode run fails at all - **it never needs to write to the source** · `--in-place` starts and fails partway rather than refusing up front · the refusal says *permission* when the medium is read-only · any sidecar, marker or `.original` write is attempted on the source in copy mode. |

## S6 (kept from soak two) - Interrupt a migration and resume it. `corpus: subset` · **ext4**

Unchanged, and kept because it is already the right shape: it injects a fault and reads what state
was left. ⚠ **ext4, not tmpfs** (§4's forty-sixth member: tmpfs cannot observe interruption), and
not the FUSE mounts above either, for the same reason.

## S11 (kept from soak two) - The disk fills mid-copy. ⚠ **needs a loopback - CANNOT RUN HERE**

Kept, and **explicitly not runnable on this machine**: no `sudo`, no `unshare -Ur`, so no loopback
filesystem. R3's `ENOSPC` variant reaches the same **errno** through FUSE and is worth running as a
partial substitute - but it is not the same test, and saying so is the point. A real full device
also produces short writes, fragmentation and metadata exhaustion, and `(aek)` was a defect in
exactly that neighbourhood. **Run it on a machine with root.**

## Dropped: S9 (`--in-place`) and S10 (`reclaim`) - and why this is not an omission

⚠ **Both were feature exercises, and feature exercises have produced one finding in twelve.**

- **S10 (`reclaim`)** was overtaken. `(aez)` fixed a live crash in exactly the path S10 would have
  walked, and `test_reclaim_never_deletes_what_it_cannot_examine.py` now pins the property that
  matters - *a file reclaim cannot read is never a deletion candidate* - on both interpreters and
  on every lane. Running S10 on a healthy library would exercise the path that already works.
- **S9 (`--in-place`)** is not dropped so much as **absorbed**: R6 runs `--in-place` against a
  refusing source, which is the case a healthy-library S9 could not reach. The layout and journal
  behaviour S9 was aimed at is already covered by S5 and S6.

**What is genuinely lost:** neither drop covers `--in-place` or `reclaim` **at scale on a real
library**. If a population defect lives there - an O(n²) pass, a journal that grows wrong over
thousands of rows - this plan will not find it. That is a deliberate trade, made because the
evidence says the defects are in the refusal paths, not because those two steps are worthless.

---

## Order, and what to do with findings

R1 → R2 → R6 → R5 → R3 → R4, then S6. Cheapest and most contained first; the two that leave a
mount in an odd state last. **Each finding gets a letter and an entry before the next step runs** -
soak two's own discipline, and the reason its five findings did not turn into one unreadable
report.

⚠ **Every step restores what it broke, in a `finally`.** A `chmod 000` left behind on a source
folder, or a FUSE mount left dangling, is a worse outcome than the defect being hunted - and
`~/TruestillLibrary/` is free scratch, but the two format repos under `~/ad/application/` are
version-controlled and must end `git status`-clean.

⚠ **The fence is unchanged and applies to every step**: `/home/dinesh/pCloudDrive/` and
`/home/dinesh/Icedrive/` are never read, walked or stat'd, at any depth, under any flag. They are
themselves FUSE mounts, which makes them a tempting subject for R4. **They are not available for
it.** Every mount this plan uses is one it created.
