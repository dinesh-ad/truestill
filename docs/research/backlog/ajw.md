# (ajw) EVERY PUBLISHED BUILD CALLS ITSELF "truestill unknown (not installed)" ON ITS OWN SETTINGS SCREEN.

*Body of backlog entry `(ajw)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
