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

  **Before any React work.** `react-migration-plan.md` now says why: until the release lane builds
  the frontend, a React screen is a developer-only artefact, as the island has been since
  2026-08-15. **Before the next tag**, obviously.
