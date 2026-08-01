# truestill - Backlog (approved but unbuilt)

Things that were **decided** but not yet built - captured here so nothing lives only in chat
history. This is not a wishlist of everything possible; only items already agreed, with the
decision context that produced them.

> **How to read this file: status is per ENTRY, never per section. A heading is not a status.**
> Read the entry's own text before acting on it - several are *partial*, and partial is the
> normal state here rather than the exception. This is written at the top because it is the
> defect the 2026-07-31 audit found: 20 of the 36 entries under a heading that said *"not yet
> built"* were built, and separately `(n)` and `(ii)` described shipped work as unstarted. Both
> directions cost real money - one hides finished work, the other invites rebuilding a schema
> that already ships.

> **Items (w) and (x) came from a three-report external research synthesis (2026-07-27) whose
> main result was that it changed nothing.** It reviewed the shipped architecture and validated
> it point-for-point; these two are the entire delta, one of them trivial and one of them
> post-launch. That outcome is worth recording as loudly as a finding would have been - an
> external review that produces two small additive items is evidence the recorded decisions
> have been holding, and it is the kind of result that quietly disappears if only the deltas
> get written down.

## Item letters

Letters are **permanent identifiers, not an ordering** - `IMPLEMENTATION_STANDARDS.md` §8 cites
`(u)` by letter, so reusing or renumbering one silently redirects a citation. They are assigned
across *all* sections of this file, not per-section.

**Used: (e)-(z), (aa)-(zz), (aaa), (bbb)-(fff), (aab)-(aan). Next free: (aao).** Check here before assigning - `(u)` and `(v)` were proposed
a second time on 2026-07-27, four hours after they were first taken, because nothing recorded
which letters were spoken for.

Several early letters no longer appear anywhere in this file: their items shipped and the
Shipped entries describe the work rather than repeating the letter. `(e)` and `(h)` are still
cited by name in `drive-identity-research.md` and `org-structure-research.md`. **A letter that
is invisible here is retired, not free.**

## Approved - still to build

Everything here has work left. **Two entries are partial and say so in their own text:**
`(bbb)` (the safety half shipped, the `_original` recovery offer did not) and `(r)` (the hash
cache shipped, Analyze mode itself did not). A partial entry lives here, not in the built
section, because what is left is the part that still has to be written.

- **(aan) A "verified against code" clause must still resolve.** Recorded 2026-08-01 while
  moving `(aae)` and `(jj)` into the built section. **Record only - needs its own
  measured-scope pass before it is built.**
  - **The failure it prevents.** `(aae)` sat in the wrong section asserting a *"Current state,
    verified against code 2026-07-31"* that named `DEFAULT_CATALOG_PATH`, `catalog_startup.py`,
    `cli.py` and `server.py` line numbers. The symbol had been deleted and the line numbers had
    moved. **A document saying it was code-verified is not evidence**, and a cold start has no
    way to tell which of those citations still means anything.
  - **Why the obvious guard is the wrong one, measured before proposing it.** A check keyed on
    completion vocabulary appearing in the section for open work **misses `(aae)` entirely**,
    because that entry carried none of it - it said *record only*. It also cry-wolfs
    immediately on `(bbb)` and `(r)`, which are legitimately partial, say so, and are licensed
    by this section's own preamble. So the discriminator is not status vocabulary. It is
    whether the entry's factual claims about code still hold.
  - **The check that fits:** every backticked **symbol** inside a verified-against-code clause
    must exist under `packages/*/src`. Symbols, never line numbers -
    `IMPLEMENTATION_STANDARDS.md` already states that symbols are cited over line numbers
    because line numbers drift by design.
  - **The cry-wolf surface, which is why this is recorded and not built.** A backtick in these
    documents holds a Python symbol, a table name (`file_copies`), a column
    (`files.date_source`), a CLI flag (`--apply`), a setting key
    (`layout.everyday_day_threshold`), a typed confirm word (`delete forever`) and a filename.
    Only the first is checkable this way and no regex separates them by shape. Whatever rule is
    chosen needs the measured before/after row this repo asks of every guard - the worked
    example is `test_backlog_references.py`, scoped against the real file rather than a
    plausible phrase list.
  - **A second instance of the same class, in case the guard should generalize.**
    `scripts/benchmark_hashing.py` says `TRUESTILL_CORPUS` is *"named by environment variable
    (`docs/PROJECT_STATUS.md` §6)"*. §6 exists and documents nothing of the kind - the variable
    appears nowhere in that file. A live citation to a real section that does not carry the
    claim, which an anchor-existence check would not catch either.
  - **Related, not the same.** `test_backlog_references.py` already guards the opposite
    direction - a settled item described as pending elsewhere - and deliberately scans only
    settled sections. Noted while here: its `_SETTLED` markers do not match
    `## Shipped (kept for provenance)`, so that section is currently outside its scope.

- **(aak) The skipped-file summary is written twice.** `organizer._skipped_extension_counts`
  and `service/organize._skipped_summary` are the same logic in two homes - extension counts
  plus the plain exiftool-backup label. **Pre-existing; found while building `(aac)`**, which
  had to thread one new field through both. The companion rule (`ENGINEERING_STANDARD.md` §4)
  says prefer deleting a copy to guarding two, so the fix is one shared helper in core that the
  app calls, not a parity test over the pair. Small, and worth doing the next time either is
  touched rather than as its own errand.

- **(aai) The plain copy path does not verify at write time.** Recorded 2026-07-31, and
  **re-scoped 2026-07-31 after the original reasoning was found to be wrong.** **DEFERRED with
  the cost stated - not an open item awaiting work.**
  - ⚠ **The original entry was wrong, and its "fix" would have been a regression.** It said the
    path records "the hash of what was sent, not what landed", and proposed re-reading the
    destination so the recorded hash described the bytes that actually arrived. That is
    backwards. `verify` compares **the file on disk against the recorded hash**, so:
    - recording the **source** hash (what ships) means a truncated or half-flushed copy
      **fails** verify - the user is correctly told that copy is bad;
    - recording **what landed** would have `verify` compare a file against a hash taken from
      *that same file*. It would **pass**. A corrupted copy would be blessed VERIFIED, forever.

    So the change would have made verify **tautological on the copy path** and destroyed the
    protection it exists to give. It is recorded here rather than quietly replaced because it
    would have looked like an obvious improvement to whoever picked it up - and because it is
    the bake's reasoning applied where it does not belong: a bake needs the landed hash
    *because it deliberately changes the bytes and no source-truth claim survives*; a plain copy
    has a source, and the source is the truth.
  - **What the real gap is: detection latency, not correctness.** `organizer._upload_copy`
    writes and returns nothing, and `copy_sha` is the source hash. Nothing re-reads the
    destination, so §1's `copy -> record -> re-verify` ordering - which `_move_source` really
    does perform for `--move` - has no equivalent on the plain copy path. A bad write is
    reported as `organized` and is discovered **at the next `verify`, rather than never**. The
    copy is protected either way; what is missing is catching it at the moment it happens.
  - **Why it is deferred rather than open.** Two measured constraints, both of which make this a
    design exercise rather than a fix:
    - **Cost:** a full re-read of every written file. Proxy measurement from the attach work -
      ~6.3 s per 6.2 GB local, ~22 s on a cloud FUSE mount - which is roughly **30-50% on the
      copy phase of every organize**, paid always, to shorten the detection window for something
      already detected.
    - **It cannot be unconditional:** `RcloneDestination` has **no `checksum`** and the base
      raises `DestinationError`. So a post-write verify either skips silently on rclone - a new
      silent hole, which is worse than the one being closed - or needs its own
      UNVERIFIABLE-style outcome plumbed through the organize report. That is design.
  - **If it is ever built**, the recorded hash must **stay the source hash**; the verify step is
    an additional check, never a replacement for what is stored.

- **(aaf) Persisted skip record - "show me what was skipped last week".** Ruled by the
  maintainer, 2026-07-31, from the duplicate-naming gap check. **Record only - do not build.**
  - **What is already done, and what is not.** The *current run* now names every match it
    skipped, on both surfaces (`duplicate_explain`, `organize._duplicate_report`). What is
    missing is asking **afterwards**. `stats.py` states the reason in its own payload today:
    `"exact_duplicates_found": None`, because *"Exact-duplicate skips are not stored in the
    catalog; computing this would require a new scan outside the read-only stats contract."*
    That sentence was written as `(ddd)`'s "intentional omission"; this entry is that omission
    promoted to an item of its own.
  - **Why it is (m)-sized rather than another payload fix.** `Resolution` objects live only for
    the duration of the job and are discarded with it. Nothing persists a skip, so there is no
    row to read later and no amount of payload plumbing produces one - **it needs a new table**,
    plus a retention policy (a 40,000-file re-run would write 40,000 rows nobody asked for) and
    a decision about whether an undone organize retracts its skip records.
  - **Market evidence, recorded because it will not be re-derivable later.** The single
    most-repeated complaint about photo tools, unchanged 2007-2026, is a tool that declares a
    file a duplicate and will not show *which* file it matched. One Lightroom thread has been
    open since **2018** with **21,798 views**, and users call it an *"absolute dealbreaker"*.
    The live half of that complaint is answered; this is the historical half.
  - **Open questions for the design pass:** which table and whether it belongs beside the
    catalog or in it; retention; whether the record survives `undo-organize`; and whether this
    is the same surface as (m)'s inventory of unknown media or a different one.

- **(aag) Near-duplicate grouping and burst review.** Ruled by the maintainer, 2026-07-31, from
  the same gap check. **Record only - do not build.** ⚠ **Overlaps `(m)`**, whose "visual
  side-by-side compare" clause is this item; scope the two together.
  - **This is a review surface over behaviour that is already correct, which is what makes it
    deferrable.** truestill already **keeps** near-duplicates and flags them - `Resolution`
    carries `near_duplicate` and the file is organized anyway, never dropped (`should_upload`
    ignores it), and both surfaces now name what each one resembles and say it was kept. On the
    behaviour the market complains about, truestill is **ahead** of the tools being complained
    about: the complaint is about tools that silently discard.
  - **The distinction that decided the order.** The duplicate-naming payload gap was a **§9
    contract violation** - an outcome counted but not named - and contract violations are not
    deferrable. This is a **feature**: choosing between look-alikes a user can already see
    listed. Same subject, different kind of work, and only one of them was a defect.
  - **Market evidence.** Second most-repeated complaint after the naming one: *"group photos
    that are not quite duplicates, let me pick which to keep"* - burst shots, bracketed
    exposures, near-identical retries.
  - **Open questions for the design pass:** grouping (by perceptual distance, by capture time,
    or both); what "pick which to keep" does given the copy-only invariant, since truestill does
    not delete - it would have to be a *reclaim* offer or a side-bin move, and (§1) constrains
    both; and whether the existing distance threshold is the right grouping key or only the
    right detection key.

- **(aad) Desktop installers - LAUNCH-BLOCKING for the paid product.** Ruled by the maintainer,
  2026-07-31. **Record only - no design pass yet, and it does not block the current
  date-provenance program.**
  - **The problem.** PyPI reaches developers only. `pip install` needs Python present, a
    terminal, and knowing what pip is. The target buyer - someone with a messy photo library -
    has none of the three. **A perpetual licence (`DECISIONS.md` D6) cannot be sold to a user
    who cannot install the product**, which is what makes this blocking rather than merely
    desirable: every other launch item improves a product that person still cannot reach.
  - **Needed:** download-and-double-click installers per platform - Windows `.exe`/`.msi`,
    macOS `.dmg`, Linux AppImage or `.deb` - built by CI on tag and served from `truestill.app`.
  - **PLATFORM SCOPE RULED (2026-08-01): Windows and Linux only, unsigned - `DECISIONS.md` D9.**
    Zero spend; no certificate is bought. macOS keeps its CI lane and its tests but is **not
    published**, because Gatekeeper refuses unsigned apps outright and only the $99/yr Apple
    Developer account changes that - building without publishing is what stops macOS rotting
    unnoticed. **This unblocks the bundler decision**, which can now be made for two platforms
    with no signing step in the pipeline. D9 also carries a launch-page requirement: Windows
    users are told what SmartScreen will show *before* they download.
  - **PyPI stays**, as the developer / self-hosted channel. It stops being the *primary* one.
  - **MEASURED, THEN DECLINED (2026-08-01). The ~90 MB stays in the build.** Ruled on product
    grounds: at this size the download is unremarkable for a desktop app - **VS Code is ~350 MB
    and Cursor ~600 MB** - the saving buys nothing functionally, and the mechanism that achieves
    it is a permanent maintenance surface plus a landmine for whoever adds a hashing-algorithm
    option later. Recorded with the numbers so it is a decision rather than an oversight.

    | build (PyInstaller 6.21.0, Linux, whole `dist/` tree) | bytes | |
    |---|---|---|
    | with scipy + PyWavelets | 218,212,013 | **208.1 MiB (218 MB)** |
    | with both excluded | 132,045,324 | **125.9 MiB (132 MB)** |
    | difference | 86,166,689 | **82.2 MiB (39.5%)** |

    **THREE CORRECTIONS TO THE RULING'S PREMISES, verified rather than argued - read these
    first if this is ever reopened, because each one points the opposite way from the belief it
    replaces.**

    1. **`--exclude-module` DOES work here.** The ruling assumed it cannot, because `imagehash`
       imports scipy at module level. It does not: `imagehash/__init__.py` imports only `sys`,
       `numpy` and `PIL` at module level (lines 33-36); `scipy.fftpack` is imported *inside*
       `phash` and `phash_simple` (lines 273, 293) and `pywt` *inside* `whash` (line 361). The
       exclusion was run and it worked - `xref-{name}.html` showed **scipy absent from all
       1,213 modules** and pywt as `ExcludedModule`. So the 82.2 MiB is genuinely available
       with two flags and no shim at all. **This is a free-standing option, not a blocked one.**
    2. **PyInstaller #1584 and #3265 do not establish the limitation they were cited for.** Both
       are real and both **closed**; they show `--exclude-module` surprising users, but neither
       documents a module-level-import limitation. Cited accurately here so the next person does
       not treat a closed issue as a standing blocker.
    3. **`dhash_int` does not exist in `imagehash`, and no `imagehash` function silently returns
       a wrong value.** This was carried into the ruling as the decisive danger - that under
       exclusion `dhash_int` falls back to NumPy and returns wrong hashes while `phash` raises.
       Verified against the installed source: `grep dhash_int` over `imagehash` 4.3.2 (which is
       also the newest release) finds **nothing**, and `phash`, `phash_simple` and `whash` each
       do a bare `import` and raise with **no fallback path**. Removing the module cannot
       produce a wrong number, only an exception.

       **Where the belief comes from, because it is not baseless:** `dhash_int` is a real
       function in **Ben Hoyt's separate `dhash` package** on PyPI, which is a different library
       that truestill does not depend on, declare, or install. The asymmetry it describes is not
       a property of anything in this build.

    **What the actual risk is, stated plainly for whoever reopens this:** with scipy excluded,
    `phash`/`phash_simple`/`whash` raise `ModuleNotFoundError` naming an internal package, from
    four frames inside a vendored library - undiagnosable for a photo user, but **loud**. There
    is no silent-wrong-value failure mode to fear. The real cost of reopening is the one the
    ruling identified correctly: a shim is a permanent maintenance surface, and a build where an
    algorithm works in a source checkout and raises when frozen is a trap for whoever adds an
    algorithm option. Nothing in the product calls those three today.

    **The mechanism, if it is ever wanted:** `--exclude-module scipy --exclude-module pywt` for
    the bytes, plus a packaging-layer shim replacing `imagehash.phash`, `phash_simple` and
    `whash` with a refusal naming the algorithm and the alternative rather than the module,
    installed via `--runtime-hook` so a source checkout is untouched. Both halves were built and
    verified working, then removed under this ruling; `git log` for `feat(aad): drop 82 MiB` has
    the implementation if it is wanted back.

    **`dhash` is bit-identical with and without the exclusion** - source, baseline and frozen
    builds all returned `8bcb9521242eca28` for the same fixture. Whatever is decided later, that
    is the bar: the catalog stores hash output as identity.

    **Untested and belonging to the packaging work:** whether the exclusion interacts with the
    `_MEIPASS` layout on Windows, and the Windows byte figure, which will differ.
  - **~90 MB of the install is a code path that never runs** (dependency audit, 2026-08-01).
    `imagehash` declares `scipy` and `PyWavelets` as hard requirements with **no extras split**,
    so every install pulls **81 MB scipy + 8.6 MB PyWavelets**. They back `phash` and `whash`,
    imported lazily inside those functions; truestill defaults to `dhash`, and a `dhash` call in
    a clean process loads neither (verified). Nothing can be done at the dependency layer - the
    only levers are a bundler `--exclude-module` or vendoring, which makes this **(aad)'s
    decision, not core's**. Worth deciding deliberately: 90 MB is a visible fraction of a
    download aimed at people who will judge the product by how heavy it feels. **Unverified
    here:** whether the bundlers' static analysis picks up those function-level imports, and so
    whether an exclude is needed at all - that is a build-time question for the packaging work,
    and per the "stop measuring" ruling it was not measured now. If the exclude is taken,
    `phash` must fail loudly rather than at first use: it is reachable today via
    `perceptual_hash(algorithm="phash")`.
  - **Open questions for the design pass, deliberately not answered here.** Recorded so the
    pass starts from them rather than rediscovering them:
    - Packaging approach: PyInstaller, Briefcase, Nuitka, or something else.
    - The **exiftool binary dependency** and how it ships. It is not a pip package
      (`IMPLEMENTATION_STANDARDS.md` §7 records it as an external binary), and every metadata
      path needs it.
    - **Code signing and notarization** on macOS and Windows. Unsigned installers are blocked
      or scary-warned on both, which is fatal for a product whose whole proposition is trust.
    - Installer size and startup time.
    - How it interacts with the **parked Tauri-vs-local-web decision** (`(o)` and the Product /
      strategy section) and with **D5's licensing/update server**, which is separately unbuilt.
  - **Throwaway measurements, 2026-08-01. Recorded because they rule things OUT; they do not
    choose a bundler, and Linux alone cannot.** Both builds ran on Linux, in scratch venvs
    outside the repo.
    - **PyInstaller 6.21, one-dir.** App starts, serves a page, writes its URL file. exiftool
      resolution **failed at first**: `--add-binary` content lands under `_internal/`, and
      `dirname(sys.executable)` is not `sys._MEIPASS`, so `bundled_bin_dirs()` came back empty
      inside a bundle that had shipped exiftool. Fixed by adding the `_MEIPASS` rule, then
      re-measured in the artifact: resolution now finds it.
    - **Briefcase 0.4.4, `linux system`.** All four assertions pass against the fixed contract.
      But `sys.frozen` and `sys._MEIPASS` are **both absent** - it ships an ordinary
      interpreter - so `is_bundled_install()` reads **False**, and the layout is FHS
      (`usr/bin/<app>` with code under `usr/lib/<app>/{app,app_packages}`), so the
      beside-the-executable rule looks in `usr/bin/bin/` and **misses**.
    - **What that rules out:** the hoped-for "Briefcase needs zero packaging config" advantage
      **does not hold on Linux**. Measured, not assumed.
    - **What stays open, and why Linux cannot close it.** `linux system` is a *distro package*,
      so its FHS layout is required rather than chosen. **Windows Briefcase is one directory
      with the executable on top**, where a `bin/` sibling is natural - and Windows is the
      platform installers actually matter for. **Do not extrapolate the Linux result to a
      recommendation.** A Windows measurement is the missing input.
    - **Friction - and this entry OVERSTATED it; corrected 2026-08-01.** Briefcase's
      `linux system` target took **three failed builds** in the throwaway: a PEP 639 `license`
      declaration (not `license.text`), an actual licence **file** via `license-files`, and a
      **changelog** with a recognised name. **Two of those three were artifacts of the
      throwaway being a bare project.** This repo already has `LICENSE` and `CHANGELOG.md` at
      root, so a real truestill Briefcase project hits **one** of the three, not three. The
      original wording read as evidence against Briefcase and was not.
      **What survives as real friction:** it must run under the **distro's** python3 rather than
      a venv's, because a `linux system` package links against system Python; it downloads a
      **support package and stub** at build time; it is **pre-1.0** (0.4.4); and `sys.frozen` is
      absent, so `is_bundled_install()` needs a replacement signal. PyInstaller needed one
      command and built first try on both platforms.
    - **The `is_bundled_install()` signal for Briefcase, ranked but NOT implemented** - it is
      only needed if Briefcase wins. The criterion is *does it survive the bundle being
      incomplete*, and it does the ranking on its own:
      1. **The running code's own location** (`truestill_core.__file__` under `app_packages/`) -
         the only candidate that **cannot be absent while the code is executing**.
      2. *Path shape* (`app/` + `app_packages/` siblings) - survives a missing binary; if
         `app_packages` were gone nothing could import at all.
      3. *A marker file we ship* - **weakest**: in a bundle broken by missing files, the marker
         can be the missing file. That is the failure this rule exists to prevent.
      4. *`BRIEFCASE_*` environment variables* - **none exist at runtime**; not available.
         `sys.prefix` is `/usr`, indistinguishable from any system-python script.

  - **WINDOWS measurements, 2026-08-01 (run 30692798020, both builds succeeded). The bundler is
    NOT decided, and the reason is the first item below.**
    - **CORRECTED 2026-08-01, same day: the console result was MY MEASUREMENT, not Briefcase.**
      The first reading of this run said the Briefcase app "has a console despite
      `console_app = false`", and scored PyInstaller as winning windowed-ness. **Both claims
      were wrong**, and the mechanism is the valuable part.
      - **Briefcase's configuration applied exactly as written**, on three independent
        confirmations: the build downloaded **`GUI-Stub-3.13-amd64-b11.zip`**
        (`stub_type = "Console" if is_console_app else "GUI"`); the executable was named
        `TruestillProbe.exe`, the **`formal_name`** form Briefcase uses for GUI apps rather than
        the `app_name` form it uses for console ones; and the stub was downloaded and its **PE
        header read directly - `Subsystem = 2 (WINDOWS_GUI)`**. `console_app` also defaults to
        `False`, so it would have been GUI even if the setting had been ignored.
      - **The cause was the launcher. A GUI-subsystem process does not get a console
        ALLOCATED, but it still INHERITS one from a parent that has it** - the subsystem field
        controls allocation, not inheritance. The job launched both artifacts with PowerShell
        `Start-Process`, and the runner's PowerShell owns a console.
      - **It contaminates PyInstaller equally, in the other direction.** Its `--noconsole`
        bootloader frees and nulls the standard streams *in software*, so it reports no console
        **however it is launched**. The two were never compared on equal terms. The run's own
        `AttachConsole` data shows exactly this asymmetry: PyInstaller's control attached
        successfully (**no console attached to that process**) while Briefcase's failed with
        `ERROR_ACCESS_DENIED` (**already attached to one**).
      - **The narrow true statement, as the current state of knowledge:** PyInstaller guarantees
        null streams regardless of how it is launched; Briefcase's GUI stub relies on there
        being no console to inherit. **For a double-clicked shortcut both should be
        console-free - and that is UNMEASURED.**
      - **So "PyInstaller wins windowed-ness" is withdrawn.** It rested on a contaminated
        measurement. The re-run launches both detached, so the comparison is finally fair.
    - **PyInstaller layout - `_internal/` holds on Windows exactly as on Linux.**
      ```
      sys.executable          = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\truestill-probe-pyinstaller.exe
      dirname(sys.executable) = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller
      sys._MEIPASS            = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\_internal
      bundled_bin_dirs()      = [D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\_internal\bin]
      exiftool resolved       = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\_internal\bin\exiftool.EXE
      ```
      ``dirname(sys.executable) != sys._MEIPASS``, so **the `_MEIPASS` rule is the only reason
      exiftool resolves at all**. Stated plainly because it justifies `92774fb` retroactively:
      **without that commit this Windows build fails assertion 2 as well**, not only the Linux
      one it was written for.
    - **Briefcase layout - the beside-the-executable rule FIRES on Windows.**
      ```
      sys.executable          = D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src\TruestillProbe.exe
      dirname(sys.executable) = D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src
      bundled_bin_dirs()      = [D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src\bin]
      exiftool resolved       = D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src\bin\exiftool.EXE
      ```
      One directory with the executable on top, so `bin/` beside it is exactly where the
      zero-configuration rule looks. **The advantage that died on Linux's FHS layout is real on
      the platform installers actually matter for** - measured, not assumed.
    - **`sys.frozen` is absent under Briefcase, now confirmed on Windows**
      (``sys.frozen: null``, ``is_bundled_install(): false``). The limit recorded when that
      signal was chosen holds, and **the replacement ranking already stands**: the running
      code's own location is the only candidate that cannot be absent while the code executes -
      here ``...\windows\app\src\app_packages\truestill_core\binaries.py``.
    - **STOP MEASURING. The remaining questions CANNOT decide the bundler** (2026-08-01, after
      two runs that produced no measurements, both lost to rig faults rather than to the
      bundlers). Recorded so nobody restarts the rig looking for an answer it cannot give.
      - **Windowed-ness is already settled by mechanism, not pending measurement.** PyInstaller
        `--noconsole` produces a GUI-subsystem binary; Briefcase's stub **is** GUI-subsystem -
        its PE header was read directly, `Subsystem = 2 (WINDOWS_GUI)`. A GUI-subsystem process
        gets **no console allocated**, and a double-click from Explorer has **no parent console
        to inherit**. So both are console-free when double-clicked. A run would confirm that; it
        cannot decide anything, because **the answer is the same for both**.
        The one real difference slightly favours *Briefcase*: PyInstaller additionally nulls the
        streams in software, so run from a terminal it skips the legacy probe even though the
        user chose that directory, while Briefcase consults it correctly.
      - **`CREATE_NO_WINDOW` is not a bundler question at all** - see the separate note below.
      - **What actually decides it was never measured, and no probe could have measured it:**

        | | PyInstaller | Briefcase |
        |---|---|---|
        | Produces an **installer** | **No** - a binary; then WiX/Inno, dmgbuild, appimagetool | **Yes** - MSI, DMG, deb/AppImage natively |
        | **Signing / notarization** | Wire it per platform yourself | Built in |
        | Build simplicity | One command, first try, both platforms | Project config + support download |
        | Maturity | 6.x, large install base | 0.4.4, pre-1.0 |

        The rig measured **runtime layout**, which `TRUESTILL_BIN_DIR` already solves in one
        line for either bundler. Installers and signing are what `(aad)` exists for.
    - **THE LEAN, recorded as CONDITIONAL rather than decided.**
      - **Briefcase if all three platforms ship**, on the installer-output and signing column,
        with the version pinned and its config expected to break on upgrade.
      - **PyInstaller + Inno Setup if Windows ships first** - more proven and simpler, and the
        three-platform argument that favours Briefcase does not bite yet.
      - **This turns on a product question - which platforms launch first - not an engineering
        one.** Do not resolve it in code.
    - **When packaging resumes, go straight to a real installer.** Not another probe: a
      double-click on a real machine answers the console question more directly than any rig,
      and a real installer answers the table above by existing. Two gates first, and neither is
      engineering: **the signing decision** (an unsigned installer is fatal for a product
      selling trust, per this entry's own reasoning, so building one now yields an artifact that
      cannot ship) and **soak closing** (`PROJECT_STATUS.md` §2 puts installers at #3, behind
      the soak gate).

  - **`CREATE_NO_WINDOW` suppression is NOT a bundler question, and is recorded separately so it
    stops riding along in the wrong rig** (moved out of the comparison 2026-08-01).
    - **It is our flag, not a bundler's.** It lives in `truestill_core.binaries.run` / `.popen`,
      and whether it suppresses a console window is a Windows question with the **same answer
      under either bundler**. It was measured inside the bundler rig purely because the rig was
      the only Windows lane, and that made two runs look like they were about the choice when
      they were not.
    - **The technique used was also wrong, independently of the rig.** `AttachConsole`
      attachability cannot distinguish suppressed from unsuppressed, because
      `CREATE_NO_WINDOW` creates an **invisible console** - the child *is* attached to one -
      while `DETACHED_PROCESS` is the flag that yields no console at all. The right observable
      is the console's **window**: `GetConsoleWindow()` returns `NULL` for a console that has
      none.
    - **Its real weight is cosmetic**: black console windows flashing while exiftool runs in
      batches. Worth fixing, not worth a bundler decision, and cheap to check on any Windows
      machine once one is to hand. Status recorded in `PROJECT_STATUS.md` §3.

  - **Settled 2026-07-31: do NOT run a VirusTotal comparison to choose the bundler.** It was
    proposed, approved, and then withdrawn on the design pass. Recorded here with the reasoning
    so it is not proposed again from the same premise - *"the AV claim is load-bearing and
    testable"*. It is load-bearing. It is not testable in a way that would decide anything.
    - **The deciding argument: signing dominates, and it is the same decision either way.** The
      gate a user meets is SmartScreen, which is reputation-based per file hash and per
      certificate. Unsigned, **both** candidates get warned on; signed, **both** accrue
      reputation on the certificate. So the AV question is **orthogonal to the choice it was
      meant to inform**.
    - The artifacts are not comparable anyway. PyInstaller ships a self-extracting bootloader -
      the packing behaviour heuristics target - while a Briefcase MSI is a native installer that
      packs nothing. The result would confirm from measurement what the mechanism already
      predicts, while reading as "Briefcase is safer".
    - The number would not even be stable. Detection counts track the **bootloader build's**
      reputation, not the approach (`pyinstaller#8164`: counts change with the PyInstaller
      version), and VirusTotal's raw count is unweighted, with a handful of engines producing
      most false positives. A single artifact per tool cannot separate signal from that noise.
    - **What a scan is still good for**, and where it belongs: a **release smoke test** on the
      signed artifact we actually ship, to catch a regression. Not a selection input, and not
      before there is something signed to scan.
  - **Not designed here on purpose.** The questions above are genuinely open and several are
    coupled (the shell decision changes the packaging answer, which changes the signing answer);
    picking one now would be guessing in public.

- **(aac) Organize must name and count unreadable source files the way verify does.** Ruled by
  the maintainer, 2026-07-30, from the Pass 1 F2/F1 asymmetry left after the code-quality audit.
  **Record only - do not fix in the same pass that closed F1/F2.**
  - **What shipped.** F1 gave `verify` `CopyStatus.UNREADABLE`, a count, and filenames on CLI
    and app. F2 kept `compute_hashes` alive on an unreadable source (empty hashes +
    `BrokenExecutor` guard) so an organize preview/run no longer aborts the whole pass.
  - **What is still silent.** Empty hashes mean no dedup identity and **no user-facing line**.
    A locked or `EIO` file in the source tree vanishes from the report; quieter than F1's old
    crash, same never-silent class (`IMPLEMENTATION_STANDARDS.md` §9).
  - **Requirement.** Organize preview and run summaries must count and name unreadable
    sources the same way verify reports unreadable copies. Do not treat empty hashes as a
    finished answer.

- **(vv) Known limit: app per-drive job lock is process-local; CLI↔app overlap is not serialized.**
  Recorded 2026-07-29 when Commit 3 of (oo) shipped the server-side one-op-per-drive guard.
  - **What is covered.** Concurrent jobs inside one `truestill-app` process (reload, second tab,
    double-click) are refused with `DriveBusy`.
  - **What is not.** The lock lives in `JobManager` memory. A `truestill` CLI invoke in another
    process does not see it, and a restarted app starts empty (no stale lock - deliberate).
    Catalog/journal crash-safety still applies; this is not a claim that two writers cannot
    touch the same drive across processes.
  - **Do not assume solved** when designing reclaim, migrate, or backup concurrency. A real
    cross-process guard (e.g. flock on the drive marker or catalog) is a separate design if
    soak ever shows CLI↔app races mattering in practice.
  - **Date-provenance step 4 narrows this, and does not close it (2026-07-31).** The bake
    refuses to write while a migration is journalled and unfinished on the same drive, reading
    `Catalog.pending_migration` - the journal lives in the shared catalog, so unlike this lock
    it **is** visible across processes. It re-checks before **every file**, so the exposure is
    the gap around a single write rather than the length of a run. **That is a check, not a
    mutex, and the residual race belongs to this item:** closing it needs the cross-process
    on-disk lock described above, deliberately not smuggled into step 4. Coverage measured
    while deciding: app-vs-app is already complete, because every job route goes through
    `server._start_drive_job` keyed on `uuid:<marker uuid>` (pinned by
    `test_every_drive_touching_route_starts_through_the_locked_helper`), so the real exposure
    is CLI-vs-app and CLI-vs-CLI.
  - **What the residual actually costs, stated so nobody over-corrects for it.** If the check
    does interleave, migrate compares the relocated file against its journal snapshot, finds the
    baked bytes, and **raises** - a loud, recoverable stall. `destination.relocate` copies rather
    than renames, so the file is preserved at its old path with an orphan at the new one and the
    journal row still pending; nothing is lost. That outcome is *why* `(aah)` was closed rather
    than built: weakening the comparison to avoid this stall would cost a real check, and the
    right fix if soak ever shows it biting is the on-disk lock above.
  - **Not fixed here, on purpose** - recorded only, per instruction.

- **(ss) Organize preview hashes every file before showing anything - slow on a network mount.**
  Ruled by the maintainer from a soak finding, 2026-07-29: measured **9.9 files/sec on a 2,064-file
  folder over a cloud FUSE mount, ~8 minutes to see a preview at all** - against an industry
  baseline of tens of thousands of files/sec for SHA-256 (the bottleneck is I/O, not the
  algorithm), which points at the network mount, not the hash.
  - **Checked in code before recording: both proposed fixes are already built.** The size-group
    pre-filter is not a gap - `scan.py`'s `_needs_sha` already hashes only files whose byte size
    collides within the scan or is already known to the catalog (`compute_hashes`'s whole
    stated purpose, "concurrent hashing pass with a byte-size pre-filter"). The hash cache is
    already wired into preview too - `service.organize_preview` opens `HashCache.beside(db)`
    and passes it through to `resolve(...)`, the same cache backlog **(r)** shipped. So the
    slowness is not explained by either mechanism's absence; **do not build them again** -
    whoever picks this up should confirm they are live on the affected path first.
  - **Cold-preview phase profile measured 2026-07-29** - see
    [`docs/preview-performance-profile.md`](preview-performance-profile.md). Numbers came from
    **`Crypto Folder/Photos/Vintage/.../Wayanad '14`** (2,064 files) - that tree is now
    **OFF LIMITS** (`PROJECT_STATUS.md` §4); keep the figures as historical only. On that
    run, **exiftool is 74% of cloud-mount wall** (231 s); hashing wall is 26% and is almost
    entirely unconditional `perceptual_hash` (SHA-256 already ~1% of files via `_needs_sha`).
    FUSE vs local gap is 13×, ~75% of it exiftool. Stat/walk are noise. Local twin was
    `TruestillLibrary/Input/2014/Wayanad '14`.
  - **Requirement for any fix:** measured **before/after on an allowed real cloud / FUSE
    corpus** (relocated Memory Cabinet, Output, or `<cloud mount>/2015`) - not a
    synthetic fixture, and **not** anything under `Crypto Folder/` (`PROJECT_STATUS.md` §4).
- **(xx) Absolute-path columns and hash-cache keys are not machine-portable.** Ruled by
  the maintainer from the 2026-07-30 move audit. **Record only - do not fix in the loud-failure
  series.** Commits 1-3 (**(ww)** path hints, catalog startup announcement, reclaim/undo
  staleness) made a machine move **survivable by failing loudly**; the remaining work is
  **portability**, not safety. User procedure:
  [`docs/moving-machines.md`](moving-machines.md).
  - **`files.source_path`** - absolute. Used by reclaim and by display labels (`where`,
    near-dup "matched" paths). After a move the recorded sources are gone; reclaim reports
    the missing count rather than a silent empty plan. A future rewrite (relative-to-drive,
    or clear-on-reclaim-only) is product design, not a hotfix.
  - **`inplace_runs.source_root` / `dest_root`** - absolute. Undo refuses unreachable stored
    roots and points at `--source-root` / `--dest-root`. Making the journal remount-native
    (uuid + relatives only) is later work; the overrides already exist.
  - **`reclaim_journal.source_path`** - absolute. Crash/audit resume only; stale after a
    move. Low urgency once reclaim no longer pretends mid-flight old paths are live.
  - **Hash-cache non-portability** (`catalog.cache.sqlite`, keyed by absolute path + size +
    `mtime_ns`, plus a tag-set fingerprint for metadata). Machine-local and disposable by
    design (`IMPLEMENTATION_STANDARDS.md` §8). Copying the sidecar to a new machine does
    **not** preserve the ~170× warm metadata win; first preview is cold.

    | | Absolute keys (today) | Drive-relative (`uuid` + relative) |
    |---|---|---|
    | Survives remount with preserved mtimes | No | Yes for **organized drive copies** |
    | Helps arbitrary unmarked `--source` trees | Yes (path-scoped) | No |
    | Cross-machine copy that resets mtime | Miss anyway | Miss anyway |
    | Wrong-file collision risk | Lower | Higher if relative reused / wrong root |
    | Matches custody model | Intentionally **not** in the catalog | Closer to custody, couples cache to "is this a drive?" |

    Prefer leaving the cache disposable over a half-portable key until a concrete trigger
    (measured remount pain that loud failures do not cover) appears.
  - **Not fixed here, on purpose** - recorded only, per instruction.

- **(yy) Reconnect a moved location (Lightroom-style Find Missing Folder).** Ruled by
  the maintainer 2026-07-30 after research into how Lightroom Classic repairs a moved library -
  the closest mature analogue. **Record only - do not build yet.** Cross-reference
  **(xx)** (`files.source_path` absolute).
  - **Why Lightroom's version works at scale.** Reconnecting the *top-level* missing
    folder cascades to every subfolder in one action. That cascade is load-bearing: without
    it, a moved library is a per-folder slog; with it, the fix is roughly two minutes.
  - **Scope for truestill - narrow on purpose.** Needed **only** for `files.source_path`
    (and the reclaim / search / near-dup labels that read it). After a move those absolute
    sources are dead: reclaim reports missing rows instead of offering deletes, and Find /
    near-dup display cites old paths. **Drive-relative copies need no repair at all** -
    custody is uuid + `file_copies.relative` under the marker; do not invent a reconnect
    flow for organized drive trees or anyone will over-build what already survives a remount
    (see [`moving-machines.md`](moving-machines.md)).
  - **Design when built.** Point once at the new root; rewrite the stored absolute prefix
    for every affected `files.source_path` row; preview-then-typed-confirm like every other
    bulk change in this product; never silent. Cascade from the chosen root the way
    Lightroom cascades from the top folder - one action, all descendants.
  - **Not fixed here, on purpose** - recorded only, per instruction.

- **(bbb) exiftool `_original` backups.** Ruled by the maintainer, 2026-07-30. When anyone edits a
  photo's date with exiftool, the default is to leave `file.jpg_original` beside it holding the
  **original** metadata (only `-overwrite_original` skips this).
  - **Safety - Built 2026-07-30.** Measured first: on the default path, `*.jpg_original` was
    already skipped as unrecognized (suffix `.jpg_original`, not `.jpg`). The residual bug was
    `--all-files`, which organized both the live file and the sidecar as near-copies (same
    pixels, different SHA/dates). Fix: `is_exiftool_original_backup` refuses
    `{live_filename}_original` at `scan_source` / `discover` for every caller, including
    `--all-files`. Skipped report uses the plain label **exiftool backup**, not a bare
    `.jpg_original` extension count. Matcher covers any extension (exiftool appends `_original`
    to the full filename). Collision pinned: a legitimate `vacation_original.jpg` ( `_original`
    before the extension) is **not** a backup and is still organized.
  - **Recovery - BUILT 2026-07-31 (step 6), with item 4 PARTIAL.** The offer ships in the rescue
    flow: `date_rescue.original_candidates` finds a ``{name}_original`` beside the recorded
    source, reads its date with the same resolver everything else uses, and offers it **only
    when it parses and differs**. Accepting pre-fills the rescue field; the commit is the same
    typed `confirm_file_date`, so a sidecar date is not a second route into `HUMAN_CONFIRMED`.
    Items 1, 2, 3 and 5 are satisfied as written.

    **Item 4 is one half built and one half DECIDED AGAINST - `(aaj)`, now in *Consciously out
    of scope*.** Verified against code, not assumed:
    - *"the human wins"* - **satisfied, structurally.** `confirm_date` writes
      `captured_at` + `date_source = HUMAN_CONFIRMED`; `migrate` renders from
      `files.captured_at` and `rederive_rules` re-reads metadata for **ambiguous labels only**,
      never dates; `record_uploaded` re-applies a confirmation on re-ingest. All five whole-disk
      operations are pinned by O4 in `test_confirmation_survives.py`.
    - *"note the embedded conflict (never silent)"* - **not built, and not going to be.** The
      only disagreement surfaced anywhere is the **sidecar's**, and only as an offer. Nothing
      compares the live file's embedded EXIF against a confirmation, and `confirm_date` sets
      ``date_tag = NULL`` - so the machine's prior evidence is *discarded*, and the catalog can
      no longer say what the file claimed without re-reading it.

    **Which comparison ships, because the design flagged this as a trap:** against **recorded
    provenance** (`files.captured_at`), never the file's current embedded metadata. After a bake
    the organized copy agrees with the confirmation while the *source* still does not, so
    comparing live metadata would make every rescued file report a conflict with itself forever.
    That trap is avoided - but honestly, it is avoided because the live comparison was never
    built, not because it was built carefully. It was then **decided against** on 2026-07-31,
    once the design showed the only constraint-satisfying route needs a column storing a value
    the system has already ruled wrong; see `(aaj)`. **The trap is recorded there, not open
    here** - and it applies again only if `(aal)` is ever built.

  - **Recovery - original design, kept for provenance** (see **Converged programs**):
    not a parallel `_original` tool. Full design (do not invent a separate surface):
    1. **No silent substitution.** Reading `_original` never auto-wins over the live file's
       embedded date in `resolve_capture_datetime`.
    2. **Same provenance as (ii):** if the user accepts the sibling date, record
       **`human-confirmed`** (highest tier), durable via the date-source column **(n)** and
       **(ii)** share. Machine suggestion only; human commits.
    3. **Same rescue seam:** when the live file has a date *and* a sibling
       `path.name + "_original"` exists with a different parseable capture date, offer a rescue
       candidate on the (ii)/(n) surface ("why this date?" → action). Wording like: "exiftool
       backup beside this file still has 2014-08-17 - use that date?" Confirm → place by
       confirmed date + provenance.
    4. **Disagree visibly:** if live EXIF and `_original` disagree after a human confirm, keep
       human-confirmed; optionally note the embedded conflict (never silent).
    5. **Dedup / identity:** rescue edits the catalog row for the **live** file; `_original`
       stays an unorganized sidecar (never ingested as a second library copy).
    - **Out of scope for recovery:** inventing merges, rewriting live EXIF from `_original`
      without confirm, treating `_original` as a second library citizen.
    - **Sequencing:** recovery UI waits on the (ii)/(n) provenance column - same screen. Safety
      shipped independently so this item is not "untouched".

- **(nn) Prove destination timestamp parity against a live rclone remote.** The destination
  timestamp seam is implemented for rclone as `touch --no-create --timestamp`. The installed
  rclone help was checked and a unit test pins the exact invocation, but **no real remote has
  exercised it**. That is command-shape evidence, not backend parity. Before claiming parity,
  run a dated normal copy against a disposable configured remote and verify its reported
  modification time equals the capture timestamp, the local source timestamps stay unchanged,
  and the failure path cannot create a zero-byte remote object.

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
  - **Still to build:** Analyze mode itself.

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
  - **Why the cache is not a separate item.** Analyze performs the **full expensive pass** --
    dates, hashes, dedup. Without a cache the natural journey *Analyze → Organize* pays for
    that pass **twice**, which makes the free analysis feel like a tax on organizing rather
    than an invitation to it. With it, the second pass is nearly free, and preview→run and
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
- **(v) BK-tree for perceptual dedup - build on the alarm, not before.** The linear scan is
  O(n²) *by decision* (`PERFORMANCE.md` §3): 0.7s at 2,275 images, ~22.6 min at 100k. A BK-tree
  today would be machinery bought before the problem.
  - **The trigger is instrumented, not remembered:** `dedup.LINEAR_SCAN_ALARM = 10_000` logs one
    line the first time an index crosses it. **This item is unblocked when that line appears in
    a real run**, not when someone re-reads this file.
  - Design already settled: BK-tree over Hamming distance, which fits a *fixed small* threshold
    like `DEFAULT_PHASH_THRESHOLD`. VP-tree is the more general metric-space answer and buys
    nothing extra here; LSH is for *approximate* nearest-neighbour at far larger scale and would
    trade away exactness we currently have. `DedupIndex`'s interface was designed for the swap.

- **GPS-derived per-photo timezone.** Deferred during Takeout Rescue Mode. `--tz` is a single
  fixed offset for the whole run, which cannot correctly date a library that spans timezones;
  the real fix derives each photo's timezone from its GPS. The near-midnight caveat is
  surfaced honestly in the ingest report until this exists.

- **(kk) Persist GPS at ingest - it is read and then thrown away.** Found while designing trip
  grouping (`trip-grouping-research.md` §5), and the scope is much wider than trips.
  - ⚠ **NOTHING OF THIS IS BUILT, and one half was in scope for a program that has now closed.**
    Verified 2026-07-31: the catalog has **no latitude/longitude columns and no `GPSDateStamp`**.
    `(kk)` was split by ruling - the **`GPSDateStamp`** half belonged to the date-provenance
    program (as the cross-check for a suspect dead-clock date), the lat/lon half serves
    places/map and is separate. **The date-provenance program completed 2026-07-31 without the
    `GPSDateStamp` half**, so this is not "the rest of a mostly-done item": both halves are
    unstarted, and a reader should not have to infer that from the program's closure notes.
  - **The defect.** GPS is read live from exiftool during an organize run and used for the
    event-clustering jump cut (`event_review.py:80` builds `EventItem.gps`), and then it is
    **never written to the catalog**. `files` has no latitude/longitude column at all, and
    `camera_copies_for_events` selects `sha256, captured_at` and nothing else. The data is
    obtained, used once, and discarded.
  - **Why it matters beyond trips.** A places / map view is a **high user expectation** in
    `org-structure-research.md`, and it is unbuildable without stored coordinates. The trip-edge
    case is only the symptom that exposed it: an arrival evening 80 km from home is trivially
    distinguishable from an evening at home, and truestill had that fact in memory and dropped it.
  - **It is permanently lost for already-organised libraries.** Every library placed before this
    lands has no stored GPS, and recovering it means re-reading every file. **We already pay the
    read cost** on every run - this is a column, not a pass.
  - **Scope:** persist latitude/longitude at ingest; persist `GPSDateStamp` alongside, since
    `date-layering-gap-check.md` §4(b) already ruled it the cross-check for a suspect dead-clock
    date and it is the same exiftool read. **`GPSDateStamp` is part of the date-provenance
    program** with `(n)` / `(ii)` / `(bbb)` recovery (see **Converged programs**) - the lat/lon
    columns also unlock places/map views, which are a separate product surface on the same write.
  - **Open question, deliberately not answered here:** whether existing libraries get a backfill
    pass. It is a re-read of the whole library, so it is opt-in work with a real cost, and it
    wants its own decision rather than being smuggled in with the column.

- **(ll) Sub-day event identity that survives a changing file set.** The day-event half of the
  identity defect recorded in `trip-grouping-research.md` §6.
  - **The defect.** `EventCandidate.signature` (`events.py:109`) is a SHA-256 over the member
    `sha256`s, and that is the `UNIQUE` key `event_by_signature` looks up. Membership *is*
    identity, so ingesting one more photo from an already-named day changes the signature and the
    event is proposed again as new, with the name already given orphaned.
  - **The trip fix does NOT apply here, and this is the point of the entry.** Trips are keyed on
    `trip_days.day` because a day belongs to at most one trip. **Day events are not days.**
    2014-08-16 alone produced two clusters (565 and 157 files) and 2014-08-17 produced three;
    keying on the date would collapse a morning outing and an evening one into one identity and
    silently merge two separately-named events. **Do not apply the day-key remedy to events.**
  - **What is needed instead:** an identity stable under a changing file set that still separates
    several events within one day - a time-anchored key (day plus cluster start, tolerance
    matched) is the obvious candidate and needs its own design pass and its own evidence.

- **Recognize additional real-world video extensions (l).** The metadata-chain corpus surfaced
  container formats truestill's `MEDIA_EXTENSIONS` doesn't recognize, so they are skipped (now
  *reported*, not silent). Recognize the ones that are actually common - **`.vob`, `.ts`, `.m2v`,
  and the `.asf` family at minimum** - with the final list driven by **prevalence evidence, not
  the whole corpus zoo** (`.swf`, raw `.hevc`/`.mjpeg` elementary streams are not "photos to back
  up"). Each extension added must have its **category and date handling verified via the corpus
  probe** before inclusion. **Post-launch, demand-driven.**


- **(aam) Sidebar reference: profile header, section labels, submenus.** Ruled by the
  maintainer, 2026-08-01. **Record only - not built, and one question below blocks building.**
  - **Why the profile header applies at all, corrected.** It was first set aside on the
    assumption that truestill has no accounts. `DECISIONS.md` **D5** supersedes D1: truestill
    **requires a user account**, created at activation against a self-hosted licensing server.
    So an identity in the UI is not scaffolding for a feature that will never exist - it is the
    surface D5 needs. **Cursor is the model:** sign in once, work offline afterwards, identity
    visible in the interface rather than hidden in a settings page.
  - **Profile header:** avatar, name, and **licence state** (Pro / free - **not** trial; see
    `DECISIONS.md` D6 §4, which abolished the trial after this entry was written) in the position
    the reference gives a role line. This is also **where the account surface lands when D5's
    licensing server ships**, so it is built once rather than added beside something later.
  - **Wordmark** from [`brand.md`](brand.md), above or beside the profile header. Which of the
    two is a decision for the build, not now.
  - **Section labels** (`MAIN` / `SETTINGS`), **pill active state**, and a **collapsed icon rail
    with tooltips** - the rail is already built in `(fff)`, so this reference confirms it rather
    than adding it. **Flyout submenu on hover when collapsed** is the new part.
  - **The bottom action is not "Logout".** A one-click logout next to Help treats activation as
    a session, and it is not one: activation happens **once**, and a perpetual licence
    (`DECISIONS.md` D6) is not a login. The bottom item is **account or licence details**, with
    sign-out available *inside* it. Recorded with the reasoning because the failure mode is
    specific and severe: **a casual logout button can strand a user from software they have paid
    for**, on a machine that may be offline, for a product whose whole proposition is custody.
  - **BLOCKING QUESTION, deliberately not answered here: do any screens get NESTED SUBMENUS?**
    truestill's screens are flat today. Adopting the reference's hierarchy means deciding which
    screens have children and which do not, and that is **information architecture, not
    styling** - it changes what the product says its parts are. Needs a ruling before any of
    this is built; the flyout behaviour above is meaningless until it has one.
  - **The cost, recorded so it is priced rather than discovered.** A hover flyout **needs a
    keyboard equivalent**. `(fff)` already established this exact rule for the collapsed rail -
    tooltips on hover **and focus**, recorded there as "not optional polish" - and a submenu
    reachable only by hover is **unreachable by keyboard**, which is worse than a tooltip that
    is merely invisible: the navigation itself becomes unusable. Whatever the answer to the
    nested-submenu question, the flyout is two implementations, not one.

## Approved and built (provenance - do not rebuild)

These were approved here and **are shipped**. They keep their letters, because
`IMPLEMENTATION_STANDARDS.md` §8 cites `(u)` by letter and a retired letter is not a free one -
see **Item letters**. They stay in this file rather than moving to **Shipped (kept for
provenance)** below, which records work that never had a backlog letter.

**Read an entry's own status line, never this heading.** The heading told you these are built;
only the entry tells you *how much* of it, and two entries elsewhere in this file were found
recording shipped work as unstarted, which is the more expensive direction of the same mistake.

- **(n) "How your dates were determined" honesty stat - BUILT 2026-07-31 (steps 1, 2 and 5).**
  **Part of the date-provenance program** (see **Converged programs**) - do not build this
  alone.
  - **Built:** the durable provenance column (`files.date_source`, schema **v13**, plus
    `date_tag` at **v14**), `Catalog.stats_date_provenance`, and the honesty view itself, live
    in the app at `service/stats.py` (`_date_provenance`). `date_explain.py` is the single place
    a tier becomes a sentence, including the calm **NOT_RECORDED** wording for libraries
    organized before v13 - which on the maintainer's own 2,300-row catalog is **every row**.
  - **The drill-down shipped in step 5** (`Catalog.files_in_date_tier`,
    `stats.date_tier_files`, `GET /api/dates/files`): each tier opens to the files in it, every
    row carrying the sha256 the rescue action is keyed on. That answers the walkthrough finding
    below - a bare count with no way in - for the **files** and not only the **mix**.
  - ⚠ **This entry read as unstarted until 2026-07-31**, after the column, migrations and view
    had all shipped, and then read as *partly* built for one more day after the drill-down
    landed. A cold start would have rebuilt `date_source` from scratch. That is the inverse of
    `(bb)`'s optimistic marking and the more expensive direction of the two - and it recurred
    twice in one program, which is why status now lives on the entry and the entry lives in the
    section matching it.

  The original description, kept because the requirement it states is still the target: a
  per-run/library figure in the reports/UI showing the **provenance mix** of capture
  dates - e.g. "82% from embedded EXIF, 11% from filename, 5% from Takeout, 2% Undated" (a
  metadata-accuracy %). truestill already resolves and could persist `date_source` (see the
  metadata-chain §1b.3 schema-v9 note); surfacing it honestly tells a user how much to trust
  their timeline, in truestill's voice.
  - **Validated by the UI-v2 walkthrough:** the organize result's "**N no date → Undated**" line
    confused a first user - a bare count with no way in. It must be **explorable**: click it to see
    *which* files were undated and *why* no date was found (which tags were checked, whether a
    filename date was tried). Same treatment for the provenance mix - each slice drills to its
    files. This is the concrete first slice of (n) to build first post-launch.

- **(ii) Rescue flow for side-bin and undated files - BUILT 2026-07-31 (steps 3 and 5).** Ruled by the
  maintainer from a soak finding, and the finding is the argument: real memories genuinely do sit
  in `Saved/`, `WhatsApp/` and `Undated/` - a photo someone sent you of a day you were there is
  still your memory. **Part of the date-provenance program** (see **Converged programs**) - do
  not build this alone.
  - **Built - the storage half.** `date_confirmations` (schema **v15**), `Catalog.confirm_date`
    (one transaction: the durable row plus the `files` update that makes catalog-driven
    re-render place by the confirmed date) and `Catalog.confirmed_date`. Obligation **O4** is
    tested against every whole-disk operation by name in `test_confirmation_survives.py`:
    migrate-layout, re-layout under a different preset, in-place organize, undo-organize, and a
    re-ingest. The re-ingest case found a real defect - `record_uploaded` reverted a confirmed
    date while the confirmation sat intact beside it - now fixed and pinned.
  - **Built - the surface, in step 5.** `POST /api/dates/confirm`
    (`date_rescue.confirm_file_date`) records the date, refuses a precision the model cannot
    represent rather than rounding it, and answers with the three states a user needs: what the
    library now believes, that the file has not moved, and what the file itself still says.
    Reached from the honesty view's drill-down. **App-only by recorded deferral** - see
    *App-surface deferrals*.
  - So the sentence this entry used to open with - *"today there is no durable way to move one
    onto the timeline"* - is now simply **out of date**, and kept only as the argument that
    produced the item.
  - **The problem, precisely.** A hand-move is *undone by the next whole-disk operation*. The
    catalog still records the old location and the old, untrusted date, so `migrate-layout`
    re-renders the file straight back to the bin it was rescued from. The user's correction is
    not merely forgotten - it is actively reverted, which is worse than not supporting it.
  - **A rescue is a CATALOG event, not a file move.** The user confirms the true capture date
    (and optionally an event); truestill places the file in the timeline itself, through the
    normal seam, and records the date with provenance **`human-confirmed`**. Nobody drags
    anything; the tool does the move because the tool owns the placement.
  - **Human-confirmed provenance outranks machine derivation, permanently.** Every subsequent
    organize, migrate and verify routes the file by the confirmed date. This is the whole
    feature: a rescue that does not survive every future whole-disk operation has not happened.
  - **It fits the existing model rather than bolting on.** `DateSource` already ranks tiers
    (EXIF → Takeout → filename → none/rejected-sentinel); `human-confirmed` becomes the new
    highest tier and the resolver's ordering does the rest. Persisting it needs the date-source
    column that item **(n)** has been waiting on - so (n) and (ii) share a schema step.
  - **Surfaced from the bins and the Undated view**, and it shares (n)'s UI surface: (n) makes
    "why is this undated?" explorable, and this is the action offered once the user is looking
    at the answer. Building either alone builds half a screen.
  - **Research pass before build:** how Google Photos and Immich handle user date edits, and
    specifically their *persistence* semantics - whether a corrected date survives re-scan,
    re-import and library moves, and what they do when embedded metadata later contradicts a
    human edit. That last case is the design's real question: truestill's answer must be that
    the human wins, but the disagreement should be visible rather than silent.
  - ⚠ **Interaction with dedup, to design against:** a rescued file's content hash is unchanged,
    so a re-run must not treat the rescue as a new file *or* re-place it by its old evidence.
    The catalog row is the identity; the rescue edits it.
  - **Sequencing: post-arc.** Priority argued **up** by the soak finding - without it, rescuing
    anything out of a side bin is not merely unsupported but impossible to do durably. **Same
    program as (n) / (bbb) recovery / (kk) GPSDateStamp** - see **Converged programs**.

- **(oo) Long-running actions must show they are running.** Ruled by the maintainer from a soak
  finding, 2026-07-29, same class as the silent-failure gap fixed in `670ab5d` - that one hid
  **errors**, this one hides **work**.
  **Built (2026-07-29).** Core progress through rederive/plan; job-ify of migrate/events/ingest
  preview; server-side per-drive JobManager lock; reusable `withBusy` UI helper (disable for
  the duration, re-enable on success/cancel/error) covering job-ified and sync triggers;
  DriveBusy surfaced as its own message; Playwright e2e for disable/progress/second-click/
  DriveBusy.
  - **The finding.** After "Save names" on a 2,057-photo trip over a cloud mount, the preview
    step (`/api/events/{session}/preview`) took **~3 minutes with zero UI feedback** - no
    spinner, no progress text, no disabled button. The screen looked frozen. A user in that
    position will assume it is broken, click the button again, or force-quit mid-operation -
    the same "did anything happen?" defect the ten soak findings in `PROJECT_STATUS.md` §2.1
    were made of, just on the *work* axis instead of the *error* axis.
  - **Root cause, verified in code, not guessed.** Two different mechanisms exist side by side.
    `organize_preview`/`organize_run`/`verify_run`/`backup_run`/`migrate_run`/
    `events_apply_to_disk` all go through `jobs.start(...)` - a background job the client polls
    via `streamJob`/SSE, with a real progress bar (`createProgress`). Everything else is a
    **plain, blocking request/response** with no progress channel at all:
    `backup_preview`, `migrate_preview`, `ingest_preview` (Import), `events_propose` (Find
    trips & events), `events_merge`, `events_split`, `events_apply`, and
    **`events_preview`** - the exact call this finding is about. Nothing about `events_preview`
    is special; it simply happens to be the one that runs long enough (a real `migrate.py`
    plan over 2,057 files on a network mount) to expose that none of this group has ever had a
    busy state.
  - **Requirement (met).** Every action that can exceed ~1s must: (1) show busy state on its own
    trigger the instant it is clicked (disabled/spinner), (2) show a progress or status line
    naming what is happening **and its scale** ("Planning moves for 2,057 photos…", not just
    "Working…"), and (3) refuse a second click while the first run is still in flight.

- **(uu) CORRECTNESS: non-Apple videos with only UTC `CreateDate` are filed as local wall-clock.**
  Ruled by the maintainer from a discovery pass, 2026-07-29. **Built (2026-07-30).** Evidence ladder
  after Apple `CreationDate`: MakerNotes `TimeZone`, GPS UTC proof (wired, unexercised by
  corpus), filename+duration (half-hour grid, unique match, ε=3s). `DateSource.INFERRED_LOCAL`
  + parseable `date_tag`; fallthrough is `CreateDate|not_proven_utc` (treated as local, usually
  correct - not a defect). Never-silent report names file + before/after + offset. Canon
  `MVI_2550.MOV` regression pin stays **14:28:39** via `DateTimeOriginal`. Stills untouched.
  Rung 5 corroboration-only. Mutation tests lock unique-match, duration, half-hour grid, and
  messenger refusal. **Do not blanket-convert** - cameras often write local into CreateDate.
  - **The defect (historical).** Video containers store `CreateDate` in UTC per spec; many
    cameras write local instead. Treating digits as local without evidence mis-dates Android
    clips ~5.5h early (IST soak); near midnight, wrong day/trip folder.
  - **Documented trap - do not walk into it:** EXIF `OffsetTime` is modification time, never
    use it to convert `DateTimeOriginal`.

- **(pp) No in-app undo for a trip/migration apply-to-disk - CLI-only today, and the visible
  in-app "undo" is the wrong one.** Ruled by the maintainer from a soak finding, 2026-07-29.
  **Built (2026-07-29).** `GET /api/migrate/undo`, preview/apply jobs through JobManager,
  durable affordance on Trips and Settings (re-queried on load and after every migration),
  reusable `typedConfirm` with the word `undo`, refusals surfaced. Reuses `undo_migration`
  directly - no parallel journal. The `undo-organize` CLI string on the in-place card is a
  different mechanism and is unchanged.
  - **The finding.** `migrate.py`'s reversal (`undo_migration`, keyed on
    `catalog.reversible_migration(drive_uuid)`) exists and works - it is the mechanism behind
    `truestill migrate-layout <path> --undo` (preview) / `--undo --apply` (typed `undo`
    confirm) - but it was wired **only into the CLI** (`cli.py`'s `_cmd_migrate_undo`). Nothing
    in `server.py` exposed it, and nothing in `app.js` linked to it. A user who names trips,
    applies them to disk from the app, and regrets it had no way back inside the app at all.
  - **The mismatch is worse than the absence.** The only "undo" string the app shows for
    in-place organize is still `truestill undo-organize` - a **different** reversal, for a
    **different** operation (`inplace_runs`/`inplace_moves`), sharing no code with
    `migrate.py`'s journal. That CLI hint remains; migration undo is now a separate in-app
    affordance so the two cannot be confused.
  - **Requirement (met).** Preview first, typed confirm `undo`, refuse changed files out loud,
    state plainly that only the most recent migration on a drive is reversible, re-query after
    every migration because supersession has no other signal.

- **(qq) The path on a trip/event completion card's reveal link does not open the folder.**
  Ruled by the maintainer from a soak finding, 2026-07-29, from a live trip apply.
  - **Built.** `migration_apply` joins each `file_copies.relative` ancestor onto the connected
    drive mount before putting it in the reveal `path` field (`_reveal_folder_on_drive`).
    `/api/reveal` then receives an absolute folder under the drive, not a cwd-relative fragment.
  - **Audit (same class):** the only other `data-open` / reveal callers are drive cards
    (`list_drives` path hints - already absolute) and the shared click handler. Find/inventory
    rows show `relative` as display text only, never as a reveal target. No second site.

- **Empty-folder cleanup (provenance: (rr), (zz), (eee) Commit 4).** **Built**
  (`7d9830c` + Commit 4 of `(eee)`). One shared capability across move / in-place organize,
  undo-organize, and trip/migrate apply-to-disk: leftover empty folders are **reported**
  (count + names) and the same preview + typed-confirm `clean-empty` flow is **offered**,
  reusing `emptied_directories` / `plan_cleanup` / `run_cleanup`. Folders are never
  auto-deleted. Do not treat `(rr)` / `(zz)` as separate open work - they closed as this.

- **(ww) Stale absolute path hints after a drive moves.** Ruled by the maintainer from a soak
  finding, 2026-07-30; **fixed 2026-07-30.** `locate_drive` / `path_is_usable_dir` swallow
  ``OSError`` (ENOENT, PermissionError, …) and return the drive-correction payload instead.
  Failed hints are **cleared** (not ignored) so Backups does not re-stat a dead mount every
  load; Check now / open-folder only appear for live paths. Verify soft-fails the same way
  migration already did. Identity remains the marker uuid.
  - Remaining absolute-path / hash-cache portability is **(xx)**, not a re-open of this item.

- **(aaa) Typed confirmations crash with raw `EOFError` in non-interactive runs.** Ruled by
  the maintainer from the 2026-07-30 maiden voyage: `organize --in-place --apply` aborted with a
  traceback when stdin was non-interactive (pipe/script/CI).
  - **Built (`f19a45c`).** Shared `_typed_confirmation` catches `EOFError` and exits with a
    clear refusal: interactive confirmation is required. Wired to every typed-confirm site:
    in-place `move`, migrate `move`, migrate-undo `undo`, clean `clean`, permanent
    `delete forever`, reclaim `delete`.

- **(ccc) Plain-language audit of user-facing copy.** Ruled by the maintainer, 2026-07-30.
  - **Built 2026-07-30.** Inventory + rewrites across app/CLI help/README (CHANGELOG excluded).
    Kept `custody` (defined once), kept `catalog` where it names the file, distinguished
    folder pattern vs saved folder pattern, bridged UI "in this same folder" to `--in-place`,
    and rewrote errors as plain sentences that still carry what/why/next without scaffold
    labels. Living-grep guard + allowlist in `test_user_facing_copy.py`.

- **(ddd) Stats view (custody-first).** Ruled by the maintainer, 2026-07-30.
  - **Built 2026-07-30.** New `Stats` screen in the app with three sections:
    Custody (photos/videos/size, 2+/1/0-drive counts, per-drive rollup, never-verified),
    Completeness (undated, timeline-vs-side-bin, near-duplicate flagged), and Shape (by-year,
    by-format, oldest/newest capture).
  - **Performance contract kept:** catalog-only aggregate SQL (`service.library_stats` +
    `Catalog.stats_*`), no file reads, no hashing, no exiftool, no per-file Python loops.
  - **Actionability:** at-risk and never-verified route to Backups; undated routes to Find and
    shows sample paths.
  - **Intentional omission:** exact-duplicate "found" count is not persisted in catalog and is
    omitted here rather than recomputed by a fresh scan; the UI states this plainly.
    **That omission is now its own item, `(aaf)`**, with the reason it is (m)-sized: `Resolution`
    objects die with the job, so there is no row to read later and it needs a new table. Do not
    treat this bullet as the whole story - `(aaf)` carries the market evidence and the open
    design questions.

- **(eee) Three organize modes in the app (copy / move / in-place).** Ruled by the maintainer,
  2026-07-30; CLI modes already proven.
  - **Built 2026-07-30.** App surfaces Copy / Move / Reorganize in this same folder with
    mechanism-aware reversibility before typed confirm; durable `undo-organize` affordance;
    Playwright + mutation coverage. Empty-folder leftovers on these paths are the shared
    **Empty-folder cleanup** capability (provenance `(rr)` / `(zz)` / Commit 4), not a
    separate feature.

- **(fff) Collapsible sidebar.** Ruled by the maintainer, 2026-07-30.
  **Built (2026-07-30).** Hamburger toggle (expanded icon+label / collapsed icon-only rail);
  required hover **and** focus tooltips when collapsed; persist via catalog setting
  `ui.sidebar.collapsed` (no localStorage); compact custody pips-only in the rail; keyboard
  toggle keeps focus; short width transition; Playwright collapse/expand, persistence,
  tooltips, custody bounds, keyboard; each guard broken once then restored.
  - Hamburger toggle: expanded = icon+label; collapsed = icon-only narrow rail.
  - Collapsed **must** show label tooltips on hover **and** focus (not optional polish).
  - Persist via existing catalog settings key/value - **no** localStorage / new store.
  - Custody strip adapts when collapsed: compact indicator only; must not reintroduce path
    overflow in the narrow rail.
  - Keyboard: toggle focusable/operable; collapsing must not trap or lose focus.
  - Short width-transition animation only.
  - Playwright: collapse/expand; persists across reload; tooltips on hover when collapsed;
    custody stays inside rail; keyboard toggle works. Break each, watch fail, restore.

- **(tt) No fast, no-hashing inventory - progressive disclosure is missing.** Ruled by the maintainer
  from a soak finding, 2026-07-29, the natural complement to **(ss)**: a user who only wants
  "how many photos/videos, which formats, how big" has to wait for the full hashing preview to
  get an answer neither dedup nor dating touches.
  - **Built 2026-07-29.** `organizer.inventory_source` + `service.organize_inventory` +
    `POST /api/organize/inventory` return counts by type/extension and total media bytes after
    the walk + one dedicated `stat` pass - no exiftool, no hashing. UI: **Look inside** shows
    that card immediately; **Check for duplicates** is the explicit second step that runs the
    existing full preview job. Size is a dedicated pass (not `compute_hashes._sizes`) so
    inventory stays off the expensive path; profile evidence puts that `stat` at ~0.3 s on
    a cloud mount vs ~231 s for exiftool.
  - **Not the same thing as backlog (r)'s Analyze mode - complementary, likely its precursor.**
    (r)'s Analyze mode explicitly runs "the existing dry-run engine" for a *richer* report
    (duplicates, look-alikes, capture-date range) - it is the same expensive pass as preview,
    with better output, not a cheaper one. (tt) is the tier **before** that.

- **(u) Metadata (exiftool) cache.** **Built 2026-07-29** into the existing
  `hash_cache.HashCache` sidecar (same path+size+mtime_ns key; tag-set fingerprint; force
  re-read via `--refresh-metadata` / app checkbox). Known mtime-without-bump limit documented
  at the cache site. Verify and reclaim still never use it.

- **(aa) Introduce an `Event` value object** (`start`, `slug`, `name`, `id`). **Built
  2026-07-30.** One object replaces the three parallel dicts (`assignments`, `event_ids`,
  `names`) that were the root cause of the audit's F1 (missing names): parallel collections is
  the anti-pattern where each new need adds another array instead of changing the existing
  type. `apply_events`, `execute`, CLI review, and app `commit` all take `dict[str, Event]`;
  a member cannot carry a slug without its id/name slot. Optional `name=None` keeps the slug-
  folder fallback. Golden paths + catalog event rows pinned in `test_event_value_object.py`.
  Day/sub-day distinction respected - `start` is the cluster timestamp, not a calendar day
  (see `(ll)`).
- **(bb) `rule` becomes a `StrEnum`.** **Built 2026-07-30** (input half; output/`Placement`
  half shipped earlier in Stage 2a). `RuleName` enumerates the seven emitters;
  `TIMELINE_RULE = RuleName.DEVICE`; `classify` coerces/`assert_never`-matches on the enum so a
  typo raises instead of silently side-binning. Not a catalog column - no durable string is
  validated against the enum.
- **(cc) Collapse `preview()` into `preview_scheme()`.** **Built 2026-07-30.** Dead
  `preview()` deleted; collision + path-length risk lives once in `_preview_rows`, used by
  `preview_scheme`. Tests retargeted at the shared helper so the rule cannot diverge.
- **(dd) Extract `execute()`'s per-file body into named steps.** **Built 2026-07-30** in two
  commits. Matrix first (`test_execute_matrix.py`): ActionResult sequence + destination tree +
  catalog `files` + `inplace_moves` for exact-dup, near-dup, undated skip, dry-run, in-place
  rename, cross-device fallback, Takeout bake, and cancel mid-run (cancel was **new** coverage).
  Extract Method second: `_write_organized_bytes` -> `_record_organized_file` ->
  `_journal_or_delete_source` under `_execute_one_write`, order bake/write -> catalog ->
  journal/delete unchanged; exception boundary and `baker.close()` unchanged. PLR0912/PLR0915
  suppressions removed (honestly earned); PLR0913 kept (kwargs API).
- **(ee) Move the pin out of `layout.py`.** **Built 2026-07-30.** The catalog-touching trio
  (`pin_existing_layout`, `effective_layout_string`, `resolve_scheme`) now lives in
  `layout_settings.py`, which imports `Catalog` directly. Invented `CatalogLike` Protocol
  retired. `layout.py` stays pure grammar/routing/rendering.
- **(ff) Typed payloads at the app boundary.** **Built 2026-07-30** (six slices). `service.py`
  returns `dict[str, Any]` many times was not theoretical: the `dict(PRESETS)` regression -
  dataclasses about to be serialized into the API - was invisible to mypy precisely because the
  return type was `Any`. Boundary is now TypedDicts mirroring JSON exactly; `-> dict[str, Any]`
  count at the service boundary is zero.
  - **Slice 1 - Built 2026-07-30:** `LayoutState` / preview / set-layout TypedDicts. `presets`
    is `dict[str, str]`; mypy rejects `dict(PRESETS)`. Key-set pins in `test_settings_http`.
  - **Slice 2 - Built 2026-07-30:** organize mode, sidebar, filesystem-relationship leaves.
  - **Slice 3 - Built 2026-07-30:** reveal + `fs_dirs` / `fs_create` / `fs_validate` (optional
    keys preserved, including the resolve-failure shape without `is_drive`).
  - **Slice 4 - Built 2026-07-30:** sync leaves - `organize_inventory`, `clean_empty_*`, `where`,
    `library_stats`, `library_status`, `backup_preview`, plus `list_drives` / `at_risk` element
    types. Shared `MediaBreakdown` helper typed; `_completion` / job summaries deferred (fan-out
    report before typing).
  - **Slice 5 - Built 2026-07-30:** `CompletionBase` (17 keys), `OrganizeDoneSummary` (plus mode /
    mechanism / drive_label / single_copy; `leftover_empty_folders` NotRequired), shared
    `LeftoverEmptyFolders` used by organize + migration apply. `cancelled` is UI-only (commented);
    `elapsed_seconds` NotRequired - jobs.py injects it on dict summaries (documented boundary).
  - **Slice 6 - Built 2026-07-30:** remaining job targets and helpers (`_summarize`, organize
    preview/undo, verify, ingest, backup run, migration preview) typed to zero
    `-> dict[str, Any]` at the service boundary.
- **(aab) Split `dates.py`.** **Built 2026-07-30.** Video ladder + offset grid + `LadderHit`
  moved to `video_utc.py`; inferred-local ``date_tag`` / ``format_offset`` to cycle-free
  `date_provenance.py`. `models._format_offset_hhmm` / `_parse_offset_hhmm` deleted - both
  sides share the provenance module. `dates.py` keeps resolve chain, EXIF/filename parsing,
  and Tier A/B sentinels.

- **(aae) Catalog and cache belong in OS-conventional locations, and are not the same kind of
  data.** Ruled by the maintainer, 2026-07-31.
  - **Built.** `5db91b9` resolved catalog and cache to OS-conventional locations; `5bf98b1`
    added the `truestill catalog` command that says where the catalog lives and moves it on
    request; `42b30d0` made the resolution happen per call and isolated it in tests; `df9bd13`
    narrowed the legacy question to the case where a working directory was actually chosen.
  - **Current state, verified against code 2026-08-01.** `default_catalog_path`
    (`app_paths.py`) resolves **on every call** rather than as a module constant, so an
    override set after import is still honoured and a test can isolate it. The old
    `DEFAULT_CATALOG_PATH` is **gone** - `catalog_startup.py` carries a comment at the site
    saying why it was removed. `TRUESTILL_DATA_DIR` and `TRUESTILL_CACHE_DIR` (`DATA_DIR_ENV`,
    `CACHE_DIR_ENV`) override both roots on every platform, which is what makes the suite
    isolatable by construction rather than by discipline. `LEGACY_CATALOG_PATH` wins when it
    exists and a working directory was genuinely chosen, so an upgrade keeps using the catalog
    the user already has instead of silently opening an empty new one; `standard_catalog_path`
    is where it *belongs*, and `move_catalog_to_standard` (`catalog_move.py`) is the explicit,
    refusing-on-doubt move between the two.
  - **The open questions are answered.** `platformdirs` **is** justified in writing, at the top
    of `app_paths.py`, against the stdlib alternative as `ENGINEERING_STANDARD.md` §4 requires.
    An existing `reports/catalog.sqlite` is **adopted, never orphaned**. The filename stayed
    `catalog.sqlite` (`CATALOG_FILENAME`), the enclosing directory now naming the app instead -
    which was the recorded weak point, and the enclosing directory answering it was one of the
    options this entry listed.
  - **`--db` stays the override, traced 2026-08-01 because this entry left it open.** Both
    surfaces take an explicit path ahead of the resolved default: every catalog-touching CLI
    subcommand declares `--db` with `default=default_catalog_path()`, and the app does
    `args.db if explicit_db else default_catalog_path()`. Whether the path was **named** rather
    than **resolved** is carried separately as `explicit_db`, threaded to `inspect_catalog`,
    `create_app` and `library_status`, so the startup announcement can say which of the two
    happened rather than printing a path with no provenance.
  - **The finding that produced it, kept as provenance: two different kinds of data sharing one
    fate.** `catalog.sqlite` is **user data** - the custody record, human-confirmed dates
    (`date_confirmations`), trip names. Losing it is unrecoverable. `catalog.cache.sqlite` is
    **cache** - derived, disposable, and its own module already says "delete this file and
    nothing is lost but time" (~12 s to rebuild). The cross-platform convention separates them
    precisely because their correct treatment differs: `user_data_dir` vs `user_cache_dir` (XDG
    on Linux, `~/Library/Application Support` vs `~/Library/Caches` on macOS, `%APPDATA%` vs
    `%LOCALAPPDATA%` on Windows).
  - **Why it was more than tidiness.**
    - A cache in the OS cache location may be **cleared by the OS or excluded from backups** -
      which is *correct* for a cache and *catastrophic* for a catalog. Sharing a directory meant
      any such policy hit both.
    - **CWD-relative defaults produced the silent-empty-catalog trap.** Announcing the resolved
      path (`catalog_startup.inspect_catalog`) treated the symptom; the cause was that running
      from a different directory silently addressed a different catalog.
    - **(aad) installers make it fatal.** A double-clicked desktop app has no meaningful working
      directory, so a relative default is not merely untidy there - it is undefined.
  - **The cache is ONE file, deliberately, and that does not change.** Not per-folder and not
    per-year. It is keyed by absolute path + size + `mtime_ns`, so a single sidecar serves every
    drive and every run. Scattering cache files through a user's library would make the library
    non-portable and would leave truestill's droppings inside the very folders it promises only
    to organize. Moving the file must not become an excuse to split it.

- **(jj) Archive ingestion - read a library straight out of its archives.**
  **BUILT AND COMPLETE 2026-08-01. Nothing outstanding.** Zip and tar, core through UI, in eight
  commits: the preconditions (`abcd1fb`), the extractor (`346135c`), the pipeline wiring
  (`ca6effc`), tar and `.tgz` (`d330fce`), this record (`c08ed03`), the scope correction
  (`c08eb50`), the `--source` rename (`8dbbb50`) and the UI (`4606713`). Guard rule 8
  (`720b217`) came out of the tar work and is recorded in `ENGINEERING_STANDARD.md`.
  - ⚠ **SCOPE, corrected 2026-08-01: this is NOT a Takeout feature.** It reads any `.zip`,
    `.tar`, `.tgz` or `.tar.gz` from any source - a friend's shared folder, an old backup, a
    phone export, a NAS dump. **Takeout is the motivating case, not the scope**, and the export
    table below shows why: every major photo service hands a user a `.zip`. Every user-facing
    string was audited and reworded; six read as Takeout-specific and no longer do.
    **What stays named "Takeout", correctly:** `scan_takeout`, the JSON sidecar matching and the
    `photoTakenTime` parsing are **Google's own format**, and `takeout.py` says so at the top so
    a future sweep does not "fix" a correct name. A second service with its own sidecar format
    would get its own module, not a widened name here.
  - **What shipped.**
    1. *Preconditions, before anything is written* (`archive_set`, `archive_ingest`). Header
       reads only - it does not even create the destination, so declining is free. Numbered
       parts are grouped into one logical set, **gaps are named** (a set missing `-009` would
       otherwise yield a library with a hole in it, silently), and space is checked against the
       destination drive. The size shown is labelled in the user-facing text as **the archives'
       own claim, never a measurement truestill made** - it is a header field whoever built the
       archive chose.
    2. *Extraction* (`archive_extract`). The journal is written and **fsynced before any byte
       exists**, so a crash never leaves files nothing can attribute; recovery is proven against
       a real `SIGKILL` and asserted **from a fresh process**. Entry names are **refused, not
       rewritten**. Files are written to a sibling and renamed, because a truncated JPEG still
       hashes. The byte budget is the *lower* of free space minus a 1 GiB reserve and the claim
       plus 10%, and it aborts on the **real running total** rather than the declared one.
    3. *Pipeline wiring* (`scan_takeout` unchanged - **that it needs no change is the claim, and
       it is asserted**). The multi-part correctness test builds a `Photos from 2014` folder that
       genuinely straddles two parts and proves the sidecar still matches; its cry-wolf
       counterpart proves extracting the parts separately **loses the date**.
    4. *Tar and `.tgz`*, via `tarfile.data_filter` **per member** rather than
       `extractall(filter="data")`, so tar shares the same counter, journal and rename as zip
       instead of forking the extractor.
  - **CLI:** `--source` takes an archive or a directory, and **pointing at one part finds the
    rest**. That is correctness, not convenience: requiring every part would mean forgetting one
    does not fail but *succeeds*, quietly leaving those photos undated.
    `--takeout` remains as a **permanent hidden alias** - it shipped, scripts use it, it costs
    one line and resolves to the same `dest`, so there is no second code path and a removal
    window would break those scripts in exchange for nothing.
  - **REFUSED, with reasons, so they are not proposed again as obvious wins.**
    - **`.7z` is out of scope, and the deciding evidence is demand rather than dependencies**
      (re-examined 2026-08-01 on request, rather than resting on the first refusal).
      **Users do not choose their archive format - the exporter does**, and no major photo
      service emits `.7z`:

      | Service | Export format |
      |---|---|
      | Google Takeout | `.zip` / `.tgz` |
      | Facebook | `.zip` |
      | Flickr | `.zip` |
      | Amazon Photos | `.zip` |
      | Dropbox | `.zip` |
      | iCloud | no archive - individual files |

      So `.7z` is not a format users *receive*; it is one someone might *make* by re-compressing
      by hand. That distinction is what decides it. The dependency argument (`py7zr` is a new
      runtime dependency under §4) still applies and is now the *second* reason rather than the
      only one.
      **Research gap, recorded honestly:** two searches for user voices on whether the
      DataHoarder audience re-compresses photo archives to `.7z` returned vendor and reference
      pages, not people. That question is **unanswered**, and the instrument for it is the soak
      or a direct forum read - not more web search. If it ever turns out to be common, this
      refusal is the one to revisit, and the export table above is not the evidence that would
      settle it.
    - **`.rar` is out of scope for an INDEPENDENT reason that holds whatever the demand.**
      `rarfile` **shells out to an unsigned external `unrar` binary**, and a product whose whole
      proposition is custody should not invoke one on a user's files. This reason survives even
      if `.rar` turned out to be common, which is why it is recorded apart from the demand
      question rather than bundled with it. The honest answer for a user holding a `.rar` is
      "extract it yourself first": one step for them, no attack surface for us.
    - **Archive-inside-archive is refused outright**, naming the entry. Recursive extraction is
      **unbounded depth on untrusted input**, and the Takeout case never needs it.
    - **Delete-staged-files-as-you-go is refused, and deliberately NOT built as an option.**
      It would halve the peak disk requirement, which is exactly why it looks like an obvious
      win. truestill's whole posture is that **it never destroys the user's source**, and an
      option to delete the input is a switch that exists only to be regretted at 3am. If disk
      space is genuinely the blocker, the honest answer is *"extract fewer archives at a time"* -
      a step for the user, and no invariant lost.
  - **The UI shipped in `4606713`** and is not outstanding. Preview-then-confirm in the Rescue
    screen, progress and cancel through the existing job machinery, and the space figure
    labelled in the copy as the archives' own claim.
    **Refusals carry their CODE in the DOM** (`data-refusal="<code>"`), and the browser tests key
    on that rather than on the sentence - five refusals render similar-looking prose, so matching
    words lets a test pass because a *different* refusal fired. That is guard rule 8, and it is
    mutation-proved: dropping the codes fails the same three tests as ignoring the refusal
    entirely, so the provenance assertion is load-bearing rather than decoration.
    Eight Playwright tests drive the flows rather than asserting about them, per
    `ENGINEERING_STANDARD.md` §2, and the seven HTTP tests cover the two API routes that were
    briefly untested.
  - **Original design notes below, kept for the reasoning that produced the above.** Three of
    them were **overtaken by what was built** and say so inline, rather than being left as a
    second, contradictory answer in the same entry.
  - Near-launch priority: it is central to the Takeout-rescue pitch, because what a refugee
    actually has is a pile of archives, not an extracted folder. Generalized from the older
    "zip-direct Takeout" note, which was too narrow - the problem is archives, not Google's.
  - **One archive-source interface**, so the pipeline sees a source of media and does not care
    what it came out of. The same shape `Destination` already demonstrates, at the other end.
  - ⚠ **SUPERSEDED - `.7z` was to be first-class via a pip package.** It is not: see the refusal
    above. A pip package is still a **new runtime dependency** under §4, and the format is not on
    the path this feature exists for - Google offers `.zip` and `.tgz`.
  - ⚠ **SUPERSEDED - `.rar` was to be optional, lighting up when `unrar` is present.** Refused
    above instead. "Optional" understated the cost: `rarfile` **shells out to an unsigned
    external binary**, and a product selling custody should not invoke one on the user's files.
    The honest-about-absence instinct in the original note is right and survives - it is now
    applied to the *refusal* (name the format, say to extract it first) rather than to a
    degraded mode.
  - ⚠ **A multi-part set is ONE archive.** Google splits an export across `takeout-001.zip`,
    `-002.zip` and so on, and **a photo and its JSON sidecar can land in different parts**.
    Treating the parts independently silently breaks date rescue for exactly the files this
    feature exists to rescue. The set is opened as a unit or not at all.
  - ⚠ **SUPERSEDED - "streamed extraction, never a full unpack".** Extraction to disk was ruled
    2026-08-01 and is **forced, not chosen**: exiftool is a subprocess that needs a real file,
    and hashing, EXIF reading and copying all assume one, so a pure stream cannot feed the
    pipeline. The design question was never *whether* to extract but *where and with what
    protections*.
    The cost this bullet was worried about is real and is answered rather than dodged: staging
    goes on the **destination drive** (not the system temp dir, which on many machines is a
    tmpfs), the space precondition states the requirement **before** any work starts, and the
    only way to halve the peak - deleting staged files as you go - is **refused above**. The
    honest mitigation for a user short of space is to extract fewer archives at a time.
    What did survive from this bullet is *streaming within* extraction: entries are read in
    fixed chunks through a running byte counter, never whole into memory.
  - **Copy-only, as everywhere else: an archive is never modified**, never deleted, never
    rewritten in place. It is a read-only source.
  - **Encrypted archives are detected and surfaced**, never silently skipped. "I could not read
    this, here is why" is the never-silent rule applied to a container.


**Not doing, and why:** the audit found no inheritance-for-reuse and no deep hierarchies
anywhere (the only inheritance is `Destination` -> `Local`/`Rclone`, a genuine is-a), so there is
no composition refactor to schedule.

## Shipped (kept for provenance)

- ~~**(mm) `migrate.py` asks the wrong template how an event folder is spelled.**~~ **Delivered.**
  `plan_migration` no longer reads `scheme.template_for(Placement.EVERYDAY).event_naming` for
  every event; each event's naming now comes from its own placement, resolved with one
  `classify()` lookup per event (a representative row supplies the rule) in place of the fixed
  lookup - `O(events)` either way, same cost as building the `events` dict already was. Events
  are grouped by the naming their own placement resolved to before disambiguation, since
  `disambiguate_event_folders` takes one naming per call; collision detection is therefore
  scoped per group, not across the whole drive, which is exact today (every event still
  resolves to `Placement.EVENT_DAY`, so there is exactly one group) and a known, explicitly
  flagged boundary for whoever adds a second naming (Stage 2d's `TRIP_DAY`) to close with
  evidence, not guessed here.
  - **Proven behaviour-preserving today, and proven to actually matter.** Two fixtures, each run
    against the defect first: a scheme where `EVERYDAY` and `EVENT_DAY` genuinely disagree
    (`READABLE` vs `SLUG`) shows the old, fixed lookup reporting a same-date, same-name
    collision that real per-file rendering (which already routed through each row's own
    placement) would never actually produce - the fix reports none. The same two events on a
    scheme where every placement shares one naming (every shipped preset, today) still collide
    exactly as before, proving no regression the other direction.
  - **Unblocks Stage 2d.** `TRIP_DAY` is the first placement whose template genuinely needs a
    naming that differs from `EVERYDAY`'s; migration now asks the right question for whichever
    shape a file's own placement turns out to be.

- ~~**(w) Self-describing month preset.**~~ **Delivered by the year-first default correction**
  (2026-07-28). Self-describing months (`2014-08`, never a bare `08`) are baked into every
  shipped preset and into the default itself, so the standalone preset this item asked for would
  have been redundant. The argument it recorded - a folder must still say what it is once copied
  away from its parent - is now `IMPLEMENTATION_STANDARDS.md` §4.

- ~~**Browser end-to-end test layer.**~~ **Delivered** (`9be7529`, `0103454`). Playwright via
  `pytest-playwright` against an in-process app server, run in CI as its own chromium-on-ubuntu
  lane. Every UI bug the soak era found is now a **named regression test**, the golden path is
  one journey rather than six set-up tests, and the "a clean runtime install pulls no browser"
  claim is itself tested. Rules in `IMPLEMENTATION_STANDARDS.md` §6; scope rulings and the
  Playwright-over-Docker rationale in `DECISIONS.md` D2/D3.
- ~~**Performance audit + its convictions.**~~ **Delivered** (`1e458df`, `39d889a`, `8f77de1`).
  Measured every pipeline stage, then fixed only what evidence convicted: the per-file exiftool
  write (255ms → 9.3ms/file) and the custody strip's row-building count (224ms → 17.5ms at
  100k). The O(n²) perceptual scan was **deliberately not fixed** - it became item (v) with a
  runtime alarm. Baseline, rule and the do-not-touch list in `PERFORMANCE.md`.
- ~~**(q) In-place organize (same-device optimization).**~~ **Delivered.** `organize --in-place`
  moves files by rename when source and destination share a filesystem: no bytes rewritten, no
  zero-copy window visible to another process, hash unchanged because the inode is. (Crash
  atomicity is the filesystem's to give; FAT32/exFAT do not, and the undo journal covers them.) Plain `--move` takes the
  same fast path automatically; `--in-place` *requires* it and refuses a cross-device
  destination rather than silently copying. Typed `move` confirmation, mechanism split in the
  report, empty folders left and reported. `truestill undo-organize` ships with it (catalog
  v10, `inplace_runs` + `inplace_moves`) - reversible, not merely resumable. The `Destination.adopt`
  seam is on the interface, so `migrate-layout` can adopt it later without rework.
  **Two landmines found in the build and fixed with it:** `reclaim` would have deleted the only
  copy of an in-place file (source and drive copy are one inode, so its re-verify gate was a
  tautology), and an undo that left `files` rows behind would have made the library
  un-organizable by re-running dedup against itself. Both pinned by tests. See
  `IMPLEMENTATION_STANDARDS.md` §1. App surface for in-place + move shipped as **`(eee)`**;
  `reclaim` remains CLI-only (see App-surface deferrals).
  - **Still open:** cloud tier (server-side move within a remote, never via mounts) waits for
    the rclone work; a `--prune-empty-dirs` opt-in waits for soak evidence that the folders
    left behind are actually intolerable.
- ~~**`--skip-undated` on organize/ingest (j).**~~ Delivered: default OFF (undateable files still
  copy to `Undated/`); with the flag, they are skipped as `SKIPPED_UNDATED` and **counted + named**
  in the report - never silent. CLI on organize/ingest, plus an app organize toggle.
- ~~**Space-safe move: source reclamation (k).**~~ Delivered as one verify-gated mechanism, two
  surfaces: `organizer.execute(move=True)` / `organize --move` (copy → record → re-verify → delete,
  `MOVE_KEPT` on failure, no zero-copy window) and `reclaim.run_reclaim` / `truestill reclaim` (dry-run
  default, re-verify-at-delete on a connected drive, typed `delete` confirmation, `--min-copies N`
  with single-copy warning, `reclaim_journal` at schema v9). The copy-only-invariant exception is
  documented in `IMPLEMENTATION_STANDARDS.md §1`. **`organize --move` is in the app via `(eee)`**;
  **`reclaim` stays CLI-only** until an app surface is explicitly approved.

- ~~**(gg) Adaptive day-folder threshold for Everyday photos.**~~ **Built 2026-07-30.**
  Un-evented days over `layout.everyday_day_threshold` (default 40) get
  `{yyyy}-{mm}-{dd} - Everyday`; under stay in the monthly bucket. Both-direction migrate
  reconcile with per-day reasons; Settings warns on threshold change and routes to migrate;
  app migrate uses `typedConfirm("move")`. Research: `docs/adaptive-day-folder-research.md`.
  - **Soak finding (2026-07-30), recorded so it is not misread later.** `(gg)` is correct but
    **rare on real data.** One hit in the full soak catalog: **2013-09-30**, 62 photos,
    un-evented and non-trip-claimed (still in the monthly Everyday folder until migrate). The
    **2,057-photo 2014-08 Everyday folder that prompted `(gg)` was explained entirely by the
    Wayanad trip claim**, not by threshold behaviour - the trip work had already solved that
    folder. Do not treat `(gg)` as the fix for Aug 2014.
  - **Product implication (note, do not act on):** heavy days are usually trips or named
    events, so the threshold mostly guards the residual case - a genuinely busy day that
    belongs to nothing. Worth having; frequency is low. Any future tuning of the default
    should be judged against that residual rate, not against the Aug 2014 example.

- ~~**Metadata recovery fallback chain - decided on evidence.**~~ A 37-file, 22-format corpus
  test (`docs/metadata-chain-research.md`) showed exiftool already dates every datable file
  (including AVCHD `.mts` and WhatsApp `.mp4`), **no** fallback parser recovered a genuine capture
  date it missed, and naive parsers emit epoch sentinels (1904/1970) that would misfile. Outcome:
  **no parser added**; shipped the never-silent **skipped-file reporting fix** (`scan_source` +
  report); recorded the **sentinel-rejection rule** and ffprobe/schema-v9 reservation as binding
  conventions (`IMPLEMENTATION_STANDARDS.md §1`). The `CreationDate` UTC-vs-local fix shipped
  earlier (`01ebaa0`). Remaining follow-on tracked as item (l).
- ~~**Event merge/split.**~~ Delivered in the local web UI's Event review screen (merge/split
  are UI-only capabilities the CLI's name/skip flow lacks), exercised end-to-end through the HTTP
  API against real clustered fixtures. The CLI stays name-or-skip only, by design - a terminal is
  the wrong surface for interactively re-partitioning clusters.
- ~~**Configurable organization structure.**~~ Delivered: `LayoutTemplate` seam + token grammar,
  catalog v7 settings (`layout_template`) + validation, `truestill config` with 5 presets and live
  preview, and `truestill migrate-layout` (crash-safe, journaled, catalog v8) plus the app Settings
  screen. Split-era default: a template change affects new files only; migration relocates an
  existing library preview-first. See `docs/org-structure-research.md`.
- ~~**Drive identity + offline catalog + verify.**~~ Delivered: `.vaeon-drive.json` marker,
  catalog v6 (`drives` + `file_copies`), and `truestill drives`/`where`/`verify`/`status`. See the
  CHANGELOG and `docs/drive-identity-research.md`.

## Settled technical stances (recorded so they are not re-litigated)

- **The catalog stays SQLite.** Parquet and Feather were considered and rejected on three
  grounds, each sufficient alone: they are **immutable** (no row update without rewriting the
  whole file, and the catalog updates a row per organized file), they offer **no transactional
  safety** mid-migration (the journal that makes `migrate-layout` resumable and reversible
  depends on it), and they would add a **heavy `pyarrow` dependency** against §7's stdlib-first
  policy. Columnar formats are right for analytics over immutable batches; this is a mutable
  transactional record. JSON remains in exactly one place - the small, human-readable drive
  marker - where being readable by a person with a text editor is the point. This is also what
  `(z)` means by catalog-first; **no change is pending.**

- **`psutil` for filesystem detection: rejected.** It would delete `parse_proc_mounts` and the
  `ctypes`/`GetVolumeInformationW` branch in `filesystem.py` - roughly 60 lines including a
  hand-written parser - and `disk_partitions()` reports `fstype` on macOS via `getfsstat`, which
  is the one thing truestill currently cannot answer. Rejected anyway, on four counts: it is a
  **compiled C extension in the runtime graph** of a stdlib-first product; it is a large,
  general-purpose library carried for one function; `disk_partitions()` returns *mounted*
  partitions, so the **longest-prefix match still has to be written on top of it**; and what it
  buys is macOS, which today returns **unknown** and therefore refuses nothing - an honest
  answer, not a broken one.

  **The gap, named so the trade can be reopened on evidence:** on macOS `facts_for` returns
  `FilesystemFacts(filesystem=None, max_file_bytes=None)`. Nothing is refused there, so a macOS
  user copying a >4 GB video to a FAT32 card gets the improved EFBIG *message* after the failure
  instead of the preflight *before* it. If macOS detection ever becomes load-bearing - a report
  of that exact failure, or a feature that needs the filesystem name rather than its limit -
  this is the decision to revisit, and psutil is the candidate to weigh again.

- **`imagehash`: watch, do not move.** Last PyPI release **2025-02-01**, last repository commit
  **2025-04-17**. That is quiet, and quiet is **not** abandoned - the distinction is worth
  keeping, because it decides whether to act. The repository is **not archived**, its 26 open
  issues are open rather than closed en masse, there is no maintainer statement winding it down,
  and **no fork is positioned as a successor**. That is the opposite of the httpx picture, where
  the issue tracker and discussions were closed and Pydantic's `httpx2` was named by the
  maintainers as the path forward - which is why httpx was a move and this is a watch.

  **What would turn it into a move:** an archive notice, a maintainer statement, a security
  finding left unfixed, or a successor with real adoption. Absent one of those, the cost of
  switching a perceptual hash is the point: the catalog stores its exact bit output, so any
  replacement re-hashes every library or silently changes what counts as a near-duplicate.

- **Distributed task queues (Taskiq, Celery, Dramatiq) stay out of the desktop app.** They are
  *distributed* queues: their purpose is dispatching work across a network to separate worker
  processes, and each requires a broker - Redis, RabbitMQ, NATS or Kafka. Taskiq's own
  introduction says it exists because nothing could send async functions over distributed queues
  like RabbitMQ. That is a real problem, and it is not this one.

  truestill is a single-user desktop app: one process, no network, no worker fleet. Adopting one
  would mean asking a photographer to install and run Redis before organising their photos -
  precisely the install friction recorded against Immich's Docker requirement in
  `docs/org-structure-research.md`, and the thing this product is positioned against.

  **What is already there instead:** `JobManager`, roughly one module. Background threads
  in-process, SSE progress, cancel, and a per-drive lock. It covers every long operation -
  organize, verify, backup, migrate, trip apply, archive ingest, undo - with no service for the
  user to run and nothing to keep alive between sessions.

  **Where one WOULD be a reasonable choice, so this rejection is not over-read:** the
  self-hosted licensing and update server (`docs/DECISIONS.md` **D5**) is a genuinely networked
  service, and a queue is a fair question there. That is post-launch, unbuilt, and its own
  decision. Nothing here rules on it.

## Product / strategy (parked decisions)

> **Settled stance these sit under:** a user's **photo data never leaves their machine** and
> there is no telemetry. Pro is gated by a **signed local token** obtained at a one-time account
> activation - `docs/DECISIONS.md` **D5**, which supersedes D1's no-accounts stance on the maintainer's
> ruling. Any Pro-tier item below inherits that constraint, and none of the licensing
> infrastructure is built yet.

- **Web dedup teaser.** A Pro-tier positioning idea (a lightweight web-facing "find your
  duplicates" hook); not started. Reference stack proven in PixSort's browser mode, all
  **client-side - nothing is uploaded**: `exifr` (image EXIF), `mediainfo.js` (WASM, video
  dates), `hash-wasm` (BLAKE3 hashing in the browser). PixSort's `lib/metadata.ts` and
  `lib/hash.ts` (present under both `frontend/` and `apps-platform/`) are the reference
  implementations to study when we build this.
- **Desktop UI: Tauri vs local-web.** Parked architecture decision. The Rust-backed Tauri path
  informed the SHA-256/no-BLAKE3 hashing choice; the event-review interaction is the feature
  that will ultimately force the decision.
  - **(o) Lessons from the PixSort audit** (`PixSort/AUDIT_REPORT.md`): whatever wraps the UI,
    **one process serves the real UI**, bound to **loopback only**, and there is **never a second
    framework runtime beside the Python core**. PixSort's Electron+Next.js shell ran a whole JS
    runtime alongside the backend - the coupling and bundle weight it caused is exactly what
    truestill's single-process, server-rendered, no-build local-web UI avoids. A native shell (if ever
    built) wraps that one process; it does not add a second app runtime.

## Converged programs (do not pick in isolation)

These are not duplicates to delete - they are **one job split across lettered items**. Anyone
picking one up must map the combined order before building.

- **Date provenance → honesty → rescue → optional `_original`.** Items: **`(n)`**, **`(ii)`**,
  **`(bbb)` recovery**, and **`(kk)`'s `GPSDateStamp`** (lat/lon on `(kk)` also serves
  places/map, but the stamp is this program's cross-check). **One program, now partly built -
  check each step before starting it:**
  **PROGRAM COMPLETE 2026-07-31**, with one clause carried out as `(aaj)` - see `(bbb)` item 4.

  1. ✅ **Done.** Persist a durable date-provenance column: `files.date_source` (**v13**) and
     `date_tag` (**v14**), written by `record_uploaded`, worded once in `date_explain.py`.
  2. ✅ **Done.** Honesty view (`(n)`): the provenance **mix** ships in `service/stats.py`, and
     since step 5 each tier drills down to the files in it, each carrying the sha256 the rescue
     is keyed on.
  3. ✅ **Done.** Rescue (`(ii)`): stored durably, survives every whole-disk operation
     (`date_confirmations`, **v15**; O4 tested by name), and **reachable** since step 5 -
     `POST /api/dates/confirm`, app-only by recorded deferral.
  4. ✅ **Done.** `_original` offer (`(bbb)` recovery): same surface, same `human-confirmed`
     tier, never a parallel tool and never a silent substitution. Item 4's "optionally note the
     embedded conflict" clause was **decided against** - see `(aaj)`, now out of scope.

  Also not started: **`(kk)`'s `GPSDateStamp`** - verified 2026-07-31, the catalog has no
  latitude/longitude columns and no `GPSDateStamp`, so no part of `(kk)` has landed.

  Building an unbuilt slice alone still builds half a screen; **starting a built one rebuilds a
  shipped schema.** Steps 1 and 2 read as unstarted in this file until 2026-07-31.

- **Empty-folder leftovers.** Already shipped as one capability - see **Empty-folder cleanup**
  (provenance `(rr)` / `(zz)` / `(eee)` Commit 4).

- **Walk-and-classify on a drive.** `(hh)` (`adopt`) shares machinery with shipped `clean-empty`;
  map that reuse when `(hh)` is chosen - do not invent a second walker.

- **Preview cost / progressive disclosure.** `(tt)` + `(u)` Built; remaining is measured
  `(ss)` work and `(r)` Analyze (richer dry-run report, not a cheaper pass).

- **Loud failure vs portability for absolute paths.** `(ww)` Built; `(xx)` / `(yy)` remain the
  portability + reconnect half of the same family.

- **LayoutScheme axes.** `(gg)` Built (adaptive day folders); `(y)` / `(z)` are further axes on
  the same seam - do not rebuild routing.

## Ideas / deferred

> **Sequencing note - several of these share machinery, and picking them one at a time is the
> expensive order.** See **Converged programs** first. `(n)` and `(ii)` (and `(bbb)` recovery /
> `(kk)` GPSDateStamp) are one date-provenance program; `(hh)` (`adopt`) shares the
> **walk-and-classify** machinery with shipped `clean-empty`. When the first of a cluster is
> chosen, map a combined order before building - the schema step and the UI surface are each
> worth paying for once.

- **(aal) How often is the machine wrong about dates, and about what?** Recorded 2026-07-31,
  separated from `(aaj)` deliberately. **Idea - do not build schema for it now.**
  - **The question.** Across a library, where does human correction disagree with machine
    derivation - which tiers, which cameras, which filename patterns? truestill is the only tool
    that records both a machine tier and a human override, so it is uniquely able to answer it.
  - **Why it is not `(aaj)`.** A conflict *note* is one sentence on one file. A conflict *rate*
    is an aggregate over time, and it is the use that would genuinely justify keeping the
    superseded evidence - a column holding what the machine thought before it was overruled is
    debt when its only consumer is explanatory text, and an asset when it is the dataset.
  - **Nobody has asked for this.** It is recorded so the reasoning is not lost, and explicitly
    **not** as licence to add the column now. If it is ever built, the column is justified by
    *this*, and `(aaj)` stays closed on its own merits.

- **(m) Duplicate-cleanup staging UX.** ⚠ **Overlaps `(aag)`** - the visual side-by-side compare
  described below *is* `(aag)`'s subject. Scope them together or the same review surface gets
  designed twice; `(aag)` also records why it is deferrable (truestill already keeps and flags
  near-duplicates, so it is a review surface over correct behaviour, not a correctness gap).
  A **preview → confirm → trash (with restore)** flow for
  removing duplicates - the validated safe-delete pattern (same spirit as `reclaim`'s dry-run +
  typed confirm, but for dedup). Note the real gap PixSort never closed: truestill's near-duplicate
  review still needs a **visual side-by-side compare** (show the two look-alikes at actual pixels
  so a human decides which to keep) - PixSort had no such compare, and a trash-with-restore is
  only trustworthy once the human can actually *see* what they're removing.

  **Binding design constraints, from reviewing PixSort's live duplicate screen:**

  1. **Never auto-select keep/remove by filesystem timestamp.** Observed on real data: PixSort's
     "keep oldest" chose a `(Copy).jpg` to **keep** and the original to **remove**, because the
     mtimes lied - a copy operation had rewritten them. This is the **same lie truestill already
     refuses for dating** (`IMPLEMENTATION_STANDARDS.md` §1: "Dating uses an evidence chain, never
     filesystem mtime"). That invariant currently governs *placement* only; item (m) extends the
     identical distrust to **keep/remove selection**, where being wrong is irreversible rather
     than merely untidy. The corpus already contains this exact shape (`scan-a.jpg` + its
     `(Copy)`), so it is testable on day one.
  2. **Rank by evidence, in this order:** embedded capture date → resolution / bitrate →
     original filename pattern (a `(Copy)`/`(1)`/`-kopie` suffix is evidence *against* being the
     original) → catalog provenance (what truestill already recorded about where each copy came
     from). Every one of these is a property of the *file*, not of the filesystem around it.
  3. **Default to NO pre-selection when the evidence is ambiguous.** A pre-ticked checkbox is a
     recommendation the user will accept without reading; if truestill cannot prove which copy is
     the original, it must say so and select nothing. **A reviewed decision, not a trusted
     heuristic** - and never a heuristic wearing a decision's clothes.
  4. **Staged trash-with-restore, never a permanent delete**, with the two actions labelled by
     consequence - **"Recommended"** vs **"Irreversible"** - so the dangerous one is never the
     path of least resistance. Same spirit as `reclaim`'s typed `delete` confirmation.
  5. **Adopt the honest capability notice pattern**: state plainly what the screen can and cannot
     determine, in place, rather than implying more certainty than the evidence supports. This is
     the never-silent rule applied to a UI surface - the existing precedents are the HEIC
     perceptual-skip notice and the Tier A / Tier B date-quality lines.

  **Quality ranking - the layer that makes the review worth doing (research-grounded).**
  Within each near-duplicate group, rank the candidates by objective quality signals and use
  that ranking to power the side-by-side review's **default suggestion**.

  - **Never auto-action.** Constraint 3 above stands unchanged: a ranking produces a
    *suggestion*, and where the evidence is weak it must still suggest nothing. Ranking makes
    the human's decision cheaper; it does not make it for them.
  - **Why this is the value, from the literature.** Representative-photo-selection and
    burst-quality-assessment work (the PhotoCluster lineage through current blur/quality
    assessment research) consistently finds that in de-duplication and burst review the
    bottleneck is **review effort, not judgement**: people know which photo they want once
    they see the pair, and give up long before they finish looking. A good ranked default is
    therefore the feature -- it turns "review 400 pairs" into "confirm 400 defaults, correct
    a few". Presenting an unranked pile is what makes duplicate review get abandoned.
  - **Signals, cheapest first:** sharpness (Laplacian variance and similar classical focus
    measures), exposure sanity, and resolution -- plus the evidence truestill already has from
    constraint 2: original-vs-recompressed, and the copy-suffix filename pattern as *negative*
    evidence.
  - **Classical metrics first, zero ML dependencies.** They are cheap, explainable in one
    sentence to a user, and defensible in a UI that promises honesty about what it can
    determine. A learned model is only ever a justified later step, against measured
    inadequacy of the simple metrics -- and it would have to earn its dependency against the
    same policy every other dependency does (`IMPLEMENTATION_STANDARDS.md` §7).
  - **Positioning:** this is what makes (m) the **Pro-tier crown feature alongside (p)**. The
    safe-delete flow is the table stakes; knowing which copy to keep is the part worth paying
    for.
- **(p) "Share safely" - metadata-stripping export. PRO TIER (behind the capability seam).**
  A dedicated **export** action that writes cleaned copies for sharing, so a user can post a photo
  without leaking where they live or what device they use. Market demand is documented (a whole app
  category - CleanShots, ExifStrip, etc.; dating / kids / marketplace / forum use cases; email /
  Slack / Telegram-file preserve EXIF). **Design decisions, recorded now:**
  1. **Export-only, never a library operation.** The user selects files; truestill writes cleaned
     copies to a dedicated **share-export folder**. The organized library and the originals keep
     their full metadata, untouched. A strip control anywhere near the library would contradict
     truestill's metadata-preservation identity and invite accidents - it lives only in this export.
  2. **Complete removal, verified.** `exiftool -all=` on the copy (clears EXIF + XMP + IPTC +
     MakerNotes + embedded thumbnails - the thumbnail is the classic leak); for video, an exiftool
     pass **plus** an ffmpeg container rewrite (`-map_metadata -1`, no re-encode) for the
     `uuid`/`udta` boxes; handle **Live Photo** JPEG+MOV pairs together. Then **re-scan each output**
     and produce a verification report ("0 metadata fields remain") - the never-silent rule applied
     to removal. UI states honestly that cleaning affects the *copies*; the originals still exist
     with their metadata (that is the point).
  3. **Folder protection + lineage.** The share-export folder gets a `.truestill-shared.json` marker;
     the scanner **refuses a marked folder as an organize source** with a clear explanation (so
     dateless cleaned copies are never re-swept into `Undated/`). The catalog records lineage
     (cleaned copy ↔ source hash) so dedup never mistakes a stripped copy for a lost original.
  4. **Modes:** **strip-all** (default) and **GPS-only** - the two the market ships.

  Post-launch build; Pro-tier candidate. Research refs to carry in: the embedded-thumbnail trap,
  the XMP/IPTC/MakerNotes layers, MP4 container metadata boxes, and Live Photo pairing.

- **(x) XMP sidecar export for user-generated context.** Post-launch, demand-driven. Trip and
  event names are the one thing in a truestill library the *user* created rather than the files
  carrying it - so they are the one thing that is currently lost if someone stops using
  truestill. Writing them to standard XMP sidecars makes them portable to Lightroom, digiKam,
  Immich and anything else that reads XMP.
  - **Why it fits the identity rather than diluting it.** The promise is a library you can
    still read without the tool. That already holds for *files* (ordinary folders, ordinary
    names, full metadata). It does **not** yet hold for the context the user added on top.
    This closes that gap, and it is the no-lock-in argument taken to its own conclusion: the
    exit path should be complete, not partial.
  - **Sidecars, never in-place edits, by default.** Writing into originals contradicts §1;
    a sidecar sits beside the file and can be deleted with no trace. The scoped Takeout bake
    stays the only path that modifies content, and it stays scoped.
  - **Open questions for the research pass**, none of them blocking today: which XMP fields
    carry an "event" honestly across readers, whether sidecars belong beside the organized copy
    or the source, and what happens on re-export when a user has renamed an event.
  - **This is export, not a second source of truth.** The catalog stays authoritative;
    re-importing user context from sidecars is a separate question and is *not* part of this
    item.
  - **Virtual views, albums-as-first-class-objects and faces remain out of scope**, unchanged -
    see "Consciously out of scope" below and the composition stance recorded there. Portable
    *context* is not the same request as a gallery.
- **(hh) `truestill adopt` - bring stray media in an organized drive into the catalog.** Ruled
  by the maintainer. A drive can hold media truestill does not know about: files copied in by hand, a
  restore from elsewhere, or anything added after the last run. Today they are invisible to
  `verify`, to the custody count, and to `clean-empty`'s classification.
  - **Scan an organized drive for media files not in the catalog, report them named**, and on
    confirm run them **through the full normal organize pipeline** - EXIF, category rules, dating,
    dedup all decide placement.
  - ⚠ **Never the folder they were found in.** A file sitting in `Camera/2019/` is not evidence
    that it is a 2019 camera photo; someone may have dropped it anywhere. Placement is derived
    from the file's own metadata like every other file, or truestill would be laundering a
    guess as a decision - the same mistake the `(m)` selection rules forbid.
  - **Never automatic, never silent.** Offered after `verify` or `migrate-layout` when unknowns
    are found, and available standalone. Preview names every file; a typed confirm adopts.
  - **Precedent:** Lightroom's *Synchronize Folder*, which is the same operation for the same
    reason and is well understood by the audience.
  - **Shares the walk-and-classify machinery with `clean-empty`** - both answer "what is on this
    drive that the catalog does not account for", from opposite ends.

- **(y) Optional photo / video split - default TOGETHER, and pair-aware or not at all.**
  Post-layout-correction. An opt-in that separates standalone videos into their own top-level
  branch, leaving photos on the timeline.
  - **The default stays together**, because a chronological timeline is the thing the layout
    correction exists to produce and splitting media types cuts across it. This is a preference,
    not an improvement.
  - ⚠ **The constraint that makes or breaks it: a naive split destroys Live / Motion Photos.**
    An iPhone Live Photo is a **pair** - a `.HEIC`/`.JPG` still plus a `.MOV` sharing a content
    identifier - and a Samsung Motion Photo is the same idea. A split that routes by extension
    sends the still to `Photos/` and its motion half to `Videos/`, silently dismembering an asset
    the user thinks of as one thing. This failure is documented in Apple's own asset model and
    has been reported repeatedly against Immich; it is not hypothetical.
  - **Therefore: the pair moves together, and only a STANDALONE video goes to `Videos/`.** A
    `.MOV` that is the motion half of a Live Photo is not a video for this purpose.
  - **Depends on asset pairing**, which truestill does not have yet - matching a still to its
    motion half (content identifier where present, else name + timestamp + duration heuristics).
    That dependency is the real work; the split itself is a routing branch once pairing exists.
    **Do not build the split first and pair later** - shipping it in that order is shipping the
    dismemberment.
  - Fits the existing router as a third axis (`LayoutScheme` already routes on rule, then on
    evented), so the mechanism is understood; it is blocked on evidence, not on design.

- **(z) Optional source / device manifest - catalog-first, hash-keyed.**
  Post-layout-correction, opt-in, **local-only** (no network; the no-library-data rule of D5
  applies). Answers "what
  device and which app did this file come from?" across a library.
  - **Catalog-first, keyed by content hash.** The catalog already keys everything on `sha256`,
    which is what makes the record survive a rename, a move, a re-layout and an in-place
    organize. A path-keyed record would be wrong the first time `migrate-layout` ran.
  - ⚠ **The JSON is a GENERATED EXPORT, never a loose per-file sidecar.** Per-file sidecars
    orphan the moment a file is renamed or moved - the exact failure the hash key exists to
    avoid - and they would also scatter truestill-named artifacts across a user's drive, which
    §3.1 keeps to a single marker file. Export on demand; regenerate rather than maintain.
  - **The data is largely already known:** device from EXIF `Make`/`Model` (the `device` rule
    already reads them), platform/app from the derived category, and both are already recorded
    per file. This is mostly a query and a serializer, not new extraction.
  - **Opt-in** because it is a reporting feature, not part of custody; nothing about placement
    or verification should depend on it.
  - Open question for the research pass: whether it persists a `device` column (a schema
    version) or derives on demand from stored metadata - decide on measured query cost, not
    taste.

- **(s) Source-folder names as event evidence.** Generalize the Takeout **album → event**
  mapping to plain sources: a meaningful source folder name becomes a **pre-named event
  proposal** in the existing review flow.
  - **The problem, concretely:** an `Olympics/` input folder scatters by capture date today
    and its name -- the single best piece of evidence about what those photos *are* -- is
    discarded. Dates say when; the folder said what.
  - **Filtered against noise:** `DCIM`, `Camera`, `Pictures`, date-pattern directories
    (`2024-06-15`, `20240615`) and similar carry no meaning and must not become event names.
  - **Never auto-applied.** It produces *proposals*; the user confirms, renames or skips, in
    the review flow that already exists. A folder name is evidence, not a decision -- the
    same posture as every other derived label.
  - Reuses `events` + `event_review` machinery; the new part is the evidence source and its
    noise filter.
- **(t) Reflink / copy-on-write fast path.** On filesystems that support it (APFS, btrfs, XFS,
  ReFS) a clone (`FICLONE` / `clonefile`) makes a copy effectively instant and free.
  **Optimization, not correctness** -- `shutil.copy2` already uses `sendfile`/`fcopyfile` fast
  paths today, so this is a further step rather than a missing one, and newer Python is
  growing stdlib support worth waiting for.
  - ⚠ **Recorded caution, to design against before building:** a clone initially **shares
    blocks with the source**. That interacts directly with the independent-verified-copy story
    -- `copy_sha256` would still verify, because the bytes are identical, but "a second copy"
    that shares extents with the first is not the same thing as an independent one for the
    purposes truestill's custody model claims. Two files on one drive sharing blocks survive
    a `verify` and do **not** survive the block going bad. Decide explicitly what a cloned
    copy means for `file_copies`, for the custody count, and for the at-risk banner **before**
    any of it ships; the honest answer may be that clones are fine within a drive but must
    never count toward 3-2-1 redundancy.

## App-surface deferrals

Copy / Move / Reorganize-in-place and `undo-organize` are **in the app** - see **`(eee)`**.
What remains CLI-only shares one reason: each is a **space-safe or irreversible** operation
whose failure mode is permanent, and GUI demand is still judged from soak / launch feedback
rather than assumed.

- **The date rescue (`confirm_file_date`) is APP-ONLY**, recorded 2026-07-31 when step 5 made it
  reachable. A rescue is review-shaped - look at a photo, judge it, correct it, with the evidence
  in front of you - which is what the honesty view already is. A CLI equivalent would need file
  addressing by hash or path and would be used for bulk correction: a different, more dangerous
  feature that wants its own design. **Written down explicitly rather than left implicit**,
  because `test_surface_parity.py`'s second blind spot is a surface that omits a key entirely,
  so an undocumented single-surface contract is indistinguishable from drift.

- **`truestill reclaim`** stays **CLI-only** until an app surface is explicitly approved. When
  one does get a surface, the pre-approved shape is advisory same-device detection plus a typed
  confirmation identical to the CLI's.
- **`{camera_model}` layout token** -- demand **re-confirmed by the user** during the soak
  era. Stays **deferred / Pro-tier candidate** as originally recorded in
  `org-structure-research.md` (§C1 "explicitly NOT v1 tokens"): it needs device metadata
  plumbed into the template render context. Recorded here so the re-confirmation is not lost
  the next time the token list is reviewed.

## Consciously out of scope (recorded with reasons)

Not "not yet" -- decided **against**, so the question does not get re-litigated every time a
neighbouring product ships one. Each would be a reasonable feature in a different product.

- **A `warnings` field on `MigrationApplySummary`.** Found and **decided against 2026-07-31**,
  while closing the §9 gap where a missing exiftool degraded a migration silently. Recorded so
  it reads as a boundary someone chose, not a corner someone missed.
  - **What is still silent, precisely.** `migration_preview` surfaces the "folder names could
    not be checked against the files" warning through `warnings`, which the UI already renders,
    and the CLI prints it before the plan. `migration_apply` re-derives the same rules and has
    nowhere to put the reason, so a **direct apply without a preview** would degrade silently.
  - **No shipped flow performs that call.** The UI previews and shows the warning *before* the
    user confirms; `truestill migrate-layout` prints it in the same invocation that then
    applies. The silent path is reachable only by calling the service function directly, which
    is not a user flow.
  - **The cost is out of proportion to the case.** Closing it reaches the `TypedDict`, the
    payload construction, and the JS render - a public surface change, for a state nothing
    currently produces.
  - **What would make it worth doing:** *a caller that applies without previewing.* An API
    client, a scheduled or unattended migration, or a UI change that lets a user re-apply from
    a stored plan. Any of those turns this from unreachable into a real silent degradation, and
    the fix should land with that caller rather than in advance of it.

- **Migrate verifying against the live copy hash instead of its journal snapshot `(aah)`.**
  Found 2026-07-31 while closing condition 3 of the date-provenance program. **Decided against
  2026-07-31**, after the analysis rather than before.
  - **Live catches no failure the snapshot misses.** On-disk corruption, a partial file from a
    crash, a half-finished relocate - the snapshot catches every one, and so does live, because
    corruption never updates the catalog. Every row where live "wins" is a **false alarm
    avoided, not a detection gained**.
  - **The snapshot is an independent second record; live collapses to self-consistency.** Two
    records that must agree catches a class one record checked against itself cannot - a catalog
    value that drifted from the bytes, or a row that now describes a *different* file after a
    re-organize. That is the same defect as `(aai)`: **a hash read from the thing it validates
    is not a check.** It is also what "a resume knows what it expected" buys - a resume finishes
    a plan made earlier, and must not silently re-derive one.
  - **Its entire benefit was already bought.** The only realistic source of the false alarm is a
    bake landing mid-migration, and condition 3 removes it at zero cost to the snapshot: the
    bake refuses while a migration is journalled and unfinished, re-checked before every file.
    `(aah)` would trade a real property away for something already secured.
  - **The hybrid is rejected too.** Accepting the on-disk hash if it matches *either* the
    journalled or the current value tolerates the bake and still catches corruption - but it
    reintroduces the self-consistency hole for exactly the case the snapshot exists to cover.
    *Two records must agree* beats a rule with an escape clause.
  - ⚠ **Reopening condition, deliberately specific:** evidence that the cross-process race
    actually bites - a soak run showing a real stall caused by a legitimate bake. Even then the
    fix is **`(vv)`'s on-disk lock, not weakening the comparison**; the residual and its cost
    are recorded on `(vv)`.

- **Noting an embedded-metadata conflict against a human-confirmed date `(aaj)`.** The
  "optionally note the embedded conflict" clause of `(bbb)` item 4. **Decided against
  2026-07-31**, after the design was worked out rather than before.
  - **The disagreement is already surfaced where it matters most**: the three-state card shown
    the moment someone confirms a date says exactly what the file still claims inside
    (*"The file itself still says 2014 inside"*), computed from the row being overwritten. What
    `(aaj)` would add is seeing that **later**, on the honesty view.
  - **Seeing it later needs the prior claim, and `confirm_date` destroys it.** It overwrites
    `captured_at` / `date_source` and sets `date_tag = NULL`; nothing else holds the old values.
    So the feature requires **storing a value the system has already decided is wrong** -
    forever, on every row, with every migration and every `record_uploaded` obliged to reason
    about it - whose only consumer is a line of explanatory text. *A column that exists only to
    be disagreed with* is the reason not to add one.
  - **The alternative was ruled out too.** Re-reading the file is live metadata, which the
    stated constraint forbids, and it inherits `(xx)`: with the drive disconnected it would read
    "cannot check" for most rows most of the time.
  - **The clause said "optionally".** That word was written by someone who already knew this was
    nice-to-have. The human-wins half of item 4 is built, tested by name against all five
    whole-disk operations, and is the half that carries the promise.
  - ⚠ **Do not reopen this to enable a *statistics* feature** - see `(aal)`. That is a different
    question with different requirements, and it is the use that would justify the column.

- **Face recognition / people albums.**
- **Semantic AI search** ("photos of a beach at sunset").
- **Auto-generated Memories / highlight reels.**

- **Per-camera or per-person subfolders inside an event.** It fragments **one memory by
  source** - the same error as an unconditional photo/video split. Four phones at one trip is
  precisely the case where everything should stay together, and splitting by device turns a
  shared afternoon into four partial accounts of it. Device identity is real and worth keeping;
  it belongs in the **catalog**, queryable, not carved into the folder tree - see `(z)`.

- **Conditional `Photos/` + `Videos/` subfolders ("create them only when both are present").**
  A structure must never rewrite itself because one file arrived: adding a single video to a
  618-photo day would force **619 files to move**. That is the same instability that rules out
  date-range folder names, and it is worse here because it triggers on an ordinary import. The
  optional, always-on, pair-aware split remains available as `(y)`.

**Why all three, together:** they are one class -- **ML infrastructure** -- and adopting any of
them changes what truestill *is*. Each needs models shipped or downloaded, a vector store or
embedding index beside the catalog, GPU-or-slow inference, and a retraining/refresh story; that
is a permanent tax on every install, and it lands squarely against the lean, local, no-network,
minimal-dependency identity recorded in `ENGINEERING_STANDARD.md` §1 and
`IMPLEMENTATION_STANDARDS.md` §7. It is also **Immich's and Ente's territory**, where they are
strong and mature: competing there means being a worse version of a server product, while the
thing truestill does that they do not -- custody of files you can still read without it -- goes
unfinished.

The honest framing for a user who wants these: run truestill for organizing and custody, and a
gallery server for browsing and search. They compose. That answer is better than a shallow
imitation of both.
