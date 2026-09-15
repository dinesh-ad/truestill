# -*- mode: python ; coding: utf-8 -*-
"""Two executables, one COLLECT. `(akv)`

⚠ **THE CLI WENT MISSING FROM THE SHIPPED PRODUCT AND EVERY GATE STAYED GREEN.** The lane froze
`truestill_app/__main__.py` alone and named the result `truestill`, so the binary a customer got
was the web UI wearing the CLI's name. Six capabilities have no other home - `reclaim`, `rescan`,
`repoint-sources`, `carried`, `self-check`, `catalog --move` - and they were not CLI-only for a
customer, they were **unreachable**. Measured on the 2026-09-15 dry-run `.deb`: `truestill
analyze` exited 2 with *"unrecognized arguments"*, and the usage line it printed named
`truestill-app`, a program the package does not install.

**THE NAMES ARE NOT CHOSEN HERE. They are read off `[project.scripts]`**, which both packages have
declared all along - `truestill = truestill_cli.cli:main` and `truestill-app =
truestill_app.__main__:main`. The freeze is what diverged. Matching it makes `CLAUDE.md`'s *"The
command is `truestill`; the local web UI is `truestill-app`"* true of the artifact rather than
only of a clone.

⚠ **TWO EXECUTABLES, NOT ONE THAT SWITCHES ON `argv[0]` OR A FLAG.** PyInstaller issue #6244 is
what that costs: a `--noconsole` build has no stdout on Windows, and people are reduced to piping
to `| more` to see any output at all. A CLI needs `console=True` and a double-clicked app needs
`console=False`; that is one attribute of the EXE and it cannot hold both values. Separate
projects are the documented shape for a dual-interface application - each runs in its intended
environment with no hacks.

**ONE COLLECT IS WHAT KEEPS IT AFFORDABLE.** Both `Analysis` objects feed a single `COLLECT`,
which de-duplicates by destination name, so numpy, Pillow, the stdlib, the fonts and the vendored
exiftool are written once rather than twice. What does NOT de-duplicate is each `EXE`'s own `PYZ`
- the pure-Python archive is embedded in the executable - so the cost of the second binary is that
archive plus a bootloader, not a second tree. The measured figures are in `(akv)`'s entry.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

_ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is injected by PyInstaller
_APP = _ROOT / "packages/truestill-app/src/truestill_app/__main__.py"
_CLI = _ROOT / "packages/truestill-cli/src/truestill_cli/cli.py"

# `--collect-data truestill_app` is REQUIRED, not decorative: without it the bundle carries none
# of the app's data - no fonts, no notice, no templates, no app.js, no CSS - because bundlers
# follow imports and a data file is imported by nothing.
#
# ⚠ `copy_metadata` IS SEPARATE FROM `collect_data_files` AND NEITHER IMPLIES THE OTHER. Without
# it `importlib.metadata` raises `PackageNotFoundError` inside the bundle and the settings screen
# reads "truestill unknown (not installed)" on a working installed copy, which v0.1.0 and v0.1.1
# both shipped. `(ajw)`.
#
# ⚠ **`truestill-cli` JOINS THE LIST HERE, and it is no longer a claim about absent code.** The
# workflow comment that removed it said "truestill-cli has ZERO entries in this build" and was
# right at the time - that was the defect, stated as a reason.
_DATAS = (
    collect_data_files("truestill_app")
    + copy_metadata("truestill-app")
    + copy_metadata("truestill-core")
    + copy_metadata("truestill-cli")
    + [(str(_ROOT / "exiftool-src/bin"), "bin")]
)

_app = Analysis([str(_APP)], pathex=[], datas=_DATAS, hiddenimports=[], noarchive=False)
_cli = Analysis([str(_CLI)], pathex=[], datas=_DATAS, hiddenimports=[], noarchive=False)

_app_pyz = PYZ(_app.pure)  # noqa: F821
_cli_pyz = PYZ(_cli.pure)  # noqa: F821

# `console=False` - a double-clicked app must not flash a terminal. The icon is Windows-only:
# PyInstaller discards it on Linux outright, and `build_deb.py` stages the mark into the hicolor
# theme instead.
app_exe = EXE(  # noqa: F821
    _app_pyz,
    _app.scripts,
    [],
    exclude_binaries=True,
    name="truestill-app",
    console=False,
    icon=str(_ROOT / "brand/favicon.ico"),
)

# ⚠ `console=True`, AND THIS IS THE WHOLE REASON THERE ARE TWO. See #6244 above.
cli_exe = EXE(  # noqa: F821
    _cli_pyz,
    _cli.scripts,
    [],
    exclude_binaries=True,
    name="truestill",
    console=True,
    icon=str(_ROOT / "brand/favicon.ico"),
)

coll = COLLECT(  # noqa: F821
    app_exe,
    _app.binaries,
    _app.datas,
    cli_exe,
    _cli.binaries,
    _cli.datas,
    strip=False,
    upx=False,
    name="truestill",
)
