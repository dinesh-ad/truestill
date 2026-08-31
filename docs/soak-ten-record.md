# Soak ten - exFAT on real removable media

**Ran 2026-08-31 (P165). A record: never rewritten to match the present.** The first time the
product met a filesystem that refuses things on its own, rather than an injected `errno`.

**Machine**: Linux 7.0.0-15-generic x86_64, 16 cores, 30 GB RAM, Python 3.14.4.
**Evidence**: `/data/TruestillLibrary/soak-ten-pull-2026-08-31/` - kernel log, full 5,250-entry
manifest, and every measurement below, kept because the run cannot be repeated.

## ⚠ WHAT THIS RECORD MEASURED, BEFORE ANY RESULT IN IT

**An unclean removal of a QUIESCED device.** The stick was pulled physically, without ejecting -
but **71 minutes after the last write**, with writeback long since drained and nothing running.

🔑 **THE EASIEST WRONG CONCLUSION TO DRAW FROM THIS RECORD IS THAT INTERRUPTED WRITES ARE SAFE.**
§6 reports **712 of 712 files byte-identical off the medium** after that pull. **That is not
evidence about an interrupted write and must not be quoted as any.** It says the bytes were
already on the medium, which they had been for over an hour. The brief asked for a pull **during**
an `--apply`; that did not happen, and §7 says what staging a real one would cost.

**Everything below is true of a quiesced pull and says nothing about an interrupted one.**

## THE FINDINGS, RANKED

1. **`(aiz)` - success is reported before the medium has the bytes**, and both instruments
   nominated to catch that read the page cache. §5. **Ranked first because it is `backup`** - the
   3-2-1 command, whose only job is that a second copy exists somewhere else - and it reported the
   copy made about **ninety seconds of device time into a nine-minute write**.
2. **`(aiy)` - two registrations on one stick reported as redundancy**, by `status`, the command
   whose whole purpose is 3-2-1. §6. Ranked second: it misleads about safety the user already has,
   where `(aiz)` misleads about safety being achieved right now.
3. **`(aid)`'s character half reproduces on Linux**, and a trailing dot is silently renamed. §2.
   A dated update to an open entry rather than a new letter.

## 1. The device (Q1022)

| | |
|---|---|
| device | `/dev/sda1` - SanDisk **Cruzer Blade**, USB, serial `4C530001181103118490` |
| label / UUID | **DAMON_16GB** / `EEE4-9C94` |
| filesystem | **exFAT, kernel driver** - module `exfat` loaded, `exfat` in `/proc/filesystems`, and **no** `mount.exfat`, `mount.exfat-fuse` or `exfatfsck` binary exists on this machine. Not FUSE |
| mount | `/run/media/$USER/DAMON_16GB`, mounted by **udisks2** at login (the path is the label, not a choice), `rw,nosuid,nodev,relatime,uid=1000,gid=1000,fmask=0022,dmask=0022,iocharset=utf8,errors=remount-ro,uhelper=udisks2` |
| geometry | 14.6 GiB, **32 KiB clusters** (`statvfs f_bsize`), `f_files = 0` |
| **throughput** | **write 1.34 MiB/s, read 19.7-23.3 MiB/s** - a **15x asymmetry**, and the reason every finding below exists |
| device cache | `sd 0:0:0:0: [sda] Write cache: disabled` - bytes that reach it are durable |

⚠ **It arrived mid-copy.** 3.3 GB of dirty pages were draining to it at session start, the tail of
the copy that put `2014/` there. The first throughput probe appeared to hang; it was queued behind
someone else's writeback. **Every number here was taken after that drained** - a measurement
through a backlog is a measurement of the backlog.

**`2014/` (1,913 real photographs) was left untouched.** Every one of its filenames also appears
in `/data/TruestillLibrary`, so it was not a sole copy - checked rather than relying on
"expendable". All work happened in `soak10/`.

## 2. What exFAT actually refuses (Q1023) - the answer key

Three outcomes, and **the third is the one neither `(aie)` nor `(ain)` has ever seen**: a call that
returns success and does nothing. ext4 control run with the same script.

| probe | exFAT (kernel) | ext4 |
|---|---|---|
| `chmod(0o600)` | ⚠ **IGNORED** - returns success, mode stays `0755` | OK |
| `utime` to a fixed second | **OK, exactly** | OK |
| mtime granularity | **10 ms** (0.005 -> 0.0, 0.02 -> 0.01) | 1 us |
| atime stored separately | OK | OK |
| `:` `?` `*` `\|` `<` `>` `"` `\` in a name | **REFUSED, `[Errno 22] EINVAL`** | all OK |
| **trailing dot** | ⚠ **IGNORED** - `photo..jpg.` lands as `photo..jpg`, **and `exists()` on the name you asked for returns `True`** | OK |
| `nul.jpg` | **OK, verbatim** | OK |
| leading space, `Ünïcodé_日本` | OK | OK |
| 219 / 235 / 255-byte name | OK | OK |
| 256-byte name | REFUSED `[Errno 36]` | REFUSED `[Errno 36]` |
| case sensitivity | ⚠ **CASE-INSENSITIVE, case-preserving** - `CaseTest.bin` and `casetest.bin` are one file, keeping the first name's case | case-sensitive |
| symlink / hard link | REFUSED `[Errno 1] EPERM` | OK |
| `os.replace` onto an existing file | OK | OK |
| extended attribute | REFUSED `[Errno 95] ENOTSUP` | OK |

🔑 **Three premises the brief carried are corrected by measurement.**

- **"2-second timestamp granularity" is FAT32, not exFAT.** exFAT stores 10 ms and `utime` lands
  exactly, so `(ain)`'s syscall **succeeds** here.
- **"no chmod" understates it.** `chmod` does not refuse; it **succeeds and does nothing**.
- **`nul.jpg` is fine.** Reserved device names are a Windows *shell* rule, not a filesystem one, so
  `(aid)`'s reserved-name claim does **not** reproduce on Linux exFAT.

🔑 **AND `(aid)`'s CHARACTER HALF REPRODUCES HERE, ON LINUX.** It has been an unproven Windows-lane
`xfail` since 2026-08-29 because *"a filesystem driver decides it, nothing can force it"*. **A
filesystem that decides it is now on the desk**, and it answers `EINVAL` for eight characters.
Filed as a dated update on `(aid)`, not a new letter.

## 3. Organize onto it (Q1024) and the two fixes meeting the real thing (Q1025)

**387 real photographs copied from `Input/` to ext4, then organized onto the stick.** 362 analysed
(3 unrecognized, 2 hidden, 1 hidden folder), **356 to organize**.

```
      344  organized
       12  organized (renamed to avoid a name clash)
        6  duplicate, skipped
```

**SUMMARY and EXECUTED agreed exactly** - 356 = 344 + 12 - so **no `(aim)` divergence**. The 12
clashes were resolved correctly *despite* case-insensitivity, because `_free_relative` asks
`destination.exists()` rather than consulting a Python set; on exFAT that call is itself
case-insensitive, so a `.jpg`/`.JPG` collision is caught rather than silently merged. **A null
finding, and it is only a null because the code asks the filesystem instead of guessing.**

### 🔑 Q1025: both fixes were built for a shape this filesystem does not produce

`os.utime` and `os.chmod` wrapped for the whole run, each outcome verified by reading the effect
back:

| call | n | outcome |
|---|---|---|
| `utime` on the committed file (`(ain)`'s call) | **353** | **OK, every one** - delta `0.0` exactly |
| `chmod` inside `copystat` on the `.partial` (`(aie)`'s call) | **356** | ⚠ **IGNORED, every one** - asked `0o644`, mode stayed `0o755` |

**Neither fix can fire on exFAT.** `(ain)` handles a refused `utime`; exFAT takes it. `(aie)`
handles a raising `copystat`; exFAT's `chmod` returns success and does nothing, and `shutil`
swallows the `ENOTSUP` xattr failure. Both were proved against an injected `EPERM`, and **the
filesystem they were filed against raises neither.** Neither fix is wrong. `ENGINEERING_STANDARD.md`
§4's fifty-fourth member - an instrument silent in the case it exists for - aimed at a fix rather
than a test.

**The IGNORED case is harmless here**, because exFAT synthesises modes from `fmask=0022`. Nobody
knew that: it was assumed to be a refusal.

## 4. In place on the stick (Q1026) - passed completely

Source and destination both on exFAT, 120 real photographs.

| | |
|---|---|
| result | **116 moved by rename**, 4 exact duplicates left where they were, exit 0 |
| wall | **3 s** - renames are metadata-only, so the 1.34 MiB/s ceiling never applies |
| `utime` calls | 116, **all OK** |
| `verify` | 116 verified, 0 missing, 0 mismatch |
| `undo-organize --apply` | "Restored 116 file(s)" |
| after the reversal | ⚠ **all 120 photographs byte-identical**, compared as a hash multiset |

Only `.truestill-decisions.json` changed across the reversal, and only its `written` timestamp.
Three empty folders were left behind, which the run said it would do and `clean-empty` owns.

⚠ **It refused to run non-interactively** - *"interactive confirmation is required; this operation
cannot run non-interactively"* - and had to be driven through a pty typing `move`. Correct, and
worth recording that it held on removable media.

## 5. 🔑 THE DURABILITY WINDOW, AND THE TWO INSTRUMENTS THAT CANNOT SEE INTO IT

**The finding of this soak that is about the product rather than the filesystem.**

```
From 'Damon exFAT' to 'Damon Backup': 356 file(s) to copy, 717 MB.
Copied 356 file(s), 717 MB.                                    <- 4.74 s wall
```

At the instant that line printed: **570 MiB still dirty in RAM**, and the device needed **~7 more
minutes**. `organize --apply` behaves the same - 4.08 s for 356 files, 649 MB still unwritten.
This is **`backup`**, the 3-2-1 command, reporting the copy made about ninety seconds of
device-time into a nine-minute write.

⚠ **This is NOT an argument for `fsync`, and none is proposed.** `safe_copy.py` rules it out in
its own words - *"No `fsync`, deliberately - do not add one as an obvious improvement… `fsync`
addresses whether content survives power loss, which `copy_sha256` and `verify` already own."*
**The ruling nominated two mechanisms to own durability. Both are blind inside the window the
ruling creates:**

| instrument | why it cannot see |
|---|---|
| `backup`'s destination check | `_copy_verified` does `written = sha256_file(staged.temp)` on bytes written moments earlier. **717 MB hashed inside 4.74 s is 151 MB/s on a stick that reads at 19.7.** It compares the kernel's copy against the source's copy; both are in RAM |
| `verify` | **1.45 s warm against 35.18 s cold** for the identical 356 files. Asked soonest after a write - which is when a user asks - it answers from the page cache |

**The defect is in the remedy, not the decision.** Filed as `(aiz)`, and **ranked first in this
record** because the command that did it is `backup`.

### The field settled this argument for rsync, and settled it the same way

**This is not a novel problem and the answer is not novel either.** Ted Ts'o argued on LKML that
`rsync` should call **`sync()` before exiting** - *"not a big deal, and not all that costly"* -
and **Chris Mason stated our exact case in 2009**:

> *"If we crash just after the rsync, the backup logs won't know."*

**That is a `file_copies` row for bytes the medium never received**, in someone else's words,
seventeen years earlier. The shape is: a copy tool that returns before the data is durable leaves
a **record** claiming a copy exists, and the record is what the next run trusts.

⚠ **AND THE CAVEAT MATTERS AS MUCH AS THE REMEDY - fsyncgate.** `sync()` makes the **timing**
honest; it **cannot make the outcome certain**. A writeback failure can leave pages **neither
written nor marked dirty**, so a later `sync()` returns success over data that was lost. So
`sync()` is the right answer to *"has the device been given a chance to take this yet?"* and is
**not** an answer to *"did it take it?"*. The second question is what `verify` is for - which
returns this record to its own finding: `verify` must read the **medium**.

## 6. The pull (Q1027, Q1030-Q1035)

⚠ **NOT the briefed measurement.** `backup --apply` ended **10:05:24**; the pull was **11:16:14**.
Nothing was running, no catalog write was open, writeback had completed (system-wide Dirty was
10 MB). **Nothing printed and there is no exit code**, because nothing was executing. The
sequencing error is the recorder's: a nine-minute backup was promised and it returned in 4.74 s,
so by the time the stick was pulled there was nothing left to interrupt.

### What the kernel said

```
11:16:14  usb 1-2: USB disconnect, device number 13
11:16:14  Buffer I/O error on dev sda1, logical block 0, lost sync page write
11:17:59  exFAT-fs (sda1): Volume was not properly unmounted. Some data may be corrupt.
          Please run fsck.
```

**Block 0 is the volume header.** It remounted **`rw`**, not read-only: `errors=remount-ro` fires
on errors *during* operation, not on a dirty flag at mount.

### 🔑 4.3 GB and 4,299 deleted files came back

| folder | files | size |
|---|---|---|
| `2014` | **2,110** (was 1,913) | 6,093 MB (was ~5,200) |
| `A 1` … `A 13` | 1,125 | 1,440 MB |
| `IV Bangalore` | **1,064** | 2,348 MB |
| `soak10` | 838 - exactly what was written | 1,579 MB |

Nobody touched the stick between the pull and the measurement; it sat on the desk. **exFAT has no
journal**, the deletions' directory entries and allocation-bitmap updates were in the kernel's
cache, the volume-header write was lost, and the on-medium metadata reverted to a pre-deletion
state. **The damage was entirely metadata, and not one byte of file content was wrong** - exactly
what a lost header write predicts on a device whose own write cache is disabled.

### And every byte of the soak data survived (Q1031-Q1033)

Cold - the medium genuinely read, at 23 MiB/s over ~30 s:

| | `soak10/drive` | `soak10/backup` |
|---|---|---|
| catalog rows | 356 | 356 |
| **hash matches** | **356** | **356** |
| MISSING / ZERO-LENGTH / TRUNCATED / MISMATCH | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| on the medium with no catalog row | 0 | 0 |

`truestill verify` cold agreed: **356 verified, 0 missing, 0 mismatch on both**, in 36.52 s and
35.43 s. **The feared outcome - a truncated file under a clean `verify` - does not exist here.**
It says nothing about a pull during a write.

### Convergence (Q1034)

Re-running the backup: **`0 file(s) to copy, 0 MB`** in 0.30 s, 358 files still on the target, no
duplication. 🔑 **And it names its own limit unprompted**: *"That is a comparison of records, not a
fresh look at the drive. To check what is really there: truestill rescan …"*

### Do `rescan` and `verify` meet the state (Q1038)?

**Yes, both, and well.** Constructed on the backup drive: one recorded file made to vanish, one
file whose content nothing has ever hashed added.

```
  ON THE DRIVE, NOT IN THE CATALOG: 1      NOT ACCOUNTED FOR: 1
      Saved/2013/resurrected-unknown.jpg       2011/…/20111108_220924_Photo0264.jpg
```

`verify` reported `MISSING 1` and **exited 1**. `rescan` disclaims itself correctly - *"It answers
WHERE your files are, never whether their contents are still good"* and *"No command repairs any
of the above yet."* Repair is `(abn)`, already filed and open.

#### ⚠ THE NEAR-MISS, PUT WHERE A READER MEETS THE TEST THAT PRODUCED IT

**The first probe was wrong and passed.** It "added a file the catalog has never seen" by copying
the **vanished file's own bytes**. `rescan` hashed it, recognised it, and reported:

```
  MOVED: 1
      2011/…/20111108_220924_Photo0264.jpg  ->  Saved/2013/stray-resurrected.jpg
```

**That is correct, and it answers a different question than the one asked.** Written up as it
stood, this record would have said *"`rescan` reports a resurrected file as a move"* - a false
finding about a command that had behaved perfectly. The second probe used content nothing had ever
hashed, and got the two-sided answer above.

🔑 **A constructed test that answers a different question than the one asked is how a false
finding ships**, and the tell was that the answer was too tidy: a resurrected directory entry has
no reason to carry the bytes of the file that went missing beside it. `ENGINEERING_STANDARD.md`
§4's fifty-fourth member is the instrument-silent case; **this is its twin - the instrument that
speaks, clearly, about something else.**

⚠ **BUT THE ACTUAL DAMAGE WAS OUT OF SCOPE.** The resurrected folders landed at the **volume root**,
outside every registered drive directory, so no truestill command would ever look at them. Not a
defect - a scope fact, and the reason this soak's real damage is invisible to the product.

### Q1035, and what could not be run

`errors=remount-ro` did **not** trigger. The drive marker and decisions document are still valid
JSON on both drives, and both drives verified clean. ⚠ **The read-only `fsck.exfat -n` was not run
at the time this section was written** - it needs root - **and it was run later the same day; see
the addendum at the end of this record, which is the finding this section could not reach.** ⚠ **udisks2 auto-mounted the volume `rw` on re-insertion before anything could be
captured**, and a later clean unmount cleared the dirty flag - so *"not properly unmounted"* now
exists only in the preserved kernel log.

## 7. What was NOT run, and what a real mid-write pull would cost

- **The mid-write pull.** `organize` and `backup` both return before the device has the bytes, so
  **there is no window to aim at** unless the write is large enough to hit the kernel's dirty
  throttle. This machine has 30 GB RAM and `dirty_ratio = 20%`, so a writer blocks only after
  **~6 GB**. The stick has ~8.6 GB free. **A ~7 GB run would genuinely block in writeback and stay
  pullable for over an hour at 1.34 MiB/s.** That is the only honest way to stage it on this
  hardware, and it is the maintainer's call whether to spend the hour.
- **`restore`** - no named trips or events existed to restore, because naming needs the app and
  this soak was CLI-only. The decisions document round-tripped as a *file*; its *content* was
  never exercised.
- **`fsck.exfat -n`** - needs root, see above.
- **exFAT via FUSE** - not installed on this machine, so every result here is the kernel driver's.
- **Windows or macOS against this stick** - the reserved-name and 260-character halves of `(aid)`
  remain unreachable from here.

## 8. Findings filed

Ranked at the top of this record, with the reasons; repeated here as the index.

| rank | letter | what |
|---|---|---|
| **1** | **`(aiz)`** | the durability window of §5 - **`backup`** reported the copy made ~90 seconds of device time into a nine-minute write, and both instruments nominated to own durability read the page cache |
| **2** | **`(aiy)`** | `status` calls two registrations on **one physical device** "nicely redundant". `st_dev` is consulted in `service/organize.py` and `run_health.py`; **`drive.py` never asks** |
| 3 | `(aid)` | dated update: the character half **reproduces on Linux exFAT** with `EINVAL`; the reserved-name half does **not**; and a **trailing dot is silently stripped while `exists()` returns `True`** |

**Nothing was fixed.** `(aie)` and `(ain)` are left exactly as they are: both are correct, and §3
records only that this filesystem cannot exercise either.


---

## ADDENDUM 2026-08-31, after this record was committed: `fsck` calls it CLEAN

**Run by the maintainer with root, before the device was wiped for soak eleven** - the last chance
to ask the filesystem what it thought of the pull. `-n` is `--repair-no`: reports, changes nothing.

```
$ sudo fsck.exfat -n -v /dev/sda1
exfatprogs version : 1.3.2
label: DAMON_16GB
sector size:  512.00 B    cluster size: 32.00 KB    volume size: 14.58 GB
/dev/sda1: clean. directories 113, files 5137
```

🔑 **CLEAN, OVER 4,299 RESURRECTED FILES.**

**The two counts agree exactly, and are reconciled here so they do not read as a contradiction.**
`fsck` counts **5,137 files and 113 directories** - it reports the two separately. This record's
manifest counted **5,250 ENTRIES**, files and directories together. **113 + 5,137 = 5,250.**
So `fsck`, the kernel and the manifest agree completely about what is on the volume.
**They agree on a state the user deleted.**

**"Clean" is the interesting result here, not a boring one, and it explains the whole record.**
The pull did **not damage** exFAT. It rolled the metadata back to a **pre-deletion state that is
perfectly valid** - directory entries, allocation bitmap and file sizes all mutually consistent,
because they are a **coherent older snapshot** rather than a broken newer one. **That is why
nothing was lost and why `fsck` has nothing to repair**: there is no inconsistency to find.

`fsck` answers *"does this metadata contradict itself?"* and the answer is no. It cannot answer
*"is this what the volume was last told?"* - **nothing on the medium records that**, which is what
having no journal means.

⚠ **So "fsck says clean" must not be read as "the pull cost nothing".** It cost 4.3 GB of deletions
and there is no instrument on the medium that can see it. §6's file-content result - 712 of 712
byte-identical - is the real reassurance here; this line is not.

⚠ **AND THE HONEST LIMIT ON THIS EVIDENCE**: by the time it ran, the volume had been cleanly
unmounted and remounted several times since the pull, so the **volume-dirty flag was already
cleared**. This verdict is about structural consistency only. The dirty flag itself is recorded
where it was seen - in the kernel log, at re-insertion.
