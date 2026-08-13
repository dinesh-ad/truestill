"""Where truestill's own files land, pinned per platform - and pinned from ONE place.

**Why this exists.** Planning the Windows installer's uninstall message meant resolving the real
paths, and they were wrong: `platformdirs` defaults the author segment to the **app name**, so
Windows produced ``%LOCALAPPDATA%\\Truestill\\Truestill\\catalog.sqlite`` - the name twice - while
`app_paths`' own docstring claimed ``%APPDATA%``. Both are user-facing: the self-check prints these
paths and the uninstaller names them.

**The fix was one argument, and its whole risk is that it might move a platform it should not.**
So the shape of all three is asserted here rather than reasoned about. These run on every lane,
because they drive the platform backends directly instead of asking the host.

**The second half is the one that would rot silently.** A path fixed in `app_paths` while some
other module derives its own is a fix to one of two, and the doubling survives where nobody looks.
That is not hypothetical: `test_catalog_command_cli.py` exists because the CLI once built the
catalog path from `platformdirs` directly and lost the ``TRUESTILL_DATA_DIR`` override with it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import platformdirs
import pytest
from platformdirs.macos import MacOS
from platformdirs.unix import Unix
from platformdirs.windows import Windows
from truestill_core.app_paths import APP_NAME, DATA_DIR_ENV, standard_catalog_path

_SRC = Path(__file__).resolve().parents[3] / "packages"

#: The one module allowed to ask `platformdirs` where anything goes.
_THE_ONE_HOME = "truestill_core/app_paths.py"


def test_app_paths_asks_for_no_author_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    """**What THIS code asks for** - not what `platformdirs` does when handed the right argument.

    Written this way after the first version drove the Windows backend directly with
    ``appauthor=False`` hardcoded: it passed with `app_paths` reverted, because it was pinning the
    library rather than our call (`ENGINEERING_STANDARD.md` §4, fourth member - aimed at the right
    module, the wrong subject).
    """
    seen: dict[str, object] = {}

    def _record(appname: str, **kwargs: object) -> str:
        seen.update(kwargs, appname=appname)
        return "/tmp/recorded"

    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(platformdirs, "user_data_dir", _record)
    # `standard_catalog_path`, not `default_catalog_path`: the latter short-circuits to a legacy
    # `reports/catalog.sqlite` when one exists beside a console-launched process, and would never
    # reach `platformdirs` at all. The standard path is also the one an installed app resolves and
    # the one the uninstaller names.
    standard_catalog_path()

    assert seen["appauthor"] is False, (
        "app_paths let platformdirs default the author segment to the app name, which is what "
        "produced %LOCALAPPDATA%\\Truestill\\Truestill on Windows"
    )


def test_that_argument_is_what_removes_the_repeated_name_on_windows() -> None:
    """And what the argument buys, which is the half the recorder cannot show.

    Asserted as *the segment appears once* - the promise - rather than against a literal string a
    `platformdirs` upgrade could reshape.
    """
    doubled = Windows(appname=APP_NAME)._append_parts("C:/base")
    fixed = Windows(appname=APP_NAME, appauthor=False)._append_parts("C:/base")
    cache = Windows(appname=APP_NAME, appauthor=False)._append_parts(
        "C:/base", opinion_value="Cache"
    )

    assert doubled.count(APP_NAME) == 2, "the defect this fix exists for is no longer reproducible"
    assert fixed.count(APP_NAME) == 1, f"the application name appears twice: {fixed}"
    assert cache.count(APP_NAME) == 1, f"the application name appears twice: {cache}"
    assert cache.endswith("Cache")


def test_windows_data_is_local_and_not_roaming() -> None:
    """A photo catalog has no business syncing to a domain profile.

    `roaming=False` is the default and is what makes the data directory ``%LOCALAPPDATA%``; the
    docstring claimed ``%APPDATA%`` until 2026-08-13. Pinned because the difference is invisible
    on a developer's machine and expensive on someone's employer's.
    """
    assert Windows(appname=APP_NAME, appauthor=False).roaming is False


def test_linux_and_macos_are_untouched_by_the_windows_fix() -> None:
    """THE CRY-WOLF HALF, and the reason it is a test rather than a sentence in a commit.

    ``appauthor`` is a Windows concept; the Unix and macOS backends ignore it. Both forms are
    asserted equal so the claim *"this moves nothing on Linux or macOS"* is checked rather than
    trusted - it was the whole risk of the change.
    """
    for backend in (Unix, MacOS):
        with_author = backend(appname=APP_NAME).user_data_dir
        without = backend(appname=APP_NAME, appauthor=False).user_data_dir
        assert with_author == without, f"{backend.__name__} data moved: {with_author} -> {without}"

        with_author_cache = backend(appname=APP_NAME).user_cache_dir
        without_cache = backend(appname=APP_NAME, appauthor=False).user_cache_dir
        assert with_author_cache == without_cache, f"{backend.__name__} cache moved"


def test_only_app_paths_asks_platformdirs_where_anything_goes() -> None:
    """A path fixed in one place while another module derives its own is half a fix.

    Enforced by parsing imports rather than grepping text, so a comment mentioning `platformdirs`
    does not fail and ``import platformdirs as pd`` does not slip through. `app_paths` is the only
    module permitted to ask; everything else goes through `default_catalog_path`,
    `default_cache_path`, `session_url_path` or `cache_path_for`, which honour the environment
    overrides that make the test suite hermetic.
    """
    offenders: list[str] = []
    for path in sorted(_SRC.glob("*/src/**/*.py")):
        relative = path.as_posix()
        if relative.endswith(_THE_ONE_HOME):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(name.split(".")[0] == "platformdirs" for name in imported):
                offenders.append(path.relative_to(_SRC).as_posix())

    assert not offenders, (
        "these modules ask `platformdirs` directly instead of going through `app_paths`:\n  "
        + "\n  ".join(sorted(set(offenders)))
        + "\n\nA data location fixed in `app_paths` and derived independently here is a fix to "
        "one of two. Route through `default_catalog_path` / `default_cache_path` / "
        "`session_url_path` / `cache_path_for`, which also honour TRUESTILL_DATA_DIR."
    )
