# Soak two - the record

**Ran 2026-08-21** against the plan in [`soak-two-plan.md`](soak-two-plan.md). This is a **record**:
it is not rewritten to stay correct, and corrections go beside it, dated.

Corpus, per the plan's §1 ruling: `Input/2013` + `Input/2014`, **2,276 files / 6.3 GB**, copied to
scratch so the destructive steps could never reach the originals. `Input/Testing-new` was out of
scope and unreachable by construction - every source root was the specific folder, never `Input`.
Format steps used copies of `exif-samples` and `metadata-extractor-images` with `.git` removed, so
no git worktree was ever organized.

**S1 ground truth, counted before the product had an opinion:** 2,276 files, 6,654,936,568 bytes,
**2,270 distinct sha256** (6 duplicate files), extensions `2272 jpg / 2 mp4 / 1 mov / 1 ini`.

## What passed

| step | result |
|---|---|
| **S2** organize into A | 2,275 media analysed, 2,269 organized + 6 duplicates. A holds **exactly the 2,269 distinct media hashes**. 37.7 s |
| **S3** second destination B | B received all 2,269; A and B are **identical sets**; `status`: *"All catalogued content has at least two drive copies."* **`(aei)` holds at scale.** |
| **S4** verify, break, restore | 7 deleted -> `MISSING: 7`, each named. Restored -> `MISSING: 0`, `missing_at` cleared to 0, stamp advanced. **The clear direction works** (§4's thirty-seventh member). |
| **S5** migrate-layout on A | 106 relocated, byte-identical set preserved, **`verify` passes afterwards** so `file_copies.relative` followed. Offers `clean-empty` for 3 emptied folders. |
| **S7** migrate undo | 106 put back; `move` typed at an `undo` prompt correctly **aborted**. |
| **S8** `--move` | 161 moved **by rename** (no bytes copied), content preserved against a pre-hash, and it named what it left: *"5 files remain in TCS-M05-Batch because an identical file from this batch was moved instead."* |
| **`(aem)`** at scale | A real `SIGKILL` at 1,277 files left **0 `.partial`, 0 zero-byte**, and `drives` said *"a run was interrupted: 1,276 of 2,269 files arrived."* `file_copies` 1,276 vs 1,277 on disk - the **safe** direction, bytes ahead of record, **no phantom row**. |
| **S12** RAW categorisation | **68 of 69** RAW files landed on the timeline with real years. The one in `Saved/` has `make=None, model=None, date=none` - a genuine unknown via `rule="fallback"`, not the 2 MP heuristic misreading a preview. |
| **S12** orientation, non-HEIC | `upright_size` correct on **all 48** images carrying a transposing tag; none drawn sideways. |

## What it found

Five, filed as `(aer)`-`(aev)`. Two would have been unreachable by any corpus of one person's
devices, which is the axis argument paying for itself on its first run.

1. **`(aer)`** organize's skipped report drops **hidden files and hidden folders**. A folder of 21
   photos, 18 in `.MyAlbum`, reported *"analysed 3, organized 3"* and **success**.
   > ⚠ **CORRECTED 2026-08-21, beside the finding.** Two claims made here were wrong. *"1
   > understates 18"* is not an understatement but a **refusal to invent**: folders are named
   > without a count because the walk never enters them (`c027dd3`), so the honest line is *"1
   > hidden folder, contents unknown"* plus the remedy. And *"analyze right, organize wrong"* was
   > too broad - it is **one surface of three** for hidden files (the app already read the census)
   > and **two of three** for folders. Full corrections in
   > [`research/backlog/aer.md`](research/backlog/aer.md).
2. **`(aes)`** `status` says *"Never checked"* about a drive that was just verified and found
   wanting, while `drives` correctly says *"checked, gaps"*.
3. **`(aet)`** a single undecodable file **aborts the whole run** with a traceback - 8 of 1,428.
4. **`(aeu)`** on HEIC the **payload and the pixels disagree** about orientation. 4 of 20, one of
   them `iphone_13_pro_max.HEIC`.
   > ⚠ **CORRECTED 2026-08-21, beside the finding rather than into it.** *"4 of 20"* counted files
   > where exiftool and PIL disagree about the **tag**. Only **1 of 20** actually rendered
   > sideways; the other three carry `irot`, decode upright already, and a fix aimed at all four
   > broke them. The proxy could not distinguish a wrong picture from a redundant tag. Outcome and
   > the remaining payload half are in [`research/backlog/aeu.md`](research/backlog/aeu.md).
5. **`(aev)`** **131 raw Pillow warnings** reached the terminal in one run, against a docstring
   that says none ever do.
   > ⚠ **CORRECTED 2026-08-21, beside the finding: this had the SUBJECT BACKWARDS.** Measured
   > while fixing it, on the same corpus: **478 image files got no near-duplicate check and only
   > 71 of them warned** - and **14 files warned while decoding perfectly well**. The warnings are
   > a **lossy 15% proxy** for a gap the product never mentioned at all, so suppressing them alone
   > would have made Truestill *quieter about a real gap*. Two more counts were wrong: the C-level
   > half recorded here as *"plus a bare `OJPEGWriteHeaderInfo` line"* is **~598 lines of 866** -
   > 4.5x the noise of the thing the entry is named for - and the four "kinds" are **three sites**,
   > 186 of 197 from one line (`TiffImagePlugin.py:950`) re-emitting an `OSError`'s message as a
   > bare `UserWarning`. Full corrections in [`research/backlog/aev.md`](research/backlog/aev.md).

## ⚠ Three harness defects, recorded because each nearly became a false finding

The maintainer's standing warning - *a zsh word-splitting trap produced five false proofs twice in
one day* - was right, three times, in one session. **Every one failed in the direction that
accuses working code.**

1. **`xargs` mangled paths containing spaces and apostrophes** (`Wayanad '14`), so a deletion did
   nothing and `verify` correctly reported `MISSING: 0`. Read naively that is *"verify is blind to
   deleted files"*, a catastrophic false finding. Caught by asserting the **precondition** - *are
   they actually gone?* - which is §4's thirteenth member: assert the subject entered the path.
2. **`timeout -s KILL` killed `uv run`, not the python child**, which ran on to completion. The
   "interrupted drive" was a **live run being sampled**, which is why three reads gave 1,988,
   2,000 and 2,013. Caught by re-measuring all counts at one instant and finding them equal.
3. **`pgrep -f` matched the shell running it** - §4's forty-fifth member exactly - and two probes
   called product functions with the wrong signature, producing 48 `TypeError`s that read as a
   defect until the signature was checked.

**The rule that caught all three: measure the precondition, not just the outcome.** An outcome
reproduced for the wrong reason retires the question.

## Not run

**S6** (interrupt a *migration* - an organize interrupt was done instead), **S9** `--in-place`,
**S10** `reclaim`, **S11** a disk that fills mid-copy. Stopped to record rather than continue:
the plan's own stop rule says findings are the product, and five had accumulated.

---

## Stock-take, 2026-08-21 - where the remaining defects are

**Added after soak two, not part of it.** Twelve entries were closed or filed in the three days
following. **Eleven of them live in code that only runs when the ordinary case did not hold** -
a file that will not decode, a folder that will not answer, a drive that is not there, a run that
was interrupted, a feed that returned 503. The one exception is `(aeu)`, the HEIF rotation, and it
is the only one a soak found by *organizing a healthy library*.

⚠ **Three were live delete-path defects, and none of them could have been found by running the
product on a corpus that was fine.** `(aez)` and `(afb)` both **raised** an uncaught
`PermissionError` - `plan_reclaim` died with a traceback, and `run_reclaim`'s did it *mid-loop,
after earlier candidates had already been deleted*. They were found by **reading**, provoked by a
pin that had been ordered for an unrelated reason.

**Why this class rots, and it is four separate reasons rather than "less coverage":**

1. **Nothing exercises it by accident.** A happy-path run never enters it, so every test must
   construct the failure deliberately - which is expensive, so it is done once and thinly.
2. **The construction is usually a simulation**, and simulations encode assumptions about how the
   failure presents. `_deny` froze the pre-3.14 stdlib and kept passing after it changed.
3. **The observable is often an absence** - a skip, a `False`, a line not printed - and absence is
   what a suite is worst at asserting. §4's fifty-fourth member recurs here more than anywhere.
4. **The fallback inside the handler is written without measurement**, because by then the author
   is reasoning about a case they cannot see. `(aek)`'s `free = 0` sentinel made a genuinely full
   disk pass its own check; `cleanup`'s `continue` conflated *refused* with *already handled*.

⚠ **And twice, the version we were treating as the risk was the one masking a live defect on the
version we ship.** 3.14 turns both `(aez)` and `(afb)` from a crash into a safe skip. The upgrade
work was aimed at what 3.14 would break; what it actually surfaced was what 3.13 was already
doing.

**What this says about the next soak.** The plan's own thesis already named the class - *"SEQUENCE
defects need control, not scale. Interruption, **refusal**, undo, resume"* - and then scheduled no
step that refuses anything. Of the four steps never run, **S6 (interrupt) and S11 (disk fills
mid-copy) are fault injection and should stay**; S9 (`--in-place`) and S10 (`reclaim`) are feature
exercises of the kind that has produced one finding in twelve. **The gap worth filling is
refusal**: no soak step anywhere `chmod`s anything, and refusal has now produced five entries.
Aim the next round at *what the product does when the filesystem says no* - on a source, a
destination, a drive that unmounts mid-run - rather than at more of the library.
