# (aex) THE WINDOWS INSTALLER IS STAMPED WITH A BRANCH NAME ON EVERY DISPATCH RUN.

*Body of backlog entry `(aex)`, **CLOSED 2026-08-22**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(aex) `MyAppVersion=main`: THE DRY-RUN PATH IS HALF-PREPARED, AND WINDOWS IS THE HALF THAT
  IS NOT.** Found 2026-08-21 by reading the release lane while planning the Python 3.14 move.
  Not reproduced by a test - **it already happened, in a run that reported success.**

  ## MEASURED

  The lane derives its version from `github.ref_name`, which on a `workflow_dispatch` from `main`
  is the string `main`. The two platforms handle that differently:

  | platform | line | on dispatch |
  |---|---|---|
  | Linux | `release.yml:159` - `[ -n "$version" ] && [ "$version" != "main" ] \|\| version="0.0.0"` | ✅ `0.0.0` |
  | Windows | `release.yml:148` - `$version = '${{ github.ref_name }}' -replace '^v', ''` | ❌ `main` |

  ⚠ **Windows has a guard that CANNOT FIRE.** The next line is
  `if (-not $version) { $version = '0.0.0-dev' }` - and `main` is a non-empty string, so
  PowerShell's `-not` is false and the fallback is dead code. It looks like the Linux defence and
  is not one.

  ## WHY IT IS A DEFECT AND NOT UNTIDINESS

  Run **31689737405** (2026-08-13, `workflow_dispatch`, `main`) built an Inno Setup installer with
  `ISCC /DMyAppVersion=main` and **passed every gate**: self-check, comparison, install, verify,
  uninstall. The artifact carried a branch name where a version belongs, into Windows'
  Add/Remove Programs, and nothing said so.

  This is `ENGINEERING_STANDARD.md` §4's fifty-fourth member on the packaging surface: the lane
  is an instrument, and it was silent in a case it exists to catch. It is also the fifty-sixth - a rule applied to one platform reads as settled while the other disagrees quietly.

  ## SCOPE, AND WHY IT IS NOT URGENT

  **No user has ever received this artifact**: the `publish` job is gated on
  `startsWith(github.ref, 'refs/tags/v')` (`release.yml:283`) and has never run. The defect is
  release-blocking rather than live - it must be fixed **before** a first tag, not after.

  ## NOT DECIDED

  - **One fallback or two.** The honest fix may be to derive the version once, in one place, for
    both platforms - `packaging/` already owns `build_deb.py`'s version handling - rather than
    repairing the PowerShell line and leaving two derivations that can disagree again.
  - **What a dispatch build should be called.** `0.0.0` (Linux's answer) and `0.0.0-dev`
    (Windows' dead fallback) are already two answers to one question.
  - **Whether the guard should refuse rather than substitute.** A build whose version is a branch
    name is arguably one that should fail the step, not quietly pick a number.

  ## ⚠ CONFIRMED IN A SECOND RUN, AND THE FIX WENT WIDER THAN THE ENTRY

  Run **32552435733** (2026-08-22, dispatch from `main`, the Python 3.14 release dry run) produced
  **`TruestillSetup-main.exe`** and passed self-check, comparison, install, verify and uninstall.

  **The entry framed Linux as the half that was right. It was not** - and its wrongness is the
  quieter one. `truestill_0.0.0_amd64.deb` is **indistinguishable from a real 0.0.0 release**,
  where `TruestillSetup-main.exe` is obviously broken. **Something plausibly wrong outlives
  something obviously wrong**, so the Linux fallback was the more dangerous of the two.

  The shipped rule is therefore **validate, not fall back** - the industry pattern for a release
  workflow: on a tag, derive and check against **three-component semver**, refusing anything else
  rather than coercing it; on a dispatch, stamp `0.0.0-dev.<run id>`, which cannot be mistaken for
  a release and names the run that made it. One derivation, `shell: bash`, serving both platforms.

  ## ⚠ AND THE ARTEFACT LIST HELD A THIRD ONE

  Run **32554315868** proved the installer and the `.deb`, and its own upload list read
  `truestill-main-Linux.tar.gz`. The archive step had never been part of the search, because the
  search was for *"where is the version derived"* rather than *"what is named after the ref"*.
  Two of three artefacts is the fifty-sixth member's shape at the level of a single fix.

  On a tag it was wrong differently and more quietly: `truestill-v1.2.3-Linux.tar.gz` carries the
  `v` that the `.deb` and the installer strip, so a real release would ship three files disagreeing
  about their own version. Fixed in its own commit; the guard now covers **every step in the build
  job** rather than the two packagers.
