# (ala) TWO SPELLINGS OF ONE PATH WERE TWO FILES, ON THE TWO PLATFORMS MOST USERS ARE ON.

*Body of backlog entry `(ala)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## THE DEFECT, AND THE RECORDED SYMPTOM WAS WRONG

`rescan.reconcile` is `Pure: no I/O`, so it compared the catalog's `relative` against the walk's
output as exact strings. On NTFS and APFS `Saved/Photo.JPG` and `Saved/photo.jpg` are **one
file**, and the comparison called them two.

⚠ **`SHIPPED.md`'s own case-insensitivity row and the audit that raised this both said the file
reports as *"both MISSING and STRAY"*. Run against a real drive it reports MOVED**, and measuring that changed what the fix had
to cover:

```
  MOVED: 1
      Saved/2013/2013-08/20130805_190106_26446.jpg  ->  ...26446.JPG
```

The drifted name is not in `recorded`, so it becomes a **candidate**, gets hashed, and its
content matches - so `reconcile` pairs it. The harm is therefore not a wrong bucket:

1. **A wall of phantom `MOVED` lines** for files that never moved, and `reconciled=False`, so the
   command exits **1**. A scripted `rescan X && next_step` stops.
2. ⚠ **Every drifted file read in full.** `HashCache` is keyed by `str(path)`
   (`hash_cache.py:get`), so a drifted path misses the cache as well. That is the whole library
   re-hashed by the one command whose docstring justifies its design by *not* doing that -
   *"~15 h for 196 GiB at the 3.9 MB/s measured on a cloud mount"*.
3. **`(ajb)`'s damaged bucket silently empties**, because `sizes` is keyed the walk's way and
   `recorded_sizes` the catalog's - the 836-zero-byte-files regression.
4. Since `(akw)`, **`verify` writes a MOVED result**, so the phantom reaches the catalog. Measured:
   the row was rewritten from `.jpg` to `.JPG`. `verify` therefore *converges* on a folding
   filesystem; `rescan`, the cheap command, never does and pays the full read every time.

## THE CENSUS - 101 SITES TRIAGED, 20 REACHABLE

Found by AST over `packages/*/src/**/*.py`, 214 raw hits triaged to 101 genuine path-identity
sites: **20 REACHABLE, 41 ALREADY HANDLED, 40 NOT REACHABLE.**

🔑 **The finding worth more than the count**: the three worst sites are **the same comparison** -
a rendered or walked relative against `file_copies.relative` - written independently in three
packages with no shared helper. `compare_key` is now that helper.

**Fixed here (the rank-4 defect):** `rescan.py`'s five comparisons, `cli.py`'s PLACED subtraction,
and `app/service/drives.py:_unrecorded_files` - the app's structural twin, which had the same
invariant in its docstring (*"at that exact path"*) and nothing defending it.

⚠ **NOT fixed here, deliberately: `organizer.py:_free_relative`** (`relative == reclaimable`).
It is the highest-stakes site in the census - the one path in the product permitted to overwrite
an existing file - and **blanket folding there would destroy data on Linux**, because `A.jpg` and
`a.jpg` really are two files and the guard would authorise overwriting the wrong one. It needs the
probe too, and changing when the single sanctioned overwrite fires is not an edit to make in a
commit about a report. Filed with the other 16 in `(alb)`.

**Already handled, so the reader can tell handled from unhandled:** 41 sites, including
`layout.py`'s two casefolds, `migrate.py`'s `.lower()` target check, and the eight that ask the
filesystem instead of comparing strings (`samefile`, `reach`, `exists`). `drive_adoption.py` is
the only module that had already reasoned this through end to end.

⚠ **Zero `COLLATE NOCASE` anywhere in the schema.** Every TEXT column uses SQLite's default
`BINARY`. `file_copies.relative` is never a lookup predicate (it is matched on `sha256` +
`drive_uuid`), which is why the SQL exposure is smaller than it looks - but `albums.name` is, and
it is in `(alb)`.

## THE DECISION: (b) PROBE THE MOUNT, NOT (a) ALWAYS FOLD

The tool this research came from chose **always fold**, calling the Linux collapse *"unusual and
harmless"*. **Here it is neither, and the counter-example is what decided it.**

At `organizer.py:_free_relative`, folding unconditionally makes the overwrite guard fire when the
file at that path is **not** the recorded copy - so the one sanctioned overwrite lands on a
stranger's file. Their fix was for a cache diff where collapsing costs a redundant re-encode; here
it costs a photograph. **Blanket folding is not the same trade in a custody tool.**

The second reason is direction: with (a), `recorded={A.jpg, a.jpg}` and only `a.jpg` on disk
reports **PLACED** for both - a genuinely missing file reported as present. Silent loss is the one
direction this product refuses.

**So: `filesystem.folds_case`, which asks the mount.**

⚠ **READ-ONLY, WHICH IS A REQUIREMENT AND NOT A PREFERENCE.** The obvious probe - create two
files differing only in case - would break `rescan`'s own promise: *"Nothing was changed: not your
files, not the drive, not the catalog."* Instead it stats a name **the walk already returned**
with its case swapped and compares `(st_dev, st_ino)`. The kernel answers, which is the instrument
`reclaim`, `catalog_move` and `app_paths` already use for *"same file, not same string"*.

⚠ **THE FILESYSTEM TYPE DOES NOT DECIDE THIS, AND A TABLE WOULD HAVE BEEN WRONG ON THIS MACHINE.**
Measured 2026-09-16:

| mount | type | `folds_case` |
|---|---|---|
| `/boot/efi` | **vfat** | **True** |
| `/mnt/windows` | **ntfs3** | **False** - mounted without `nocase` |
| a loop-mounted `ntfs-3g` image | fuse | False |
| `/tmp`, `/data` | tmpfs, ext4 | False |

A table keyed by filesystem would have answered *"NTFS, therefore folds"* and been wrong about a
real NTFS mount on a real machine. **The mount decides; only the mount can be asked.**

**What it costs**: at most 32 `stat` calls, once per run, never per file - against a walk that has
already stat'd everything it returned. **`None` is a real answer** (every sampled name caseless),
and both callers fall back to exact comparison, which is today's behaviour and correct on Linux.
⚠ That corner is rarer than it looks: a test asserting `20140817_120000.jpg` cannot answer
**failed**, because the *extension* carries the case.

## `casefold`, NEVER `lower`, AND NEVER STORED

`["straße", "STRASSE", "strasse", "Straße"]` gives **one** key under `casefold` and **two** under
`lower`. German filenames are ordinary in a photo library.

⚠ **The folded form never leaves the comparison.** Unicode's own rule: *"case-folded text should
be used solely for internal processing and should not be stored or displayed"* - version 13 added
169 folding entries version 8 did not have, so a folded key in the catalog would mean something
different after a Python upgrade. Every bucket carries a spelling that came in; `placed` keeps the
**catalog's**, because nothing moved and there is nothing to re-record.

## NFD versus NFC - EXPOSED, A DIFFERENT FIX, AND OUT OF SCOPE

**Established, not assumed.** macOS HFS+ stores filenames decomposed, so `café.jpg` written there
is `café.jpg` while the same name written on Linux is `café.jpg` - different bytes,
identical case.

- ⚠ **`casefold` does not fix it**: `'café'.casefold() == 'café'.casefold()` is **False**.
  `unicodedata.normalize("NFC", ...)` does. **A different fix, not this one.**
- **Exposure, measured**: the maintainer's library is **0 of 2,587** filenames non-ASCII; the two
  format corpora are **4 of 10,818**, and **0 of those are decomposed** - because they were
  created on Linux and Windows, not on a Mac. So it is unreachable on every corpus this project
  can currently test against.
- **Out of scope for this entry, and said rather than folded in quietly.** It needs its own
  evidence - a macOS-written tree, which this machine has even less access to than a folding mount
  - and its own decision about whether normalising is safe on Linux, where the two forms are two
  genuinely different files and the same silent-loss argument applies. Filed as `(alb)`.
  The shape accommodates it: `compare_key` is the one place a second normalisation would go.

## THE PROOF, AND WHAT IS WEAKER ABOUT IT

⚠ **No unprivileged route to a writable case-insensitive mount exists on this machine**, and each
was tried rather than assumed:

| route | outcome |
|---|---|
| `ntfs-3g` (setuid root) | **mounts**, but rejects `ignore_case` - POSIX namespace, case-sensitive |
| `lowntfs-3g` (supports `ignore_case`) | **not setuid**: *"User doesn't have privilege to mount"* |
| `unshare --user --map-root-user --mount` + `mount -t vfat` | unprivileged user namespaces disabled: *"write failed /proc/self/uid_map"* |
| `ciopfs`, `fusefat`, `fuse2fs` | not installed |
| `mkfs.ext4 -O casefold` | image builds; mounting ext4 needs root |
| `/boot/efi` (vfat, folds) | root-owned `drwxr-xr-x` - readable, **not writable** |

**A real mount would need** `sudo mount -t vfat` (or `chmod u+s /usr/bin/lowntfs-3g`), neither of
which this turn had.

**What is nevertheless proved on real filesystems**: the probe, against **four** mounts including
a genuinely case-insensitive one (table above). **What is exact rather than simulated**:
`reconcile` is pure and takes plain strings, so feeding it the strings a folding filesystem
produces **is** the input, not a model of it. **What is forced rather than observed**: `folds_case`
is monkeypatched in the CLI and app tests, which exercises the real code path on every lane with
no `skipif` - the injection `(ais)`'s resolution calls for.

⚠ **What is NOT proved, stated plainly**: no run anywhere shows a real folding mount's **walk**
returning the drifted spelling end to end. That is the one step a `sudo mount` would add, and it
is the step between "the filesystem folds" and "truestill sees two names".

## VACUITY CHECK

**15 mutations, 15 caught**, one only after a survivor:

| mutation | caught by |
|---|---|
| the key never folds / always folds / uses `lower` | 3 core tests, separately |
| the damaged lookup stops folding | `test_the_damaged_bucket_survives_a_drift` |
| the stray subtraction stops folding | `test_the_buckets_stay_disjoint_under_folding` |
| the probe trusts the name instead of the inode | `test_two_real_files_that_differ_only_in_case_are_not_folding` |
| the probe guesses `False` when it cannot tell | `test_the_probe_says_it_cannot_tell_rather_than_guessing` |
| **the probe writes to find out** | `test_the_probe_reads_nothing_and_writes_nothing` |
| the app stops folding / decides by platform / returns everything | 3 app tests |
| **the CLI stops folding** | ⚠ **survived** - see below |
| the fold reaches `reconcile` but not the subtraction (and the reverse) | the new CLI tests |

⚠ **The survivor is the interesting one.** Turning off the CLI's fold was caught by **no CLI
test**: the core tests feed `reconcile` directly and the app tests read the app. The CLI's own
half is the PLACED subtraction, which is where the *cost* lives - a fix that corrected the report
and left the library being re-read would have passed. `test_the_drifted_file_is_not_hashed_when_the_mount_folds`
counts calls to `sha256_file` and is what closes it.
