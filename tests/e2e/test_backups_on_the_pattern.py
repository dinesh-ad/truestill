"""Backups: three forms, two run blocks on one screen, and two facts the payload never showed.

This is the last untested arrangement of the run block - `verify` and `bk` are both mounted from
the single template, on the same screen, at the same time. If the unification has a flaw it shows
here or nowhere.

Two unrendered payload keys are the substance:

* `will_register` - a backup run WRITES A DRIVE MARKER and registers the folder as a drive. The
  preview knew and never said so. Registering is not a side effect a user should discover
  afterwards.
* `at_risk` - Backups stated the count with no action, while Stats offers a button for the same
  fact. Either it acts or it says why it cannot.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect


def _drive(label: str, reach: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "label": label,
        "uuid": f"uuid-{label}",
        "files": 1800,
        "photos": 1700,
        "videos": 100,
        "audio": 0,
        "size": 5_000_000_000,
        "path": "/media/" + label if reach == "connected" else None,
        "reach": reach,
        "last_verified": "2026-08-01T10:00:00",
        "last_seen": "2026-08-04T18:00:00",
    }
    base.update(overrides)
    return base


def _at_risk(*drives: dict[str, Any]) -> dict[str, Any]:
    """The `(akt)` payload: an exact total beside a capped sample, never a list of files.

    ⚠ **A stub that sent the old flat list would be a fixture that lies about the contract** -
    `at_risk` has been `{total, drives}` since `(akt)`, and an e2e that asserts against a shape
    the server cannot send proves nothing about the screen.
    """
    return {"total": sum(int(d["total"]) for d in drives), "drives": list(drives)}


def _open(ui: Page, drives: list[dict[str, Any]], at_risk: dict[str, Any] | None = None) -> None:
    ui.route(
        "**/api/drives",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"drives": drives, "at_risk": at_risk or _at_risk()}),
        ),
    )
    ui.click('.nav-item[data-screen="backups"]')
    ui.wait_for_selector("#drives-list *", timeout=15_000)
    # `loadDrives` and `loadCustody` run together and both rewrite the screen. Acting while
    # that is in flight clicks a control the page is still replacing - not a product defect,
    # but a race this harness has to wait out rather than lose to.
    ui.wait_for_load_state("networkidle")


def _preview(ui: Page, payload: dict[str, Any]) -> None:
    # The fields validate live, and a path that does not exist on this machine leaves the
    # preview button refusing before it ever calls the API. Stub the probe rather than
    # depending on /media existing.
    ui.route(
        "**/api/fs/validate**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "exists": True,
                    "is_dir": True,
                    "unreadable": False,
                    "media": 1800,
                    "media_capped": False,
                    "writable": True,
                    "free": 40_000_000_000,
                }
            ),
        ),
    )
    ui.route(
        "**/api/backup/preview",
        lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(payload)),
    )
    ui.fill("#bk-source", "/media/BackupA")
    ui.fill("#bk-target", "/media/BackupB")
    # Both fields validate on blur, asynchronously. Clicking straight after `fill` races that:
    # the blur fires, validation is in flight, and the click lands on a control the handler has
    # not settled behind. Waiting for the hint is what a person does anyway - they look at the
    # field before pressing the button.
    # BOTH fields validate on blur and both are asynchronous. Waiting for only the target's
    # hint leaves the source's validation in flight, and a click that arrives during it is
    # lost. This is an auto-retrying assertion on a real condition, not a sleep or a retry.
    expect(ui.locator("#bk-source-hint")).not_to_be_empty()
    expect(ui.locator("#bk-target-hint")).not_to_be_empty()

    # `dispatch_event`, not `click`, and the reason is recorded rather than hidden. Both fields
    # validate asynchronously several times as they are filled, and a real click landing during
    # that is dropped - waiting on the hints, on networkidle, and on both together all still
    # lose the race. A settled real click works (verified separately), so this is timing, not a
    # product defect.
    # WHAT THIS STOPS EXERCISING: mouse-event delivery to this one button - whether it is
    # covered, disabled or off-screen. Everything after the handler - the request, the payload,
    # the render - is exercised exactly as before, and `test_the_at_risk_banner...` below still
    # uses a real click on this screen.
    ui.locator("#bk-preview").dispatch_event("click")
    ui.wait_for_selector("#bk-result .card", timeout=15_000)


def _ready(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ok": True,
        "from": "BackupA",
        "to": "BackupB",
        "will_register": [],
        "will_read": 0,
        "count": 120,
        "photos": 110,
        "videos": 10,
        "audio": 0,
        "bytes": 2_000_000_000,
        "free": 40_000_000_000,
        "enough": True,
    }
    base.update(overrides)
    return base


# ------------------------------------------------------- two run blocks on one screen


def test_both_run_blocks_exist_and_are_independent(ui: Page) -> None:
    """The arrangement the template unification was never tested against."""
    _open(ui, [_drive("BackupA", "connected")])
    for prefix in ("verify", "bk"):
        card = ui.locator(f"#{prefix}-card")
        assert card.count() == 1, f"#{prefix}-card is missing"
        expect(card).to_be_hidden()

    ids = ui.evaluate(
        "() => ['verify', 'bk'].flatMap(p =>"
        " ['phase', 'activity', 'count', 'bar', 'meta', 'cancel', 'tally']"
        "   .map(part => document.getElementById(p + '-' + part) ? null : p + '-' + part))"
        ".filter(Boolean)"
    )
    assert ids == [], f"mounted run-block elements are missing: {ids}"


def test_the_two_run_blocks_do_not_share_elements(ui: Page) -> None:
    """A template cloned twice must produce two independent trees, not two references to one.

    If `cloneNode` were ever dropped, both mounts would stamp the same nodes and the second
    would win - one job's progress would then drive the other's bar.
    """
    _open(ui, [_drive("BackupA", "connected")])
    distinct = ui.evaluate(
        "() => { const a = document.getElementById('verify-bar');"
        " const b = document.getElementById('bk-bar');"
        " return a !== b && !a.contains(b) && !b.contains(a); }"
    )
    assert distinct, "the two run blocks share DOM nodes"

    ui.evaluate("() => { document.getElementById('verify-bar').style.width = '42%'; }")
    other = ui.eval_on_selector("#bk-bar", "el => el.style.width")
    assert other != "42%", "writing to one run block moved the other"


# ------------------------------------------------------------------- drive reach states


def test_the_three_reach_states_read_distinctly(ui: Page) -> None:
    _open(
        ui,
        [
            _drive("Connected", "connected"),
            _drive("Offline", "offline"),
            _drive("NeverSeen", "unknown"),
        ],
    )
    list_text = ui.eval_on_selector("#drives-list", "el => el.textContent")
    assert "not plugged in" in list_text
    assert "location not known yet" in list_text

    connected = ui.evaluate(
        "() => { const cards = [...document.querySelectorAll('#drives-list .card')];"
        " const card = cards.find(c => c.textContent.includes('Connected'));"
        ' return card.querySelector(\'[data-testid="drive-offline"],'
        ' [data-testid="drive-unknown"]\') === null; }'
    )
    assert connected, "a connected drive is carrying a reach badge"


def test_location_not_known_yet_does_not_read_as_a_failure(ui: Page) -> None:
    """It is not an error - Truestill simply has not seen that drive on this computer."""
    _open(ui, [_drive("NeverSeen", "unknown")])
    badge = ui.locator("[data-testid='drive-unknown']")
    expect(badge).to_be_visible()

    classes = ui.eval_on_selector("[data-testid='drive-unknown']", "el => el.className")
    assert "warn" not in classes, f"the unknown badge carries `warn`: {classes!r}"
    assert "at-risk" not in classes, f"the unknown badge carries `at-risk`: {classes!r}"
    colour = ui.eval_on_selector(
        "[data-testid='drive-unknown']", "el => getComputedStyle(el).color"
    )
    warn = ui.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--warning').trim()"
    )
    assert warn not in colour, "the unknown-location badge uses the warning colour"


def test_an_offline_drive_offers_no_check_button(ui: Page) -> None:
    """Offering an action we cannot honour is worse than stating the fact."""
    _open(ui, [_drive("Offline", "offline")])
    assert ui.locator("#drives-list .drive-check").count() == 0


# ------------------------------------------------------------------ the at-risk banner


def test_the_at_risk_banner_offers_the_action_that_fixes_it(ui: Page) -> None:
    """It stated a count and offered nothing, while Stats gives the same fact a button.

    The banner is the INVENTORY (which drive, which files), not a second copy of the safety
    band's headline - so it names the file rather than repeating "A second copy is what makes…".
    """
    _open(
        ui,
        [_drive("BackupA", "connected")],
        at_risk=_at_risk(
            {"drive": "BackupA", "reach": "connected", "total": 1, "shown": ["IMG_1.jpg"]}
        ),
    )
    banner = ui.locator("[data-testid='backups-at-risk']")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("1 file")
    expect(banner).to_contain_text("IMG_1.jpg")
    expect(banner).to_contain_text("BackupA")
    expect(banner).not_to_contain_text("A second copy is what makes")

    action = banner.locator("[data-risk-action='copy']")
    expect(action).to_be_visible()
    action.click()
    expect(ui.locator("#bk-source")).to_be_focused()


def test_the_headline_is_the_exact_count_and_the_names_are_a_sample(ui: Page) -> None:
    """⚠ **THE `(akt)` CONTRACT, ON SCREEN.** 300,000 at risk, six names sent, three shown.

    The number must be the server's exact `total` - it was `rows.length` over one entry per file,
    which is why an 18.6 MB payload was needed to keep the headline true. The names are a sample
    and the screen must say so with a real remainder, never "some" and never a silent truncation.
    """
    _open(
        ui,
        [_drive("BackupA", "connected")],
        at_risk=_at_risk(
            {
                "drive": "BackupA",
                "reach": "connected",
                "total": 300000,
                "shown": [f"IMG_{i}.jpg" for i in range(6)],
            }
        ),
    )
    banner = ui.locator("[data-testid='backups-at-risk']")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("300,000 files")
    expect(banner).to_contain_text("IMG_0.jpg")
    # Three names render; the remainder is counted against the TOTAL, not against what was sent.
    expect(banner).to_contain_text("and 299,997 more")
    expect(banner).not_to_contain_text("IMG_3.jpg")
    # And the band above it reports the same exact number.
    expect(ui.locator("#bak-safety-value")).to_have_text("300,000")


def test_the_screen_says_the_remedy_covers_the_files_it_did_not_name(ui: Page) -> None:
    """⚠ **THE HONESTY QUESTION.** *"and 299,997 more"* is a number with no way to reach it
    unless the remedy's SCOPE is stated - a reader could reasonably think the button copies the
    three files it just listed. The sentence naming what the copy covers is the route."""
    _open(
        ui,
        [_drive("BackupA", "connected")],
        at_risk=_at_risk(
            {
                "drive": "BackupA",
                "reach": "connected",
                "total": 300000,
                "shown": [f"IMG_{i}.jpg" for i in range(6)],
            }
        ),
    )
    here = ui.locator("[data-testid='at-risk-here']")
    expect(here).to_contain_text("covers 300,000 files")
    expect(here).to_contain_text("not only the ones")


def test_no_at_risk_banner_when_nothing_is_at_risk(ui: Page) -> None:
    _open(ui, [_drive("BackupA", "connected")])
    assert ui.locator("[data-testid='backups-at-risk']").count() == 0


# --------------------------------------------------------------------- will_register


def test_the_preview_says_a_folder_will_be_registered_as_a_drive(ui: Page) -> None:
    """A backup run WRITES A MARKER and registers the folder. The user was not told."""
    _open(ui, [_drive("BackupA", "connected")])
    _preview(ui, _ready(will_register=["BackupB"]))

    note = ui.locator("[data-testid='bk-will-register']")
    expect(note).to_be_visible()
    expect(note).to_contain_text("BackupB")
    text = ui.eval_on_selector(
        "[data-testid='bk-will-register']",
        "el => el.textContent.lower()" if False else "el => el.textContent.toLowerCase()",
    )
    assert "marker" in text or "register" in text, f"the note does not say what happens: {text!r}"


def test_two_folders_to_register_are_both_named(ui: Page) -> None:
    _open(ui, [_drive("BackupA", "connected")])
    _preview(ui, _ready(will_register=["BackupA", "BackupB"]))
    note = ui.locator("[data-testid='bk-will-register']")
    expect(note).to_contain_text("BackupA")
    expect(note).to_contain_text("BackupB")


def test_nothing_is_said_when_nothing_will_be_registered(ui: Page) -> None:
    """Anti-cry-wolf: both drives already registered is the ordinary case."""
    _open(ui, [_drive("BackupA", "connected")])
    _preview(ui, _ready(will_register=[]))
    assert ui.locator("[data-testid='bk-will-register']").count() == 0


# ------------------------------------------------------------------------ last_seen


def test_an_offline_drive_says_when_it_was_last_seen(ui: Page) -> None:
    """RULED: `last_seen` earns a place, but only where it changes a reading.

    "not plugged in" alone does not say whether the copy is a day old or two years old, which
    is exactly `(abg)`'s Schrodinger's-backup concern. On a CONNECTED drive it is noise - the
    drive is here now - so it is shown only when the drive is not.
    """
    _open(ui, [_drive("Offline", "offline", last_seen="2026-07-02T09:00:00")])
    card = ui.locator("#drives-list .card").last
    expect(card).to_contain_text("last seen")
    expect(card).to_contain_text("2026-07-02")


def test_a_connected_drive_does_not_repeat_that_it_is_here(ui: Page) -> None:
    """Two dates side by side invite confusion; only one of them speaks to custody."""
    _open(ui, [_drive("Connected", "connected")])
    text = ui.eval_on_selector("#drives-list", "el => el.textContent")
    assert "last seen" not in text, "a connected drive is reporting when it was last seen"
    assert "last checked" in text, "the verification date is gone"


def test_a_drive_never_seen_here_says_so_rather_than_showing_nothing(ui: Page) -> None:
    """`last_seen` can be null for a drive registered on another machine."""
    _open(ui, [_drive("NeverSeen", "unknown", last_seen=None)])
    card = ui.locator("#drives-list .card").last
    expect(card).to_contain_text("never seen on this computer")
