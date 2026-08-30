# Soak nine: the messy library with five fixes in place - record

**Ran 2026-08-30.** Machine: 16 cores, 30 GiB RAM, Python 3.14.4, **ext4 on `/dev/nvme0n1p1`
(`rw,noatime`)** - every timing below is that machine and that filesystem. Corpus built by
`scripts/make_messy_corpus.py` at **seed 20260829**, `--files 2000`, from
`/data/TruestillLibrary/Input` **by copying**; the source was verified byte-untouched afterwards
(file list + sizes, fingerprinted before and after). Everything under `/data/tmp/truestill/messy`.

**Why this soak exists.** Soak eight ran **before** `(aid)`, `(aie)`, `(ain)`, `(aim)` and the
encoding work. Every one of those was proved by injection on **three files**. None had been
verified at scale.

**⚠ COMPLETENESS.** This is a **complete forward arc, a complete reversal arc, and five fix
verifications**. What did **not** run: `reclaim`, `migrate-layout`, `bake`, `clean-empty`, the
dates rescue, `ingest`, and **every app screen**. Named here and again in §8.

---

## 1. The corpus (Q909)

| | soak nine | soak eight |
|---|---|---|
| manifest rows | 8,971 | 8,970 |
| **files on disk** | **8,951** | not measured |
| size | **18.7 GB** (18,699,548,341 B) | 18.7 GB |
| generation | **371 s** | 392 s |
| shapes | 15 (S1-S9, S11-S16) | 15 |

S1 1,994 · S2 1,095 · S3 998 · S4 1,592 · S5 993 · S6 532 · S7 667 · S8 400 · S9 2 · S11 6 ·
S12 2 · **S13 3** · S14 1 · S15 166 · S16 500.

**The long-name shape now straddles the boundary**, which is what P146 moved it for: names of
**204 B** and **244 B**, stamping to 220 and 260 against a 219-byte budget. ⚠ **And it still
cannot exercise `(aid)`** - see §4.

## 2. The answer key, from the BYTES (Q910)

⚠ **Computed by hashing the corpus, not from the manifest**, because the manifest is wrong - §5.

| | |
|---|---|
| files on disk | **8,951** |
| media-extension files | 8,676 |
| distinct contents (sha256) | **2,524** |
| contents appearing more than once | 672 |
| **expected exact-duplicate skips** | **6,427** (**6,157** media-extension only) |
| largest identical group | 52 files, one photograph |
| distinct source photographs | 666 |
| **derived perceptual candidates** | **1,860** - 500 stripped, 1,194 resized, 166 rotated |
| **non-ASCII paths** | **0** |

## 3. The arc (Q911)

| step | elapsed | result |
|---|---|---|
| organize **preview** | **79.9 s** | 8,676 analysed · 864 unique · 1,655 near-dup · **6,157 exact-dup skipped** · 0 unreadable · **to organize 2,519** |
| organize **apply** | **14.3 s** | 6,157 duplicate skipped + **2,519 organized**; **3.0 GB written from 18.7 GB** |
| *dedup* | - | **no such subcommand** - `(ail)`'s retired phantom. De-duplication is inside organize; ran `status` instead: 2,519 files, all single-copy |
| **verify** | **7.7 s** | 2,519 verified · 0 missing · 0 mismatch · 0 unreadable · 0 unverifiable |
| **backup** | **20.4 s** | 2,519 files / 3.0 GB to a second drive |
| **restore** | **0.3 s** | 2 decision documents, 0 to bring back - thin and correct |
| organize **--in-place --apply** | **25.4 s** | 1,229 duplicate skipped · **666 moved by rename** |
| **undo preview** | **1.6 s** | 666 restorable |
| **undo apply** | **5.4 s** | **666 restored; tree path-identical to the original, 1,900 files before and after** |

Categories: Camera 1,825 · WhatsApp 498 · Saved 196.

⚠ **Undo needed two refusals to reach.** Run against the copy-mode arc it answered *"no
relocation run to undo - nothing has been organized in place"* (correct: `undo-organize` reverses
`--in-place` only, and a copy run leaves the source untouched). Run non-interactively,
`--in-place --apply` refused for a typed confirmation (correct). **Both refusals are the product
being right**, and both are why soak eight never reached this half.

## 4. The five fixes (Q912)

⚠ **THREE WERE VERIFIED AT SCALE AND TWO WERE NOT, and five ticks must not read as five.**

| fix | verified by | at scale? |
|---|---|---|
| `(aie)` | the corpus, 2,519 files, `EPERM` at `copystat` | ✅ |
| `(ain)` | the corpus, 2,519 files x 3 runs | ✅ |
| `(aim)` | the corpus, a stop after 400 of 8,676 | ✅ |
| `(aid)` | **six constructed files** - the corpus cannot reach it | ❌ |
| encoding | **five constructed files** - the corpus holds none | ❌ |

`(aiu)` is why, and it is filed rather than worked around silently. The two constructed
verifications are real evidence **about the product** and no evidence at all **about the corpus** -
which means the next soak inherits the same blind spot until `(aiu)` is built.


### `(aid)` - VERIFIED, and **not by the corpus**

⚠ **Both S13 long-name files are exact duplicates** (their content appears 22x and 18x), and
`_organize_each` skips a duplicate **before** it composes a name - so the long name is never
built and the refusal is never reached. **P146 made the shape straddle the byte boundary but not
the code path.** Filed as `(aiu)`.

Verified instead with six **unique-content** long names. Staging overhead **20 B** this run, so
the budget is **219**:

| original | stamped | result |
|---|---|---|
| 200 / 210 / **218** B | 216 / 226 / 234 | **organized** |
| **220** / 226 / 240 B | 236 / 242 / 256 | **refused**, exit 1 |

> `its organized name needs 256 bytes and this drive stores at most 255 in one name, including
> the 20 Truestill needs for the temporary file it copies through. Shorten the file's name by at
> least 1 byte and run this again. Nothing was written, and the original is untouched.`

Shortfalls named: **1, 7 and 21 bytes**. The boundary sits exactly where
`layout.name_shortfall_bytes` computes it.

### `(aie)` - HELD over 2,519 files

`EPERM` at `copystat` for the whole run: **exit 0**, 2,519 organized, **2,519 catalog copies**,
**0 `.partial` left**, 0 orphans, every file named under `METADATA NOT SET`. Before the fix this
run discards **all 2,519 verified copies**.

### `(ain)` - HELD, and the clock shows it

`EPERM` at `set_timestamp` on every committed file, then two clean re-runs:

| run | elapsed | on disk | catalog |
|---|---|---|---|
| 1 (injected) | 91.4 s | 2,519 | 2,519 |
| 2 (clean) | **4.1 s** | 2,519 | 2,519 |
| 3 (clean) | **1.7 s** | 2,519 | 2,519 |

Nothing re-written. **Before the fix: 2,519 orphans, then 2,519 `_1` copies, then 2,519 `_2` -
7,557 files from 2,519 photographs.** The 4.1 s second run is the fix visible as time.

### `(aim)` - HELD on a stopped run at scale

`ENOSPC` after 400 copies:

```
EXECUTED
    400  organized ·  13  duplicate, skipped ·  1  failed ·  8262  not attempted
```

**400 + 13 + 1 + 8,262 = 8,676 = `files analysed`.** Exit 4. On the clean apply the plan block
heads itself *"SUMMARY - the plan. What happened is in EXECUTED, below."* and **`to organize:
2,519` equals EXECUTED's `2,519 organized`** - the promise matching the outcome over 8,676 files.

### encoding - HELD, and **not by the corpus**

⚠ **The corpus holds zero non-ASCII paths**, so it cannot test this at all - the same gap
`(aid)`'s own table records about the suite. Filed with `(aiu)`. Verified with five constructed
names: all keyed correctly through exiftool's door, all organized, catalog relatives intact -
`2012/…/20120615_180345_京都の紅葉.jpg`, `…/20140815_073647_emoji_🌅_sunrise.jpg`,
`Saved/2013/…/20131018_161410_Москва_зима.jpg`.

## 5. The answer key versus the product (Q913)

**Exact duplicates - an exact match, with no reconciliation needed.**

```
media files on disk        8,676  ==  analysed          8,676
distinct media contents    2,519  ==  catalog files     2,519
expected exact-dup skips   6,157  ==  reported          6,157
                           2,519 + 6,157 = 8,676 ✓
```

Soak eight had to explain a 284 gap (the `.chk` files organize skips by extension); computing the
key over media extensions removes that confound and the remainder agrees exactly.

**Perceptual - all 1,860 derived files scored, none sampled:**

| role | n | paired (≤5) | missed | median | p90 | max |
|---|---|---|---|---|---|---|
| stripped | 500 | **499** | 1 | 0 | 1 | 24 |
| resized-half | 398 | **392** | 6 | 0 | 1 | 28 |
| resized-quarter | 398 | **391** | 7 | 0 | 2 | 22 |
| resized-web | 398 | **389** | 9 | 0 | 2 | 26 |
| rotated | 166 | **1** | 165 | 32 | 38 | 46 |
| **excluding rotation** | **1,694** | **1,671** | **23** | | | **98.6 %** |

🔑 **Identical to soak eight, role for role.** Five fixes changed nothing the tier does, which is
the null this soak most wanted.

**False pairs: ZERO, hand-scored, all of them.** All-pairs over the 2,491 files above
`(ahq)`'s no-signal floor: **3,101,295 comparisons, 4,011 pairs within threshold 5**, of which
3,966 are the same source photograph and **45 are cross-source**. Resolving each side to the
Input photograph it descends from, those 45 collapse to **three relationships**:

| d | pair | what it is |
|---|---|---|
| 0 | `DD/2014816101549.jpg` ↔ `DD/2014816101549_1.jpg` | **one photograph stored twice** in Ad's library |
| 2-3 | `IMG_20200714_213432_Bokeh` ↔ `…_213435_Bokeh` | **a burst, three seconds apart** |
| 4-5 | `Vj 1/DSC_2141.JPG` ↔ `DSC_2142.JPG` | **consecutive camera frames** |

The same three soak eight found, reproduced independently. Histogram: `0:2580 · 1:937 · 2:313 ·
3:120 · 4:35 · 5:26`. **The tier never joined two photographs that are not of the same moment.**

## 6. What broke (Q914)

Four findings, all from reading artifacts rather than exit codes. **Three of them are things a
green run would have hidden.**

🔑 **`(ait)` RANKS ABOVE THE OTHER THREE, AND IT IS NOT A PRODUCT DEFECT AT ALL.** The other three
are each one wrong sentence on one screen. `(ait)` is a **wrong answer key**, and every future
soak scores the engine against it - so it corrupts measurements silently and without limit, and a
soak that trusted it could exonerate a real defect or manufacture a phantom one. It already did
the second: soak eight's *"284 missing"* was the instrument, not the engine (see that record's
2026-08-30 correction). **That is `(aiv)`'s shape one layer up** - a count nobody can act on,
except here the reader is the next soak rather than a user.


1. **`(ait)` - the corpus manifest overstates by 20 files and 20 rows carry a stale `sha256`.**
   `make_messy_corpus.py` keys every destination on `source.name`, and this library holds two
   pairs of *different* photographs sharing a basename (`IMG_0386.JPG`, `Photo0268.jpg`). Each
   pair collides at ten destinations; the second write wins. ⚠ **Soak eight's published answer
   key carries the same error** - same seed, same source.
2. **`(aiu)` - two of the five fixes could not be exercised by the corpus at all.** `(aid)`'s
   long-name files are exact duplicates, so dedup skips them before a name is composed; and the
   corpus holds **zero** non-ASCII paths. Both were verified by constructed inputs instead. A
   shape that cannot reach its subject is `ENGINEERING_STANDARD.md` §4's silent instrument.
3. **`(aiv)` - `cli._reason_key` collapses neither message shape, so `(afd)`'s cap misreports.**
   The `(aie)` run printed *"and 2,499 more METADATA NOT SET (**2519 distinct reasons in
   total**)"* for **one** fact: the mount refused timestamps for the whole run. Both
   `_upload_failure`'s *"could not copy `a.jpg` to '…'"* and
   `drive_unwritable.metadata_not_preserved_note` lead with the source filename **unquoted**, and
   `_reason_key` only strips quoted fragments. `(afd)` exists precisely to stop 2,096 failures
   from one condition reading as 2,096 reasons.
4. **`(aiw)` - `undo-organize` emptied 90 folders and reported none.** The same run's organize
   prints *"Empty folders left behind are reported, never deleted"* and does report its own
   (*"1 folder(s) are now empty"*). `(afi)` wired that offer into `migrate-layout` and then
   organize; **undo is the third path that empties folders and stays silent.**

**What was checked and was clean**, so this is not a soak that did not look: `.partial` debris
after every injected run (**0**), catalog-versus-disk on all four drives (**no orphans, no
missing**), the two "extra" files on disk (`.truestill-drive.json` and `.truestill-decisions.json`
- both expected), the `_1`/`_2` suffix scan (**5 hits, all original source filenames in the
corpus, not collision suffixes** - a false positive in my own harness), verify over 2,519 copies,
and the undo tree compared path-by-path against the original.

## 7. Does the engine hold? (Q915)

**Yes, for the arc that ran, and the answer is stronger than "the fixes work".**

- **Nothing was lost anywhere.** Across five full-corpus runs including three with a syscall
  refused for every file, the catalog and the disk agreed **every time**: 2,519 = 2,519, no
  orphans, no debris, no unrecorded copies.
- **The reversal arc closes.** 666 files moved by rename and 666 restored, tree identical.
- **The two properties most likely to destroy data both held**: a metadata refusal never
  discarded a verified copy `(aie)`, and never orphaned a committed one `(ain)`.
- **The counts a user reads are now honest on the path that used to lie** - a stopped run
  accounts for all 8,676 files, and the promise equals the outcome.
- **The de-duplication tier is unchanged by all five fixes** - recall identical to soak eight,
  role for role, and zero false pairs over 3.1 M comparisons.

### ⚠ The scope, plainly

**This soak ran on ext4 and nothing else.** No SMB, no NFS, no FUSE, no exFAT, no FAT32 - *which
is the product's actual subject matter*, and the class of destination `(aie)` and `(ain)` were
both filed against. No Windows and no macOS. **Seven commands were never run**: `reclaim`,
`migrate-layout`, `bake`, `clean-empty`, `ingest`, `repoint-sources` and the dates rescue, plus
every app screen.

**This is not evidence that no engine defect remains. It is evidence that this arc did not
provoke one.** The four findings are all **instrument or reporting** defects, which is what a soak
over a corrected engine should be expected to find - and finding only those is a weaker statement
than finding nothing, because two of the five fixes were never put to the corpus at all (§4).

## 7b. What to build next (Q920)

Ranked against each other **and** against what is already open. The axis is *what does a user lose
if this is left standing*, with instrument defects judged by what they cost the next measurement.

| rank | item | why here |
|---|---|---|
| **1** | **`(ait)`** | A wrong answer key corrupts **every** future soak, silently and without bound. It has already produced one false finding (soak eight's "284 missing"). Nothing else on this list can mislead an entire measurement programme. **Two lines in `CorpusWriter`** to refuse a repeated path - the smallest fix here by a wide margin |
| **2** | **`(aiu)`** | Same file, same session, and it is the reason two of five fixes were never put to the corpus. Fixing `(ait)` without it leaves a correct key over a corpus that still cannot reach `(aid)` or the encoding seam |
| **3** | `classify_unwritable`'s `EPERM`→`REFUSED` versus `persists_for_the_run`'s `EROFS` | The **third `(aie)` repair**, open since P141. One errno is called *"the drive refuses writes"* and *"not persistent"* at once. It decides **whether a run stops**, so it is the only open item here that can change what happens to files rather than what is printed about them |
| **4** | **`(aiv)`** | Measured at scale, and the sentence is on screen for every file of a refused run. But nothing is lost, and its honest fix is `(aep)` - structured `detail` - not another pass at a text heuristic |
| **5** | `(aip)` | Migrate/backup silent metadata degradation. Real, unmeasured, and its `relocate` half may be unreachable in practice |
| **6** | `(aiw)` | A broken promise on a command a user reaches for when already unhappy. Empty directories are inert and `clean-empty` works |
| **7** | `(aio)` | Unreproduced, Windows-triggered, one narrow window on the bake path |
| - | Condition 1's last two, condition 3 | **Not ranked here on purpose.** Both are `PROJECT_STATUS.md` §4 programme conditions with their own blockers - condition 3 is BLOCKED on an untyped consumer and retires only when `app.js` goes (`(ahn)`). Neither is a defect this soak has anything to say about, and ranking them beside soak findings would imply otherwise |

🔑 **I would build `(ait)` next, and it is not a close call.** It is the cheapest item on the list,
it is the only one whose harm compounds across future work rather than sitting still, and
**leaving it means the next soak's numbers cannot be trusted - including any number that would be
used to justify the other six.** `(aiu)` should ride in the same commit: they are one file, one
session, and one class - *a corpus that does not test what it claims to*.

⚠ **The argument against ranking `(ait)` first, stated rather than dodged**: it ships nothing a
user sees, and three product-visible findings sit below it. That is exactly the trade `(ago)`
warns about in the other direction - a new artifact must earn itself - so the case here rests on
`(ait)` being a *correction to an existing instrument*, not a new one, and on it having already
produced a false finding rather than being predicted to.

## 8. What was NOT run

`reclaim`, `migrate-layout`, `bake`, `clean-empty`, `ingest`, the dates rescue, and **every app
screen**. `(aid)`'s **character** half (a colon legal on ext4, refused by NTFS) is unreachable
here by its own premise and remains an `xfail` on the Windows lane. No timing here is a
cross-platform claim.
