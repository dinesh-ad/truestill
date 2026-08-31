# Soak eleven - the interrupted write, on real removable media

**Ran 2026-08-31 (P166). A record: never rewritten to match the present.** Soak ten measured a
pull of a **quiesced** device and left the interrupted-write case unmeasured. This is that case.

**Machine**: Linux 7.0.0-15-generic x86_64, 16 cores, 30 GB RAM, `dirty_ratio` 20%, Python 3.14.4.
**Device**: SanDisk Cruzer Blade, serial `4C530001181103118490`, `/dev/sda1`, **re-verified by
serial and label immediately before every destructive command**.
**Evidence**: `/data/TruestillLibrary/soak-eleven-2026-08-31/`.

## 🔑 WHAT HAPPENED, IN PLAIN WORDS, BECAUSE NO SINGLE ENTRY SAYS IT

The three letters below each describe **one mechanism**. None of them states the path a person
actually walks, and that path is the finding:

> `organize --apply` said **2062 organized**. **1,223 were true.**
> The stick was pulled. **836 photographs are now zero bytes.**
> The obvious remedy - plug it back in, run it again - reported
> **"2,068 already on this drive"** and **exit 0**, and **repaired nothing**.
> Only `truestill verify` dissents, and only if the user knows to run it.

**Every automatic path reports success.** That sentence is the finding; `(aja)`, `(ajb)` and
`(aiz)` are its parts.

## THE FINDINGS, RANKED

1. **`(aja)`** - the re-run refuses to repair what the interruption broke, **because the row
   written too early tells it there is nothing to do**. §4.
2. **`(ajb)`** - `rescan` holds the recorded size and stats the real one and **compares neither**,
   and its disclaimer tells the user size would not help. §5.
3. **`(aiz)`** (already filed, soak ten) - reproduced here **as loss rather than as a window**. §3.

## 1. Pass 1: exFAT, and the refusal table reproduces exactly

Kernel driver (module `exfat`; no `mount.exfat*` binary on this machine), fresh volume, label
`SOAK11`, `rw,nosuid,nodev,relatime,uid=1000,gid=1000,fmask=0022,dmask=0022,iocharset=utf8,errors=remount-ro`.

**All 26 probes gave soak ten's answers on a clean filesystem** - `chmod` **IGNORED** at `0755`,
`utime` exact, **10 ms** granularity, eight characters `EINVAL`, **trailing dot silently
stripped**, **case-insensitive**, symlink/hardlink `EPERM`, xattr `ENOTSUP`, 255 OK / 256
`ENAMETOOLONG`, `f_files = 0`. **Soak ten's table was taken on a 77%-full volume carrying another
library; it is now confirmed a property of the filesystem, not of that volume.**

⚠ **One number moved and it is fragmentation, not the medium**: sustained write + `fsync` was
**1.34 MiB/s** at 77% full and is **3.21 MiB/s** fresh. Read is **19.7-23.3 MiB/s** either way.

## 2. The mid-write pull - staged so there was something to interrupt

Soak ten could not stage this: `organize --apply` returns before the device has the bytes, so
there is no window to aim at. **The fix is to exceed the kernel's dirty throttle** - 20% of 30 GB,
so a writer blocks after ~6 GB. Source: **2,570 real photographs, 6.71 GiB**, staged on ext4.

At the moment of the pull: `organizing: 1453/2547`, **3.5 GB dirty in RAM**, process alive and
blocked. **That is the state soak ten never reached.**

### What the product did (Q1053), and it did well

```
     2062  organized          6  duplicate, skipped
        1  failed           478  not attempted        RUN EXIT=4
```

**Exit 4, not 0.** It stopped rather than failing 478 more times, and **said it had stopped** -
`478 not attempted` is `(aim)`'s divergence line working. The failure named the file, the target,
the cause, the byte count and the orphaned staging path. **The catalog survived**:
`PRAGMA integrity_check` = `ok`, 2,062 rows.

⚠ **`(aid)`'s wording defect reproduced with a new errno** - *"…the drive stopped responding part
way through 5,255,328 bytes of it are still at…"*: two sentences run together, the number reading
as part of the first. Filed there as a second instance.

### What the medium actually held (Q1054), cold

```
catalog rows      : 2,062        MISSING     :   2
OK (hash matches) : 1,223        ZERO-LENGTH : 836
TRUNCATED         :     0        MISMATCH    :   1
read 2,500 MiB in 109.0s -> 22.9 MiB/s   COLD (the medium was read)
```

**839 of 2,062 claimed copies are damaged - 40.7%.** The kernel logged it as it happened:
`lost async page write` on blocks from **6,187 to 5,288,576** - data blocks, gigabytes apart, where
soak ten lost only block 0.

⚠ **fsyncgate observed rather than quoted.** Those pages are neither written nor still dirty. A
later `sync()` would return success over data that no longer exists - exactly the caveat `(aiz)`
carries in prose.

### 🔑 Does `verify` catch every one? (Q1055) YES - 839 of 839

**Checked by set intersection of paths, never by count**, because a miss can hide inside a
matching total:

```
my independent hash check flagged : 839      verify flagged : 839
DAMAGED FILES verify DID NOT FLAG :   0      exit code 1
```

**`verify` is sound, including the one file no size check could find.** It is the only instrument
here that dissents, and everything that ran before it reported success.

## 3. `(aiz)` reproduced as loss, not as a window

Soak ten filed `(aiz)` on a window with nothing lost inside it. **This is the same window with a
pull inside it**, and the result is 839 damaged copies against 2,062 confident rows. The entry's
"what this does not claim" section - *"nothing was lost… the loss is conditional on a pull inside
it, and that pull is unmeasured"* - **is now measured, and the condition was met.**

## 4. 🔑 `(aja)`: THE RE-RUN REPAIRS NOTHING (Q1057)

Same source, same destination, stick back in:

```
     2069  duplicate, skipped        467  organized
       11  organized (renamed)             2,068 already on this drive
RERUN EXIT=0
```

Re-stat'ed cold against the recorded list of 839 damaged paths:

```
STILL ZERO-LENGTH : 836      STILL MISSING : 2      now non-empty : 1
```

**838 of 839 are exactly as the pull left them.** The one "now non-empty" is the MISMATCH file,
which was never zero and is still the wrong bytes.

**The row written too early is the same row that suppresses the repair**: dedup trusts
`file_copies`, and `file_copies` is precisely what the interruption falsified.

⚠ **And the re-run's arithmetic is internally honest, which makes it worse.** `467 + 11 = 478`,
**exactly** the `not attempted` count from the interrupted run. **It converged perfectly on work it
had never started and not at all on work it had recorded wrongly.** Those are two different
properties and only the first holds - so a reader checking the numbers concludes it worked.

## 5. `(ajb)`: `rescan` HOLDS BOTH SIZES AND COMPARES NEITHER

```
  in place           : 2538, where the catalog says they are    <- includes all 836 zero-byte files
  NOT ACCOUNTED FOR: 2
  LEFT BEHIND BY TRUESTILL: 1   (the .partial)
  time taken         : 0.28 s
```

**Prediction 3 HIT** - both truly-missing files found, and the `.partial` message is the
counter-example proving the product can do this well: *"a run was interrupted while writing these
- a disk that filled, **a drive pulled out**, the process killed. They are not your photos: delete
them."*

**But `2538 in place` includes every zero-byte file.** The catalog records a size for **2,540 of
2,540** rows; the walk stats to enumerate; and `reconcile()` takes `on_disk: Collection[str]` -
**paths only**, under *"Pure: no I/O"*. **A size comparison would have caught 836 of 839 in that
same 0.28 s, reading not one byte.**

⚠ **And the disclaimer talks the user out of it**: *"Silent damage to a file changes neither its
name nor its size, so only `truestill verify` can find it."* **True of bit-rot, false for what an
interrupted write actually produces** - 3,554,132 bytes became 0. It is the sentence a user reads
when deciding whether the fast check was enough.

## 6. `fsck`, and the prediction it falsified (Q1058)

```
/dev/sda1: corrupted. directories 56, files 1906
/dev/sda1: files corrupted 1, files fixed 0
```

**Predicted "clean"; it says corrupted, one file. MISS - and the corrected statement is stronger:**

> 🔑 **`fsck` measures agreement between metadata and metadata. The 836 destroyed photographs agree
> with themselves** - entry says 0 bytes, allocation says 0 clusters, and `st_blocks = 0` on all
> 837, so the data is **gone, not orphaned; nothing to recover**. There is nothing for a
> consistency checker to object to. **Only the catalog, which lives outside the filesystem, knows
> they should be 3.5 MB each.**

**That is `(ajb)`'s real argument**: the filesystem's own checker *structurally cannot* find this,
so `rescan` comparing the size it already holds against the size it already stats is not a
convenience - **it is the only thing that can.**

### ⚠ AND `files 1906` IS NOT A COUNT OF THE VOLUME

The medium holds **2,541 files / 56 directories** (excluding root, which `fsck` also excludes -
the directory counts reconcile **exactly**). The 635-file gap is **one directory**:
`2014-08-15 - Everyday` holds **exactly 635 files**, and it is the directory with the corrupted
entry. **`fsck` never traversed its contents**, and the numbers were **stable across two runs**, so
this is a silent skip rather than a halt.

**A user reading `files 1906` has no way to know 635 were never examined.** Same shape as
everything else here: an instrument reporting a number that means less than it appears to.

## 7. Method note, recorded because it cost two round trips

⚠ **CHECK WHAT POLKIT ALREADY PERMITS BEFORE DECLARING SOMETHING NEEDS ROOT.** Both
`org.freedesktop.UDisks2.Block.Format` and `org.freedesktop.UDisks2.Filesystem.Check` run **without
a password** for an active local session on removable media - `Check` invokes `fsck.exfat` and
returns its output verbatim. Soak ten's `fsck` was reported as needing root and did not; so did
this one, twice. `pkcheck --action-id org.freedesktop.udisks2.modify-device --process $$` answers
in one command.

## 8. Predictions, scored (Q1056)

| # | prediction | verdict |
|---|---|---|
| 1 | truncated files | **MISS** - 0 truncated, **836 zero-length**. Reasoning from "interrupted write ⇒ partial file" describes how ONE file fails; at batch scale the loss lands on whole files, not inside them |
| 2 | `verify` catches every one | **HIT** - 839/839 by set intersection |
| 3 | `rescan` reports the unaccounted | **HIT** - and it reported 836 ruined files as *in place* |
| 4 | convergence repairs rather than skips | **HIT ON THE DANGER** - the named risk, *"a file skipped because a row exists"*, happened 838 times |
| 5 | `fsck` says clean | **MISS** - corrupted, 1 file; and the corrected statement is better than the hit |
| - | a **size-correct, content-wrong** file | **NOT PREDICTED, 1 occurred** - the only failure here that defeats every cheap check |

**Two misses and an unpredicted case, which is the useful part of the run.**

## 9. What was NOT done

- **Passes 2 and 3 - NTFS and FAT32 - are not in this record.** Pass 1 alone produced three
  findings and they were filed before a reformat could wipe the evidence they rest on.
  ⚠ **NTFS has a journal and may behave completely differently, and that difference is the
  measurement**; FAT32's **4 GiB per-file ceiling** is untested and no test has ever met it.
- **`(aiz)` on NTFS and FAT32** - so it remains a measurement on one filesystem, and whether it is
  a product property or an exFAT interaction is **unresolved**.
- 🔑 **NOTHING WAS A TRIP OR AN EVENT, AND NOTHING COULD BE** (Q1059). Checked, not assumed:
  `grep -rn "commit_trips|assemble_trip_review|propose_trips" packages/truestill-cli/src/` returns
  **0** - there is no trips path in the CLI at all - and neither soak passed `--events`. Both
  catalogs confirm it: `trips=0 trip_days=0 events=0`. **Naming is app-only and both passes were
  CLI-only, so it is not that the corpus produced no trips - nothing ever asked.** What that
  leaves untested is wider than trips:
  - **trip and event folder rendering** - every path measured was `Everyday`, never
    `2014-08-15 - Corsica`;
  - **`rename`** - `(aix)`'s whole arc, shipped 2026-08-30, **has never met a real filesystem**;
  - **the decisions document's CONTENT** - it round-tripped as a *file* on exFAT, always empty
    (`trips: []`, `events: []`), so `(ahz)`'s guard and `(aix)`'s lease had nothing to protect;
  - **`restore`** - and this is why.

  ⚠ **`restore` HAS NOW GONE UNTESTED ACROSS SOAKS TEN AND ELEVEN BOTH, AND THAT IS A GAP RATHER
  THAN A LINE ITEM.** **Two soaks, three filesystems, three physical mid-write pulls - and the
  recovery command has never run on removable media at all.** In soak ten there was nothing to
  restore because no names existed; in pass 1 here the same; and by pass 2, when a real trip
  finally existed and had been renamed through the app, the pull damaged the drive and the arc
  moved on. **`restore` is the command a user reaches for at exactly the moment these soaks
  manufacture** - a drive that was interrupted, a catalog that may be wrong about it - and it is
  the one command none of this has exercised. [`soak-six-record.md`](soak-six-record.md) covers the
  rebuild drill on a **fixed disk**; **nothing covers it on a stick.**
  ⚠ **It also sharpens soak six rather than repeating it**: that run measured what a lost catalog
  costs *because names existed*. Ten and eleven measured the durability of files whose names are
  **all machine-derived** - the recoverable half. The irrecoverable half was never on the stick.
- **The app** - every command here was the CLI.


## 10. A shape a user would misread, found while reading the tree (Q1060)

```
635  2014-08-15 - Everyday        736  2014-08-16 - Everyday
656  2014-08-17 - Everyday         31  2014-08 - Everyday
```

**A month folder beside three day folders, and it is correct.** All 31 files in the month bucket
carry a **full day-precision date**, `2014-08-14` - not month precision, not `year_only`. The rule
is **volume, not precision**: `layout.py`'s `DEFAULT_EVERYDAY_DAY_THRESHOLD = 40`
(`adaptive-day-folder-research.md`, OnePoll/Mixbook ~23 per occasion, ~20 per day). 31 ≤ 40 stays
in the month bucket; 635, 737 and 656 each earn a day folder. Backlog `(gg)`'s shape, working.

⚠ **But nothing on disk explains it.** Standing in `2014-08/`, the natural inference is *"the month
folder holds the ones with a vaguer date"* - which is **wrong**, and was the first reading this
soak's reviewer made. The folder names carry no clue that a **count** decided it. The threshold is
settable (`layout.everyday_day_threshold`), but a folder tree is what a user reads when they have
forgotten the setting exists. **Recorded, not filed**: it is a legibility question about a
deliberate design, not a defect in it.


---

# PASS 2: NTFS, and pass 3: FAT32

## The three refusal tables side by side (Q1047)

**Driver (Q1050): udisks2 chose `ntfs3`, the KERNEL driver** - no `ntfs-3g` process, though the
FUSE binary is installed - mounted with **`acl`**, which is why permissions behave.

| probe | ext4 | exFAT | **NTFS `ntfs3`** | **FAT32 `vfat`** |
|---|---|---|---|---|
| `chmod(0o600)` | OK | **IGNORED** | **OK** (`acl`) | **IGNORED** |
| `utime` exact | OK | OK | OK | OK |
| mtime granularity | 1 us | 10 ms | sub-ms | ⚠ **2 SECONDS** |
| atime | full | full | full | ⚠ **DATE ONLY** - asked `1200000000`, got `1199923200` (midnight) |
| `:` `?` `*` `\|` `<` `>` `"` `\` | OK | **EINVAL** | ⚠ **ALL CREATED** | **EINVAL** |
| trailing dot | OK | **stripped** | **kept** | **stripped** |
| `nul.jpg` | OK | OK | OK | OK |
| 255 / 256 bytes | OK / E36 | OK / E36 | OK / E36 | OK / E36 |
| case | sensitive | **INSENSITIVE** | **SENSITIVE** | **INSENSITIVE** |
| symlink / hard link | OK | EPERM | **both OK** | EPERM |
| xattr | OK | ENOTSUP | **OK** | ENOTSUP |
| cluster / `f_files` | 4 K / real | 32 K / **0** | 4 K / **0** | 8 K / **0** |

🔑 **P166's brief said exFAT had "2-second timestamp granularity". FAT32 does; exFAT stores 10 ms.**
The premise was right about the family and wrong about the member, and it took three passes to
place. **FAT32's atime is worse than the brief supposed** - not coarse but absent, a date with the
time discarded.

🔑 **AND `(aid)`'S CENTRAL CLAIM IS FALSE FOR NTFS** - all eight characters created verbatim under
`ntfs3`. **exFAT and FAT32 are the strict filesystems; NTFS-under-Linux is the permissive one.**
Filed as `(ajc)`: a name that writes fine on Linux and cannot be opened on Windows is a different
hazard from one that refuses at write time, and `moving-machines.md` is its home.

## The NTFS pull

`organize` (2,540 files), a trip named **through the app's own HTTP routes**
(`/api/events/propose` -> `/apply`), `migrate-layout` placing 2,059 files into
`2014-08-14 - Wayanad/`, then `truestill rename` - **`(aix)` on a real filesystem for the first
time since it shipped**.

🔑 **`(aix)`'S CENTRAL PROPERTY, MEASURED MID-FLIGHT.** 45 seconds in, 2,059 photographs moving:

```
catalog trip name : ['Wayanad']            <- STILL THE OLD NAME
leases            : {}                     <- not yet written
pending journal   : 1963                   <- intent recorded before the moves
on disk: 2014-08-14 - Wayanad (1963)  +  2014-08-14 - Wayanad Monsoon 2014 (97)
```

Every clause held: journal before the move, **name flips LAST**, lease written in the same
transaction as the flip (so `{}` while nothing is flipped), and a half-moved folder telling the
truth. Until now this was shown only by an injected failure and an `os._exit` kill on a 12-file
ext4 fixture. **On completion**: 2,059 moved, name flipped, lease `('trips', <day set>) ->
'Wayanad'` - **the OLD name**, which is `--force-with-lease` exactly as designed - and the drive's
document republished.

⚠ **A rename is NOT a fast metadata operation here**: 2,059 files took **~29 minutes**, the same
rate as the copy. A user renaming a four-day trip waits half an hour behind a counter with no
estimate.

### 🔑 The journal changes the damage, and that is the pass's finding

| | exFAT | **NTFS** |
|---|---|---|
| zero-length files | **836** | **0** |
| missing / unreadable | 2 | **304 UNREADABLE** ("stat refused") |
| mismatch (size right, bytes wrong) | 1 | **1** |
| the volume afterwards | remounted **rw**, silently | ⚠ **REFUSED TO MOUNT** - *"volume is dirty and force flag is not set"* |
| source drive | - | **2,540 of 2,540 byte-identical, cold** |

**exFAT kept the entry and lost the data - a file that exists and is empty. NTFS rolled the
incomplete entries out of existence.** A missing file is honest; a zero-byte file is a lie. And
NTFS **locked the door** rather than letting the user back in to a quietly ruined library - which
is digiKam's *"a loud refusal, never a divergence"*, arriving from the filesystem rather than the
product.

⚠ **`verify` was more precise than this soak's own instrument.** It reported `MISSING 0,
UNREADABLE 304`; the check script reported `MISSING 304`, because `Path.exists()` returns `False`
when `stat` **raises**. The product distinguished a case the measurement flattened.

## Q1051: `(aiz)` reproduces on NTFS - it is a PRODUCT property

429 rows written, **124 files actually on the medium**. `backup` recorded **305 custody claims for
bytes that never landed**, exactly as on exFAT. **Not an exFAT interaction.**

## Q1049 on NTFS: the re-run does not lie, it dies

See `(aja)`'s NTFS section and `(ajd)`.

## 🔑 PASS 3: THE 4 GiB CEILING - FOUR PREDICTIONS, ALL WRONG, IN THE GOOD DIRECTION

**The field research said nobody preflights**: `rsync` discovers `EFBIG` at the write, Windows names
it at the boundary, and `robocopy` - the only tool that preflights anything - preflights **volume
space, not per-file size**. Predictions were written from that.

A 4,582,842,624-byte file (4.268 GiB, 288 MB over `2^32-1`) built from a real phone video:

```
====================================================================================================
THIS DESTINATION CANNOT HOLD THIS RUN
====================================================================================================
  These files are too large for this drive (vfat): BIG_VIDEO_over_4GiB.mp4 (4.6 GB). Drives
  formatted FAT32 cannot hold a single file of 4 GB or more, however much free space they show.
  Use a drive formatted exFAT or NTFS for these.
EXIT=4     19:52:50 -> 19:52:51
```

| # | prediction | verdict |
|---|---|---|
| 1 | no preflight, fails at the boundary after ~21 min | **MISS** - **1 second, 0 bytes written** |
| 2 | `EFBIG` reaches the user as raw OS words | **MISS** - never reaches an errno |
| 3 | reported per-file, run continues | **MISS** - the whole run refused up front |
| 4 | a ~4 GiB `.partial` orphan left behind | **MISS** - nothing staged |

**`organize` does the thing no tool in the field does**, names the file, the size and the
filesystem, explains *"however much free space they show"* - the exact confusion in every forum
thread - and gives the remedy.

### ⚠ AND `backup` DOES NOT SHARE THE PREFLIGHT

Same file, same destination, same product:

```
From 'ext4 source' to 'FAT32 target': 2 file(s) to copy, 4.6 GB.
Preview only. Nothing was copied. Re-run with --apply to make the backup.
```

**No warning. An invitation to proceed.** Under `--apply` it wrote to exactly `4,294,967,295` bytes
- `2^32-1`, the ceiling to the byte - and then **blocked in `rq_qos_wait`** for ~15 further minutes
flushing ~1.9 GB of dirty pages belonging to a file that can never exist.

| | `organize` | `backup` |
|---|---|---|
| decision | **1 s**, before any I/O | ~10 min to reach the wall |
| written to the stick | **0 bytes** | **4.0 GiB, all discarded** |
| time to tell the user | **1 s** | **~26 min**, most of it after the answer was known |

🔑 **The cache makes the mistake cheap to make and expensive to learn about.** This is `(ajd)`'s
third instance: `organize` careful, `backup` not, on a command people run when they are already
worried.

## 🔑 THE THIRD PULL: FAT32, AND THE WEAKEST FILESYSTEM LOST THE LEAST

`organize --apply`, 2,570 files, pulled at `organizing: 150/2547`.

```
      158  organized      5  duplicate, skipped
        2  failed      2382  not attempted        EXIT=4
FAILED: final.jpg: … 'the drive is not there any more'
FAILED: gkkk.jpg:  … 'the drive stopped responding part way through'
```

⚠ **Two different sentences for two different failures** - one never opened, one died mid-write.
Better errno classification than this record had been giving `organize` credit for.

**The kernel at the pull:**

```
FAT-fs (sdb1): Directory bread(block 8423621…8423630) failed
FAT-fs (sdb1): unable to read boot sector to mark fs as dirty
FAT-fs (sdb1): bread failed in fat_clusters_flush
```

⚠ **A prediction made and withdrawn the same hour.** *"It could not mark itself dirty, so it may
mount clean while damaged"* - **wrong**: vfat sets the dirty bit **at mount** and clears it on a
clean unmount, so the failed write was an attempt to **re-assert** it. The pull could not
**un**-mark it, which is the safe direction, and re-insertion warned correctly.

| | dirty flag | mounted afterwards |
|---|---|---|
| NTFS | set | ⚠ **REFUSED** until repaired |
| exFAT | set | `rw`, silently |
| FAT32 | set **at mount**; the pull could not clear it | `rw`, with a warning |

### The damage, all three side by side

| | exFAT | NTFS | **FAT32** |
|---|---|---|---|
| zero-length | **836** | 0 | **38** |
| unreadable / missing | 2 | **304 unreadable** | 1 |
| mismatch (size right, bytes wrong) | 1 | 1 | **0** |
| **dirty in RAM at the pull** | 3.5 GB | 2.7 GB | ⚠ **16 MB** |

🔑 **THE WEAKEST FILESYSTEM LOST THE LEAST, AND NOT BECAUSE IT IS STRONGER.** FAT32 produced
exFAT's failure - zero-byte files, because both keep the directory entry - but far fewer, because
**udisks2 mounts vfat with `flush`** and only 16 MB was ever in flight. **The size of `(aiz)`'s
durability window is set by the mount options, not by the product and not by the format.** Q1051's
third answer. No cross-linked clusters and no FAT1/FAT2 divergence appeared; the specific "worse"
predicted did not happen.

### The three instruments, ranked by what they could tell the user

```
verify     : verified 119 | MISSING 1 | MISMATCH 38 | UNREADABLE 0   -> 39 of 39, BY NAME
fsck.vfat  : (false,)  the volume is not consistent                  -> "somewhere"
rescan     : in place 157 | NOT ACCOUNTED FOR 1                      -> 1 of 39
```

🔑 **The filesystem's own checker dissents where `rescan` does not** - `fsck` says the volume is
broken while `rescan` says everything is where it should be. **In soak ten the relationship was the
other way round** (`clean` over 4,299 resurrected files). But it does not beat `verify`: **a
consistency checker can say the volume is damaged; only `verify` can say which photographs.** That
is `(ajb)`'s argument in one line - the cheap check should catch these, because the filesystem's
cheap check can only say *"somewhere"*.

⚠ **Limit**: udisks2 returned a bare boolean for vfat where it passed exFAT's text through, so
**there is no detail on what `fsck.vfat` found** - no cluster or FAT-copy comparison. `sudo
fsck.vfat -n -v` would settle whether the damage is the FAT table or only the dirty flag, and was
not run.

## ⚠ METHOD: AN INSTRUMENT OF THIS SOAK'S OWN, AND IT LIED

The check script labelled a genuinely cold read **`WARM - page cache`**. The label is a **duration**
threshold (`>10s`); 199 MiB at device speed takes 8.9 s. **The RATE is the tell** - 22.4 MiB/s is
the medium, 151 MB/s was RAM - and the threshold works only for large datasets. **Same class as
every product finding here: an instrument reporting a number that means less than it appears to.**

## ⚠ METHOD: A WATCHER'S LIFETIME MUST BE TIED TO THE WORK, NOT TO ONE COMMAND

**Three failures in one day, the same shape each time:**

- a poller **alive 5h 31m** after the process it watched was killed, waiting for a string that
  could never arrive;
- **25 minutes idle** after `rename` finished, because the next step was described in a message and
  never launched;
- **2h 16m idle** after the heartbeat exited **on schedule** when its one command completed,
  leaving three further steps unwatched and then nothing at all.

**Each was invisible from the outside**: a report about a finished step looks exactly like a report
about a running one. **The maintainer found all three, twice by asking "is anything running?"**

**The fix is structural** - a heartbeat that runs until explicitly stopped and prints
`NOTHING RUNNING` when no process matches, rather than one that exits when a command does. A soak
on a 3 MiB/s medium is mostly waiting, and waiting is exactly when a silent stall is
indistinguishable from progress. ⚠ **And stop it deliberately when device work ends**: a heartbeat
ticking `NOTHING RUNNING` through an hour of document-writing teaches the reader to ignore it.

## ⚠ METHOD: CHECK WHAT POLKIT ALREADY PERMITS BEFORE DECLARING SOMETHING NEEDS ROOT

`org.freedesktop.UDisks2.Block.Format`, `.Filesystem.Check` and `.Filesystem.Repair` all run
**without a password** for an active local session on removable media, and `Check` returns
`fsck`'s output verbatim. **This soak declared root necessary three times when it was not**, costing
the maintainer round trips. `pkcheck --action-id org.freedesktop.udisks2.modify-device --process $$`
answers in one command. ⚠ **The genuinely root-bound steps were `mount -o force` and `umount`** -
blocked by udisks2 policy (`OptionNotPermitted`) rather than by file permissions, which is the
distinction to draw. **`ntfs-3g` being setuid did NOT help**: it is past the binary check and still
fails on the device node without group `disk`.
