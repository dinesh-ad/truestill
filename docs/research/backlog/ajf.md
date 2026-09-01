# (ajf) SHOULD A COMMAND SAY "COPIED" BEFORE THE MEDIUM HAS THE BYTES? A WORDING RULING, NOT A DEFECT.

*Body of entry `(ajf)`, **SHIPPED 2026-09-01**. The closure is in [`SHIPPED.md`](../../SHIPPED.md);
the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Filed 2026-08-31 (P167), split out of `(aiz)` when its consequence half shipped. Body written
2026-09-01 - **the entry was open for a day with no body, the only one of 118 in that state**; the
mechanism that let that happen is ruled on at the end.

## THE SENTENCE, AND WHAT WAS TRUE WHEN IT PRINTED

`backup --apply` printed

> **`Copied 356 file(s), 717 MB.`**

in **4.74 s**, with **570 MiB still dirty in RAM**, onto a stick measured at **1.34 MiB/s**.
Measured in [`soak-eleven-record.md`](../../soak-eleven-record.md) §5; not re-measured here,
because it needs the physical stick.

At 1.34 MiB/s, 570 MiB is **seven minutes** of writing still to do. The sentence is in the **past
tense** and the work is in the future. It is written inline at the end of `cli._cmd_backup`
(there is no separate printer for it, checked - `grep -n 'Copied' cli.py`):

```python
print(f"\nCopied {outcome.copied} file(s), {_gb(outcome.bytes_copied)}.")
```

`organize` has the same shape in `_print_summary` - `organized (unique) : N` - and the same
exposure. **Whatever is ruled here applies to both**; a fix to one of them is half a fix.

## ⚠ THE HARM THAT MADE THIS URGENT IS GONE, AND THAT IS WHY IT IS A WORDING QUESTION NOW

`(aiz)` shipped: a `file_copies` row is believed only while the target holds a file of the
recorded size, so a false custody claim no longer defends itself and the next run repairs it.
`(ajb)` shipped: `rescan` compares the size it already holds and names what is wrong. **The
data-loss path this came out of is closed.**

What is left is **whether the sentence is honest**, which is a different kind of question and
answers to a different authority. 🔑 **This is a product call and a defect fix is not where it
belongs** - `(ajd)` and `(aja)` are already the precedent that behaviour fixes get taken one at a
time, on evidence, and wording that a person reads and acts on is not that.

## WHAT THE CODE ALREADY RULES, IN ITS OWN WORDS

`safe_copy`'s module docstring refuses `fsync` explicitly, and names its successor:

> **No `fsync`, deliberately - do not add one as an obvious improvement.** [...] `fsync` addresses
> whether *content* survives power loss, which `copy_sha256` and `verify` already own. A flush per
> file on a photo library is a full write-through per file [...]

⚠ **`copy_sha256` IS A COLUMN, NOT A FUNCTION, and anyone reading that sentence as an instruction
will go looking for the wrong thing.** It is a `file_copies` column and a `record_copy` keyword;
the hash is computed by **`hashing.sha256_file`**, and the command that re-reads a copy and
compares is **`verify.verify_copies`**. Both exist and neither is invoked by `backup --apply` on
the path in question - which is precisely the gap: the durability owner is a *separate command the
user has to know to run*, and the sentence that would prompt them to run it is the one claiming
the work is done.

## THE FIELD SETTLED THIS ARGUMENT FOR `rsync`, AND THE THIRD VOICE IS THE ONE THAT MATTERS

LKML, April 2009, the *"Linux 2.6.29"* thread. **All three quotes verified at source 2026-09-01**
rather than carried over from the index entry:

| who | what |
|---|---|
| **Chris Mason** | *"If we crash just after the rsync, the backup logs won't know. The data could still be gone."* - the exposure, stated as ours |
| **Ted Ts'o**, replying | *"So have rsync call the sync() system call before it exits."* **"Not a big deal, and not all that costly."** |
| **Matthew Garrett**, replying to Ts'o | ⚠ **"sync() isn't guaranteed to be synchronous. Treating it as such isn't portable."** |

⚠ **A NEAR-CORRECTION, RECORDED WHERE THE CITATIONS LIVE.** The first page fetched
(`.../0904.0/00567.html`) appears to attribute **both** of the first two quotes to Ts'o, because
it is Garrett quoting Ts'o quoting Mason, and the nesting does not survive extraction. Fetching
the parent (`00566.html`) settled it and confirmed the index entry was right all along.
**A confident correction there would have introduced the error it was fixing** - which is the
whole hazard of citing from a single page, and the reason both were read.

## 🔑 CANDIDATE 1 IS ELIMINATED, AND ON A TECHNICAL CONSTRAINT RATHER THAN A PRODUCT CALL

**Garrett's objection is not a caveat here; it is disqualifying**, and this repo has already paid
for the class once.

- **`os.sync` does not exist on Windows.** Typeshed, in this repo's own venv:
  `if sys.platform != "win32": def sync() -> None: ...  # Unix only`. Candidate 1 has **no
  implementation at all** on one of the three platforms `ci.yml` gates on
  (`os: [ubuntu-latest, macos-latest, windows-latest]`).
- **This repo has already shipped an fsync-on-Windows defect**, and `catalog_backup.py` records
  it in its own comment: *"`os.fsync` on a read-only descriptor is `[Errno 9] Bad file
  descriptor` there, green on Linux and macOS, caught only by the three-OS lane."* Garrett's
  abstract portability warning is a thing that has concretely happened here.
- **And `fsyncgate` removes the payoff even where it runs.** When a writeback error occurs, Linux
  **marks the dirty pages clean without writing them** - *"the dirty pages which cannot been
  written-out are practically thrown away"* - and reports the error to **the first caller only**,
  so a later flush returns success over bytes that were discarded.

**So a `sync()` before printing buys honest TIMING and no certainty whatever.** Only re-reading
the bytes settles the outcome - `verify_copies` - **which is what `safe_copy` said first**, before
any of this was measured. ⚠ Note the posture that already exists and would be inverted: this
codebase **does** `os.fsync` its small metadata (`drive`, `drive_lock`, `decisions`,
`archive_extract`, `catalog_backup` - five sites) and deliberately does **not** fsync media.
Candidate 1 flips exactly the bulk path that asymmetry was chosen for.

## 🔑 RULED 2026-09-01: CANDIDATE 4, WITH THE CONDITION IN THE SENTENCE

**Shipped.** `backup.EJECT_BEFORE_UNPLUGGING`, one wording home in core, read by both surfaces:

> **`If this drive unplugs, eject it first - that is what finishes the write. Then run: truestill verify`**

**Eject is primary, `verify` is the net.** Ejecting is the mechanism that actually flushes and
every desktop OS ships it; `verify` catches the case where they did not. The field states the
harm plainly - *"pulling it before all updates have completed might simply mean part of a file is
missing (typical of NTFS) or may actually corrupt the filesystem itself (on FAT based
filesystems)"* - which soaks ten and eleven measured independently, on three filesystems.

⚠ **THE COUNT ABOVE IT STAYS UNQUALIFIED.** *"Copied N file(s)"* is true: the copy completed and
was verified, and on a fixed disk those bytes are as durable as anything else the machine holds.
This is a conditional **instruction about the drive**, not a hedge on the copy. A sentence that
made every successful backup read as unfinished would be the cry-wolf `run_health`'s docstring
names as the failure mode to fear. Pinned by `test_the_copied_count_is_not_hedged_by_it`.

### ⚠ WHY THE CONDITION IS IN THE SENTENCE AND NOT IN THE CODE

**Truestill cannot tell whether a destination is removable. Five checks, all negative, run
2026-09-01:**

| check | result |
|---|---|
| `grep -rn removable packages/*/src` | every hit is `cleanup.py`'s removable **folders**. Zero device hits |
| `/sys/block/*/removable` | **zero occurrences** in the tree |
| udisks2 / `GetDriveTypeW` | **zero occurrences** |
| `filesystem.parse_proc_mounts` | reads `/proc/mounts` and takes **only field 2 (fstype)** - it already reads the line carrying the answer and **drops field 4, where the flags are** |
| the `drives` table | six columns - `uuid, label, first_seen, last_seen, last_verified, notes`. No device, no mount point, no filesystem |

And the word *"eject"* appeared **nowhere** in the product before this entry; every `grep -i eject`
hit was *"rejected"*.

🔑 **A filesystem-type proxy was REFUSED with a measurement, not a preference.** `facts_for()`
returns a real answer (`vfat`, measured against a loop volume), but gating on it **fails both
ways**: it fires on an internal Windows NTFS disk, and it stays silent on an **ext4 USB stick** -
the dangerous direction, and the case where a user is most likely to be surprised, because they
believe ext4 is the safe one. A gate that is wrong in the dangerous direction is worse than no
gate. `filesystem.py` is also **unknown on macOS by design**, so the proxy is absent for a whole
platform.

**Detection is `(ajh)`, a separate letter rather than a prerequisite** - it would have delayed a
one-line honesty fix behind a per-platform feature. The sentence above is true on every
destination without knowing which it is.

## THE CANDIDATES AS THEY STOOD



~~1. **Say *"copied"* only after a `sync()`.**~~ **ELIMINATED above** - unimplementable on
Windows, and worthless where it does run.

2. **Say *"copied, not yet flushed"*** (or *"handed to the drive"*). Costs nothing, is true on
   every platform, and is the only candidate that does not make a promise the layer below refuses
   to keep. ⚠ Its risk is the opposite one: a hedge on every successful run teaches the reader to
   skip the last line, and then the one run where it matters reads the same as the 500 before it.
3. **Say nothing different and let `verify` own it.** The status quo, and defensible now that
   `(aiz)` and `(ajb)` have closed the harm - the cost is that the sentence stays false for a
   window whose size is the mount options, which soak eleven measured at 3.5 GB on exFAT and
   16 MB on FAT32.

**A fourth, not in the index entry and worth having on the table**: say *"copied"* unchanged, and
**append the next step** - *"run `truestill verify` to check the bytes arrived"* - only when the
destination is removable. It concedes nothing about timing, and it puts the durability owner in
front of the person at the moment they are looking.

## WHAT IS NOT ESTABLISHED

- **Whether the window is user-visible at all on fixed disks.** Every measurement behind this
  entry is removable media. `soak-nine-record.md` is a fixed disk and did not look at this.
- **What `organize` should say**, separately. It has the same tense problem and a different
  audience: `backup` is explicitly about a second copy, `organize` is about moving a library the
  user still has.
- **What a `sync()` would have COST, which is now moot and recorded anyway.** *"Not all that
  costly"* was said about `rsync` in 2009 on rotating disks; nobody has measured it on this
  workload. It is not worth measuring now - candidate 1 died on portability, not on price - but if
  it is ever revisited, `/tmp` is tmpfs, so an ad-hoc benchmark would measure RAM unless run under
  `suite_scratch.scratch_root()`.
- **Whether any of this is reachable from the app.** The app's backup surface prints its own
  wording; nothing in this entry has looked at it, and
  [`soak-twelve-record.md`](../../soak-twelve-record.md) records why: **twelve soaks, none with
  the app as subject.**

## RELATED

`(aiz)` (the window, consequence half shipped), `(aja)` (the self-defending row),
`(ajb)` (`rescan`'s size compare), `(abn)` (repair, still unbuilt),
[`soak-eleven-record.md`](../../soak-eleven-record.md) §5,
[`soak-twelve-record.md`](../../soak-twelve-record.md).
