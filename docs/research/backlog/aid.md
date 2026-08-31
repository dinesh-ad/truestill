# (aid) THE ORIGINAL FILENAME IS NEVER SANITIZED, AND THEN GAINS SIXTEEN CHARACTERS.

> ✅ **THE LENGTH HALF SHIPPED 2026-08-30 (P146); THE CHARACTER HALF IS INSTRUMENTED, NOT FIXED.**
> Provenance is in [`SHIPPED.md`](../../SHIPPED.md).
>
> ⚠ **THE "219 BYTES" BELOW IS ONE PROCESS'S READING, NOT A BUDGET, and the body is left
> unrewritten as the measurement it was** - a record edited to stay correct stops being one.
> P146 re-measured **220** on the same machine. The staging token carries the pid in hex, so the
> overhead is 16-21 bytes and the usable budget moves over **218-223** on one box. The exact form
> is `255 - stamp - staging_overhead`, and nothing in the fix writes a number down.
>
> ⚠ **`PATH_LENGTH_WARN` still has no reader in `organizer.py`.** The fix refuses on the
> **component** limit; the Windows 260-character **path** limit this entry also names is a
> different number with a different remedy, and it is still open.

*Body of backlog entry `(aid)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aid) THE ORIGINAL FILENAME IS NEVER SANITIZED, AND THEN GAINS SIXTEEN CHARACTERS.** Filed
  2026-08-26 (P118), read from source. `layout.py`'s four defences - illegal characters, reserved
  device names, trailing dots, the 255-byte cap - apply to **token values only** (the event name,
  the category), which `filename-safety-research.md` scopes correctly as *"user-supplied names"*.
  But `dated_filename` returns `f"{stamp}_{original_name}"` untouched (`naming.py:104`).
  `Trip: day 1.jpg` and `nul.jpg` are legal on ext4 and **refuse on NTFS**; a 248-byte name
  becomes 264 and refuses everywhere. ⚠ **`PATH_LENGTH_WARN` exists (`layout.py:99`) and organize
  never imports it** - the two readers are `layout.py:517` and `migrate.py:623`, so the one screen
  that warns about length is the settings preview, where nothing is being moved.
  `ENAMETOOLONG` and `EINVAL` are not in the errno table, so what the user gets is raw OS words.

  ## WHAT IS DEFENDED AND WHAT IS NOT

  `layout.py` carries four defences and they are good ones - illegal characters, reserved device
  names, trailing dots, a 255-byte cap. **All four apply to token values**: the event name, the
  trip name, the category. [`filename-safety-research.md`](../../filename-safety-research.md)
  scopes itself to *"user-supplied names"* and is **correct about its own subject**.

  The file's own name is not a token. `dated_filename` returns `f"{stamp}_{original_name}"`
  (`naming.py:104`) with `original_name` passed through untouched, and `stamp` adds **sixteen
  characters** in front of it.

  ## WHAT BREAKS, AND ALL OF IT IS LEGAL ON THE SOURCE

  | source name | legal on ext4 | destination |
  |---|---|---|
  | `Trip: day 1.jpg` | yes | `:` is illegal on NTFS - **refuses** |
  | `nul.jpg` | yes | reserved device name on Windows - **refuses** |
  | a 248-byte name | yes | 264 after the stamp - **refuses everywhere** |
  | `photo?.jpg`, `a*b.jpg` | yes | illegal on NTFS and exFAT |

  ⚠ **A user copying a library from a Mac or a Linux box onto an external NTFS drive is the
  ordinary case**, not a contrived one - and it is `moving-machines.md`'s subject.

  ## ⚠ THE WARNING EXISTS AND ORGANIZE DOES NOT IMPORT IT

  `PATH_LENGTH_WARN = 200` (`layout.py:99`) has exactly two readers: `layout.py:517` and
  `migrate.py:623`. **`organizer.py` imports neither the constant nor anything that checks it.**
  So the one screen that warns about path length is the settings preview, where nothing is being
  moved, and the run that actually writes says nothing until the OS refuses.

  `ENAMETOOLONG` and `EINVAL` are absent from the errno table, so the refusal arrives as raw OS
  words with no next step - against `ENGINEERING_STANDARD.md` §4's rule that naming a problem
  without a remedy is half a report.

  ## WHAT IS NOT ESTABLISHED

  Whether to sanitize the original name (changing what the file is called, which a user may
  reasonably object to) or to **refuse in the preview with a named remedy** (leaving the name
  alone and making the problem visible before anything is written). The second is cheaper and
  loses nothing; it is not obviously right, and this entry does not rule.

  ## RELATED

  `(aic)` and `(aie)`, [`filename-safety-research.md`](../../filename-safety-research.md) (correct
  about tokens, silent about this), [`moving-machines.md`](../../moving-machines.md).

  ## ⚠ WHY IT SURVIVED - THE LANES STRUCTURALLY CANNOT SEE IT

  Shared by `(aic)`, `(aid)` and `(aie)`, and it is half of why all three are still here. This is
  not *"no test covers it"*; it is *"no lane can reach the state"*. `ENGINEERING_STANDARD.md` §4's
  fifty-fourth member - an instrument silent in the case it exists for.

  | what would be needed | what the lanes have |
  |---|---|
  | a non-en-US locale | **none.** Both non-Linux runners are en-US; nothing sets `LC_ALL` or a code page |
  | a non-ASCII filename **on disk** | **zero in the whole suite.** The one Unicode fixture is lexical - a string in a test, never a file |
  | a path near 260 characters | CI paths never approach it |
  | exFAT, FAT32, FUSE, SMB or NFS | **none.** No lane touches any filesystem but the runner's own boot volume - *which is the product's entire subject matter* |
  | an older exiftool | one version, whatever the image ships |
  | scale | small fixtures only |

  ⚠ **`architecture-excellence-2026-audit.md:198-200` already said this** about the lock design
  pass: the filesystems the product exists to write to are the ones nothing runs on. It is advisory
  and no implementation was authorized; this is the same gap arriving from a different direction.

  ⚠ **ALREADY GUARDED, so none of this is re-filed**: the 4 GB preflight, exFAT permission
  handling, reserved device names for **typed** values, timezone handling, WAL-is-moot, stale
  locks, and a missing exiftool. The three entries are the complement of that list, not a claim
  it is empty.

  ## ⚠ REPRODUCED 2026-08-29 (P140) - REAL, AND THE ARITHMETIC UNDERSTATED IT BY 20 BYTES

  Measured on ext4 (`/dev/nvme0n1p1`, 16 cores, Python 3.14.4), organize apply against a
  constructed source. **The length half is a real defect and the character half cannot be
  measured here** - they are two claims with different platforms, and this entry stated them as
  one.

  **What the user sees, verbatim:**

  ```
  FAILED: holidayxxx....jpg: could not copy holidayxxx....jpg to
  'Saved/Undated/holidayxxx....jpg': File name too long 0 bytes of it are still at
  .../holidayxxx....jpg.5580514b3be.partial, and could not be removed.
  ```

  🔑 **THE 16-CHARACTER STAMP IS NOT THE WHOLE COST - THE STAGING SUFFIX ADDS 20 MORE.**
  `safe_copy` stages at `<name>.<token>.partial` (`safe_copy.py:65`, *"Appended LAST"*), which is
  `.` + an 11-character token + `.partial` = **20 bytes**. Measured threshold, by bisection:

  | original name | organized name (+16) | result |
  |---|---|---|
  | 219 bytes | 235 | organizes |
  | **220 bytes** | 236 - still under 255 | **FAILS, `File name too long`** |

  **So the real budget for an original filename is 219 bytes, not the 239 this entry implies.** A
  name that is legal raw *and* legal after the stamp still fails, because the temporary it stages
  through is longer than the file it becomes. A 230-byte name reproduced that exactly.

  ⚠ **Two corrections to this entry's own text.** (1) *"stops the run"* is **wrong**: the run
  continues and reports `1 failed`; it is the FILE that fails, not the run. (2) The failure
  message runs two sentences together with no punctuation - *"File name too long 0 bytes of it
  are still at ..."* - and then names a `.partial` path it says *"could not be removed"*, when the
  temporary could not be created in the first place. That is a second, smaller defect inside the
  first, and it is a wording fix rather than a length one.

  ## ⚠ THE CHARACTER HALF IS A WINDOWS FACT AND DID NOT REPRODUCE HERE - BY ITS OWN PREMISE

  All four NTFS-illegal names organized **successfully** on ext4, unsanitised, landing verbatim:

  ```
  20190712_103000_Trip: day 1.jpg      20190713_103000_nul.jpg
  20190714_103000_report<v2>.jpg       20190715_103000_pipe|name.jpg
  ```

  That is the premise working, not a refutation: a colon, `<`, `|` and the reserved name `nul`
  are legal on ext4 and refused on NTFS. **The instrument is an xfail on the Windows lane**, the
  shape `(aif)` used to get a Windows fact no local run could reach - and `(aif)`'s xfail returned
  a real answer on its first CI run. Until that exists, the character half stays **unproven**, and
  this section is what stops it being read as measured.

  ## ⚠ THE CHARACTER HALF REPRODUCED 2026-08-31 (P165, soak ten) - ON LINUX, ON exFAT

  **The section above is right that it did not reproduce on ext4, and right about why. It was
  wrong that only a Windows lane could answer it.** The premise was *"a filesystem driver decides
  it, nothing can force it"* - and a filesystem that decides it was put on the desk: **exFAT,
  kernel driver, on a USB stick**, mounted `iocharset=utf8`.

  | name | ext4 | **exFAT (kernel)** |
  |---|---|---|
  | `Trip: day 1.jpg` | created verbatim | **REFUSED `[Errno 22] EINVAL`** |
  | `photo?.jpg`, `a*b.jpg`, `pipe\|name.jpg` | created verbatim | **REFUSED `[Errno 22]`** |
  | `report<v2>.jpg`, `say"hi.jpg`, `back\slash.jpg` | created verbatim | **REFUSED `[Errno 22]`** |
  | `nul.jpg` | created verbatim | ⚠ **created verbatim** |
  | `photo..jpg.` (trailing dot) | created verbatim | ⚠ **SILENTLY STRIPPED** to `photo..jpg` |
  | 255 / 256 bytes | OK / `[Errno 36]` | OK / `[Errno 36]` - **identical** |

  🔑 **THREE CORRECTIONS TO THIS ENTRY, EACH MEASURED.**

  1. **Eight illegal characters are now reachable without a Windows runner.** The `xfail` is still
     the right instrument for **NTFS**, but it is no longer the only one: exFAT refuses the same
     character class with `EINVAL`, and this machine can mount it.
  2. ⚠ **`nul.jpg` IS FINE.** A reserved device name is a **Windows shell** rule, not a filesystem
     one - so this entry's table row is wrong about the mechanism even where it is right about the
     outcome. It will not reproduce on exFAT under Linux at any effort.
  3. ⚠ **A TRAILING DOT IS WORSE THAN A REFUSAL, AND THIS ENTRY DID NOT PREDICT IT.** The write
     **succeeds**, the file lands under a **different name**, and `Path.exists()` on the name that
     was asked for returns **`True`** - because the lookup is stripped the same way. So a caller
     that writes a name and then checks for it is told yes, and `_free_relative`'s collision logic
     is asking a question that has already been mangled. **Neither a refusal nor a success: a
     silent rename.** The length half's remedy - refuse in the preview with a named remedy - does
     not reach it, because nothing refuses.

  **The byte budget is unchanged on exFAT** - 255 accepted, 256 `ENAMETOOLONG` - so §"REPRODUCED
  2026-08-29"'s arithmetic stands on this filesystem too.

  Measured in [`soak-ten-record.md`](../../soak-ten-record.md) §2; the probe is preserved with the
  run's evidence.
