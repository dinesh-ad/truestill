"""The recover card, in a browser: the reassurance, and when the button is offered. Stage 3.

⚠ **THE REASSURANCE IS ON SCREEN BEFORE ANY REQUEST, and that is what these tests defend.** The
user arriving at this button has met restores that destroy things - UrBackup ships restore
disabled by default, and
Backblaze tells people to make another backup first. Truestill's never overwrites and
never deletes, and the remedy for that inherited fear is a sentence read *before* deciding to be
brave. It is substituted into the markup server-side for exactly that reason, so a test that
waited for a preview would be testing the wrong moment.

**The button obeys `loadDrives`' own rule**, quoted from the source it sits next to: rendered only
when we know where the drive is, because *"offering an action we cannot honour would be worse than
stating the fact plainly."*
"""

from __future__ import annotations

import json
from typing import Any

from e2e_support import open_backups
from playwright.sync_api import Page, expect


def _drive(label: str, uuid: str, path: str | None, **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": label,
        "uuid": uuid,
        "files": 2,
        "photos": 2,
        "videos": 0,
        "audio": 0,
        "size": 100,
        "last_seen": None,
        "last_verified": None,
        "path": path,
        "reach": "connected" if path else "unknown",
        "decisions": None,
    }
    row.update(over)
    return row


def _show(ui: Page, drives: list[dict[str, Any]], cannot_name: str = "") -> None:
    ui.route(
        "**/api/drives**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "library": {
                        "files": 2,
                        "photos": 2,
                        "videos": 0,
                        "audio": 0,
                        "bytes": 100,
                        "by_format": {},
                    },
                    "at_risk": {"total": 0, "drives": []},
                    "drives": drives,
                    "cannot_name_library": cannot_name,
                }
            ),
        ),
    )
    open_backups(ui)


# ------------------------------------------------------------------------- the reassurance


def test_the_screen_says_nothing_is_deleted_before_anything_is_pressed(ui: Page) -> None:
    """⚠ **The sentence that answers the fear, and WHEN it is readable.**

    Asserted without any interaction at all: no field filled, no preview run. A reassurance that
    appeared only after a preview would be one the user reads after deciding to be brave.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])

    banner = ui.locator("#recover-safety")
    expect(banner).to_contain_text("deleted or replaced", timeout=30_000)
    expect(banner).to_contain_text("only added")
    expect(banner).to_contain_text("left exactly as it is")
    expect(banner).to_contain_text("only read from")


def test_the_reassurance_is_not_styled_as_an_aside(ui: Page) -> None:
    """⚠ **Found by looking at it.** The first version used `class="banner ok"`, and `app.css`'s
    `.banner:not(.warn)` deliberately demotes every non-warning banner to muted small text - right
    for a first-run diagnostic, wrong for the one sentence on the screen that has to be believed.

    Asserted on the CLASS rather than on computed colour: the class is what selects the treatment,
    and a colour assertion would re-encode the palette here and break on a token change.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])

    expect(ui.locator("#recover-safety")).to_have_class("banner safe", timeout=30_000)


# ------------------------------------------------------------------------------- the button


def test_a_connected_drive_is_offered_the_action(ui: Page) -> None:
    """The positive half. Without it, a button that never rendered would pass the test below."""
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    expect(ui.locator(".drive-recover")).to_have_count(1)


def test_a_drive_whose_location_is_unknown_is_not_offered_it(ui: Page) -> None:
    """⚠ **`loadDrives`' rule, obeyed rather than restated**: *"offering an action we cannot
    honour would be worse than stating the fact plainly."* Without a path there is nothing to
    recover from, so neither this button nor `Check now` renders."""
    _show(ui, [_drive("Morrowkeep", "u1", None)])

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    expect(ui.locator(".drive-recover")).to_have_count(0)
    expect(ui.locator(".drive-check")).to_have_count(0)


def test_the_button_fills_the_form_rather_than_starting_a_run(ui: Page) -> None:
    """⚠ **It opens the question, never the copy**, and that is the difference from `Check now`.

    A verify only reads, so its button runs immediately. This one leads to writing into a library,
    so the button's whole job is to fill the field and let the typed word start anything.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)

    ui.locator(".drive-recover").first.click()

    expect(ui.locator("#rcv-drive")).to_have_value("/mnt/backup")
    # Nothing was started: no confirmation appeared, and the result region is untouched.
    expect(ui.locator("#rcv-confirm")).to_be_empty()


def test_clicking_it_on_the_library_itself_says_so_instead_of_starting_a_job(ui: Page) -> None:
    """⚠ **The rule obeyed at the moment it becomes obeyable.**

    `library_path` is written by the app's own organize flow, so on a catalog built by the CLI it
    is absent and the button renders on every connected drive - including the library's own card.
    Once the user has typed where their library is, the un-honourable click is answerable, and it
    is answered here rather than by starting a job that can only refuse.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/library")])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    ui.locator("#rcv-library").fill("/mnt/library")

    ui.locator(".drive-recover").first.click()

    expect(ui.locator("#rcv-result")).to_contain_text("That is your library")
    expect(ui.locator("#rcv-drive")).to_have_value("")


# ------------------------------------------------------ what the card knows before it is asked


def _carrying(label: str, uuid: str, path: str | None, **over: Any) -> dict[str, Any]:
    row = _drive(label, uuid, path)
    row.update(
        {
            "is_library": False,
            "carried": None,
            "carried_lead": "",
            "carried_short": "",
            "carried_full": "",
        }
    )
    row.update(over)
    return row


def test_a_drive_carrying_files_says_how_many_and_where_the_number_came_from(ui: Page) -> None:
    """⚠ **A COUNT ON A CARD READS AS A FACT ABOUT THE DRIVE, and this one is a fact about the
    catalog's records of it.** So the number never renders without its provenance beside it -
    asserted together, because either alone is the defect."""
    _show(
        ui,
        [
            _carrying(
                "Morrowkeep",
                "u1",
                "/mnt/backup",
                carried=7,
                carried_lead="not recorded in your library",
                carried_short="from records",
                carried_full="Counted from this catalog's records, not from a fresh look at the drive.",
            )
        ],
    )

    # The number and what it is about lead.
    expect(ui.locator("#drives-list .drive-carried")).to_contain_text(
        "7 files not recorded in your library", timeout=30_000
    )
    # ⚠ **The qualifier is on screen WITHOUT opening anything** - it is what stops the number
    # being misread, so it is not behind a disclosure. A `<summary>` renders its own text.
    expect(ui.locator("#drives-list .drive-why summary")).to_contain_text("from records")
    # And the full sentence is reachable rather than absent.
    expect(ui.locator("#drives-list .drive-why")).to_contain_text("not from a fresh look")
    expect(ui.locator(".drive-recover")).to_have_count(1)


def test_a_drive_carrying_nothing_says_so_and_is_offered_no_button(ui: Page) -> None:
    """⚠ **"Bring these back" - which these?** A drive with nothing to bring needs a sentence,
    not an offer. The zero case is the note ALONE: rendering the count too produced "0 files your
    library does not record, nothing here that your library does not already record"."""
    _show(
        ui,
        [
            _carrying(
                "Morrowkeep",
                "u1",
                "/mnt/backup",
                carried=0,
                carried_lead="nothing your library does not already record",
                carried_short="from records",
            )
        ],
    )

    expect(ui.locator("#drives-list .drive-carried")).to_contain_text(
        "nothing your library does not already record", timeout=30_000
    )
    assert "0 file" not in ui.eval_on_selector("#drives-list", "el => el.innerText")
    expect(ui.locator(".drive-recover")).to_have_count(0)


def test_a_drive_nobody_walked_shows_no_number_at_all(ui: Page) -> None:
    """⚠ **THE WORST WRONG ANSWER ON A CARD.** `drives --init` writes a marker and does not walk,
    so a drive holding a whole library has no rows. `carried` is `null`, and the card must say it
    was not checked - never "nothing to bring back" - and must offer `Check now` instead."""
    _show(
        ui,
        [
            _carrying(
                "Morrowkeep",
                "u1",
                "/mnt/backup",
                carried=None,
                carried_lead="not checked yet",
                carried_full="This drive was registered but never checked.",
            )
        ],
    )

    expect(ui.locator("#drives-list .drive-carried")).to_contain_text(
        "not checked yet", timeout=30_000
    )
    assert "0 file" not in ui.eval_on_selector("#drives-list", "el => el.innerText")
    expect(ui.locator(".drive-recover")).to_have_count(0)
    expect(ui.locator(".drive-check")).to_have_count(1)


def test_the_library_card_carries_neither_a_number_nor_the_button(ui: Page) -> None:
    """Recovering a drive into itself is refused by the engine, so a button there is the
    un-honourable offer the rule forbids - and a gap against itself is not a question."""
    _show(ui, [_carrying("Morrowkeep", "u1", "/mnt/library", is_library=True)])

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    expect(ui.locator(".drive-carried")).to_have_count(0)
    expect(ui.locator(".drive-recover")).to_have_count(0)


def test_the_library_field_is_filled_from_the_card_the_catalog_names(ui: Page) -> None:
    """⚠ **ITEM 1: the app asked for a path it already knew.** `is_library` comes from
    `organize_runs`, which the CLI writes too - so this now works on a catalog the app never
    touched, where `library_path` is absent and the earlier check failed open."""
    _show(
        ui,
        [
            _carrying("My Library", "u1", "/mnt/library", is_library=True),
            _carrying(
                "Morrowkeep",
                "u2",
                "/mnt/backup",
                carried=3,
                carried_lead="not recorded in your library",
                carried_short="from records",
            ),
        ],
    )

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    expect(ui.locator("#rcv-library")).to_have_value("/mnt/library")


def test_the_confirm_is_not_uppercased(ui: Page) -> None:
    """⚠ **ITEM 3.** `.field > label` is right for "DRIVE FOLDER" and wrong for the most serious
    sentence on the screen: uppercase reads as an alarm. Asserted on the computed style, because
    `text-transform` changes what is PAINTED and leaves `textContent` alone - a text assertion
    would pass while the screen shouted."""
    _show(
        ui,
        [
            _carrying(
                "Morrowkeep",
                "u1",
                "/mnt/backup",
                carried=3,
                carried_lead="not recorded in your library",
                carried_short="from records",
            )
        ],
    )
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    ui.locator("#rcv-library").fill("/mnt/library")
    # ⚠ **The page's OWN helper, not a click**, because reaching the confirm through the button
    # means running the preview job and stubbing an SSE stream - which would be testing the job
    # machinery in order to assert a style rule. `typedConfirm` is what the rule governs, and all
    # seven of its call sites render this same markup.
    ui.evaluate(
        """() => typedConfirm(document.getElementById("rcv-confirm"), {
             word: "recover",
             label: "Type recover to copy 3 files into My Library",
             buttonLabel: "Bring them back",
             onConfirm: () => {},
           })"""
    )

    label = ui.locator("#rcv-confirm label.confirm-ask")
    expect(label).to_be_visible(timeout=30_000)
    assert label.evaluate("el => getComputedStyle(el).textTransform") == "none"
    # And not demoted either: `--fg-secondary` would make the screen's most serious sentence the
    # one a reader skips. Asserted against the body's own colour rather than a hex.
    assert label.evaluate("el => getComputedStyle(el).color") == label.evaluate(
        "el => getComputedStyle(document.body).color"
    )


def test_a_catalog_that_cannot_name_the_library_says_so_once_and_names_the_remedy(
    ui: Page,
) -> None:
    """⚠ **Refusing to guess was right; going blank was not.**

    Two organize destinations means the gap has no single subject, so no card carries a count.
    The reason is a fact about the CATALOG, so it appears once above the cards rather than 148
    characters on every one - and it names a remedy that exists: Settings writes `library.root`
    and is reachable at any time, which was checked before the sentence was written.
    """
    _show(
        ui,
        [_carrying("Morrowkeep", "u1", "/mnt/a"), _carrying("Riverhold", "u2", "/mnt/b")],
        cannot_name="Truestill has organized into more than one folder, so it cannot tell which "
        "is your library. Say which in Settings, under 'Where your library lives'.",
    )

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    expect(ui.locator("#drives-list")).to_contain_text("cannot tell which is your library")
    expect(ui.locator("#drives-list")).to_contain_text("Settings")
    # Once, not once per card.
    assert ui.eval_on_selector("#drives-list", "el => el.innerText").count("Settings") == 1
    expect(ui.locator(".drive-carried")).to_have_count(0)


def test_an_ordinary_catalog_carries_no_such_banner(ui: Page) -> None:
    """The cry-wolf half: a sentence that always rendered would be noise on every screen."""
    _show(
        ui,
        [
            _carrying(
                "Morrowkeep",
                "u1",
                "/mnt/a",
                carried=2,
                carried_lead="not recorded in your library",
                carried_short="from records",
            )
        ],
    )

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    assert "cannot tell which" not in ui.eval_on_selector("#drives-list", "el => el.innerText")
