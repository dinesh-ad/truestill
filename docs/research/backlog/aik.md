# (aik) NOTHING READS A META ARCHIVE'S SIDECAR, AND ITS MEDIA ARRIVES STRIPPED.

*Body of backlog entry `(aik)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aik) NOTHING READS A META ARCHIVE'S SIDECAR, AND ITS MEDIA ARRIVES STRIPPED.** Filed
  2026-08-29 (P135), from source. **A gap, not a design** - what is established is below, and the
  three things that are not are named as such.

  ## THE EVIDENCE

  A Facebook or Instagram "download your information" archive ships media with **metadata
  stripped** and the dates **separately in JSON** (`timestamp_ms`). So the photograph carries no
  date and the date carries no photograph, and only the pairing recovers it.

  **Nothing in the product reads that pairing.** Every `json.load*` in `packages/*/src`,
  enumerated rather than sampled:

  | file | what it reads |
  |---|---|
  | `takeout.py` | **the only media-sidecar reader in the tree** |
  | `drive.py` · `decisions.py` · `run_record.py` · `hash_cache.py` · `archive_extract.py` | truestill's own files |
  | `exif.py` | exiftool's own output |

  `takeout.py` is Google-specific at **both** ends: `parse_sidecar` reads `photoTakenTime` /
  `creationTime`, and `_SUPP_RE` matches Google's *supplemental-metadata* naming and its
  truncations. A Meta archive shares the idea and none of the spelling.

  🔑 **The prior art is inside the product, and the shape is already ruled.**
  `takeout.SidecarIndex` is the index-then-O(1)-lookup design
  [`takeout-format.md`](../../takeout-format.md) §1 records as what mature tools converge on. And
  `takeout.py`'s own docstring pre-commits the answer to the design question before it is asked:

  > *"If a second service ever ships a sidecar format, **it gets its own module beside this one**
  > rather than a widened name here."*

  ⚠ **And this is genuinely unexamined rather than previously refused.**
  [`messenger-dates-research.md`](../../messenger-dates-research.md) ruled on messenger **filename
  conventions** - the live-folder case, where a name like `IMG-20250804-WA0020.jpg` is a delivery
  date. It never looked at an **archive**, which is a different producer with a different artifact.

  ## THE THREE THINGS TO ESTABLISH BEFORE ANY CODE

  1. **Whether the export format is stable.** `takeout-format.md` exists *because* Google's sidecar
     naming turned out to be a moving target with at least five spellings and a length cap that
     truncates the word `supplemental-metadata` at arbitrary points. Meta's export has no
     comparable field notes in this repo, and assuming stability is how the Takeout work would have
     gone wrong.
  2. **Whether the date attaches to a MESSAGE rather than to a file.** A Messenger archive's JSON
     is a *conversation* log. If `timestamp_ms` belongs to a message that carries an attachment,
     the join is one-to-many and ordered - a different problem from Takeout's
     one-sidecar-per-media, and `SidecarIndex`'s shape may not carry over.
  3. ⚠ **A Meta date arriving under `DateSource.TAKEOUT` would name the wrong producer.** That is
     `(afl)`'s class - the provenance record must say what the evidence actually was - and it is a
     **contract consequence, not an implementation detail**: either the members generalise, or the
     new module brings its own. `models.DateSource`'s ladder is ordered by *what the evidence is*,
     so a new member has to say what it is evidence OF.

  **The honest first step is a field-notes document** - `docs/meta-export-format.md`, the way
  `takeout-format.md` preceded the Takeout work - **not code.**

  ## ⚠ THE FALSE PREMISE THIS LETTER WAS TWICE GIVEN, RECORDED SO NOBODY RE-DERIVES IT A THIRD TIME

  `(aik)` was specified twice as a **folder-date tier**: *"a camera filename beats a YEAR-ONLY
  folder"*, and *"`year_only` is on the record and dropped before the reader"*. **No such tier
  exists, and the null had already been reported from the other direction in P132** before the
  second specification arrived. Four checks establish it, all against today's code:

  1. **`dates.resolve_capture_datetime` touches `path` exactly twice** - `_exif_tier(...)` and
     `_filename_capture_date(path.name)`. **`path.parent` appears zero times** in the function.
  2. **No folder-date extractor exists** in `packages/*/src` - no `date_from_folder`, no
     `folder_date`, no `def …folder…date…`.
  3. **`year_only` does not exist.** Its only two hits in the whole tree,
     `truestill_app/service/date_rescue.py` and its test, say the **opposite**: *"``captured_at`` is
     a ``datetime``; the model has **no year-only or month-only form**."*
  4. **`folder_hint.py` is a name suggester, not a date reader.** Its `_LEADING_DATE` and
     `_TRAILING_YEAR` regexes **strip** dates out of a folder name to propose a clean trip name;
     its only caller is `service/trips.py`'s `suggest_name`.

  Measured, not argued - the three cases the specification asked to be *made* true are **already**
  true, because the folder is never a contender:

  | path | today |
  |---|---|
  | `Wedding 2019/DSC_0043.jpg` | `None` / `none` - unchanged |
  | `2019 Backup/IMG_20140816_170748.jpg` | **`2014-08-16`** / `filename` |
  | `2019 Backup/IMG-20190712-WA0001.jpg` | `None` / `none` |

  ⚠ **If dating a photo from its folder is ever wanted, it is a NEW CAPABILITY and not a repair** -
  and it collides with `IMPLEMENTATION_STANDARDS.md` §1's *dates are never guessed* and with
  `(aco)`'s retirement. It needs its own ruling first.

  ## ⚠ THE MIDNIGHT NOTE - REPORTED, NOT A DEFECT, SO NOBODY FILES IT AS ONE

  A filename date lands at **00:00:00**: `IMG_20140816_170748.jpg` resolves to
  `2014-08-16 00:00:00` even though the name carries `170748`, because `date_from_filename`'s
  patterns take the date and drop the time.

  **This is NOT PhotoPrism #1102's completion.** There, a partial date is silently *completed* with
  a default - the 1st of the month - so a value is invented. Here **nothing is invented: the date
  is real and the time is simply absent**, and `DateSource.FILENAME` sits outside
  `models._TRUSTED_DATE_SOURCES`, so the file is already flagged approximate and reviewable.
  Measured on soak five's catalog: **18 filename-dated files, every one at midnight, every one
  correct** - checked at source, they either carry no date tag at all or carry a
  `0000:00:00 00:00:00` sentinel that `dates.HARD_SENTINELS` refuses, so the filename genuinely was
  the only evidence.

  ## RELATED

  `(aih)` (the stripped-copy placement this shares a cause with), `(afl)` (provenance must name the
  real producer), [`takeout-format.md`](../../takeout-format.md),
  [`messenger-dates-research.md`](../../messenger-dates-research.md),
  [`soak-eight-record.md`](../../soak-eight-record.md).
