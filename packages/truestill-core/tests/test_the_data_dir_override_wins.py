"""An explicit `TRUESTILL_DATA_DIR` outranks the legacy catalog, and every case says which won.

`(adv)`. `default_catalog_path` asked two questions in the wrong order: it checked
`reports/catalog.sqlite` - a **relative** path resolved against the working directory - before it
honoured the environment variable. So a compatibility guess beat an explicit instruction, and a
user who set the variable could organize, bake and register drives against a different catalog
than the one they named.

⚠ **EVERY TEST HERE CREATES A `reports/` IN ITS WORKING DIRECTORY, AND THAT IS THE POINT.** The
defect is invisible from a directory without one: the legacy branch never fires, the override
always wins, and the test passes against the broken code. A test that inherits an ordinary
temporary directory cannot reproduce this.

**The precedence, from precedent rather than principle.** `platformdirs` - already a dependency,
and the de facto standard for this question - reads its own overrides as
``os.environ.get("XDG_CONFIG_HOME", "").strip() or <default>``: **the variable is consulted
first, and a blank one is the same as an unset one.** Verified rather than cited: with
``XDG_DATA_HOME`` set to ``""`` and to ``"   "``, `platformdirs` returns ``~/.local/share`` both
times.

⚠ **The stranding half of this was retired with `(adw)` on 2026-08-19.** The override used to
have to yield to an existing `reports/catalog.sqlite`, because that file was `(aae)`'s
backwards-compatibility promise. It is no longer consulted at all - it was relative, so the
promise was kept against whichever directory the process started in - so there is nothing left
for the override to strand. `truestill catalog --move` migrates one; nothing adopts one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.app_paths import (
    CATALOG_FILENAME,
    DATA_DIR_ENV,
    default_catalog_path,
    resolve_catalog_choice,
)


def _a_working_directory_holding_a_legacy_catalog(tmp_path: Path) -> Path:
    """A CWD with a real `reports/catalog.sqlite` in it - the condition the defect needs."""
    legacy = tmp_path / "reports" / CATALOG_FILENAME
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"")
    return legacy


def _an_override_holding_a_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    catalog = elsewhere / CATALOG_FILENAME
    catalog.write_bytes(b"")
    monkeypatch.setenv(DATA_DIR_ENV, str(elsewhere))
    return catalog


def test_an_explicit_override_beats_a_legacy_catalog_in_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE GUARD. A stated instruction must outrank a guess made from the working directory."""
    monkeypatch.chdir(tmp_path)
    legacy = _a_working_directory_holding_a_legacy_catalog(tmp_path)
    wanted = _an_override_holding_a_catalog(tmp_path, monkeypatch)

    chosen = default_catalog_path()

    assert chosen == wanted.resolve(), (
        f"TRUESTILL_DATA_DIR named {wanted}, and {chosen} was used instead. A user who sets the "
        "variable would be operating on a catalog they did not name."
    )
    assert chosen != legacy.resolve()


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_override_is_treated_as_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blank: str
) -> None:
    """`platformdirs`' rule, and the reason for it: an unset variable and an empty one must not
    mean different things. Without this, `TRUESTILL_DATA_DIR=` resolves a catalog into a
    directory literally named by whitespace."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(DATA_DIR_ENV, blank)

    choice = resolve_catalog_choice()

    assert choice.reason == "default", f"a blank override was honoured as {choice.path}"
    assert choice.path.is_absolute(), f"a blank override produced {choice.path}"


def test_the_banner_says_which_path_won_and_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It read identically in every case, which is what made `(adv)` hard to notice: the resolved
    path was on screen and nothing said a variable had been set and lost.

    ⚠ **Two rules now, not three.** `(adw)` retired the legacy `reports/catalog.sqlite` lookup on
    2026-08-19, so there is no longer a branch between the override and the default. The property
    this test exists for is unchanged and is not about the count: **a user is told which rule
    decided, and no two rules read alike.**
    """
    monkeypatch.chdir(tmp_path)
    seen = {}

    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    seen["default"] = resolve_catalog_choice()

    _an_override_holding_a_catalog(tmp_path, monkeypatch)
    seen["override"] = resolve_catalog_choice()

    assert [c.reason for c in seen.values()] == ["default", "override"]
    summaries = [c.summary for c in seen.values()]
    assert all(summaries), "every case must state why this path won"
    assert len(set(summaries)) == len(summaries), f"two cases read identically: {summaries}"
    assert DATA_DIR_ENV in seen["override"].summary
