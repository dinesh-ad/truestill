# Soak four - the two commands that delete

> ⚠ **RAN 2026-08-22 - the results are in [`soak-four-record.md`](soak-four-record.md)**, and this plan is left as written: it is the
> prediction the record grades (noted 2026-09-03, P203; a status line below that says otherwise is the record).

**Status: written 2026-08-22. NOT RUN.** Soaks one and two organized a library at scale; soak
three made things refuse. This one points at the two commands that **remove the user's data**, and
neither has ever been run against a real library in any soak.

## Why these two, and why the gap survived three soaks

| command | what it removes | ever soaked? |
|---|---|---|
| `truestill reclaim` | **source files**, with `Path.unlink()` | **no** |
| `truestill clean-empty` | **directories**, to the OS trash | **no** |

Soak two listed both as never run (`soak-two-plan.md:156-160`) and did not reach them. Soak three
**dropped S10 (`reclaim`)** deliberately - `(aez)` had just fixed a live crash in that path and
`test_reclaim_never_deletes_what_it_cannot_examine.py` pinned the property - and **absorbed S9**
into R6. Each decision was defensible on its own day. ⚠ **The cumulative result is that the
product's two most destructive commands have no soak evidence behind them at all**, which no
single one of those decisions would have chosen.

⚠ **A unit test pinning "reclaim never deletes what it cannot examine" is not the same claim as
"reclaim deleted exactly what it said it would, on 55,110 real files."** The first is about one
branch; the second is about the whole gate meeting a real population.

## ⚠ THIS SOAK DELETES. THAT CHANGES THE METHOD, NOT JUST THE CARE.

Every previous soak could be re-run by pointing at the corpus again. This one cannot: a step that
removes the wrong file has already produced its finding and destroyed the evidence for the next
one. So three things are part of **every** step below, not preamble to them.

### 1. What is copied before each step

**A real byte copy of a bounded subtree, into a fresh working root.** Never the whole library -
117 GB is not the unit of work, and a bounded subtree is what makes the after-check affordable.

```
rsync -a --no-links /data/TruestillLibrary/<subtree>/ /data/soak4/<step>/before-copy/
```

⚠ **NOT `cp -al`, and this is the trap worth naming.** A hard-link snapshot is the cheap way to
protect a big tree, and here it would **silently neuter the test**: `reclaim._is_the_copy_itself`
decides with `Path.samefile`, so a hard-linked backup makes the source and the drive copy one
inode, every candidate is excluded, and `reclaim` correctly does nothing - a green run that
exercised none of the gate. ⚠ ext4 has no reflink either, so there is no cheap-copy shortcut to
reach for: it is a real copy or it is not a backup.

### 2. How "only what was meant to go, went" is verified afterwards

**The preview is the promise; the diff is the check.** Every step is run twice - preview, then
`--apply` - and the preview's list is captured as the *expected* delta.

```
# before
find "$ROOT" -type f -printf '%P\n' | sort > before.txt
find "$ROOT" -type d -printf '%P\n' | sort > before.dirs
# after
comm -23 before.txt after.txt > actually-gone.txt
diff <(sort expected-gone.txt) actually-gone.txt      # MUST be empty
```

⚠ **Both directions matter and only one is obvious.** Something gone that was not promised is the
frightening half; something promised that is still there is the half that means the report lies.
The check is set **equality**, never containment.

**Content, not just names.** For the reclaim steps a `sha256` manifest of the surviving files is
taken before and after: a file that keeps its path while its bytes change would pass a name diff
and is exactly the failure the re-verify gate exists to prevent.

```
find "$ROOT" -type f -print0 | sort -z | xargs -0 sha256sum > manifest.txt
```

### 3. What counts as the app deleting something it should not have

⚠ **This is the third column, and here it matters more than anywhere else in any soak plan.** It
is stated once, generally, and then each step narrows it:

> **Any file or directory absent after `--apply` that the preview did not name, without
> exception.** Not "unimportant", not "obviously junk", not "recreated anyway". The preview is the
> whole permission; anything outside it is the defect, and its size or value is irrelevant to
> whether it happened.

And four specific forms, each of which a gate exists to prevent:

- **A source deleted whose backup copy does not hold its content** - the re-verify gate
  (`_verify` re-hashes the destination immediately before the `unlink`) failed to bite.
- **A source deleted that IS the backup copy** - `_is_the_copy_itself` failed, and the only copy
  of that content is gone. After an in-place organize this is one inode with two names.
- **A directory removed that held something not in `JUNK_NAMES` and not zero-byte.**
- **Anything removed that the migration journal does not show this product emptied** - scope is
  the journal, never a filesystem sweep.

---

# The steps

`corpus` is a bounded subtree of `/data/TruestillLibrary` (55,110 files / 117 GB, ext4,
774 GB free), copied per §1. Each step: what to **do**, what to **read**, and what would count as
**the app deleting something it should not have**.

## D1 - `reclaim` on a library where the backup is genuinely good. `corpus: ~2,000 files`

| | |
|---|---|
| **Do** | Organize a subtree to a destination drive, register it, then `reclaim` the drive - preview, capture the list, then `--apply` and type the confirmation. |
| **Read** | The preview's count and total bytes, the typed-confirmation prompt, the applied count, the two manifests, and `verify` afterwards. |
| **Untrue if** | the applied set differs from the previewed set **in either direction** · any surviving file's sha changed · `verify` afterwards reports a copy the catalog claims and the drive does not have · the freed-bytes figure does not match the sum of the deleted files' sizes · a source is deleted whose destination copy fails a fresh `sha256`. |

## D2 - ⚠ `reclaim` deletes PERMANENTLY, and `clean-empty` does not. `corpus: small`

⚠ **The asymmetry this step exists to surface, found by reading before writing this plan.**
`run_reclaim` calls `candidate.source_path.unlink()`. `cleanup` goes to the OS trash and treats a
trash refusal as a refusal (`IMPLEMENTATION_STANDARDS.md` §1, condition **(d)**). So the command
that deletes **files the user chose to keep** is less recoverable than the one that removes
**folders the product itself emptied**.

| | |
|---|---|
| **Do** | Reclaim a handful of files and then look for them: in `~/.local/share/Trash`, in `/data/.Trash-1000`, anywhere. |
| **Read** | Whether anything is recoverable, and **what the preview and the confirmation prompt led the user to expect**. |
| **Untrue if** | the wording implies recoverability that does not exist · the two commands describe the same act in words that imply the same reversibility · nothing in the preview distinguishes "deleted" from "moved to trash". **This may be a finding about wording rather than a defect in either command** - and if the ruling is that reclaim *should* trash, that is a new entry, not a fix inside this soak. |

## D3 - `reclaim` where the backup copy is CORRUPT. `corpus: ~200 files`

| | |
|---|---|
| **Do** | Organize, then **alter bytes in the middle of ~10 destination copies** (not truncate - same size, different content), then `reclaim`. |
| **Read** | Whether those ten are offered, counted unverified, or named. |
| **Untrue if** | ⚠ **any of the ten sources is deleted** - the gate re-hashes and must catch every one · they are silently absent from the report · they are counted as reclaimable and the numbers still balance · the run reports success without distinguishing them. |

## D4 - `reclaim` where the source IS the copy (in-place). `corpus: ~200 files`

| | |
|---|---|
| **Do** | `organize --in-place` a subtree so `files.source_path` and `file_copies.relative` name **one inode**, then `reclaim` that drive. |
| **Read** | The candidate count - it should be zero for those files - and whether the report explains why rather than just omitting them. |
| **Untrue if** | ⚠ **any such file is deleted. This is the one that destroys content with no other copy anywhere**, and `_is_the_copy_itself` is the only thing preventing it · the files are counted as "already reclaimed" · they are silently missing from every total. |

## D5 - `clean-empty` after a real migration. `corpus: ~2,000 files`

| | |
|---|---|
| **Do** | `organize --move` a nested subtree so folders are genuinely emptied, then `clean-empty` - preview, capture, `--apply`, type `clean`. |
| **Read** | The previewed folder list, every leftover file named beside its folder, the trash afterwards, and the folder diff. |
| **Untrue if** | a folder is removed that the preview did not name · a folder is removed that still held a non-junk, non-zero-byte entry · the removal is not recoverable from the trash · a folder the journal does not cover is touched · the count in the confirmation prompt disagrees with the list above it. |

## D6 - ⚠ `clean-empty` across a filesystem boundary. `corpus: small` · **the untested condition**

⚠ **`/data` is a separate ext4 mount from `$HOME`.** The freedesktop trash spec wants a
`.Trash-$uid` on the same filesystem; `send2trash` is the backend here. What happens when a folder
on `/data` is trashed has **never been observed**, and the two plausible behaviours are far apart:
a per-mount trash directory, or a cross-device copy into the home trash.

| | |
|---|---|
| **Do** | `clean-empty --apply` a folder on `/data` with the home trash on `/`. Then repeat with the trash made unavailable, and read what `--permanent` asks for. |
| **Read** | Where the folder went, whether `/data/.Trash-1000` was created, how long it took, and the refusal path's wording. |
| **Untrue if** | a trash refusal is silently downgraded to a permanent delete - condition **(d)** · `--permanent` proceeds without its own confirmation · a cross-device trash **copies** without saying so · the folder is gone and in no trash at all. |

## D7 - `clean-empty --permanent`, the `rmdir` claim. `corpus: small`

`_remove_permanently` removes named junk with a non-recursive wildcard and then calls
`folder.rmdir()`, which **physically cannot** remove a non-empty directory. That is a strong claim
and it has never been tested against a real tree.

| | |
|---|---|
| **Do** | Point `--permanent` at a folder that contains junk **and** one unexpected non-junk file placed there after the preview was taken. |
| **Read** | Whether `rmdir` refuses, what is reported, and whether the junk it already removed is mentioned. |
| **Untrue if** | the folder is removed · the unexpected file is removed · the run reports success · ⚠ **the junk removed before the `rmdir` refusal is not reported** - a partial destructive action that says nothing is the shape `(aez)` was. |

---

## What this soak cannot answer, stated rather than implied

- **Windows and macOS.** `send2trash` has a different backend on each, `unlink` semantics differ,
  and `chmod` does not deny the owner on Windows. Every step here is **Linux only**.
- **A trash that is full.** Not stageable without filling a real filesystem, which is S11's
  standing blocker: no `sudo`, no `unshare -Ur`, no loopback on this machine.
- **The app's screens.** Every step reads the CLI. Neither command has an app surface today, and
  if one is added this plan does not cover it.
- **Interruption mid-delete.** `SIGKILL` between the `unlink` and the count is S6's shape aimed at
  a destructive loop. ⚠ **Deliberately excluded**: it needs the crash-resume reasoning in
  `reclaim_journal` that `(yy)` explicitly left out of scope, and mixing it in here would make a
  finding hard to attribute. It is worth its own step once D1-D4 have established the baseline.

## Order, and the rules

**D1 → D3 → D4 → D2 → D5 → D7 → D6.** Correctness before wording; the two `reclaim` gates
(D3, D4) immediately after the happy path that proves the harness works at all; the trash-boundary
step last because it is the one that may leave 117 GB of state somewhere unexpected.

⚠ **D1 must pass before any other reclaim step runs.** If the happy path does not delete exactly
what it promised, a later step's "it deleted the wrong thing" is unattributable.

⚠ **Every step restores from its copy before the next one starts**, and the restore is **verified
by manifest**, not assumed. A step that cannot restore is a step that ends the soak.

⚠ **Each finding gets a letter and an entry before the next step runs** - soak two's discipline,
and the reason its five findings did not become one unreadable report.

⚠ **The fence is unchanged**: `/home/dinesh/pCloudDrive/` and `/home/dinesh/Icedrive/` are never
read, walked or stat'd, at any depth, under any flag. ⚠ **And a new one for this soak**: no step
points a destructive command at anything outside `/data/soak4/`. The library itself is the
*source* of copies and is never the *target* of `--apply`.
