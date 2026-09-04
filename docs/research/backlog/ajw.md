# (ajw) EVERY PUBLISHED BUILD CALLS ITSELF "truestill unknown (not installed)" ON ITS OWN SETTINGS SCREEN.

*Body of entry `(ajw)`, in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

✅ **CLOSED 2026-09-04 (P208).** The filing below is left exactly as written, in the present tense
it was written in; **the record of what was built, and the two things this entry got wrong, are at
the bottom of this file.**

- **(ajw)** Filed 2026-09-03 (P202), during the stranger's verification of the published 0.1.1.

  ## THE EVIDENCE, PASTED

  The published `.deb`, installed with `dpkg -i`, the app started with `--no-browser`, the page
  fetched with its own session URL:

  ```
  $ dpkg -s truestill | grep Version
  Version: 0.1.1
  $ curl -sS "$session_url" | grep -oE 'id="app-version"[^>]*>[^<]*'
  id="app-version">truestill unknown (not installed)
  $ dpkg -L truestill | grep -ciE "truestill_(app|core|cli)-.*dist-info"
  0
  ```

  `truestill_app/__init__.py`: `__version__ = distribution_version("truestill-app")`;
  `truestill_core/version.py:distribution_version` returns `UNKNOWN_VERSION` on
  `PackageNotFoundError`, *"Never raises: a missing version must not be able to take down a
  `--version` flag or a settings screen"* - so the screen renders the fallback instead of failing.
  `release.yml` builds with `--collect-data truestill_app`, which copies the package's data files
  and no distribution metadata; PyInstaller's `--copy-metadata <dist>` is what carries a
  `.dist-info` into the frozen tree. The self-check's `install` finding says `packaged` and
  carries no version, so the release lane never compared the artifact's idea of its version to
  the tag it was built from. **0.1.0 says the same words**: same flags, same fallback.

  ## WHAT A USER SEES

  Settings shows *truestill unknown (not installed)* on an installed, working copy. Harmless to the
  library and wrong on its face - the one line that should tell a person which build they have,
  when they report a problem, tells them it is not installed.

  ## THE FIX, AND ITS GUARD

  1. `release.yml`: `--copy-metadata truestill-app --copy-metadata truestill-core --copy-metadata
     truestill-cli` beside `--collect-data`, both platforms.
  2. `selfcheck.py`: a `version` finding - `DEGRADED` when it is the unknown value, `OK` with the
     string as evidence otherwise - so the artifact reports what it thinks it is.
  3. `compare_selfcheck.py` (and the tag-time job): the reported version equals the tag's, so a
     build stamped from the wrong checkout cannot pass.
  4. The rehearsal's next run lists the version finding from the artifact.

---

## ✅ SHIPPED 2026-09-04 (P208) - what was actually built, and what the entry above got wrong

**The premise held.** Reproduced on today's tree before anything was changed: a local PyInstaller
freeze with `release.yml`'s exact flags, run with `--no-browser`, served
`id="app-version">truestill unknown (not installed)`. So the defect was not stale.

### One correction to the fix this entry proposed: TWO distributions, not three

`--copy-metadata truestill-cli` was proposed and is **wrong**. Measured from the build's own
`Analysis-00.toc` and `PYZ-00.toc`: **zero** `truestill_cli` entries. The frozen entry point is
`truestill_app/__main__.py` and nothing it imports reaches the CLI, so the shipped `.deb` and
installer contain no CLI at all. Copying its metadata would put a claim about absent code into the
artifact - the same shape as the guard-that-cannot-fire this file's neighbour already documents.

### And one thing the entry did not say: the frozen tree was never metadata-free

The control tree carried `numpy-2.5.1.dist-info` and `click-8.4.2.dist-info`, put there by
PyInstaller's own bundled hooks. The entry's *"no `truestill_*.dist-info` at all"* is exact and
correct; *"the workflow collects data and never metadata"* is not. What is missing is metadata for
**our** distributions, because no hook exists for them and no flag asked.

### What `--copy-metadata` costs, researched before it was added

PyInstaller documents it as *"Copy metadata for the specified package"* and states that it *"does
not collect these metadata files by default"*; the only caveat in its own docs is the 4.3.1 change
preventing `dist-info` being renamed to `egg-info`. **Size is not a reason to hesitate**: measured
+4,946 bytes against a 220.3 MiB tree, **+0.0021%**.

⚠ **The one real cost is not in the docs**: a `.dist-info` contains `direct_url.json`, which
records the **absolute build path** and `"editable": true` for a workspace install. Every copied
distribution therefore ships one build-machine path. Two is the whole need, which is the second
reason `--recursive-copy-metadata` was refused - the first being that nothing here calls
`importlib.metadata.requires`, which is all that option exists to serve.

### The guard, which is the half that matters

Three refusals, deliberately independent, because this shipped **twice** through a lane that had
already been rehearsed:

1. `selfcheck.py:version_finding` - `DEGRADED` on the unknown value, so `worst` is a failure and
   the artifact's own `--self-check` exits non-zero. **`INFO` here would have reproduced the
   defect exactly**: green gate, wrong screen.
2. `compare_selfcheck.py:_version_problems` against the checkout's `pyproject.toml`. **Runs on
   every path, including a dispatch with no tag** - which is what makes the rehearsal able to
   catch this class at all.
3. The same function against the **tag**, when there is one. `release.yml`'s version step emits
   the flag, so one derivation serves all three call sites - the rule that file already learned
   the hard way.

**The version step moved earlier** in `release.yml`, because it produced the tag the comparison
needs and ran after it. It is otherwise byte-identical; the fail-fast placement (before the build,
so a malformed tag costs seconds) was available and **not taken**, since it changes when the lane
refuses and that was not asked for.

### Proved by mutation, both directions, on real frozen artifacts

| direction | artifact's own `--self-check` | `compare_selfcheck.py` |
|---|---|---|
| `--copy-metadata` **reverted** | exit **1**, both version findings `degraded` | exit **1**, four errors |
| as shipped, no tag | exit **0**, `0.1.1` | exit 0 |
| as shipped, tag `0.1.1` | - | exit 0 |
| as shipped, tag **`0.1.2`** | - | exit **1**, *"THE ARTIFACT DISAGREES WITH THE TAG"* |

### The screen, read the way `(ajw)` was found - from a package, not a fixture

`dpkg -i` needs root, which this machine does not grant unattended, so the `.deb` was **extracted
with `dpkg-deb -x`** - the same bytes `dpkg` copies, since it copies rather than rewrites - and the
binary at `usr/lib/truestill/truestill` was started with `--no-browser`:

```
$ dpkg-deb -c truestill_0.1.1_amd64.deb | grep -ciE "truestill_(app|core|cli)-.*dist-info"
19                                          # this entry's own command read 0
$ curl -sS "$session_url" | grep -oE 'id="app-version"[^>]*>[^<]*'
id="app-version">truestill 0.1.1
```

⚠ **The honest delta**: `dpkg -i` itself, and the Windows installer, were not run here. Both are
exercised by `release.yml`'s own install-verify-uninstall steps, which now carry the comparison.

## Does this warrant 0.1.2? No - it rides the next release

**The call, 2026-09-04.** It is cosmetic: nothing is at risk, no library is touched, and the fix
helps only people who install *after* it. An existing 0.1.1 user will not re-download 83 MB for a
version string, so shipping alone buys almost nothing for the people already affected.

Against that, a release is not free here. The publish job's second gate is **a human approval**
(`environment: release`), the only manual control in the lane, and spending one on a version
string is the wrong use of it; Windows SmartScreen reputation is per file and resets on every new
installer.

**What actually closes the exposure is the guard, not the tag**: the defect cannot reach a third
release now, whenever that release is. So this waits for the next one carrying something else.

⚠ **The condition that would flip it**: if the next release is far enough out that bug reports
start arriving quoting *"unknown (not installed)"* - the string is the first line of Settings and
the one a reporter pastes - then the reporting cost stops being cosmetic and this ships alone.

