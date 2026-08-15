# (aad) Desktop installers - LAUNCH-BLOCKING for the paid product.

*Body of backlog entry `(aad)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aad) Desktop installers - LAUNCH-BLOCKING for the paid product.** Ruled by the maintainer,
  2026-07-31. **Rewritten short 2026-08-13; the reasoning behind every line below is in the
  commits it came from (`git log --grep '(aad)'`).**
  - **The problem.** PyPI reaches developers only - `pip install` needs Python, a terminal, and
    knowing what pip is. **A perpetual licence (`DECISIONS.md` D6) cannot be sold to a user who
    cannot install the product.** PyPI stays as the developer channel; it stops being primary.
  - **Needed:** download-and-double-click installers, built by CI **on tag** and served from
    `truestill.app`. **Scope: Windows and Linux, unsigned** (`DECISIONS.md` D9). macOS builds in
    CI and is not published - Gatekeeper refuses unsigned outright.

  ### The two acceptance criteria (binding, on the FROZEN artifact)

  1. **It must resolve a real trash backend.** A bundle that drops `send2trash` makes
     `clean-empty` refuse every folder on Windows, where there is no `gio`
     (`IMPLEMENTATION_STANDARDS.md` §1).
  2. **It must carry and SERVE the typefaces and the Bitstream Vera notice** - 200 and the byte
     count of the source file. Lower severity than 1 (cosmetic drift, plus a licence defect for
     the notice), and silent, which is why it is checked.

  **Both are on the artifact because every source-tree guard passes while a bundle is broken.**
  Discharged by `truestill self-check` / `truestill-app --self-check` reporting from inside the
  bundle, plus `packaging/compare_selfcheck.py` deciding whether the reported bytes are the
  repository's. **The artifact reports what it HOLDS; the checkout decides whether that is
  right** - an artifact cannot know what it was supposed to contain.

  ### STATE, 2026-08-13

  | | Windows | Linux |
  |---|---|---|
  | **PyInstaller** | ✅ both criteria (run 31671053639) | ✅ both criteria, incl. served (31637337544) |
  | **Briefcase** | ✅ both criteria (31671053639) | 🔴 **cannot build** - see below |

  - **Serving is proven on Linux only** (assertions 3/4/5: `HTTP 200`, 343140 / 334268 / 4007
    bytes matching the repository). Windows proves collection, not serving.
  - 🔴 **Briefcase `linux system` cannot build truestill.** pip: `Package 'truestill-core'
    requires a different Python: 3.12.3 not in '>=3.13'`. The target **links against the distro's
    Python**; Ubuntu 24.04 ships 3.12.3. Blocked until truestill supports 3.12, the distro ships
    3.13, or a target that bundles its own interpreter is used. **PyInstaller has no equivalent
    constraint.**
  - **`--collect-data truestill_app` is required for any PyInstaller spec.** Without it the
    bundle carries **none** of the app's data - no fonts, no notice, no templates, no `app.js`,
    no CSS - and would not serve a page. Measured: 52 entries under `_internal/`, no
    `truestill_app` directory.
  - **Briefcase sets no `sys.frozen`**, so `is_bundled_install()` reads False and a Briefcase user
    with a broken install is shown the **source** exiftool message (`sudo apt install`).
    Confirmed on a real artifact. Needs a second signal if Briefcase wins - ranked at
    `binaries.is_bundled_install`, the running code's own location first.

  **Startup, seconds to reachable** (`session-url.txt` written; run 31672340257; cold = first run
  after build, warm = median of the rest). Cold is a **lower bound** - a runner cannot drop its
  page cache.

  | | cold | warm |
  |---|---|---|
  | PyInstaller / Linux | 0.407 | 0.405 |
  | PyInstaller / Windows | 0.509 | 0.511 |
  | Briefcase / Windows | 1.064 | 0.999 |
  | Briefcase / Linux | not built | - |

  The ~50 s figure often quoted is for **one-file**, which extracts to temp on every launch. This
  builds **one-folder**; it never applied and is retired as an input.

  ### DECIDED: PyInstaller, both platforms. Inno Setup for the Windows installer.

  **Ruled 2026-08-13, every column measured.**

  **THE ELIMINATOR: Briefcase cannot build Linux for this project at all.** `linux system` links
  against the distro's Python and fails on `requires-python` - pip's words,
  **`3.12.3 not in '>=3.13'`**. D9 publishes **two** platforms, and the tool that produces the good
  MSI produces **nothing** on one of them.

  > 🗑 **THE MEASUREMENT RIG WAS REMOVED 2026-08-15, AND IT WAS REFUTED RATHER THAN ABANDONED -
  > which is the distinction this note exists to preserve.** Gone: `packaging-throwaway.yml`,
  > `packaging/pyproject.toml` (the Briefcase project), `packaging/truestill_probe/`, the
  > `CHANGELOG` and `LICENSE` that existed only because Briefcase refuses to build without them,
  > `packaging/uv.lock`, and the `briefcase>=0.4.4` dev dependency. Copies are in
  > `.superseded/packaging-throwaway-2026-08-15/`.
  >
  > **The trigger was the rig's own fence** - *"DELETE OR REPURPOSE THIS FILE once the bundler is
  > chosen"* - and the bundler **is** chosen: `release.yml` builds Linux and Windows with
  > PyInstaller. Its last five dispatches all failed, on 2026-08-12/13.
  >
  > ⚠ **A future reader must not read this as "we gave up on Briefcase and could revisit it."**
  > The paragraph above is a *measurement*: briefcase produces **nothing** on a platform D9
  > publishes. Reopening it needs that answered - a Python floor lowered for packaging
  > convenience, a published platform dropped, or AppImage taken against its own maintainers'
  > advice - not a fresh preference. The rig is gone because the question it existed to ask is
  > **settled**, not because it went stale.
  >
  > **Side effect, checked rather than assumed:** briefcase was the **only** package in `uv.lock`
  > declaring `httpx`, so removing it drops httpx from the environment entirely. Nothing imports
  > plain `httpx` - the test client uses `httpx2` - so nothing depends on it. Recorded because the
  > root manifest's own comment claimed httpx "remains INSTALLED as a transitive dependency of
  > briefcase", and that sentence went false with this change. Choosing it means dropping a published platform,
  lowering the project's Python floor for a packaging convenience, or taking AppImage - a backend
  **its own maintainers discourage**. Nothing in the other columns outweighs a platform that
  cannot be built.

  **The columns behind it.** PyInstaller: both criteria discharged on both platforms, and **~2x
  faster to reachable on Windows** (0.509 s vs 0.999 s warm; 0.509 vs 1.064 cold). Maturity 6.x
  against 0.4.4 pre-1.0.

  **WHAT THIS LOSES, and it is a real cost rather than a courtesy.** Briefcase **produces a real
  installer with no second tool**; PyInstaller produces a folder, and **the installer around it is
  now the largest unbuilt thing in this entry**, with the unattended-install constraint below
  already attached to it. An **MSI carries AV and enterprise trust a bare `.exe` does not**, and
  Microsoft's tooling handles it natively - Briefcase's 2026 Q2 work improved exactly that column.
  Briefcase **collects app data wholesale**, so the `--collect-data` defect that cost a dispatch
  could not have happened under it, and its beside-the-executable layout satisfies
  `binaries.bundled_bin_dirs` with **zero packaging configuration** on Windows.

  ⚠ **The ruling does NOT rest on installer output - that column is still unmeasured.** Briefcase's
  MSI was built and never installed; no Inno artifact exists. Decided with it **known-absent**,
  which is why the reopening conditions are specific.

  **Reopens if:** Briefcase `linux system` becomes buildable (truestill supports 3.12, or the
  target distro ships 3.13); the Inno work proves disproportionate or cannot meet the
  unattended-install constraint; **signing is bought** (a D9 reversal, where Briefcase's built-in
  signing matters again); or a supported Briefcase AppImage/Flatpak path appears.

  ### What remains, in order

  0. **BUILD ORDER, ruled 2026-08-13: the Windows installer first** - it has a recovered starting
     point and a working bundle - **then the `.deb`**.
  1. ✅ **The release lane - BUILT 2026-08-13** (`.github/workflows/release.yml`). Tag-triggered
     (`v*`), plus `workflow_dispatch` with `dry_run` defaulting to **true** so exercising it never
     publishes. **The self-check is the gate**: a build that cannot report a real trash backend
     and its own typefaces does not publish. Signs `SHA256SUMS` with sigstore keyless
     (`id-token: write` on the publish job alone), verification instructions in the README.
     **It publishes ARCHIVES, not installers** - the installer is item 2 and the packaging step is
     where it slots in. **Never yet fired**: no tag exists.
  2. ✅ **The Windows installer - BUILT 2026-08-13** (`packaging/installer.iss`, built and verified
     in `release.yml`). Per-user, `/VERYSILENT`-capable, Start-menu entries for the app **and the
     self-check**, and an uninstall message that names the catalog it keeps.
     - **Four refusals, each with a reason, because each will be re-proposed as an oversight:**
       **not all-users** (an unsigned installer already meets SmartScreen; UAC would make it two
       alarming dialogs, and it is the class of the 2026 Briefcase advisory), **no elevation**,
       **not on PATH** (the buyer has no terminal; a global side effect buying them nothing), and
       **no file associations** (truestill organises a library, it is not a photo viewer).
     - **The detector, and it is the reason this is not just a build step.** The installer is
       installed with `/VERYSILENT` - which is how the unattended constraint gets *tested* rather
       than assumed - the **installed** copy runs `--self-check` and is compared against this
       repository, and **a marker written into the data directory must survive the uninstall**.
       That last assertion is the uninstall promise as a test, and it is exactly what the deleted
       rig's registry-only check could not see.
     - **The self-check is reachable without a terminal**: `_run_self_check` with no console now
       writes its report beside `session-url.txt` and opens it with the user's own viewer. This is
       what `exif.py`'s *"this installation looks incomplete"* has never had - something to run.
  3. ✅ **The `.deb` - BUILT 2026-08-13** (`packaging/build_deb.py`). FHS layout:
     `/usr/lib/truestill/` for the frozen app, `/usr/bin/truestill` as a relative symlink, a
     desktop entry, and a `copyright` file naming what the bundle carries. **83.5 MB packaged**,
     `Depends: perl`. Verified in the lane with the same detector as Windows - install, ask the
     **installed** copy what it contains, remove it, and assert the catalog survived.
     - **`Depends: perl`, not exiftool.** We vendor exiftool's *modules*; we do not vendor an
       *interpreter*. Declaring it is what makes the package honest rather than lucky.
     - ⚠ **Debian Policy §4.13 on vendoring, before someone tells us:** *"Debian packages should
       not make use of these convenience copies unless the included package is explicitly intended
       to be used in this way."* It **discourages rather than forbids**, it binds packages **in the
       Debian archive** - this one is served from our own site - and the exception fits almost
       verbatim, since exiftool's README documents running the script with its `lib/` beside it
       precisely so it need not be installed. The +21 MB tree is what that costs.
     - ~~**SUPERSEDED: exiftool was a DECLARED DEPENDENCY on Linux** (ruled 2026-08-13, reversed
       the same day).~~ The reasoning is kept rather than deleted because it was sound on its
       premises: *the platform's tooling exists to solve this, and bundling means carrying a Perl
       tree we cannot patch when a CVE lands*. **What reversed it was measurement** - the official
       tarball is self-contained by upstream's own documented contract, so bundling does not mean
       hand-assembling a runtime, and it removes a dependency on a distro packaging decision we do
       not control. The CVE point survives as a maintenance obligation: a pinned vendored tree is
       ours to bump.
  4. ✅ **exiftool acquisition - RULED AND BUILT 2026-08-13: vendor the official distribution on
     BOTH platforms** (`packaging/exiftool_source.py`), version-pinned with a recorded SHA2-256.
     - **Both platforms have the same shape**, and it is the one upstream's README states: *"if
       you move the exiftool script to a different directory, you must also either move the
       contents of the lib directory or install the Image::ExifTool package"*. Unix: `exiftool` +
       `lib/` (225 modules). Windows: `exiftool(-k).exe`, a **57 KB launcher** (CC0), plus
       `exiftool_files/` at **34 MB** carrying `perl.exe`, its DLLs and the same modules.
       **There is no self-contained single exe on either platform.**
     - **Why `--add-binary` was never going to work:** PyInstaller documents that it deliberately
       does not collect `/lib` or `/usr/lib`, assuming they exist everywhere. The modules were
       excluded **by design**. `--add-data` on the tree is the mechanism.
     - **Why vendored rather than a package manager:** chocolatey's `exiftool.exe` was a **shim**
       pointing outside the bundle - it resolved, it was a real `.exe`, and it did nothing.
       Leaning on packaging we do not control is how this broke.
     - **Size: +21 MB (Unix staged) against a 230 MB bundle.** The cost of a metadata reader that
       handles the camera makes and the video formats a photo library actually contains.
     - **Digest policy, and its limit:** the SHA2-256 is pinned in the repo and the build fails if
       the artifact changes. Each was **corroborated at pin time against a second origin** - bytes
       from SourceForge, digest from `exiftool.org/checksums.txt`. That is stronger than
       trust-on-first-use and is **not provenance**: a first fetch already compromised at both
       origins would be verified forever. exiftool publishes digests over HTTPS, **no signature**.
     - **Linux still needs a perl interpreter** (floor `require 5.004`; distributions ship
       5.36-5.40), and the self-check **proves** it rather than assuming - a missing interpreter
       reports differently from a broken bundle.
  4b. 🔴 **THE HISTORY, kept because it is what the criteria caught:** `--add-binary` copies **one file**, and on Linux `exiftool` is
     a Perl script whose `Image::ExifTool` modules live in the distro's `/usr/share/perl5`. The
     bundle carries none of them: proven by `find` over the artifact, and by
     `Can't locate Image/ExifTool.pm in @INC` once that directory is hidden. **It ran on the build
     machine only because exiftool was already installed there** - the one machine that does not
     need it bundled. Windows is unaffected (choco ships a real `.exe`).
     - **The self-check passed it, and that was the second defect.** It resolved a path and never
       invoked the binary. `exiftool_finding` now runs `-ver` and reports **degraded** when a
       resolved exiftool will not run; the version is in the evidence, so `ok` cannot be produced
       without the binary having answered.
     - Still open: how exiftool is obtained, versioned and licence-carried per platform.
  5. **The download page** - D9 requires Windows users be told what SmartScreen will show, in
     plain language, above the button, before they download. Still mandatory (see winget below).
  6. **CLI startup under freezing is UNMEASURED.** Freezing costs per process, so it lands hardest
     on a repeatedly-invoked command - a real concern with **no number**. The rig freezes the app
     entry point; there is no frozen `truestill` CLI to time. Measure before quoting anything.

  ### ~~SIZING, 2026-08-13 - nothing built~~ - SUPERSEDED, everything below it was built the same day

  ⚠ **Everything from here to the end of this SIZING block is the sizing done BEFORE any of it
  existed, and items 1-4 above are what actually shipped.** Kept rather than rewritten because it
  is the record of what was costed and in what order; read it as history, and read the ✅ items
  above for what is true. The three clauses most likely to mislead a reader who lands here are
  named where they sit: the `.deb` row's dependency, the Linux ruling, and the sentence below.

  **exiftool leads this, because it decides the Linux shape rather than following it.**
  **There is no standalone Linux exiftool.** exiftool.org ships a Windows `.exe` and a macOS
  `.pkg`; **Linux gets the Perl distribution** - the script plus its `lib/Image/ExifTool` tree,
  which runs against the system perl. ~~Our bundle copies **the script alone**, which is the
  defect.~~ **Fixed by item 4**: `packaging/exiftool_source.py` stages the script *with* its 225
  modules, on both platforms.

  #### Checked before ruling: does the documented resolution rule match the code?

  **It does. The suspicion was that a system install "goes straight to PATH and never checks the
  bundle" against a §5 rule stating bundle-first - and neither half holds.** `resolve_binary` is
  override → bundled directories → PATH, as every docstring says. `bundled_bin_dirs()` filters to
  directories that **exist**, so a system install gets `[]` and falls to PATH: nothing is skipped,
  **there is no bundle to check**. And `IMPLEMENTATION_STANDARDS.md` §5 is the Process contract -
  19 lines, no statement about binaries at all. **No documented rule disagreed with the code.**
  What *was* wrong is one file over: `binaries.py` stated the bundling rule with **no platform
  split**, which the Linux ruling below now contradicts. Fixed there.

  #### Windows: what makes an unattended installer around a one-folder build

  | | unattended switch | cost | needs that we lack |
  |---|---|---|---|
  | **Inno Setup** | `/VERYSILENT` | one `.iss`, one `choco install innosetup` | nothing else - the rig already proved both |
  | **NSIS** | `/S` | one `.nsi`, a setup step | a second script language for no gain |
  | **WiX → MSI** | `/qn` | v4/v5 project, toolchain step | most config for a format whose advantage was Briefcase's, not ours |
  | MSIX | n/a | - | **signing**, which D9 refuses. Ruled out. |

  **Inno**, on the entry's own terms: cheapest, already exercised here, and `/VERYSILENT` meets
  the unattended constraint. *Interactive is Inno's default, not its limit* - the switch is the
  answer, and the installer must be **built and tested through it**, not merely capable of it.

  **Recover the deleted `installer.iss` for its SHAPE, not its content** (`git show 1c77dd3^`).
  **It was deleted as a measurement rig and comes back as an artifact** - and it was already
  unattended-capable, so a constraint that looked blocking turns out met at zero cost. That is
  why deleting it needed the reasoning it got: a file removed with its findings recorded can be
  recovered deliberately; one removed in silence gets rewritten from scratch.

  > ✅ **DONE, and the record needs to be unambiguous because the sentence that carried it is
  > gone.** `packaging/installer.iss` **was** recovered and is **live in the release pipeline** -
  > `release.yml` copies it on the Windows job, and item 2 above records it built and verified on
  > 2026-08-13. ⚠ `packaging-throwaway.yml` described its second job as removed *"with
  > `packaging/installer.iss` and `packaging/inspect-installers.ps1`"*, which reads as though both
  > files went. **They did not: `inspect-installers.ps1` is gone, `installer.iss` was promoted.**
  > That workflow was deleted on 2026-08-15, taking the misleading half with it, so the
  > distinction is written here instead - the two files shared one sentence and have opposite
  > fates, and only one of them ships.
  Worth taking: `PrivilegesRequired=lowest` (per-user, no elevation), `{autopf}`,
  `recursesubdirs createallsubdirs` over the one-folder output, `Compression=lzma2`, and the
  Start-menu / uninstaller / Add-Remove trio.
  ⚠ **Do NOT reuse its `AppId` GUID.** An `AppId` is the product's identity for upgrade and
  uninstall; inheriting a deleted measurement probe's GUID would tie the shipped product's
  identity to a throwaway. Generate a new one and never change it again.

  #### Linux: three shapes, and they are three different products

  | shape | how a user with **no exiftool** fares | cost |
  |---|---|---|
  | **`.deb`** | ~~`Depends: libimage-exiftool-perl` - **apt solves it**, needs a repo/network at install time~~ **NOT WHAT SHIPPED**: the package declares `Depends: perl, hicolor-icon-theme` and vendors exiftool's modules (item 4) | packaging metadata; apt-family distros only |
  | **AppImage** | works **only if we carry exiftool's whole Perl tree** (script + `lib/`); still needs system perl | must fix the bundling defect first; largest artifact |
  | **tarball + script** | **told to install exiftool themselves** - the developer answer | cheapest; least like a product |

  **This is the deciding column, not a detail:** the same three formats give a user with no
  exiftool three different experiences - solved for them, carried for them, or handed to them.

  #### ~~RULED 2026-08-13: exiftool is DECLARED on Linux, BUNDLED on Windows~~ - SUPERSEDED the same day

  ⚠ **REVERSED BY ITEM 4 ABOVE, which is the ruling that shipped: vendor the official distribution
  on BOTH platforms.** The strikethrough at item 3 records the same reversal; this block is its
  full reasoning and is kept for that, not deleted. What reversed it was measurement - the official
  tarball is self-contained by upstream's own documented contract, so bundling does not mean
  hand-assembling a runtime. **Two clauses below are now false about the product**: Linux is
  bundled, not declared; and `--add-binary` never placed exiftool on either platform
  (`--add-data` on the tree is the mechanism - see item 4). The CVE point survives as the
  maintenance obligation it always was: a pinned vendored tree is ours to bump.

  - **Linux: `.deb` with `Depends: libimage-exiftool-perl`. Not bundled.** It is what the
    platform's tooling exists to do, and bundling means carrying a Perl tree **we cannot verify
    and cannot patch when a CVE lands in it**. The offline-install property is worth less than
    shipping someone else's runtime with no way to update it.
  - **Windows: bundled.** exiftool.org ships a real self-contained `.exe`, `--add-binary` already
    places it, and Windows has no package-manager assumption to lean on.
  - ⚠ **The asymmetry is deliberate and is not an inconsistency:** one product meeting **two
    platforms' conventions**, rather than one packaging stretched across both. A user gets a
    working exiftool either way; only who supplies it differs.
  - **Consequence, accepted with the ruling:** the bundle-first rule now **permits a declared
    dependency as a legitimate resolution**. `exiftool` is not a Debian package name, and beside a
    `.deb` install there is nothing to find - so resolving from PATH there is the design, not a
    failed bundle lookup. Written into `binaries.py`, which stated the rule with no platform split.
  - **AppImage: available, DECLINED.** It would have to carry exiftool's whole Perl tree, its
    viability turns on an unproven third-party plugin, and `.deb` answers the same question with
    the distro's own mechanism. Recorded with the perl-runtime finding so nobody re-derives it.

  ### Constraints on whatever installer is built

  - ⚠ **It MUST support unattended installation.** Verified as a winget acceptance requirement
    (*"Non-silent installers will not be accepted in the community repository"*; validators must
    be able to perform *"an unattended installation"*) - but the constraint **outlives winget**:
    an installer that can only be driven by a human cannot be validated, scripted, or deployed by
    anyone. **Inno's interactive default does not meet it; Inno supports it via `/VERYSILENT`**,
    which the deleted rig used. MSI has `/qn` natively.
  - **Uninstall must be verified against `catalog.sqlite` in the OS data directory**, not the
    registry - see the deleted rig's finding above.

  ### winget: REFUSED BY THE CHANNEL, not declined on cost

  **Recorded so nobody re-proposes it as the SmartScreen workaround: the thing winget would have
  solved is the thing that disqualifies us.** winget's automated validation installs the package
  on a VM, and that validation is **blocked by Microsoft Defender SmartScreen for unsigned or
  not-yet-reputed executables** - execution stops at the Mark-of-the-Web / AttachmentExecute step
  (`microsoft/winget-pkgs` #3482 and the package issues around it). An unsigned installer with no
  reputation is precisely what D9 ships.
  - **This also answers the question it was raised for, in the negative:** a `winget install` is
    **not** automatically SmartScreen-free - it goes through the same Mark-of-the-Web path. The
    download-page warning stays **mandatory**, not one of two paths.
  - *Not verified:* a policy line stating this as a written eligibility criterion. What is
    verified is the validation behaviour and the unattended-install requirement above.

  ### Zero-spend integrity: available, costed, unbuilt

  - **A tag-triggered release lane does not exist.** `ci.yml` runs on push, pull_request and
    schedule only. `workflow_dispatch` is what the maintainer can trigger by hand; a **tag trigger
    is what a release needs**, and neither it nor any release job is present. Everything below
    depends on it. Cost: `on: push: tags`, `permissions: contents: write`, a build job and
    `gh release create`. **No account, no fee.**
  - **Sigstore keyless signing is free and needs no certificate.** `permissions: id-token: write`
    (a tag/push workflow only - GitHub does not issue the OIDC token to fork PRs),
    `sigstore/cosign-installer`, `cosign sign-blob` over a checksums file, and a
    `cosign verify-blob --certificate-oidc-issuer https://token.actions.githubusercontent.com`
    line on the download page. Fulcio issues an ephemeral certificate against the workflow
    identity; Rekor logs it. **It does nothing to SmartScreen** - it is a provenance claim, and
    the strongest one available at zero spend.

  ### ✅ 2026-08-13: THE FIRST COMPLETE END-TO-END PATH, BOTH PLATFORMS (run 31689737405)

  **Windows**: exiftool verified against its pinned digest, frozen, **self-checked**, **matched
  against this repository**, installer compiled, **installed silently**, the *installed* copy
  self-checked and matched again, **uninstalled silently - and the catalog survived**.
  `installer verified: installs unattended, self-checks, uninstalls, keeps the catalog`.
  **Linux**: the same, in `.deb` shape - `package verified: installs, self-checks, removes, keeps
  the catalog`.

  **This is the line between a repository and something a person can install.** Every earlier
  green in this entry was a measurement; this is the artifact.

  ### THE DETECTOR WORKED, and that is the finding

  **The step written to test unattended behaviour hung on the unattended constraint, in the
  direction nothing had tested.** The Windows installer built, installed silently, self-checked
  and matched the repository - and then the *uninstall* stopped on a modal dialog. **A silent
  install that cannot be silently uninstalled is not unattended**, and only building the detector
  surfaced it. Cause established from Inno's own reference rather than guessed:
  `/SUPPRESSMSGBOXES` does not reach a plain `MsgBox` - `SuppressibleMsgBox` *"returns the Default
  value without displaying anything to the user, whereas a standard MsgBox would still appear"*.
  The flag was not ignored; it applies to a different function. Fixed by moving to
  `SuppressibleMsgBox` with `IDOK` as the default, which is the right semantics for this message:
  **a person uninstalling by hand reads it, an unattended uninstall proceeds without it.**

  ⚠ **Both detector steps are now bounded at 10 minutes.** The hang cost a cancelled run *and its
  logs* - see `ENGINEERING_STANDARD.md` §4, forty-third member.

  ### What has never been observed, and must survive into the download page

  **CI proves what CI proves.** No double-click, no SmartScreen dialog, and no machine without
  perl has ever been observed. The lane proves the installer installs, self-checks and uninstalls
  on a runner; it does not prove the first thirty seconds a stranger spends with this product.

  ### Awaiting attorney clearance - facts, not a question

  **The Windows exiftool package carries a GPLv3 component**, and this is recorded for the same
  list as the trademark residual rather than ruled here.
  - **What is established:** ExifTool itself is *"free software; you can redistribute it and/or
    modify it under the same terms as Perl itself"* (Artistic / GPL v1+). The launcher is **CC0**.
    `exiftool_files/LICENSE` is **GPL v3** and sits beside `perl.exe` and the MinGW runtime DLLs;
    the **GCC Runtime Library Exception v3.1 is present** (`gcc-toolchain/gcc/COPYING.RUNTIME`),
    whose stated purpose is *"to allow compilation of non-GPL (including proprietary) programs to
    use… the header files and runtime libraries covered by this Exception."*
  - **How truestill uses it:** exiftool is **executed as a separate process** (`binaries.run`),
    never linked - arm's-length aggregation.
  - **Why it is not ruled here:** separately-invoked with the exception present is very likely
    fine, and *very likely* is not what a licence question wants when the answer arrives after
    shipping. The attorney gets the facts above rather than the question.

  ### Settled, do not re-open

  - **The ~90 MB scipy/PyWavelets weight stays** (2026-08-01). Measured: 218,212,013 B with,
    132,045,324 B excluded - **82.2 MiB, 39.5%**. Declined on product grounds; the exclusion
    mechanism is a permanent maintenance surface. Three premises of that ruling were wrong and
    are corrected in `e314de1` - `--exclude-module` **does** work, the cited PyInstaller issues
    establish nothing, and no `imagehash` function silently returns a wrong value. `dhash` is
    bit-identical with and without the exclusion (`8bcb9521242eca28`).
  - **No VirusTotal comparison to choose the bundler** (2026-07-31). SmartScreen is
    reputation-based per file and per certificate, so the question is orthogonal to the choice.
    A scan belongs as a release smoke test, not a selection input.
  - **The installer-comparison rig is deleted** (`1c77dd3`). Built complete, wired, **never run**.
    ⚠ **The one finding kept from it: its `uninstalled_cleanly` check read only the three Uninstall
    registry hives, so it would report a clean uninstall for an installer that deleted the user's
    catalog. Any real installer must verify uninstall against `catalog.sqlite` in the OS data
    directory** - unrecoverable user data, unlike the disposable cache (`(aae)`). **No document
    states an uninstall stance.**
  - **The console and legacy-probe questions cannot decide the bundler** - windowed-ness is
    settled by mechanism (both are GUI-subsystem; a double-click has no console to inherit).
    Readings taken under a non-detached CI launch are contaminated and are not answers.

  ### Open anomaly - do not close with a story

  ⚠ **The 2026-08-01 Windows run `30692798020` reported `assertion 4 PASS - HTTP 200`.** Templates
  were provably uncollected before `--collect-data`, so a server answering 200 with a page had no
  `index.html` to render. **That PASS is harder to account for than when it was first noticed, not
  easier.** Either that run measured something other than what it claimed, or collection behaviour
  changed. Each is a finding; neither is established.

  ### Two lessons this entry paid for

  - **Six dispatches were spent on a bespoke detached launcher that replaced a working
    `Start-Process`, and one `git show bcd1849` found it.** The mechanism was in the history.
    **Before the next bespoke anything, check whether the thing being replaced ever worked.**
  - **A byte count that changes with how you read it is not a byte count.** The check itself
    measured the notice after newline translation, so a CRLF checkout disagreed with the artifact
    on a file that was byte-for-byte correct. Own checks are not exempt from being checked.
