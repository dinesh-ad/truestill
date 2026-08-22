# Soak four - what the two deleting commands actually did

**Status: RAN 2026-08-22.** The plan is [`soak-four-plan.md`](soak-four-plan.md). All seven steps
ran. **Four findings**, one confirmation of an open entry, and ⚠ **the two properties most likely
to destroy irreplaceable data both held.**

Run order was D4 → D2 → D1 → D3 → D5 → D7 → D6, at the maintainer's instruction, rather than the
plan's D1-first. ⚠ **The plan's reason for D1 first was real** - *"if the happy path does not
delete exactly what it promised, a later step's 'it deleted the wrong thing' is unattributable"* -
so D4 was given a **positive control** instead: the same 161 files, organized by copy rather than
in place, and confirmed reclaimable. Without that, D4's zero would have been indistinguishable
from a harness that staged nothing.

## Results

| step | subject | verdict |
|---|---|---|
| **D4** | `reclaim` where the source **is** the copy | ✅ **held** - 161 skipped, named and explained |
| **D2** | reclaim/clean-empty recoverability asymmetry | ⚠ `(afh)` - both truthful, ceremony inverted |
| **D1** | `reclaim` happy path | ✅ **held** - exact set equality, bytes match, `verify` clean |
| **D3** | `reclaim` with corrupt backup copies | ✅ **held** - all 10 sources kept |
| **D5** | `clean-empty` after a migration | ✅ held, **and** ⚠ `(afi)` |
| **D7** | `--permanent` and the `rmdir` claim | ✅ held, **and** ⚠ `(afj)`, `(afk)` |
| **D6** | trash across a filesystem boundary | ✅ **held** - §1 condition **(d)** exact |

## The two that matter most, and they held

**D4 - deleting the only copy.** After `organize --in-place`, `files.source_path` and the drive
copy are one inode: 161 of 161 verified with `os.path.samefile`. `reclaim` offered **none** of
them, and said why rather than omitting them:

```
reclaimable: 0 file(s), 0.00 GB would be freed
skipped: 161 file(s) organized in place -- the source IS the copy on this drive,
         so freeing it would delete the only one
```

Positive control, same corpus in copy mode: **161 reclaimable, 0.30 GB.** The gate bites.

**D3 - deleting against a bad backup.** Ten destination copies altered **in place, same size,
different bytes**, so only a hash could catch them. `reclaim` offered 151 and skipped 10 -
*"10 copy(ies) failed re-verification (source kept)"* - and all ten sources were still on disk
afterwards. **Zero deleted with an unverifiable backup.**

**D1 - the promise.** 161 promised, 161 gone, **set equality in both directions**, the freed-bytes
figure matching `sum(size)` to the reported precision, every deleted source's `sha256` still
present on the drive, and `verify` afterwards reading `verified 161 / MISSING 0 / MISMATCH 0`.

## What the third column caught

⚠ **One thing was removed that a preview did not name** - `(afj)`. Not by `reclaim`, and not
permanently: `clean-empty`'s **trash** path takes the whole folder, so a non-junk file that
appeared between the plan and the typed confirmation went to the trash with it. The **permanent**
path, run against the same race, refused with `Errno 39` and left both the folder and the file.
The safer-looking path has the weaker guarantee, and the `rmdir` sentence that describes the
stronger one is printed by the branch that runs only when the trash refuses.

## Findings

- **`(afh)`** - reclaim removes the user's originals behind `delete` and one line; `clean-empty
  --permanent` removes folders the product emptied behind `delete forever` and three lines of
  capitals. Both truthful; the ceremony is inverted relative to the stakes. Not a rule violation:
  §1's trash condition **(d)** is scoped to the folder-removal paragraph. **Whether it was ever
  meant to be is the open question.**
- **`(afi)`** - `clean-empty` cannot see the folders `organize --in-place` empties.
  `migrated_old_paths` reads `migration_journal`; in-place writes `inplace_moves` (161 rows,
  measured) and no reader in the cleanup path touches it - while the in-place banner promises
  *"Empty folders left behind are reported."* Controlled with a `migrate-layout` on the same drive
  minutes later, which was found, offered and cleaned correctly.
- **`(afj)`** - the trash path lacks the permanent path's race protection. Above.
- **`(afk)`** - junk unlinked before an `rmdir` refusal is not reported, so a partial removal reads
  as none. Same class as `(aez)`. Small - the junk was named in the preview.
- **`(afd)` confirmed in a second command** - `clean-empty`'s failure list is `organize`'s shape
  and additionally leaks a Python `bytes` repr. Two commands reach it independently, so the remedy
  is not one list's formatting.

## ⚠ Harness defects - three, and two would have produced false results

**Recorded because the plan said the setup is part of the test**, and because soak two's record
made the same point about its own three.

1. **`comm` on locale-sorted input reported 166 files gone when 161 were deleted.** The comparison
   was void and its output had already been fed to the content check. Re-run under `LC_ALL=C`. ⚠ A
   diff that disagrees with the count beside it is the cheap signal; there was no reason to trust
   the first run over the second except that the second was explained.
2. **`chmod 555 /data/.Trash-1000` did not deny the trash**, because the writes go into
   `files/` and `info/`, which carry their own permissions. The first D7 run therefore took the
   **trash** path while claiming to test `--permanent`. It produced a real finding by accident -
   `(afj)` - but the step's actual subject, the `rmdir` claim, was **not exercised at all** until
   it was restaged denying the two subdirectories. ⚠ **A refusal that does not refuse is a green
   run testing nothing**, which is exactly what the plan's hard-link warning was about, arriving
   by a different route.
3. **The plan's D5 said `organize --move`**, which does not populate `migration_journal` at all.
   Run as written it would have printed *"no migration leftovers recorded. Nothing to clean."* and
   passed as a green step that exercised nothing. The finding `(afi)` is that same fact seen from
   the other side - the step was wrong for the reason the product is wrong.

## What this soak did not answer

- **Windows and macOS.** `send2trash` has a different backend on each and `chmod` does not deny
  the owner on Windows. Every step was Linux, on ext4.
- **A full disk or a full trash.** S11's standing blocker: no `sudo`, no `unshare -Ur`, no
  loopback on this machine.
- **Interruption mid-delete.** Excluded by the plan, deliberately, and still worth its own step
  now that D1-D4 have established the baseline.
- **The app's surfaces.** Every step read the CLI.
- **Scale.** 166 files per step, not 55,110. These are sequence defects; the corpus was bounded so
  the after-check stayed affordable, which is the same reasoning soak two recorded.
