# Truestill - Project Status & Handoff

Start here in a new session. This file is the **cold-start map**: current state, what is next,
and what blocks it. It is intentionally short; deep rationale and history live elsewhere.

---

## 0. Fresh clone to green (15 minutes)

```sh
# 1) External dependency used by metadata paths
sudo apt install -y libimage-exiftool-perl        # macOS: brew install exiftool
exiftool -ver

# 2) Workspace setup
uv sync --all-packages --group dev

# 3) Hooks (both types)
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg

# 4) Prove commit-msg guard blocks forbidden trailers
git commit --allow-empty -m "test
Co-Authored-By: someone <x@y.z>"                   # MUST be refused

# 5) Confirm author identity
git config user.name && git config user.email      # expect: dinesh-ad

# 6) Gates
make check
make e2e-install && make e2e                       # optional local lane
```

Notes:
- `make check` is the required green gate.
- Browser E2E is deliberate and separate (`make e2e`).

---

## 1. Current operating picture

- **Core product shape is shipped:** organize, ingest, dedup, drive identity, verify, backup,
  configurable layout + migration, reclaim, in-place organize + undo, local web UI.
- **Date-provenance program: COMPLETE (2026-07-31), six steps.** A user can now see **why** each
  date was chosen, **correct** one that is wrong, have that correction **survive every whole-disk
  operation**, and optionally **write it into the organized copies** so other apps read it too.
  Schema v13-v16. One clause of `(bbb)` item 4 was carried out rather than ticked - see `(aaj)`;
  `(kk)`'s `GPSDateStamp` half was in scope and was **not** built.
- **Launch gate is still soak on real library usage.** Work is prioritized by soak findings.
- **Trademark residual (live pre-monetization obligation):** TruStile Doors remains a low-risk
  residual in different IC classes; attorney clearance is still required before monetization
  (full analysis in `DECISIONS.md`).
- **Recent critical portability/safety posture:** loud failures are in place (stale hints,
  catalog-open visibility, reclaim/undo stale-path messaging); remaining work is portability
  follow-through, not silent safety failures.
- **The docs source-of-truth split is strict:**
  - binding contract: `IMPLEMENTATION_STANDARDS.md`
  - settled stances + why: `DECISIONS.md`
  - open work + build constraints: `BACKLOG.md`

What this file no longer does: carry stage-by-stage implementation history, old commit-by-commit
narrative, or volatile counts.

---

## 2. What is next (in order)

1. **Finish soak gate**
   - Continue normal use; any new soak finding outranks queued feature work.
   - Collapsible sidebar (`BACKLOG.md` `(fff)`) and adaptive day-folder threshold (`(gg)`)
     are built; pull next from backlog priority.
   - **`(gg)` soak note (2026-07-30):** correct but rare on real data - one un-evented hit
     (`2013-09-30`, 62 photos). The 2,057-photo 2014-08 Everyday folder that prompted `(gg)`
     was the Wayanad trip claim, not threshold behaviour (see `BACKLOG.md` `(gg)`).

2. **Repo-public audit + newcomer README**
   - Ensure no sensitive/local-only leakage and that user-facing docs/screenshots are current.

3. **Publish pipeline (when soak closes)**
   - Package release sequence and launch steps are still pending and should be run only after
     soak is explicitly accepted.
   - **Larger than a PyPI release, and it sits in front of this:** `BACKLOG.md` `(aad)` desktop
     installers is **launch-blocking** for the paid product - pip is not a channel the buyer can use.

4. **Post-launch queue**
   - Pull from `BACKLOG.md` in written priority order, with soak findings first.

---

## 3. Current blockers / risks

- **Soak not closed yet.** No launch actions should outrun this gate.
- **Absolute-path portability remains open** (`BACKLOG.md` `(xx)`, `(yy)`):
  `files.source_path`, inplace roots, reclaim journal path semantics, and reconnect UX.
- **Known coverage gap: the unreadable-directory path is unverified on Windows.**
  `scan_source` was swapped from `sorted(rglob("*"))` to `Path.walk(on_error=...)`, and the
  seven `test_unreadable_source.py` tests plus
  `test_unreadable_paths.py::test_a_real_locked_directory_raises_from_is_dir` **skip on
  Windows** - `chmod 000` does not deny the owner there, so the fixture cannot create the
  condition. Ordinary traversal *is* exercised on Windows (`test_organizer.py`, `test_heif.py`,
  `test_exiftool_original_backups.py`), so what is untested is specifically the part the swap
  introduced: the `on_error` callback and `SourceScan.unreadable_dirs`.
  The skip is legitimate. It is **not** coverage, and a green Windows lane must not be read as
  proof this works. Closing it needs one of: a Windows-specific denial mechanism (an ACL denying
  the current user via `icacls`, which is the real equivalent of `chmod 000` there), or a
  deliberate decision to accept the gap and say so here instead. Not yet chosen.

- **Known coverage gap: two `(aad)` fixes cannot be confirmed by CI at all, because CI has a
  console.** Both concern *windowed* launches, and every CI lane runs with `stdout` and `stderr`
  attached. A green Windows tick is real but narrower than it looks in each case, so the two are
  recorded next to what it *does* prove.

  1. **`CREATE_NO_WINDOW` suppression** (`binaries.run` / `binaries.popen`). *Green proves:* the
     flag resolves to a real constant on Windows rather than the `0` it is on POSIX, and all
     five call sites still capture output and return exit codes through the wrapper (exiftool,
     rclone and trash tests all run through it). *Green does not prove:* that a windowed build
     shows no console window. Suppression is never exercised, because a console session would
     show no window either way.
  2. **The windowed-launch branch of the legacy-catalog probe**
     (`app_paths._working_directory_was_chosen`). *Green proves:* the console branch, and that
     `Path.resolve()` behaves on the legacy path there - which is worth having after the 8.3
     short-name failure. *Green does not prove:* that a genuinely windowed process skips the
     probe. That branch is exercised only by unit tests faking `sys.stdout = None`, which run
     identically on Linux and add nothing on Windows.

  **Both close the same way: a packaged build, in `(aad)`.** Until a `pythonw` or bundled
  artifact exists there is no windowed process to observe, and no test can create one.

  **The third `(aad)` launch fix is NOT in this category, and the three must not be treated as
  one gap.** The no-console crash - uvicorn's default log config calling `.isatty()` on a `None`
  stream - is **genuinely proven either way**, on every platform, because the failure is in
  *configuration* rather than in windowing: `test_launch_without_console.py` sets both streams to
  `None` in the test body and configures logging, and its companion asserts uvicorn's own default
  still raises under the same conditions. That one is closed.

---

## 4. Standing session rules (short form)

- **Staged workflow:** one requested step at a time; no silent run-ahead.
- **Research-first + conflict-first:** flag spec/engineering conflicts before coding.
  Research sources: repo docs (outrank), source, free public only - **no paid third-party
  research APIs or hosted tools** (`ENGINEERING_STANDARD.md` §3.1).
- **Dry-run default:** writes happen only on explicit apply paths.
- **Never push unless asked.**
- **Commit identity policy:** `dinesh-ad`; no co-author/AI signature trailers.
- **Corpus fence for real-library testing/profiling/soak:**
  - allowed: `<cloud mount>/The Memory Cabinet`, `<home>/TruestillLibrary/Output`,
    `<cloud mount>/2015` (when present)
  - off limits: everything under `<cloud mount>/Crypto Folder/`

Full wording and enforcement details live in `IMPLEMENTATION_STANDARDS.md` and `BACKLOG.md`.

---

## 5. Easy-to-rediscover traps (keep these cached)

- Density-relative thresholds invert at both extremes (dense days shatter, sparse years fuse),
  and synthetic fixtures can hide it - see `events-clustering-research.md`.
- One string cannot express two shapes (event axis, Everyday bucket, effective-layout truth) -
  see `trip-grouping-research.md` and `migration-routing-research.md`.
- A fixture that cannot fail against the bug is not a regression guard - run it against the bug;
  process + examples in `ENGINEERING_STANDARD.md`.
- UI source assertions do not prove end-to-end flow correctness (the `innerHTML` re-parse case
  left resume dead; Playwright caught it) - see `IMPLEMENTATION_STANDARDS.md` and `DECISIONS.md`.
- Measure before optimizing (SHA-256 ~1% wall vs exiftool ~74%) - see `PERFORMANCE.md` and
  `preview-performance-profile.md`.
- **`(gg)` is not the fix for the 2,057-photo 2014-08 Everyday folder.** That dump was
  trip-claimed (Wayanad). The threshold guards rare un-evented heavy days (soak: one hit,
  `2013-09-30` / 62). See `BACKLOG.md` `(gg)`.

---

## 6. Where to look up details

- Product stance and superseded decisions: `DECISIONS.md`
- Binding engineering/data/process contract: `IMPLEMENTATION_STANDARDS.md`
- Open items with build-ready constraints: `BACKLOG.md`
- Performance evidence and do-not-optimize list: `PERFORMANCE.md`
- Historical investigations and alternatives considered: `docs/*-research.md`
- Move/remount user procedure: `moving-machines.md`

If a research note and the contract disagree, the contract wins.
