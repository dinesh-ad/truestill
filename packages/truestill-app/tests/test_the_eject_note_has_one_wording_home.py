"""The eject-and-verify sentence is core's, and both surfaces say core's words. `(ajf)`

**Why a guard rather than a convention.** `STOP_WORDING`'s rule has been re-broken twice in this
repo by people who could quote it, because a second surface is always written in a second language
and copying four words is easier than importing them. This pins the shape `(ahc)` settled: the
service puts the words in the payload and `app.js` renders what it was handed.

⚠ **It also pins that the COUNT stays unqualified**, which is the half a wording guard would
normally miss. `(ajf)` is a conditional instruction about the drive, not a hedge on the copy: on a
fixed disk the bytes are as durable as anything else the machine holds, and a sentence that made
every successful backup read as unfinished would be the cry-wolf `run_health`'s docstring calls
the failure mode to fear.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.backup import EJECT_BEFORE_UNPLUGGING

_APP = Path(__file__).resolve().parents[1] / "src" / "truestill_app"
_CLI = Path(__file__).resolve().parents[2] / "truestill-cli" / "src" / "truestill_cli" / "cli.py"


def test_the_sentence_names_both_the_eject_and_the_verify() -> None:
    """Eject is the mechanism that flushes; verify is the net if they did not."""
    assert "eject" in EJECT_BEFORE_UNPLUGGING.lower()
    assert "truestill verify" in EJECT_BEFORE_UNPLUGGING


def test_it_is_conditional_rather_than_an_assertion_the_drive_is_removable() -> None:
    """Truestill cannot detect removability, so the sentence carries its own condition."""
    assert EJECT_BEFORE_UNPLUGGING.lower().startswith("if ")


def test_neither_surface_spells_the_sentence_itself() -> None:
    """One wording home. A surface that retypes it is what this refuses."""
    body = EJECT_BEFORE_UNPLUGGING.split(" - ")[0]
    for path in (_CLI, _APP / "service" / "backup.py", _APP / "static" / "app.js"):
        assert body not in path.read_text(encoding="utf-8"), (
            f"{path.name} spells the eject sentence itself instead of reading "
            "truestill_core.backup.EJECT_BEFORE_UNPLUGGING"
        )


def test_both_surfaces_reach_the_one_home() -> None:
    assert "EJECT_BEFORE_UNPLUGGING" in _CLI.read_text(encoding="utf-8")
    assert "EJECT_BEFORE_UNPLUGGING" in (_APP / "service" / "backup.py").read_text(encoding="utf-8")
    assert "eject_note" in (_APP / "static" / "app.js").read_text(encoding="utf-8")


def test_the_copied_count_is_not_hedged_by_it() -> None:
    """The sentence is about the drive, never about whether the copy happened."""
    lowered = EJECT_BEFORE_UNPLUGGING.lower()
    for hedge in ("may not", "might not", "not yet copied", "incomplete", "unfinished"):
        assert hedge not in lowered, f"{hedge!r} makes a finished copy read as unfinished"
