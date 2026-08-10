"""A Backups control must still be under the pointer when the drives land - `(acd)`.

**The defect, measured 2026-08-10.** `loadDrives` writes `#drives-list`, which sits above the
cards holding the controls. `#bk-preview` moved **+142.4px** with zero drives, **+156.0px** with
one, **+563.1px** with three, while visible and enabled the whole time. A click at the old
position landed on `#bk-source-hint` or an `<h2>` and was silently swallowed.

**Why the second assertion is the real one.** A pixel-delta bound is satisfied by a fix that
moves the button 155px instead of 156. `elementFromPoint` at the position the user aimed at is
the user's actual claim: *the thing I clicked is the thing I meant*.

**The viewport is set on the first line and that is not incidental.** At the default height
`#bk-preview` already sits below the fold, so `elementFromPoint` returns `null` - which reads as
"nothing was in the way" and passes. That artifact fooled the first measurement of this defect
and it pointed in the **reassuring** direction, which is the dangerous kind.

**The `data-ready` wait before the read is insurance, and is NOT proven load-bearing.** Removing
it leaves these green, and removing it *with the defect restored* still leaves them red - the
route `fulfill` and the geometry read are separate round trips, so the render always lands
between them. It stays because a slower render would need it, but it is recorded as unproven
rather than left to look earned.

**Both endpoints are stubbed, never one.** `loadDrives` awaits `/api/drives` *and*
`/api/library/status` together; stubbing only the first lands on a different render at a
different height, and the zero-drive case needs zero media counts or it takes the
"You have 1,836 photos organized" branch instead of the shorter one.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from e2e_support import AppServer, hold_route, open_app
from playwright.sync_api import Page, expect


def _drive(label: str, uuid: str) -> dict[str, Any]:
    return {
        "label": label,
        "uuid": uuid,
        "files": 2,
        "photos": 2,
        "videos": 0,
        "audio": 0,
        "size": 100,
        "last_seen": None,
        "last_verified": None,
        "path": "/tmp/here",
        "reach": "connected",
        "decisions": None,
    }


def _drives_body(n: int) -> str:
    return json.dumps({"drives": [_drive(f"Drive {i}", f"u{i}") for i in range(n)], "at_risk": []})


def _status_body() -> str:
    """A library that HAS files, so the empty-drive case takes the longer of its two branches.

    `loadDrives` picks its empty-state copy on `hasLibrary`, and the shorter branch ("nothing to
    back up") renders at a different height - stubbing this away would test the easier case.
    """
    return json.dumps(
        {
            "library_path": "/tmp/lib",
            "backup_path": None,
            "files": 2,
            "photos": 2,
            "videos": 0,
            "audio": 0,
            "by_format": {},
            "places": 1,
            "single_copy": 0,
            "files_no_copy": 0,
            "files_one_copy": 0,
            "redundancy_floor": 1,
            "files_on_a_drive": 2,
            "held_floor": 1,
            "bytes": 100,
            "catalog_path": "/tmp/c.sqlite",
            "catalog_presence": "ok",
            "catalog_detail": "",
            "catalog_tone": "info",
        }
    )


def _open_backups_holding(page: Page, server: AppServer) -> tuple[Page, list[Any]]:
    """Boot with a stubbed status, then switch to Backups with `/api/drives` held open.

    The status stub is registered BEFORE `open_app` because `loadCustody` fetches it during boot;
    leaving it to the real catalog would make the empty-state branch depend on fixture state.
    """
    page.set_viewport_size({"width": 1280, "height": 1600})
    page.route(
        "**/api/library/status",
        lambda r: r.fulfill(status=200, content_type="application/json", body=_status_body()),
    )
    ui = open_app(page, server.url)
    held = hold_route(ui, "**/api/drives")
    ui.click('button[data-screen="backups"]')
    expect(ui.locator("#screen-backups")).to_have_attribute("data-ready", "loading")
    return ui, held


def _centre(ui: Page) -> tuple[float, float, float]:
    box = ui.eval_on_selector(
        "#bk-preview",
        "el => { const r = el.getBoundingClientRect();"
        " return {x: r.left + r.width / 2, y: r.top + r.height / 2, top: r.top}; }",
    )
    return box["x"], box["y"], box["top"]


def _what_is_at(ui: Page, x: float, y: float) -> str:
    return ui.evaluate(
        "([x, y]) => { const e = document.elementFromPoint(x, y);"
        " return e ? (e.id || e.tagName.toLowerCase() + '.' + (e.className || '')) : 'nothing'; }",
        [x, y],
    )


# Zero first: it is the case neither the DOM-order reasoning nor the maintainer predicted, and
# the one where `loadDrives` renders an empty-state card rather than nothing.
@pytest.mark.parametrize("drives", [0, 1, 3])
def test_the_button_is_still_where_the_user_aimed(
    page: Page, app_server: AppServer, drives: int
) -> None:
    """The harm claim: a click at the position the button occupied must still reach the button."""
    ui, held = _open_backups_holding(page, app_server)
    x, y, before = _centre(ui)

    assert held, "the drives request never fired"
    held[0].fulfill(status=200, content_type="application/json", body=_drives_body(drives))
    expect(ui.locator("#screen-backups")).to_have_attribute("data-ready", "ready")

    landed = _what_is_at(ui, x, y)
    _, _, after = _centre(ui)
    assert landed == "bk-preview", (
        f"with {drives} drive(s) the button moved {after - before:+.1f}px and a click at its old "
        f"position would land on {landed!r} instead"
    )
    # Exact, so there is no bound to declare. `#drives-list` renders BELOW every control, so a
    # control's position cannot be a function of how many drives arrive.
    assert after == before, f"with {drives} drive(s) #bk-preview moved {after - before:+.1f}px"
