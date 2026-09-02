# (r) Analyze mode - the hash cache half is SHIPPED.

*Body of backlog entry `(r)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(r) Analyze mode - the hash cache half is SHIPPED.** The placement clause fired: a soak run
  previewed an unchanged 2,275-file source twice and re-hashed it both times, so the cache was
  built first. Per the clarified binding, cache-first alone is fine - what the binding forbids
  is shipping Analyze *without* it, and Analyze will now arrive with it already underneath.
  - **Shipped:** `hash_cache.HashCache`, a sidecar `catalog.cache.sqlite`. Measured on
    12 MP-class photos, a repeat preview at 2,275 files went **15.8s -> 4.7s (3.3x)**; the
    remaining 4.7s is exiftool. Invariants in `IMPLEMENTATION_STANDARDS.md` §8.
  - **The measurement that changed the recorded spec:** it said "path+size+mtime -> sha256".
    That alone would have recovered ~5% of the wait - the size pre-filter already spares
    SHA-256 for ~94% of realistic-size files, while the *perceptual* hash runs for every image
    at ~69.8 ms against SHA-256's ~8.5 ms. Caching both is the feature.
  - **Next, on this evidence:** exiftool is now essentially the whole cost of a repeat preview.
    A metadata cache is the natural follow-on and is deliberately a **separate item** - metadata
    feeds *dating*, so a stale row could change where a photo lands, a class of risk the hash
    cache structurally cannot have.
  - **Still to build (corrected 2026-09-02, P186):** tier 2b - look-alikes, `perceptual=False` in
    `cli.py:_cmd_analyze` - and commit 4, the app screen; `server.py` and `app.js` have no `analyze`.
    Tiers 1 and 2a and the streaming of 3b ship.
  - **Tier 0 SHIPPED on the CLI, 2026-08-03** - `truestill analyze <folder>`. The census only:
    file count, total bytes, photo/video/audio split, per-extension formats, the skipped and
    unrecognized census, and folders that could not be listed. **Measured 0.31 s wall for
    2,269 files / 6.65 GB** on a local disk, which is what makes it the tier that earns trust:
    it answers before a user wonders whether anything is happening.
    - **It jumped the post-launch placement deliberately**, and only this tier. It is a
      reporting layer over `inventory_source`, which `(tt)` had already shipped app-only; the
      asymmetry - a fact the app could state and the CLI could not - was most of what tier 0
      cost. Nothing in the expensive path moved.
    - **Requires a folder and nothing else**: no destination, no catalog, no registered drive,
      and it deliberately does **not** accept `--db`. Pinned by
      `test_no_destination_no_catalog_and_no_registered_drive_are_needed`, because a later
      refactor that added a destination parameter would kill the funnel silently.
    - **The one engine change:** `SourceInventory` now carries `unreadable_dirs`.
      `scan_source` already found them and `inventory_source` discarded them, which made "no
      files found" and "that folder could not be opened" the same answer - `(aac)`'s defect on
      a new surface. Plumbing, not a new fact: no extra walk, no extra `stat`.
    - **Known gap, recorded not built:** the app's `/api/organize/inventory` payload still
      omits `unreadable_folders`, while the preview's empty branch carries it. That asymmetry
      predates this commit and belongs with the app work.
    - **Polished 2026-08-03 from the first real-library run** (32,628 files / 192.49 GB on a
      cloud FUSE mount), which surfaced two things 2,269 test files could not:
      - **The unrecognized extension list was unbounded** - 279 files carried 200+ distinct
        one-off extensions (apparently truncated transfers) and printing them all buried the
        report. Now capped by **two** bounds, count and rendered width, with the total left
        exact. A count alone does not bound a line: those artefacts are ~25 characters each,
        so a twelve-entry cap still produced a ~300-character line. The elision names how many
        of the hidden extensions were **seen once**, which is arithmetic; it does not say they
        are truncated transfers, which would be a diagnosis the census cannot support.
      - **Elapsed wall time is now reported**, with a files-per-second figure **withheld below
        one second** - under that it describes interpreter startup and the page cache rather
        than the source. This is expectation-setting, not a benchmark: tier 0's wall time is a
        direct signal of how the source behaves, so a slow one tells a user the expensive
        tiers will be long before they commit to them. `PERFORMANCE.md` still owns benchmarks.
    - **Commit 2 shipped 2026-08-03: the facts that existed but were unreachable.**
      `bytes_saved`, `bytes_near_dup`, `oldest` and `newest` were computed inside the app's
      `_completion` and were therefore available only *after* an organize - the wrong way round
      for a preview. They now live in `truestill_core.insights`, which the CLI preview, the app
      run and (later) Analyze all call. **Sizes are injected rather than measured**: a finished
      run sizes the file where it landed, a preview can only size the source, and baking either
      choice into core would make one of the two lie.
      - **Near-duplicate bytes are not savings, and the type refuses to imply otherwise.**
        Truestill *keeps* a near-duplicate, so no operation returns those bytes;
        `reclaimable_bytes` is exact-duplicates only. Pinned on the **wording** as well as the
        numbers - a rewording to "freed" would be a promise the product does not keep, and no
        numeric assertion would catch it.
      - **The move is proven, not assumed.** `test_insights_match_the_run_summary.py` is a
        characterization test that was green **before** the refactor and stays green after. It
        matters because the two sides select differently: `_completion` filters on
        `ActionStatus`, the core producers partition on the resolution's duplicate fields.
      - **New:** a per-year capture histogram (undated counted, never dropped, so the column
        reconciles with the file count) and a capped largest-files list. **Counts, not bars** -
        a real library spans three orders of magnitude between its quietest and busiest year,
        so a linear bar saturates and a log bar makes a proportion claim that is not true.
      - **Still tier 1-2 facts.** They appear in the organize *preview*, which does the
        expensive pass. `truestill analyze` remains tier 0 and still says *not yet analysed*.
    - **Commit 3b shipped 2026-08-04: each tier reaches the screen as it completes.**
      `(r)`'s own escape clause - *"earlier if the soak shows repeat-run pain at real scale"* -
      was satisfied by evidence rather than argument: `truestill analyze` on the 192 GB library
      took **54 minutes at 3% CPU**, about 105 s of computation stretched over 54 minutes of
      waiting on the mount (~31x I/O to CPU). Tier 0 finished in 21 s and **the remaining 53
      minutes produced nothing at all**.
      - **The sequencing was already right, which is the finding that shaped the commit.**
        `test_the_census_prints_before_the_expensive_work_starts` has pinned since 3a that the
        census prints first. It was invisible anyway, for two reasons that are not ordering:
        **nothing reported progress** during the slow tiers (`_analyze_deep` passed no
        `progress=` to either `read_metadata` or `resolve`), and **stdout is block-buffered when
        it is not a terminal** - demonstrated before the fix: a redirect file stays *empty* for
        the whole of the slow tier. So the work was progress, a stream split and a flush; no
        write was re-ordered.
      - **Results to stdout, progress to stderr** (`IMPLEMENTATION_STANDARDS.md` §9), so
        `truestill analyze <path> > report.txt` leaves a clean report while the terminal shows
        the run. **Nothing that reads the output moved**: every result line stayed on stdout,
        which is where all 42 existing analyze assertions read it, and no test anywhere asserted
        progress text. Verified: no script or package shells out to this CLI.
      - **The `\r` flooding is fixed as a side effect**, which is why it belonged here rather
        than in the ergonomics pass: the same branch decides it. A non-terminal gets no carriage
        return, no 60-column padding, and a line only every `_PROGRESS_INTERVAL_SECONDS` -
        without `\r` to overwrite with, one line per file is the same flood in a new shape. The
        real run left **127 KB** of it; the equivalent piped run now leaves a handful of lines.
      - **The throttle got its own clock.** Borrowing `_CLOCK` - the report's elapsed-time
        source - broke five unrelated timing tests, whose fixtures yield an exact number of
        readings. Two measurements with nothing to say to each other should not share one
        injection point.
      - **Three of the tests were weak and mutations proved it**, each fixed rather than
        accepted: one "some progress appeared" check that tier 2a alone satisfied (so tier 1
        could go silent unnoticed), one flush check that the forecast's own flush satisfied (so
        the census could stop being flushed), and one absent-or-tagged check driven through the
        interrupt path, which returns *before* `_print_not_yet_analysed` is ever reached.
    - **Commits 4 and 5 are unbuilt and still post-launch**, per the placement clause on
      `(r, remaining)`. **"Commit" and "tier" are different numberings** - see the staging note
      there. An earlier version of this line said *"Tiers 3-4 (streaming, app screen)"*, which
      is a category error: there is no data tier 3 or 4, and it made "tier 2" ambiguous between
      the data tier and the commit. Corrected 2026-08-03.

- **(r, remaining) Analyze mode.** Promoted from
  "ideas" and bound to the previously-standalone hash-cache item, because the pairing is what
  makes either worth building.
  - **Analyze mode.** An explicit **"Analyze"** entry point (CLI + app) that runs the existing
    dry-run engine and returns a richer **read-only** report: file counts, photo / video /
    audio split with per-extension formats, exact duplicates with the bytes they waste,
    look-alikes with their potential savings, the capture-date range, and the category split.
    Nothing is written and nothing is organized -- it answers *"what is actually in here?"* for
    someone who wants insight before, or instead of, committing to a run.
    - **Free tier by design.** It is the funnel: the moment someone learns something true
      about their own library is the moment the product earns trust. Gating it would gate the
      argument for using truestill at all.
    - **Shares its soul with the parked web dedup teaser**: same question, same honest answer,
      one in the terminal or app and one in a browser. Build them knowing that.
  - **THE TIERS (designed 2026-08-03). Four data tiers, reported as each completes.** Numbered
    0/1/2a/2b, and **that numbering is data tiers only** -- the *commits* that build them are
    numbered separately below, and the two vocabularies must not be mixed.

    | tier | what it answers | what it reads | cost at 32,628 files / 192 GB |
    |---|---|---|---|
    | **0** census | counts, bytes, formats | directory entries + one `stat` | **sub-second** (measured) |
    | **1** dating | date range, per-year, undated | file *headers*, via exiftool | minutes of CPU, bounded I/O |
    | **2a** exact duplicates | identical copies and the bytes they waste | full bytes of the size-colliding minority | **~12 GB** read |
    | **2b** look-alikes | the same photo at another size or quality | **full bytes of every image** | **~200 GB** read -- the hours |

    - **The split at 2a/2b is the load-bearing part, and collapsing it throws away ~15x on the
      fact users most want.** `compute_hashes` applies a size pre-filter, so SHA-256 runs only
      for files whose byte size collides -- it spares ~94% of realistic-size files
      (`PERFORMANCE.md` §4, and the same figure in the hash-cache entry above). The *perceptual*
      hash has no such filter: it decodes every image, so it reads the whole file. **The
      headline number -- "you are wasting N GB on identical copies" -- therefore needs only
      2a**, the cheap tier. One undifferentiated "duplicates" tier would price the cheap answer
      at the expensive one's cost.
    - **2b's savings are a softer claim and must be worded as one.** Truestill *keeps*
      near-duplicates by design, so their bytes are never reclaimable -- see `insights.py`,
      where `reclaimable_bytes` is exact-only for exactly this reason.
    - **Order is 0 → 1 → 2a → 2b, by measured cost.** Tier 1 is not a prerequisite for 2:
      metadata and hashing are independent passes in `resolve`. Cost is the only reason for the
      ordering.
    - **Not separately invocable; stoppable at any tier, keeping what completed.** Four entry
      points would multiply the surface and invite someone to run 2b without 0. One entry point
      that streams gives the same control under one name -- and the engine already supports the
      stop: `resolve` returns the partial result on cancel, and `HashCache` means a resumed run
      skips what it already hashed.
  - **THE STAGING: four commits, and commit 3 is the one to be careful with.** These are
    **commit** numbers, not tier numbers - commit 1 shipped tier 0, and commit 3 does not build
    a "tier 3".

    | commit | what it does | status |
    |---|---|---|
    | 1 | `truestill analyze`, tier 0 over the shipped `inventory_source` | **shipped** `e8c2692`, polished `58f40fe` |
    | 2 | the facts that existed but were unreachable, moved to `insights.py` | **shipped** `dc9a7d7` |
    | 3a | tiers 1 and 2a reachable from `analyze`, no destination | **shipped 2026-08-03** |
    | 3b | tier streaming and partial-truth reporting | shipped 2026-08-04 (`cli.py:_print_not_yet_analysed`) |
    | 4 | the app screen, plus export | unbuilt |

    - **Five, not four (corrected 2026-08-03).** Commit 3 split once building it began: 3a is
      the value (the free tier currently stops one tier short of its own headline number,
      because dates and duplicates are reachable only through `organize --dry-run`, **which
      requires a destination** the funnel's audience has not chosen). 3b is the risk. Splitting
      lets the value ship without waiting on the correctness feature, and 3b waits on tier 2a
      being timed against a real library.
    - **3a's sequencing, ruled 2026-08-03: print tier 0, then continue.** The census reaches
      the screen in under a second - the property commit 1 shipped for - and only then does the
      expensive work begin. **This is sequential printing, not 3b**: 3b is the app payload and
      the never-render-zero field tagging.
      - **A forecast prints before the wait**, which is the whole reason the forecast exists:
        *"checking for identical copies, needs to read X GB of your Y GB"*, plus the HEIC note
        when it applies, plus that Ctrl-C keeps what is above. An unexplained wait becomes an
        informed one, and the user can still decide not to have it.
      - **An interrupt reports the unfinished tier as not analysed, never as a partial count.**
        A duplicate total is a claim about the whole set: an unscanned file may be the twin of a
        scanned one, so the pairs found understate by an unknown amount. Unlike a file count it
        has **no honest partial reading**. Tiers complete in sequence, so an interrupt during 2a
        still reports tier 1 in full.
      - **The README's "about a second" claim was reworded** rather than left to become false.
    - **3a has a prerequisite, shipped 2026-08-03:** the read-only hash cache. Tier 2a wants
      SHA-256 without the perceptual hash, and recording that would poison the cache - see the
      hash-cache bullet in `IMPLEMENTATION_STANDARDS.md` §8. Found before building rather than
      after.

    - **Commit 3 is where this stops being a formatting feature and becomes a correctness one.**
      A tier that has not run must say *not yet analysed* and **never render a zero**. Get that
      wrong and the tool tells someone *"no duplicates"* when it has not looked - the worst lie
      this product could tell, and `(aac)`'s discipline arriving on a new surface. Concretely:
      every tier-scoped field is absent-or-tagged rather than defaulted, and the conservation
      law `new_unique + near_dup + exact_dup + unreadable == files` holds **only** once tier 2
      completed, so a partial report must not print a summing block that does not sum.
    - Commits 1 and 2 were each independently valuable and shipped alone, which is the property
      to keep: 3 and 4 must not become one commit.
  - **Why the cache is not a separate item.** Analyze's expensive tiers (1, 2a and 2b above)
    are the same dates-and-hashes pass an organize does. Without a cache the natural journey
    *Analyze → Organize* pays for that pass **twice**, which makes the free analysis feel like a
    tax on organizing rather than an invitation to it. With it, the second pass is nearly free,
    and preview→run and
    repeat batches get faster as a side effect. Shipping Analyze without the cache would ship
    the funnel and the friction in the same release.
  - **Design (unchanged from the original entry).** A small SQLite table keyed on
    `(filepath, file_size, mtime)` → content digest; a lookup validates the file is unchanged
    (size **and** mtime) before trusting the cached digest. Reference implementation to study:
    PixSort `backend/pixsort/utils/hash_cache.py`.
  - **Invariants, restated because they are the whole safety argument:**
    1. **mtime is for invalidation only, never for dating.** The absolute rule
       (`IMPLEMENTATION_STANDARDS.md` §1) is untouched: mtime never influences where a file is
       placed. The cache reads it to ask "did this file change?", which is the one question
       mtime can answer honestly.
    2. **Any size *or* mtime mismatch → hash it fresh.** Never a partial-match heuristic.
    3. **The cache can only ever cost extra work, never produce a wrong answer.** A miss means
       re-hashing; there is no path where a stale entry decides an outcome. If a design choice
       ever trades that away for speed, it is the wrong choice.
    4. **A single cache layer** -- never a second parallel store. PixSort's dual-store drift
       was a defect, not a design.
    5. **Cleanup is wired into the run lifecycle.** PixSort *defined*
       `cleanup_stale_entries()` and **never called it anywhere**, so stale rows accumulated
       forever. Pruning must actually run as part of a run, not merely exist.
  - **Placement:** the **first post-launch wave, alongside (n)**. Earlier if the soak shows
    repeat-run pain at real scale -- that evidence would move it, nothing else needs to.
- **GPS-derived per-photo timezone.** Deferred during Takeout Rescue Mode. `--tz` is a single
  fixed offset for the whole run, which cannot correctly date a library that spans timezones;
  the real fix derives each photo's timezone from its GPS. The near-midnight caveat is
  surfaced honestly in the ingest report until this exists.
