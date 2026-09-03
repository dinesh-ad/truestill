# (ajv) THE PUBLISHED v0.1.0 CARRIES NO REACT BUNDLE, SO ITS ORGANIZE RESULT REGION NEVER RENDERS.

*Body of backlog entry `(ajv)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ajv)** Filed 2026-09-03 (P194). Found by listing the artifact, not by reading the tree - the
  tree is green.

  ## THE EVIDENCE, PASTED

  The published Linux artifact, downloaded from the release and listed (86,089,464 bytes):

  ```
  $ tar tzf truestill-0.1.0-Linux.tar.gz | grep -E "truestill_app/static/" | sed 's#.*static/#static/#'
  static/  static/app.css  static/app.js  static/favicon.ico  static/fonts/  static/fonts/DejaVuSansMono-Bold.ttf
  static/fonts/DejaVuSansMono.ttf  static/fonts/LICENSE-DejaVu.txt  static/LICENSE-icons.txt  static/tokens.css
  $ tar tzf truestill-0.1.0-Linux.tar.gz | grep -c "static/dist/"
  0
  ```

  The template at the tag loads the bundle with no fallback, and `app.js` drops every write when
  the island is absent:

  ```
  $ git show v0.1.0:packages/truestill-app/src/truestill_app/templates/index.html | grep -n "static/dist"
  21:  <link rel="stylesheet" href="/static/dist/main.css">
  523:  <script type="module" src="/static/dist/main.js"></script>
  $ git show v0.1.0:packages/truestill-app/src/truestill_app/static/app.js | grep -n "const island = window.organizeResult" -A2
  666:    const island = window.organizeResult;
  667-    if (island) island.set(state);
  ```

  Why: `release.yml`'s steps run *Install uv → Set up Python → Sync workspace → Vendor exiftool →
  Build (PyInstaller)*; no `setup-node`, no `make frontend-install`, no `make frontend`.
  `.gitignore` ignores `packages/truestill-app/src/truestill_app/static/dist/`, and
  `--collect-data truestill_app` copies what is on disk. `ci.yml` does wire Node (its e2e job runs
  `make frontend-install`), so the gap is release-only and invisible to CI; `make e2e` depends on
  `make frontend`, so the browser lane is green.

  ## WHAT A USER SEES

  Both requests answer 404, the module never runs, the island never mounts. Every
  `organizeResult.set(...)` - the preview card, the running refusal, the completion card - is
  dropped. The Organize screen, the one a user lands on, shows the form and never a result. The
  other six screens are unaffected: their result regions are written by `app.js` directly.

  ## WHAT WAS NOT LOOKING

  - `selfcheck.py:app_findings` is `core_findings() + font_findings()`; nothing names the bundle.
  - `release-rehearsal-record.md` mentions `dist`, `frontend`, `react` and `vite` zero times.
  - `test_the_bundle_matches_its_sources.py` proves the served bundle matches the sources, in the
    browser lane, after `make frontend` has built it - it cannot see a release that never built one.

  ## THE FIX, IN THREE PLACES, AND THE ORDER

  1. `release.yml`: `actions/setup-node` from the frontend's `.nvmrc`, `make frontend-install`,
     `make frontend`, before the PyInstaller step - both platforms.
  2. `selfcheck.py`: a finding for `static/dist/main.js` and `static/dist/main.css`, so an
     artifact without them cannot pass its own gate, and `compare_selfcheck.py` compares them.
  3. The rehearsal's next run lists `static/dist/` in the artifact, in the record.

  ## THE CENSUS OF WHAT PACKAGES THE APP (P200) - one fix point, and two other holes of the same shape

  | path | takes its bytes from | after the fix |
  |---|---|---|
  | `release.yml` → tar/zip, `.deb` (`build_deb.py` copies `dist/truestill`), Inno (`Source: "dist\truestill\*"`) | PyInstaller's folder, which holds what `--collect-data` found on disk | the bundle is built in the job before PyInstaller, so all three inherit it |
  | `make build` → `uv build --all-packages` | hatch sweeps `src/truestill_app` in; `static/dist/` only if built | `build` depends on `frontend`; nothing publishes a wheel today (checked: no `uv build`, `twine` or `pypi` in the workflows) |
  | a clone, `make install`, `uv run truestill-app` | the working tree | the README says the bundle must be built; the self-check names the two files |

  ## WHAT A USER OF v0.1.0 SEES, EXACTLY (P200)

  The Organize screen is **usable and blind**. *Look inside* runs: the preview request completes,
  the side panel updates (`renderPanel` writes `#panel`), and the run confirm renders because
  `renderOrganizeRunConfirm` writes `#org-confirm`, outside the island. What never appears: the
  preview card (counts, folders, duplicates, the unreadable-folder warnings), the running refusal,
  **the completion card, and every error card** - `jobErrorCard` goes through the same dropped
  writer. A run proceeds with its progress block and ends in silence. `main.css` being absent
  changes nothing visible: `app.js` and the template use no Tailwind utility (`hidden` and `grid-*`
  are `app.css` classes). The other six screens are unaffected. **A note on the v0.1.0 release
  page is warranted**, and it is the maintainer's to write.

  ## 0.1.1, RECOMMENDED (P200)

  The defect is in the landing screen of the only release, it hides every error on that screen,
  and the fix is one workflow step plus a check. The honest response is a patch release from
  `main` once the rehearsal's next run lists the bundle - the repository has no release branches by
  rule, so 0.1.1 carries the 89 commits since the tag, which are engine fixes and records. Tagging
  is the maintainer's; the rehearsal is the gate.

  ## WHAT THE NEXT REHEARSAL RUN MUST LIST

  `release-rehearsal-record.md` mentions `dist`, `frontend`, `react` and `vite` zero times, so it
  could not have caught this. Its next run lists, from the artifact and not from the job log:
  `static/dist/main.js` and `static/dist/main.css` inside the archive (`tar tzf` / the zip
  listing), the self-check's two `bundle` findings `ok` with their byte counts, and
  `compare_selfcheck.py` matching them against the checkout's own build.

  **Before any React work.** `react-migration-plan.md` now says why: until the release lane builds
  the frontend, a React screen is a developer-only artefact, as the island has been since
  2026-08-15. **Before the next tag**, obviously.
