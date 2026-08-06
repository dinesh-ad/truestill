"""One name for the card that rearranges a library, in every place a person reads it.

It was retyped in four: the saved-threshold warning core produces, the card's own heading, the
button that jumps to it, and `IMPLEMENTATION_STANDARDS.md`. That is the drift `ALL_RULES` and
`SUBCOMMANDS` each produced once already.

And the old name was the reason the feature was invisible. "Move existing files to match" does
not say what it matches, so nobody looking for "rearrange my library into dated folders" found
it - while the seven-step manual procedure they were offered elsewhere is exactly what this
replaces.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.layout import EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING, MIGRATE_CARD_NAME

_APP = Path(__file__).resolve().parents[1] / "src" / "truestill_app"


def test_the_name_says_what_the_card_does() -> None:
    assert "match" not in MIGRATE_CARD_NAME, MIGRATE_CARD_NAME
    assert "rearrange" in MIGRATE_CARD_NAME.lower(), MIGRATE_CARD_NAME


def test_the_card_heading_carries_the_shared_name() -> None:
    """The heading may say MORE than the shared name; it may not say something else."""
    page = (_APP / "templates" / "index.html").read_text(encoding="utf-8")
    start = page.index('id="settings-migrate"')
    heading = page[page.index("<h2>", start) + 4 : page.index("</h2>", start)]
    assert heading.startswith(MIGRATE_CARD_NAME), heading


def test_the_button_that_jumps_there_calls_it_the_same_thing() -> None:
    script = (_APP / "static" / "app.js").read_text(encoding="utf-8")
    assert f"Go to {MIGRATE_CARD_NAME}<" in script, "the jump button uses a different name"


def test_the_saved_threshold_warning_routes_there_by_that_name() -> None:
    assert MIGRATE_CARD_NAME in EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING


def test_the_old_name_is_gone_from_every_surface_a_person_reads() -> None:
    """Anti-vacuity: the assertions above would all pass with the old name still on screen
    somewhere, and a half-renamed feature is harder to find than a consistently misnamed one."""
    for relative in ("templates/index.html", "static/app.js"):
        text = (_APP / relative).read_text(encoding="utf-8")
        assert "Move existing files to match" not in text, relative
