# The release lane, rehearsed end to end - record

**Ran 2026-08-30 (P152).** Run [`33310530340`](https://github.com/dinesh-ad/truestill/actions/runs/33310530340),
tag `v0.0.0-rehearsal`, deleted the same day. Machine: GitHub-hosted `ubuntu-latest` and
`windows-latest`, Python 3.14.

**Why it exists.** `.github/workflows/release.yml`'s `publish` job had **never executed a single
step** - six prior runs were all `workflow_dispatch`, where the job is `skipped` with `steps=0` by
design. Five steps and one identity had never run in this repository's history, and the largest of
them was an OIDC token GitHub had never been asked to issue. **A tag is not rehearsable after the
fact**, so it was rehearsed before.

## What ran

| job | result |
|---|---|
| `build (ubuntu-latest)` | success, 22 steps |
| `build (windows-latest)` | success, 22 steps |
| **`sign and publish`** | **success, 7 steps** - previously `steps=0` on every run |

The five that had never run, each green: `actions/download-artifact` with
`merge-multiple: true` · the `out/` non-file guard and `sha256sum` · `cosign-installer` ·
`cosign sign-blob` · `gh release create`.

🔑 **The platform filenames do not collide under `merge-multiple`.** That was a *reading of the
producers* before this run and is now an observation.

## What it produced

Six assets, which is what a real tag produces:

```
TruestillSetup-0.0.0-rehearsal.exe          59,476,538
truestill-0.0.0-rehearsal-Windows.zip       86,031,418
truestill_0.0.0-rehearsal_amd64.deb         84,949,436
truestill-0.0.0-rehearsal-Linux.tar.gz      86,087,070
SHA256SUMS                                         412
SHA256SUMS.sigstore.json                        10,442
```

## Verified BY HAND, not from the lane's own tick

Downloaded, then the README's *Verifying a download* commands run exactly as a user would:

```
sha256sum --check --ignore-missing SHA256SUMS
  TruestillSetup-0.0.0-rehearsal.exe: OK      truestill-0.0.0-rehearsal-Linux.tar.gz: OK
  truestill-0.0.0-rehearsal-Windows.zip: OK   truestill_0.0.0-rehearsal_amd64.deb: OK

cosign verify-blob --bundle SHA256SUMS.sigstore.json \
  --certificate-identity-regexp '^https://github\.com/dinesh-ad/truestill/\.github/workflows/release\.yml@' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS
  Verified OK
```

🔑 **`Verified OK` is the result worth keeping.** Keyless signing depends on GitHub issuing an
`id-token` to this repository and on Fulcio and Rekor accepting that identity; none of it had ever
been exercised. **It works, and the README's command is correct as written** - so the next person
cutting a tag does not need to find that out on the day.

The artifacts were opened rather than trusted by name: the `.deb` reports
`Package: truestill / Version: 0.0.0-rehearsal / Architecture: amd64`, and both archives carry the
vendored exiftool under `_internal/bin/` (781 files in the Windows zip).

## ⚠ The one honest delta

The rehearsal ran `gh release create` **with `--draft`**, added on the tagged commit alone. The
repository is public and the tag path had no confirmation gate, so without it the run would have
created a visible, latest-marked release.

**So that step is rehearsed as a mechanism and unrehearsed as a publication.** Same API call, same
auth, same asset upload, same `out/*` expansion; the difference is one visibility flag. What
remains untested is `--latest` handling and anything a public release triggers downstream.

## What this changed

⚠ **The rehearsal depended on the very hole it exposed**: a tag push reaches `publish` because
`github.event.inputs.dry_run` is `null` on a tag event and `null != 'true'` passes, so the tag
path's only condition is the tag. `(aad)`'s guard - `environment: release` with a required
reviewer - closes it, and a rehearsal today would need an approval click.

## Teardown

Draft release deleted, remote tag deleted, local tag and branch deleted. `origin` returned to
**one head (`main`) and one tag (`preserved/abw-finding-3`)**, verified by `git ls-remote`. The
scratch commit was pushed as a **tag only**, never as a branch, so `CLAUDE.md`'s one-head rule
held throughout.

> ⚠ **What `origin` holds has changed since, and this paragraph is left as it was measured.**
> On 2026-08-31 (P164) `preserved/abw-finding-3` was deleted - `(aix)` shipped the feature it
> preserved and refused its shape - so `git ls-remote` now answers **one head (`main`) and one tag
> (`v0.1.0`)**. The teardown above is still an accurate record of 2026-08-30, and the one-head
> finding it exists to report is unaffected. `CLAUDE.md`'s *Live refs* table is the current answer.

## Added 2026-09-03 (P200, `(ajv)`) - what this rehearsal did not look at, and what the next one must list

**A record, not rewritten.** The run above never mentions the React bundle, and the artifact it
rehearsed carried none: `static/dist/` is gitignored, the publish job built it nowhere, and
`--collect-data` copied what was on disk. The self-check covered fonts and core. From this date the
self-check reports `bundle main.js` and `bundle main.css` by size and digest, the job builds them
before PyInstaller, and `compare_selfcheck.py` refuses a checkout that has not built them. **The
next run must list, from the artifact itself**: both files in the archive listing, both findings
`ok` with byte counts, and the comparison matched.

**Listed, 2026-09-03, from dry run `33733154061` on `9ab3f93` (`workflow_dispatch`, `dry_run:
true`, publish skipped)**: `static/dist/main.js` 190,777 bytes and `static/dist/main.css` 16,299
bytes in `truestill-0.0.0-dev.33733154061-Linux.tar.gz`, in the `.deb`, and in the Windows zip;
both artifacts' self-checks and both installed copies' self-checks `complete: true` with the two
bundle findings `ok`; `compare_selfcheck.py` matched on both platforms. The same run's first
attempt failed on Windows at *Install, verify, uninstall* with `the installer exited ` - an empty
code - and `9ab3f93` is the fix. **A real tag has not run since; the next one owes nothing new here.**

## Added 2026-09-04 (P208, `(ajw)`) - the rehearsal passed a build that could not name itself, twice

**A record, not rewritten.** The run above proved the publish *mechanism*: five never-executed
steps, six assets, checksums, `cosign verify-blob` by hand. It asserted nothing about what the
artifact **says about itself**, and the version was the second thing to get through on that gap -
`(ajv)`'s bundle was the first. v0.1.0 and v0.1.1 both published a settings screen reading
*"truestill unknown (not installed)"* on an installed, working copy.

**What the rehearsal must assert now, and does from this date**: `compare_selfcheck.py` matches the
artifact's reported version against the checkout's `pyproject.toml`. ⚠ **That half deliberately
needs no tag** - a rehearsal has none, and a guard that only fired on a tag would have missed this
a third time in exactly the run meant to catch it. The tag comparison is the second half and runs
only on a tag. **The next run must list, from the artifact itself**: `version truestill-app` and
`version truestill-core` `ok` with the version string, and the comparison matched on both
platforms.

🔑 **The pattern under both defects, which is worth more than either fix.** A rehearsal that
exercises MECHANISMS cannot catch a CONTENT defect. Every step ran, every gate was green, and the
artifact was missing something a user would see. So the rule is: **for each thing the product
tells a person about itself, the artifact is READ and compared against the source of truth** -
never inferred from a build step having run.

⚠ **And the gap that remains, stated rather than left implied.** `release.yml` **never serves the
artifact**: it runs `--self-check` and nothing starts the app or fetches a page - `grep -c
"no-browser\|curl \|session-url" .github/workflows/release.yml` answers **0**. Both `(ajv)` and
`(ajw)` were found by a person serving the installed copy and reading the HTML, which is precisely
what no step does. A step that starts the installed copy with `--no-browser`, fetches the page it
serves, and asserts against the checkout would have caught both **before publication rather than
after**. Not built here and not filed as a letter; recorded where the next rehearsal is planned,
which is where it will be read.

