"""The custody strip is one sentence with one full stop, however many clauses it has.

**`(D5)`, and why nothing caught it.** `drive.LIBRARY_REDUNDANCY`'s values are FRAGMENTS by
design - its own comment says each one completes a sentence its caller starts - and the rail's
renderer closed the fragment with a "." and then appended the age clause, which opens with ", ".
A library that was both not-independent and never-checked therefore read:

    ...so they do not survive that device failing., never checked: Library, Library2

⚠ **No fixture in `test_custody_strip.py` sets an independence note and an age clause together**,
which is exactly why a defect visible on the maintainer's own screen survived a file of custody
tests. This one sets both, in every combination, so the join cannot regress in either direction.

The payload is stubbed rather than built from a catalog: the four combinations below are a
property of the RENDERER, and constructing four real libraries to reach them would test the
fixture instead.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect

#: The shape `renderRestingPanel` and the custody strip read. Only the fields the sentence
#: consults are set; everything else takes a resting value.
BASE: dict[str, Any] = {
    "files": 412,
    "bytes": 1024,
    "photos": 410,
    "videos": 2,
    "audio": 0,
    "places": 1,
    "held_floor": 1,
    "files_one_copy": 412,
    "files_no_copy": 0,
    "drives": [{"label": "Library", "file_count": 412, "last_verified": None}],
    "catalog_path": "/tmp/c.sqlite",
    "presence": "ready",
    "independence": "not_independent",
    "independence_note": (
        "have every copy on ONE device, so they do not survive that device failing"
    ),
    "never_checked_drives": ["Library", "Library2"],
    "custody_dated_at": None,
    "custody_dated_days": None,
    "custody_tier": None,
}


def _strip(ui: Page, **overrides: Any) -> str:
    payload = {**BASE, **overrides}
    ui.route(
        "**/api/library/status",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(payload)
        ),
    )
    ui.reload()
    expect(ui.locator("#custody-line")).not_to_have_text("Checking your library…")
    # The SENTENCE only. `#custody-line` also carries the catalog path as a child, which is a
    # filesystem path and brings its own full stops - counting those would make every assertion
    # here about the fixture's temp directory.
    return (
        ui.eval_on_selector(
            "#custody-line",
            "el => { const c = el.cloneNode(true);"
            " c.querySelectorAll('.catalog-path').forEach(n => n.remove());"
            " return c.textContent; }",
        )
        or ""
    )


def test_a_note_and_an_age_clause_do_not_collide(ui: Page) -> None:
    """The defect, exactly: both clauses present, and the join between them."""
    line = _strip(ui)

    assert ".," not in line, f"the fragment was punctuated before a comma clause: {line!r}"
    assert "failing, never checked" in line, f"the two clauses did not join: {line!r}"
    assert line.count(".") == 1, f"more than one full stop in one sentence: {line!r}"
    assert line.rstrip().endswith("."), f"the sentence does not end: {line!r}"


def test_a_note_alone_still_ends_the_sentence(ui: Page) -> None:
    """The note completes the lead clause with a space, and closes it."""
    line = _strip(ui, never_checked_drives=[])

    assert "place have every copy" in line, f"the note stopped continuing the lead: {line!r}"
    assert ".," not in line
    assert line.rstrip().endswith("failing."), f"the note did not close the sentence: {line!r}"


def test_an_age_clause_alone_keeps_its_comma(ui: Page) -> None:
    """Without a note the age still joins the lead with a comma, which other tests read."""
    line = _strip(ui, independence="possibly_independent", independence_note="")

    assert ", never checked: Library, Library2" in line, f"the age lost its comma: {line!r}"
    assert ".," not in line
    assert line.rstrip().endswith("."), f"the sentence does not end: {line!r}"


def test_neither_clause_leaves_a_bare_lead(ui: Page) -> None:
    """The cry-wolf half: with nothing to add there is no stray punctuation to add it with."""
    line = _strip(
        ui, independence="possibly_independent", independence_note="", never_checked_drives=[]
    )

    assert ".," not in line
    assert not line.rstrip().endswith("."), f"a lead clause alone gained a full stop: {line!r}"
