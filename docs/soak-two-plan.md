# Soak two - the step list

**Written 2026-08-21. NOT RUN. Read this before it is run**, and one thing in it needs a ruling
first (§1).

Soak one ran on 2026-08-20, produced five entries, and left **no written step list** - its steps
are recoverable only from the findings. This document exists so soak two's coverage is a decision
rather than a memory, and so the next person can tell what it did *not* look at.

**The method that made soak one work, restated because it is the whole design:** ground truth was
counted independently **before the product was allowed an opinion**. Every step below therefore
has three columns, and the third is the point - *what would count as the app saying something
untrue*. A step with no answer in that column is a step that cannot fail, and should be cut.

---

## 1. ⚠ ONE RULING NEEDED BEFORE THIS RUNS: which corpus

`IMPLEMENTATION_STANDARDS.md` §5 is unambiguous: **`Input/Testing-new` stays out - single copy,
uncatalogued.**

Measured 2026-08-21 (a **snapshot**, per that same clause - not a premise):

| path | files | size |
|---|---:|---:|
| `Input/2013` | 166 | 289 MB |
| `Input/2014` | 2,110 | 6.0 GB |
| **in-fence corpus (2013 + 2014)** | **2,276** | **6.3 GB** |
| `Input/Testing-new` | 1,836 | 4.7 GB |
| `Input` total | 4,112 | 11 GB |

**Soak one recorded 4,111 files and 11 GB.** `2,276 + 1,836 = 4,112`. That reconciles one way:
soak one appears to have run against **all of `Input`**, including the folder the fence excludes.
Stated as an inference, not a fact - the composition may have moved in a day, and the delta of one
file is unexplained.

**Why this is blocking rather than pedantic, and it is specific to soak two.** The fence's stated
reason for excluding `Testing-new` is *single copy, uncatalogued* - it is the maintainer's only
copy. Soak one was **copy-mode**, where including it was harmless: nothing moved, nothing was
deleted. Soak two's list below includes **`--move`, `--in-place` and `reclaim`**, which relocate
and delete sources. Running those over an unbacked folder is a different proposition entirely.

**Two acceptable answers, and the maintainer picks:**
- **(a) In-fence, 2,276 files / 6.3 GB.** The default. Everything below is designed for it.
- **(b) All of `Input`, 4,112 / 11 GB**, with `Testing-new` *excluded from every relocating step*
  by construction - a separate source root for those, never a flag anyone has to remember.

Do **not** resolve this by reading soak one's numbers as precedent. If (a) is chosen, note that
soak two's headline count will differ from soak one's, and that is correct rather than a
regression.

## 2. Cost, measured - and disk is not the constraint

`/data` (which holds `TruestillLibrary`) is **ext4, 916 GB, 813 GB available** (2026-08-21). At
6.3 GB per destination, four destinations is ~25 GB - **3% of free space**. The concern that
"11 GB per destination adds up" does not survive the measurement; **time is the constraint, not
disk**, and the step list is shaped around wall-clock rather than bytes.

Where the time goes, from `PERFORMANCE.md` at 2,275 files: **exiftool read 74.5%**, hashing 23.3%,
everything else under 2% combined. Two consequences the plan uses:

- **The hash cache is what makes re-runs affordable** - an unchanged file is never read twice, and
  a repeat pass measured 3.3x faster. So steps that re-analyse the same corpus are cheap; steps
  that *write* a fresh copy of 6.3 GB are not free but are I/O on local NVMe.
- **Perceptual dedup is O(n²)** and fine at 2,276. Do not read any timing here as a projection to
  33,000 - that is `PERFORMANCE.md` §3's territory and this soak does not measure it.

## 3. Corpus policy: which steps need the real thing

The distinction is not "big vs small", it is **what kind of defect the step is hunting**:

- **POPULATION defects need the population.** The defect only exists at real shape - a layout with
  2,110 files in one year, a trip that spans months, an O(n²) pass, a custody count over thousands
  of rows. A subset cannot produce them, and soak one's `(aei)` is the proof: it needed a *second
  real destination*, not a bigger one.
- **SEQUENCE defects need control, not scale.** Interruption, refusal, undo, resume. Here a large
  corpus is actively worse: a `kill -9` at a chosen moment is easier to land on 200 files than on
  2,276, the re-run costs seconds, and the property under test is *what state was left*, which a
  subset shows exactly as well.

**The subset is `Input/2013` - 166 files, 289 MB, already a real folder with real metadata.** It is
not synthetic, so it keeps the one thing a fixture cannot give: files nobody designed for the test.

⚠ **One trap, from `ENGINEERING_STANDARD.md` §4's forty-sixth member: any step whose subject is
interruption or partial state must run on the storage class it claims to test.** `/data` is ext4,
which is correct. **Do not move the subset to `/tmp` to make it faster** - `/tmp` is tmpfs on this
machine, the copy completes at RAM speed before the signal lands, and the run reads clean for the
one reason that makes it meaningless.

---

## 4. What soak one could not have seen

Not "did not" - **could not**, from the shape of what it ran. This is the coverage argument for
soak two, and each row below becomes a step.

| gap | why soak one could not see it |
|---|---|
| a **second destination** | it organized into one; `(aei)` was found by `status` disagreeing, not by the step |
| **`--move`** | copy-mode only, so `_move_source`, `MOVE_KEPT` and the left-behind report never ran |
| **`--in-place`** | never exercised; the rename path and `inplace_moves` journal are untouched |
| **`migrate-layout`** | never run - and it **rewrites every byte of the library** through its own copy loop |
| **`verify` at scale** | `(aej)` was found in the *reporting*, not by running verify as a step |
| **`reclaim`** | never run; the delete-after-reverify gate has never met a real library |
| **`undo-organize`** | never run; it is the only gate behind the rename path |
| **`clean-empty`** | never run; the only path that removes a directory |
| **a full disk mid-copy** | `(aek)` was found at setup; the copy path met a quota, not exhaustion mid-run |

---

## 5. The steps

Numbered for reference, not strictly ordered - but S1 must run first (it establishes ground truth)
and S12 must run last (it is the re-prove pass).

Legend: **corpus** = `full` (2,276 in-fence) or `subset` (`Input/2013`, 166).

### S1 - Count the ground truth. `corpus: full` · *no product involvement*

| | |
|---|---|
| **Do** | Before Truestill is run at all: count files by extension, total bytes, and SHA-256 every file, with `find`/`sha256sum`/`du`. Record distinct-hash count and the duplicate groups. Write it to a file. |
| **Read** | Nothing from the product. This step exists to have an answer that predates its opinion. |
| **Untrue if** | *(n/a - this is the reference)* ⚠ But note: if this disagrees with soak one's 4,111, §1 is the reason, and it is resolved there rather than here. |

### S2 - Organize into destination A. `corpus: full`

| | |
|---|---|
| **Do** | `organize <corpus> A --apply` into an empty folder. Time it. |
| **Read** | The EXECUTED tally, the skipped buckets, `status`, `where`, `drives`, and A's tree on disk. |
| **Untrue if** | organized + duplicate + skipped + unreadable ≠ S1's file count · the distinct-hash count on A ≠ S1's distinct hashes · `status` claims a redundancy A cannot have (one drive is one place) · any file in S1 is absent from A **and** absent from every report. |

### S3 - Organize the same corpus into destination B. `corpus: full`

| | |
|---|---|
| **Do** | `organize <corpus> B --apply` into a second empty folder. This is `(aei)`'s exact scenario at full scale. |
| **Read** | The tally, `status`, `drives`, `where <sha>` for a sample, and B's tree. |
| **Untrue if** | B receives fewer files than A holds · `status` still reports files on one drive · B registers as a drive with 0 files while reporting success · `where` names only one location for content that is now in two. |

### S4 - Verify both drives, then break one and verify again. `corpus: full`

| | |
|---|---|
| **Do** | `verify` A and B clean. Then delete a **known** set of files from B by hand (record which), and `verify` B again. Then restore them and verify a third time. |
| **Read** | The verify summary, `drives` custody lines, `status`, and the app's Backups screen wording. |
| **Untrue if** | the missing count ≠ the number deleted · `LAST VERIFIED` reads `never` after a verify that ran (`(aej)`'s exact shape, re-checked at scale) · a restored drive still reports files missing after a clean verify - the **clear** direction, which §4's thirty-seventh member says is the unguarded one · custody wording claims two copies for content that now has one. |

### S5 - Migrate the layout on A. `corpus: full`

| | |
|---|---|
| **Do** | Change the layout setting, preview `migrate-layout`, then apply with the typed `move`. **This rewrites every byte of A.** Time it and watch free space. |
| **Read** | The plan preview, the routing table, the journal rows, A's tree before and after, `verify` A afterwards, and `status`. |
| **Untrue if** | the preview's file count ≠ what moved · a file lands somewhere the preview did not name · `verify` fails after a migration that reported success (`file_copies.relative` not updated) · any file is lost or duplicated - S1's hash set must survive exactly · the run reports success while journal rows remain pending. |

### S6 - Interrupt a migration and resume it. `corpus: subset`

| | |
|---|---|
| **Do** | Start `migrate-layout` on a subset drive, `kill -9` mid-run, then re-run. ⚠ ext4, not tmpfs (§3). |
| **Read** | The journal, the tree, what the re-run says it is resuming, and `verify` afterwards. |
| **Untrue if** | the resumed run reports a clean finish while files sit at old paths · the interrupted state reads as complete (`(aem)`'s shape, in `migrate` rather than `organize`) · a file exists at both old and new paths and nothing says so. |

### S7 - Undo the migration. `corpus: subset`

| | |
|---|---|
| **Do** | `migrate-undo` the completed migration from S6's drive. |
| **Read** | The tree, the journal, `verify`, and the catalog's `file_copies.relative`. |
| **Untrue if** | undo reports success with files still at migrated paths · a file whose content changed since is silently clobbered instead of refused and named · `verify` fails afterwards. |

### S8 - Organize with `--move`. `corpus: subset` ⚠ *destructive to sources*

| | |
|---|---|
| **Do** | Copy the subset to a scratch source first (**the source is consumed**). `organize <scratch> C --apply --move`. Include at least one file already on C, so the skip path runs. |
| **Read** | The EXECUTED tally, the left-behind report, the source folder afterwards, `MOVE_KEPT` rows, and the empty-folder offer. |
| **Untrue if** | a source is deleted without its destination copy re-hashing to `copy_sha256` · the left-behind report omits a file still in the source · the empty-folder offer names folders while silently skipping occupied ones · the tally says moved for a file that is still in the source. |

### S9 - Organize `--in-place`. `corpus: subset` ⚠ *rearranges the only copy*

| | |
|---|---|
| **Do** | On a fresh scratch copy, `organize --in-place --apply` with the typed `move`. Then `undo-organize`. |
| **Read** | `inplace_runs` / `inplace_moves`, the tree before and after, and the tree after undo. |
| **Untrue if** | the tree after undo ≠ the tree before, file for file · a rename is journalled that did not happen, or happened and was not journalled · `reclaim` afterwards offers any file whose source **is** the drive copy (`_is_the_copy_itself` - the tautology gate). |

### S10 - Reclaim. `corpus: subset`

| | |
|---|---|
| **Do** | With content on two drives, dry-run `reclaim`, then `--apply` with the typed `delete`. Then disconnect a drive and try again. |
| **Read** | The plan, `--min-copies` behaviour, the reclaim journal, and `status` afterwards. |
| **Untrue if** | a source is deleted while its only proven copy is on a **disconnected** drive · a stale `last_verified` is trusted instead of re-hashing at delete time · single-copy outcomes are not warned · the journal does not account for every deletion. |

### S11 - Fill the disk mid-copy. `corpus: subset`

| | |
|---|---|
| **Do** | The case `(aek)` explicitly did **not** measure: a destination that has room at preflight and runs out **during** the copy. Use a small filesystem sized so the run starts and cannot finish. |
| **Read** | The per-file failures, the destination tree, the catalog, and `rescan`. |
| **Untrue if** | any `.partial` survives · any zero-byte file wears an organized name · catalog rows and files on disk disagree · the run reports success · the failure is a traceback rather than named errors. |

### S12 - One pass re-proving the four fixes. `corpus: full`

**One pass, not seven.** Re-running soak one wholesale mostly re-proves fixed code; this confirms
the four fixes hold at scale and then stops.

| fix | confirmed by |
|---|---|
| `(aei)` | S3 already is this - B receives every file |
| `(aej)` | S4's third verify - `LAST VERIFIED` reads a real timestamp and the counts match what was deleted |
| `(aem)` | `kill -9` a full-corpus `organize` into a fresh drive D at ~10%, then read `status`: it must say **interrupted**, and must not after a completed run |
| `(aek)` | point `organize` at a full filesystem with an unregistered destination: a sentence, exit 4, no marker, no drive row |

---

## 6. Stop rules

- **Stop and write it down on the first finding**, rather than completing the list. Soak one's
  value came from five entries, not from seven finished steps.
- **A step that cannot answer its third column is cut**, not run.
- **Every measurement carries its date** and is a snapshot of this machine
  (`IMPLEMENTATION_STANDARDS.md` §5) - never a fixture, never a design premise.
- **One library is a test bed, never a specification** (§4, twenty-first member). Findings here are
  facts about this corpus; generalising to the product needs its own argument, stated out loud.
