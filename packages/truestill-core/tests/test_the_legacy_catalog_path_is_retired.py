"""A `reports/catalog.sqlite` beside the working directory is no longer adopted. `(adw)`.

**The defect.** `LEGACY_CATALOG_PATH` is relative, so `default_catalog_path` asked *"is there a
`reports/` here"* where *here* was whatever directory the process was launched from. The same
install therefore found a different library depending on where it was run, with no environment
variable involved: `cd` changed which catalog you were in.

**Why retired rather than anchored**, and the reasoning has a shelf life:

* the legacy path was introduced **2026-07-31** (`5db91b9`, the `(aae)` commit);
* **no release has ever been published** - `release.yml` fires on `tags: ["v*"]`, no such tag
  exists, and its three runs were `workflow_dispatch` with `dry_run` defaulting to `true`;
* so the only way to hold one is to have run truestill from a git checkout before that date.

**Population: one, and it is the maintainer.** Anchoring the path, or resolving it once per
process, is machinery to make a bad path behave for a population that does not exist.

⚠ **`catalog --move` still migrates one**, and `LEGACY_CATALOG_PATH` survives for exactly that.
What is gone is the *resolution*: nothing consults it to decide which catalog to open.
"""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest
from truestill_core import app_paths
from truestill_core.app_paths import (
    CATALOG_FILENAME,
    LEGACY_CATALOG_PATH,
    default_catalog_path,
    resolve_catalog_choice,
    standard_catalog_path,
)


def _a_legacy_catalog_here(tmp_path: Path) -> Path:
    """A real `reports/catalog.sqlite` in the working directory - the thing that used to win."""
    legacy = tmp_path / LEGACY_CATALOG_PATH
    legacy.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(legacy))
    conn.execute("CREATE TABLE files (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    return legacy


def test_a_reports_catalog_in_the_working_directory_is_not_adopted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE GUARD. Fails against the old code, which returned the legacy file."""
    monkeypatch.chdir(tmp_path)
    legacy = _a_legacy_catalog_here(tmp_path)

    chosen = default_catalog_path()

    assert chosen != legacy.resolve(), (
        "a `reports/catalog.sqlite` in the working directory was adopted. That is what made the "
        "same install open a different library depending on where it was launched from."
    )
    assert chosen == standard_catalog_path()


def test_the_answer_no_longer_depends_on_where_you_are(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect stated as a property: two directories, one answer.

    This is the assertion the entry was filed for. It says nothing about *which* path wins - only
    that standing somewhere else cannot change it.
    """
    inside = tmp_path / "checkout"
    outside = tmp_path / "elsewhere"
    inside.mkdir()
    outside.mkdir()
    _a_legacy_catalog_here(inside)

    monkeypatch.chdir(inside)
    from_inside = default_catalog_path()
    monkeypatch.chdir(outside)
    from_outside = default_catalog_path()

    assert from_inside == from_outside, (
        f"the same install resolved {from_inside} from one directory and {from_outside} from "
        "another. `cd` must not change which library a user is in."
    )


def test_the_disclosure_is_now_two_way(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`(adv)`'s banner keeps naming which rule won - there are simply two rules now.

    Worth keeping whatever the rules are: the value was never the third branch, it was that a
    user is told *why* this path and not another.
    """
    monkeypatch.chdir(tmp_path)
    _a_legacy_catalog_here(tmp_path)

    monkeypatch.delenv(app_paths.DATA_DIR_ENV, raising=False)
    default = resolve_catalog_choice()
    monkeypatch.setenv(app_paths.DATA_DIR_ENV, str(tmp_path / "elsewhere"))
    override = resolve_catalog_choice()

    assert {default.reason, override.reason} == {"default", "override"}
    assert default.summary, "the default case must still say why"
    assert override.summary, "the override case must still say why"
    assert default.summary != override.summary, "two rules must read differently"
    assert "legacy" not in default.reason


def test_the_move_command_can_still_migrate_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ RETIRING THE RESOLUTION IS NOT REMOVING THE MIGRATION, and conflating them would strand
    anyone who has a legacy catalog with no supported way to bring it over.

    `LEGACY_CATALOG_PATH` survives for `truestill catalog --move` alone. This asserts it still
    names something that command can act on - a relative path resolved against the caller's
    directory, which is exactly right for *"move the one in front of me"* and exactly wrong for
    *"decide which library this is"*.
    """
    monkeypatch.chdir(tmp_path)
    legacy = _a_legacy_catalog_here(tmp_path)

    assert not LEGACY_CATALOG_PATH.is_absolute()
    assert LEGACY_CATALOG_PATH.name == CATALOG_FILENAME
    assert LEGACY_CATALOG_PATH.resolve() == legacy.resolve()


def test_nothing_in_the_resolver_consults_the_legacy_path_any_more() -> None:
    """The durable half. A behavioural test says the legacy file is not adopted *today*; this says
    the resolver does not reach for it at all, so re-adding the branch fails here rather than in
    whichever scenario happens to be covered."""
    source = inspect.getsource(app_paths.resolve_catalog_choice)
    assert "LEGACY_CATALOG_PATH" not in source, (
        "the resolver mentions the legacy path again. It is `catalog --move`'s source now, not a "
        "rule for deciding which catalog to open. `(adw)`."
    )
