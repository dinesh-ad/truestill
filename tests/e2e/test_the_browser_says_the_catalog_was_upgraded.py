"""A user who opens the app after an upgrade is told their catalog was changed. `(akz)`

⚠ **WHY THIS FILE EXISTS AT ALL, AND WHY IT BOOTS ITS OWN SERVER.** The `ui` fixture hands every
other browser test an app whose catalog was created by that boot - so the schema is always
current, no migration can happen, and the banner can never appear. A test on that fixture would
assert the absence and pass against a renderer that never worked.

**What this does differently is the catalog.** It writes a real one, winds `PRAGMA user_version`
back a step, and only then boots the app - so `create_app`'s own `inspect_catalog` runs the
migration chain, exactly as it would for a user who upgraded Truestill and opened it again.
"""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from e2e_support import AppServer, boot_app, open_app
from playwright.sync_api import Page, expect
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog

BEHIND = CURRENT_SCHEMA_VERSION - 1


@pytest.fixture
def upgrading_app(tmp_path: Path, retiring) -> Iterator[AppServer]:
    """An app booted against a catalog one schema version behind."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    conn = sqlite3.connect(str(db))
    conn.execute(f"PRAGMA user_version = {BEHIND}")
    conn.commit()
    conn.close()

    started, server, thread, sock = boot_app(db, token=f"e2e-{secrets.token_urlsafe(16)}")
    yield started
    server.should_exit = True
    retiring.retire(server, thread, sock)


def test_the_upgrade_is_drawn_with_both_versions_and_what_it_costs(
    page: Page, upgrading_app: AppServer
) -> None:
    """The headline, and the second half is the one a person can act on.

    `previous` is the number an older Truestill would still accept; the sentence says that build
    will now be turned away, which is the next message they would meet if they tried one.
    """
    ui = open_app(page, upgrading_app.url)

    banner = ui.locator("[data-testid='catalog-upgrade']")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text(str(BEHIND))
    expect(banner).to_contain_text(str(CURRENT_SCHEMA_VERSION))
    expect(banner).to_contain_text("refuse")


def test_it_names_the_copy_that_is_the_way_back(page: Page, upgrading_app: AppServer) -> None:
    """The remedy, in the same banner as the cost - the copy is the only route to `previous`."""
    ui = open_app(page, upgrading_app.url)

    expect(ui.locator("[data-testid='catalog-upgrade']")).to_contain_text(
        "catalog.pre-upgrade.sqlite"
    )


def test_it_is_not_the_wrong_catalog_warning(page: Page, upgrading_app: AppServer) -> None:
    """⚠ **Its own host, and the 2026-09-06 ruling is why.**

    `#catalog-notice` is `alert`-only by that ruling - *"this may not be the catalog you expect"*.
    Rendering an upgrade through it would either demote this to nothing or put a startup
    diagnostic back on the page above the h1. A version that reused the banner fails here.
    """
    ui = open_app(page, upgrading_app.url)

    expect(ui.locator("[data-testid='catalog-upgrade']")).to_be_visible()
    expect(ui.locator("#catalog-notice")).to_be_hidden()


def test_an_ordinary_library_sees_no_banner(ui: Page) -> None:
    """The cry-wolf half, on the fixture every other test uses.

    Its catalog is built by its own boot, so nothing migrates - which is the state of every user
    who has not just upgraded, and they must see nothing at all.
    """
    expect(ui.locator("[data-testid='catalog-upgrade']")).to_have_count(0)
    expect(ui.locator("#catalog-upgrade")).to_be_hidden()
