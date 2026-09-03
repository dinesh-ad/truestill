# Soak seven: the messy library - plan

> ⚠ **RAN 2026-08-29 - the results are in [`soak-eight-record.md`](soak-eight-record.md)**, and this plan is left as written: it is the
> prediction the record grades (noted 2026-09-03, P203; a status line below that says otherwise is the record).

**The plan, written before the run.** Soaks five and six had no plan document and both records are
poorer for it; this exists so the prediction below cannot become a rationalisation afterwards.

## Why this soak, and why now

Ad's library is realistic in **scale** and **format** and not in **mess**. Measured 2026-08-29:
the personal material under `Input/` is **7,527 files, 7,436 of them `.jpg` (98.8%)**, with **54
duplicate basenames** in the whole tree; soak five put duplication at **35 exact duplicates in
10,745 files (0.33%)**. One source, one naming convention, no cross-drive duplication history.

**Six soaks varied what the product was asked to do - scale, refusal, deletion, reversal - while
holding the shape of the input constant.** This varies the other axis. `soak-two-plan.md` is the
only document that ever named it, hypothetically: *"Copy from them into `TruestillLibrary` first
**if a messy tree is wanted**."* Nobody did.

The corpus is built by `scripts/make_messy_corpus.py` - deterministic, seeded, manifest-bearing,
and unable to write outside its output root. The corpus itself is not committed; the generator and
this plan are, so a finding is citable by (seed, source, commit).

## The shapes, and the field evidence each comes from

| | shape | witness |
|---|---|---|
| S1 | one photo, different names, different trees | *"the same file name, but not always"* |
| S2 | one photo **35 times** (plus a 2–6× tail) | a backup where one file appeared 35 times; 75 GB → 220 GB |
| S3 | EXIF-stripped copy beside its dated original | re-encoded WhatsApp/web copies |
| S4 | the same photo at half / quarter / web size | Flickr, PSE and phone exports |
| S5 | backup-of-a-backup, nested three deep | the 75 → 220 GB amplification |
| S6 | crash-rescue folders - `FOUND.000/FILE0001.CHK`, `recup_dir.1/f0012345.jpg` | *"two crashes where files were painstakingly stripped off"*; both are real chkdsk / PhotoRec artifacts |
| S7 | Picasa-era album beside an untouched `DCIM/100ANDRO` dump | *"Picasa, PSE, Flickr, an external drive and a phone"* |
| S8 | the same photo on **separate drive roots** | *"50,000 images across EIGHT hard drives"* |
| S9 | case collision (`IMG_0001.JPG` / `img_0001.jpg`) | Windows is the launch platform (`DECISIONS.md` D9) |
| S11 | `Thumbs.db` / `desktop.ini` / `.picasa.ini` as a population | present in Ad's library only as a trace (9 `.db`, 11 `.ini`) |
| S12 | zero-byte and truncated files | failed copies across *"three or four PC upgrades"* |
| S13 | 12-deep nesting and a 200-character name | `(aid)` is open on exactly this, with no corpus behind it |
| S14 | orphan sidecar (`.json` with no media) | multi-tool history |
| S15 | a rotated copy | multiple phones; `hashing.perceptual_hash` never calls `exif_transpose` |
| S16 | folders that encode the migration (`Old PC`, `To Sort`, `New folder (2)`) | *"three or four PC upgrades"* |

**One shape deliberately absent.** *"Backup copies whose mtime is the copy date, so dating
breaks"* cannot break anything: `models.DateSource` has **no filesystem-mtime tier**, and
`dates.py`'s `DATE_TAGS` refuses mtime by name - *"Every comparable organizer falls back to it,
and it is their most-reported dating complaint."* Recorded so nobody re-proposes it, and worth
*confirming* in the run as a strength no soak has demonstrated.

## The prediction

### S3 is the highest-value bet, and the field agrees

The prediction: **an EXIF-stripped copy and its original end up in different folders, and nothing
bridges them.** The stripped copy has different bytes (often a unique size, so `scan._needs_sha`
never computes a SHA-256 at all - `(aac)`'s open conflation), so the exact tier misses; its pixels
are untouched, so its dHash distance is **0** and it is flagged a near-duplicate; `should_upload`
is `exact_duplicate is None`, so it is **copied in**; and `dates.resolve_capture_datetime` finds
no EXIF, so it falls to `FILENAME` or `Undated/`. Original at `2015/2015-09/`, twin in `Undated/`.

**This is where every incumbent is weak, which is what makes it worth building rather than a
curiosity:**
- **Immich #8661** - an EXIF-less photo is filed at its **upload** date, and web and mobile
  disagree with each other about it.
- **PhotoPrism #1102** - every WhatsApp photo lands on the **1st of the month**.
- An **Immich maintainer** answers that bad WhatsApp metadata *"is to be expected"*.
- **LibrePhotos** is the only one with a real answer: **configurable date rules with priorities** - which is our tier ladder (`models.DateSource`) made user-editable.

### ⚠ The null, and it is the opening

**Nobody propagates a date from a duplicate that has one.** `whatsapp-media-tools` exists as a
separate repository solely to restore dates from filenames and delete duplicates - a gap every
incumbent left open, filled by a third-party script.

Truestill is one step from the answer nobody has: **measured on the corpus, the perceptual tier
pairs the stripped copy with its dated original at distance 0–1**, so the date is recoverable
*from the pair*. Today nothing consumes that link - `dates.py` never reads `near_duplicate`.
**Not built here. Recorded so that the corpus is the evidence for the letter**, and so the letter
is filed against a measurement rather than an idea.

### S4 should pair BY CONSTRUCTION, and a failure would mean something else

`imagehash.dhash` converts to grayscale and resizes to 9×8 before comparing, so **resizing is
precisely what dHash is invariant to.** Validated on the built corpus: quarter-size and web-size
copies pair at distances **0–1** against a threshold of 5.

⚠ **So if S4 fails to pair in the soak, that is a defect in the hashing path - not a finding about
messy libraries, and the two must not be confused.** The genuine open question is the *tail*:
`hashing.py`'s own note says *"re-encodes/resizes of one image typically differ by 0–6 bits"*
while `DEFAULT_PHASH_THRESHOLD` is **5**, so its stated tolerance exceeds its own cutoff. The
soak's job is to measure that distribution on real photographs, not to check that resizing works.

### The rest of the prediction

- **The brief's "dedup at scale" guess is mostly killed by the code.** `DedupIndex._by_sha` is a
  dict written with `setdefault` and duplicates are never registered, so 35 copies cost 35 lookups;
  `PERFORMANCE.md` §3.0 measures matching at ~0.8–1.3 ns/pair, so 20,000 files ≈ 0.2–0.3 s.
  **The genuine quadratic is `organizer._free_relative`**, which probes `_1`, `_2`, … for name
  collisions: **≈ k²/2 `destination.exists()` calls, about 630 for a 35-way group**, and a network
  round-trip each on `RcloneDestination` with a cold listing.
- **The real scale cost is the hash cache.** The perceptual hash is a ~69.8 ms Pillow decode, and
  `HashCache` keys on (path, size, mtime_ns) - so renamed and re-copied files, which is all this
  corpus is, **miss the cache**. Decode time should scale with copies, not with photographs.
- **`(ahq)`'s no-signal floor amplifies.** The predicate is a function of the hash alone, so if one
  photo's dHash has popcount ≤ 5, **all 35 copies are refused** registration.
- **Two "near-duplicate" counts will diverge.** `Catalog.stats_near_duplicate_flagged_count` counts
  exact hash-string collisions while the run counts Hamming distance - *"Two populations, one word,
  neither citing the other."* A corpus of pixel-identical stripped copies is what drives them apart.
- **A 35-way group leaves no durable trace**: `stats.py` reports `"exact_duplicates_found": None`
  because exact-duplicate skips are not stored in the catalog.
- **Nothing can say "35".** There is no group concept; matches are pairwise, each naming the same
  `argmin`-first twin, so the CLI prints 34 blocks naming one path.
- **S15 is confirmed already**: rotated copies hash at distance **20–35**, far outside threshold.
- **Predicted PASS**: dates survive backup-of-a-backup nesting intact, and exact-duplicate
  matching stays correct however many copies exist.

## S9 and the lane it cannot run in

S9 is emitted **unconditionally**, and its assertion **skips on ext4 with a named reason**: on a
case-sensitive filesystem the two names are simply two files and the collision cannot be observed
at all. The shape is in the corpus for the day someone runs this on Windows or APFS - the same
lane asymmetry `(aif)` was measured by, where the instrument is built before the platform that can
answer it. The test probes the filesystem rather than trusting `sys.platform`, because the
platform name is a guess about a filesystem and this shape's whole subject is what the filesystem
does.

## ⚠ The honest limit

**This manufactures the mess we can imagine from what a handful of people wrote in public forums.
It cannot manufacture the mess nobody described.** Three limits, stated so the corpus is never
mistaken for having replaced real users:

1. **The distribution is invented even where the shapes are real.** "35 times" is one reported
   backup; whether the modal user has 2× or 12× is unknown. The corpus is not a rate.
2. **A curated mess is still curated** - it contains exactly the confusions its author thought of.
   `(adp)` is the precedent: 33% of a real corpus was drawn sideways and found only by rendering
   real photographs, not by reasoning about them.
3. **Finding nothing would not mean the product is ready.** `PROJECT_STATUS.md` §1's warning
   applies: *"Yield is falling and the method is what to watch."*

## Running it

```sh
uv run python scripts/make_messy_corpus.py \
    --source /data/TruestillLibrary/Input --out /data/tmp/truestill/messy --files 2000
```

`Input/` is **source material: copied from, never pointed at.** The generator refuses an output
root inside the source, and `CorpusWriter` refuses any write outside its own root - both asserted
in `test_the_messy_corpus_generator.py` rather than intended. At `--files 60` the corpus is 320
files / 610 MB, so `--files 2000` lands near 20 GB; `/data` had 652 GB free on 2026-08-29.
