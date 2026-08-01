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
   - Collapsible sidebar (`SHIPPED.md` `(fff)`) and adaptive day-folder threshold (`(gg)`)
     are built; pull next from backlog priority.
   - **`(gg)` soak note (2026-07-30):** correct but rare on real data - one un-evented hit
     (`2013-09-30`, 62 photos). The 2,057-photo 2014-08 Everyday folder that prompted `(gg)`
     was the Wayanad trip claim, not threshold behaviour (see `SHIPPED.md` `(gg)`).

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

- **Known coverage gap: `CREATE_NO_WINDOW` suppression is unverified - and since 2026-08-01 it
  is unverified for a MEASURED reason rather than an untried one.** The distinction matters:
  this is no longer "we have not tried", it is "we tried and the flag did not demonstrably
  suppress".

  The Windows throwaway (`BACKLOG.md` `(aad)`, run 30692798020) exercised the `AttachConsole`
  technique for the first time, and **the technique is measuring the wrong thing.**
  `CREATE_NO_WINDOW` creates an **invisible console** - the child *is* attached to a console,
  it simply has no window. `DETACHED_PROCESS` is the flag that yields no console at all. So the
  flagged child being attachable is **exactly what that flag should produce**, and attachability
  cannot distinguish suppressed from unsuppressed. This is not a contaminated measurement to be
  re-run; it is the wrong observable.

  The control still earned its place twice over. Under Briefcase it failed with
  `ERROR_ACCESS_DENIED` - that process already owned a console - and the gate refused to report
  a measurement, which is the false pass it exists to prevent, caught on its first run.

  **What would actually measure it:** the console's *window*, not its existence.
  `GetConsoleWindow()` returns `NULL` for a console that has none, so attaching to the child and
  then asking for its console window distinguishes the two - the attach stops being the verdict
  and becomes the setup.

  *Green CI still proves the plumbing:* the flag resolves to a real constant on Windows rather
  than the `0` it is on POSIX, and all five call sites capture output and return exit codes
  through the wrapper. *It does not prove the window is suppressed.*

- **PARTLY CLOSED 2026-08-01: the windowed-launch branch of the legacy-catalog probe.** The
  Windows throwaway's PyInstaller artifact reported `has_console: {stdout: false, stderr: false}`
  with a `reports\catalog.sqlite` in its working directory and resolved to the **data
  directory** anyway (`skipped_the_probe: true`). No faked `sys.stdout = None` involved, so the
  branch is proven to work when the streams really are absent.

  **The caveat, since the same run's console reading turned out to be a measurement artefact:**
  that artifact had null streams because PyInstaller's `--noconsole` bootloader nulls them in
  software, not because the launch was detached. The branch is proven; *that a double-clicked
  app reaches it* is a separate claim resting on the same unmeasured question as the rest.

  Recorded rather than deleted because the pair used to be one entry and are now different in
  kind: **this one is answered; the one above is measured and still open.** The third launch fix,
  the uvicorn no-console startup crash, was never in this category at all - its failure is in
  *configuration* rather than in windowing, so it is proven on every platform and closed.

- **`(aad)` packaging is PARKED, deliberately, and the bundler is not the blocker.** Two
  measurement runs produced no measurements - both lost to rig faults - and on review the
  remaining questions **cannot decide the choice**: windowed-ness is settled by mechanism (both
  bundlers are GUI-subsystem, so both are console-free on a double-click) and
  `CREATE_NO_WINDOW` is our own flag rather than a bundler's. What *would* decide it - installer
  output and signing - no probe was ever going to measure. The lean is recorded as **conditional
  on which platforms launch first**, which is a product question. Packaging resumes as a **real
  installer**, after the **signing decision** and after **soak closes** (§2 puts it at #3).
  Full reasoning in `BACKLOG.md` `(aad)`.

- **Kept for the mechanism, since it cost two runs to learn:** the console reading that appeared
  to block the choice was a **measurement fault**, not a bundler difference. Briefcase's config
  applied exactly as written - GUI stub, `formal_name.exe` naming, and the stub's PE header reads
  `Subsystem = 2 (WINDOWS_GUI)`. The console came from the launcher: **a GUI-subsystem process
  does not get a console *allocated* but still *inherits* one**, and the job used PowerShell
  `Start-Process` from a shell that owns one. PyInstaller only looked different because its
  `--noconsole` bootloader nulls the streams in software regardless of launch.

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
  `2013-09-30` / 62). See `SHIPPED.md` `(gg)`.

---

## 6. Where to look up details

- Product stance and superseded decisions: `DECISIONS.md`
- Binding engineering/data/process contract: `IMPLEMENTATION_STANDARDS.md`
- Open items with build-ready constraints: `BACKLOG.md`
- Performance evidence and do-not-optimize list: `PERFORMANCE.md`
- Historical investigations and alternatives considered: `docs/*-research.md`
- Move/remount user procedure: `moving-machines.md`

If a research note and the contract disagree, the contract wins.
