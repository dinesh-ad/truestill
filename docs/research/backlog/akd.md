# (akd) GOING PRIVATE TURNS CI FROM FREE INTO $128.98/MONTH, AND 55% OF IT IS A PLATFORM THAT SHIPS TO NOBODY.

*Body of backlog entry `(akd)`, under **Conditional, and counted**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(akd)** Measured 2026-09-04 (P212). **The condition is the repo going private**; nothing here
  costs anything while it is public.

  ## THE METHOD, BECAUSE THE OBVIOUS ONE RETURNS ZERO

  ⚠ **`repos/{owner}/{repo}/actions/runs/{id}/timing` reports `"total_ms":0` for every OS on a
  public repo** - nothing is billed, so nothing is metered. Zero there is the absence of a meter,
  not a cost. The figures below come from each job's own `started_at`/`completed_at`, **rounded up
  per job to the whole minute** as GitHub bills, over **493 runs and 1,954 jobs in 30 days**.

  ## THE BILL

  ```
  OS                 jobs  billed min  mult  Linux-equiv  $ at own rate
  ubuntu-latest       698       4,113    1x        4,113         24.68
  windows-latest      494       3,300    2x        6,600         33.00
  macos-latest        473       1,150   10x       11,500         71.30
  TOTAL              1665       8,563             22,213        128.98
  ```

  Free includes 2,000 Linux-equivalent minutes a month, Pro 3,000. **Pro covers 13% of this.**

  ```
  job                     os                  n   equiv        $   share
  check                   macos-latest      473  11,500    71.30     55%
  check                   windows-latest    473   6,372    31.86     25%
  e2e (browser lane)      ubuntu-latest     182   2,511    15.07     12%
  check                   ubuntu-latest     473   1,381     8.29      6%
  ```

  ⚠ **The browser lane is NOT the largest consumer, and the assumption that it is should not
  survive this entry.** It is 12%. Each run is long (13.8 min) but `(ajx)` moved it off every push,
  so it runs 182 times against `check`'s 473. **The largest consumer is macOS `check`.**

  🔑 **15% of the bill is pure round-up** - 3,335 Linux-equivalent minutes billed and not used, of
  which **2,480 are macOS**: a macOS `check` runs **1.91 min and bills 2.43**, and a short job at a
  10x multiplier is the exact shape per-job rounding punishes hardest.

  ## WHAT macOS HAS CAUGHT - COUNTED FROM THE RUN HISTORY (P213, 2026-09-04)

  ⚠ **This section originally listed three findings trawled from prose, and one of them was
  wrong.** P212 displayed `catalog_backup.py`'s fsync comment under a heading reading *"defects
  the macOS lane caught"*; the code says *"It also **broke Windows** ... **green on Linux and
  macOS**"*. macOS passed. Attribution now comes from the API, not from grep headings.

  Every run in the same 30-day window where **one** `check` lane failed and the other two passed:

  ```
  runs with all three check lanes reporting: 463
    macos-latest     RED ALONE in   7 runs
    windows-latest   RED ALONE in  22 runs
    ubuntu-latest    RED ALONE in   6 runs
  ```

  All seven, with the failing test read from each job's log: BSD `make` parsing a gate recipe
  (`33630088694`, `33629382162`), the `Thread.join` race (`32279378834`, `33010957536` - the test
  documents it), a kill-timing race in `test_archive_extract.py` (`32701030596`), BSD `df`
  refusing `--output` (`32662217322`), and a CI trace upload (`31173538629`).

  **7 of 7 are harness defects. None is a defect in code a user runs.** Three are not about macOS
  being a different OS at all - they are timing races found because it is a differently *scheduled*
  machine, which a self-hosted Linux runner also provides.

  🔑 **The lane creates most of what it catches.** `ci_bounded.sh` and `golden_corpus.py` run on
  BSD only because the macOS lane runs them; remove it and those defects cease to exist rather
  than going latent. Windows is the opposite - it ships.

  ⚠ **ONE CONTRIBUTION IS NOT A SOLO-RED, AND A CENSUS THAT ONLY LOOKED FOR RED MISSED IT.**
  `thumbnails.py:_TRANSPOSING_CONTAINER_ROTATIONS` on `(aeu)`: *"Found by the three-OS matrix:
  **macOS and Windows** install a current exiftool through brew and choco and **passed**, ubuntu
  did not."* macOS was a green **control** in a differential that found a **shipped** defect - a
  class the red-only census could not see. **The ruling survives because Windows was an equivalent
  control in the same sentence**, and the tree holds no second instance.

  ## WHAT THE LANE UNIQUELY COVERS: ONE LINE

  Nine platform-conditional sites exist in shipped source, and every branch is `win32` or `linux`.
  The only macOS-only line is `binaries.py`'s `{"darwin": "open"}`; `exif.py` puts macOS on
  **Windows's** branch, and `filesystem.py` falls it through to *"unknown"* deliberately. Case
  insensitivity - the property a macOS lane is assumed to cover - has **no test at all** and is
  shared with NTFS. **Ruling and sequencing: `DECISIONS.md` beside D9.**

  ## THE PRICED ALTERNATIVES

  ```
  shape                                                 $ / month  equiv min
  A. today, unchanged, on a private repo                   127.41     21,944
  B. drop macOS entirely (D9 refuses this)                  56.11     10,444
  C. macOS nightly + pre-release only                       61.99     11,392
  D. C + Windows narrowed to the same trigger               32.76      5,546
  E. D + Linux self-hosted (check and e2e)                   9.41      1,654
  F. everything self-hosted (a Mac and a Windows VM too)     0.00          0
  ```

  **Shape E is the recommendation: 1,654 Linux-equivalent minutes fits inside even the Free
  private allowance, so the realistic cash cost is $0** - a 93% reduction with **no lane deleted**.
  macOS and Windows still run nightly and before every tag.

  ⚠ **`push` narrowing buys nothing here**: `git ls-remote --heads origin` shows `main` alone, so
  every push already is a push to main. The only lever is **frequency per platform**, which is
  `(ajx)`'s two-stage reasoning applied to OS instead of to browser.

  ## THE SELF-HOSTED RUNNER, AND WHY THE FLIP IS WHAT ENABLES IT

  Self-hosted minutes are free and unmetered. GitHub's guidance is that self-hosted runners must
  not serve **public** repos, because a fork's pull request runs arbitrary code on the machine -
  **so this option only exists on the far side of the flip.** Sigstore is unaffected: the OIDC
  token is issued by GitHub's service, not by the runner.

  🔑 **And it repays a regression the flip otherwise imposes.** `ci.yml` already records that the
  runner is not 2-core *because the repo is public*; going private drops hosted Linux to 2 vCPU,
  and **every browser-lane timing in `(ajx)`, `(ajy)` and `PERFORMANCE.md` was taken on 4**. A
  self-hosted box reverses that rather than absorbing it, and may make `(ajx)`'s `-n auto` viable
  where it failed at 1.43-1.79x against a needed >=1.88x.

  ⚠ **The risk to state: one runner is a single point of failure nobody is paged about.** A dead
  box means `check` stops running and every push still looks green.

  ## WHAT ELSE BREAKS AT THE FLIP

  1. **The release page goes private.** `README.md` sends users to
     `https://github.com/dinesh-ad/truestill/releases` in **two** places. Binaries must be hosted
     on truestill.app **before** the flip - this is the one item that gates it.
  2. **4 vCPU -> 2 vCPU**, as above.
  3. **Storage is a second meter**, and it is **not** where anyone would guess. Live artifacts are
     **2.03 GB across 1,420**, but **94.5% of that is 13 `release-*` artifacts** already at
     `retention-days: 7`; the 1,277 CI `test-results-*` artifacts at 30 days are **3.9% combined**.
     ⚠ **A first draft of this analysis proposed cutting CI retention 30 -> 7 "for a four-fold
     saving"; measuring first showed it saves 3%.** The release artifacts' 7 days is deliberate -
     a dry run skips `publish`, so those artifacts are its only output.
  4. **Sigstore keeps working.** ⚠ But Rekor is a **public** transparency log, so signing a private
     repo's artifacts publishes the repo name and workflow path. Both are already public; it
     should be a decision rather than a surprise.

  ## WHAT IS NOT YET VERIFIED

  The minute figures are measured. **The storage billing treatment - whether Actions *cache*
  (1.72 GB here) counts against the billed allowance or only against the 10 GB per-repo cache
  limit - was NOT verified** and must be checked against the account's usage page before anyone
  relies on the $0.
