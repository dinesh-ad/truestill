"""A catalog reached through a symlink is where it belongs, and is not reported as legacy. `(aeb)`

**The defect, and neither commit that caused it was wrong.** `(adv)` made the override branch
return `.resolve()`d paths so the path a user is *told* is the file that is *opened*. `(adw)`
retired the legacy lookup, which removed the only legitimate reason `default_catalog_path()` and
`standard_catalog_path()` could ever differ. Together they left a comparison whose only remaining
input was **string shape** - and a symlink anywhere in the data directory produces two spellings
of one file.

Measured on the maintainer's machine, where `/home/dinesh/TruestillLibrary` is a symlink to
`/data/TruestillLibrary`::

    default  (resolved): /data/TruestillLibrary/.../catalog.sqlite
    standard (raw)     : /home/dinesh/TruestillLibrary/.../catalog.sqlite
    differ: True      same file: True

and `truestill catalog` printed *"This catalog is in the old location"* for a catalog sitting
exactly where it belongs, advising a `--move` that cannot help.

**Two paths that resolve to one file ARE one file**, which is the question being asked. Resolving
both sides would also work today and breaks again the first time a path cannot be resolved;
`samefile` asks the real question and is what the surviving comparison uses.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from truestill_core import app_paths
from truestill_core.app_paths import CATALOG_FILENAME, DATA_DIR_ENV, default_catalog_path
from truestill_core.selfcheck import location_findings


def _a_data_dir_behind_a_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """A real symlink, not a mock: the defect is a property of the filesystem, not of a stub.

    Skips rather than passes where symlinks are unavailable - a green run on a machine that
    cannot make one would be a test reporting on nothing.
    """
    real = tmp_path / "real" / "data"
    real.mkdir(parents=True)
    link = tmp_path / "link"
    try:
        link.symlink_to(tmp_path / "real")
    except OSError, NotImplementedError:  # pragma: no cover - Windows without privilege
        pytest.skip("this filesystem cannot create a symlink, so the defect cannot be reproduced")
    monkeypatch.setenv(DATA_DIR_ENV, str(link / "data"))
    catalog = real / CATALOG_FILENAME
    conn = sqlite3.connect(str(catalog))
    conn.execute("CREATE TABLE files (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    return catalog, link / "data" / CATALOG_FILENAME


def test_the_symlink_really_makes_two_spellings_of_one_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cry-wolf half. Without a genuine symlink every assertion below passes for free."""
    through_real, through_link = _a_data_dir_behind_a_symlink(tmp_path, monkeypatch)

    assert str(through_real) != str(through_link), (
        "the fixture produced one spelling, so no symlink is in play and this file proves nothing"
    )
    assert through_real.samefile(through_link), "two spellings, one file"
    assert default_catalog_path().exists(), "the resolver must still find it"


def test_the_self_check_does_not_call_it_an_older_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`selfcheck` compared the same two values as strings, so it carried the same false claim.

    Its report exists to tell someone which file is disposable; labelling the live catalog as an
    older location is the one thing it must not get wrong.
    """
    _a_data_dir_behind_a_symlink(tmp_path, monkeypatch)
    monkeypatch.setenv("TRUESTILL_CACHE_DIR", str(tmp_path / "cache"))

    catalog = next(f for f in location_findings() if f.name == "catalog")

    assert "older location" not in catalog.detail, (
        f"the catalog is exactly where it belongs and the report says {catalog.detail!r}. Two "
        "paths that resolve to one file are one file."
    )


def test_a_catalog_that_really_is_elsewhere_is_still_distinguishable(tmp_path: Path) -> None:
    """The other direction, so the fix is not "never say anything".

    `samefile` must separate *"the same file spelled twice"* from *"two different files"*. It
    raises on a missing path, so the helper has to answer False rather than propagate - which is
    the case this pins.
    """
    a = tmp_path / "a.sqlite"
    a.touch()
    assert not app_paths.is_same_file(a, tmp_path / "b.sqlite"), "a missing file is not the same"
    assert not app_paths.is_same_file(a, tmp_path), "a directory is not the same file"
    assert app_paths.is_same_file(a, a)


def test_two_spellings_of_one_file_are_the_same_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ THE CASE THE HELPER EXISTS FOR, and without it a string comparison passes every other
    test in this file. Found by mutation: replacing the body with `one == other` survived until
    this was written."""
    through_real, through_link = _a_data_dir_behind_a_symlink(tmp_path, monkeypatch)

    assert str(through_real) != str(through_link), "no symlink, so this proves nothing"
    assert app_paths.is_same_file(through_real, through_link), (
        "two spellings of one file were reported as different files, which is the string "
        "comparison this replaced"
    )


def test_two_paths_that_do_not_exist_are_not_the_same_file(tmp_path: Path) -> None:
    """⚠ WHY `samefile` AND NOT `resolve()` ON BOTH SIDES, made concrete.

    `Path.resolve()` does not raise on a missing path, so resolving both sides would call two
    identical non-existent paths *"the same file"* - a claim about files that are not there.
    `samefile` stats them and says no.

    It matters at the one call site: `move_catalog_to_standard` asks this **before**
    `source.exists()`, so a resolve-based answer would report `ALREADY_STANDARD` for a move whose
    source does not exist, instead of `NOTHING_TO_MOVE`. Also found by mutation.
    """
    missing = tmp_path / "gone.sqlite"

    assert not app_paths.is_same_file(missing, missing), (
        "two paths to a file that does not exist were called the same file"
    )


def test_the_two_resolvers_answer_one_question() -> None:
    """⚠ THE STANDING QUESTION, ANSWERED RATHER THAN LEFT.

    `standard_catalog_path` existed to say *"where the catalog belongs"* as distinct from
    `default_catalog_path`'s *"where it currently is"*. `(adw)` removed the only state in which
    those could differ - a legacy file being preferred - so the pair reduced to one expression and
    the comparison between them became vacuous. Two functions computing one value is how the next
    divergence gets in, so there is now one.
    """
    assert not hasattr(app_paths, "standard_catalog_path"), (
        "`standard_catalog_path` is back. If a state has been reintroduced where the catalog in "
        "use can differ from where it belongs, say which state in its docstring - otherwise this "
        "is two names for one value again. `(aeb)`."
    )
