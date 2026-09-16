"""The browser is told when opening the library upgraded its catalog. `(akz)`

⚠ **`(aku)`'s precedent, applied to a sentence rather than a write.** The terminal and the
browser must not describe one event two ways, so the words come from
`catalog_startup.schema_upgrade_notice` and this package composes none of its own.

**Why the BOOT value and not a live reading**, which is the half a test can get wrong without
noticing: `inspect_catalog` is what migrates, so by the second request the schema is current and
a fresh reading says nothing. `library_status` therefore reads `boot_catalog`, the same one-way
"this is what was true at boot" fact the first-run presence already rides on.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from truestill_app.service.drives import LibraryStatus, library_status
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog
from truestill_core.catalog_startup import inspect_catalog, schema_upgrade_notice

BEHIND = CURRENT_SCHEMA_VERSION - 1


def _behind(tmp_path: Path) -> Path:
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    conn = sqlite3.connect(str(db))
    conn.execute(f"PRAGMA user_version = {BEHIND}")
    conn.commit()
    conn.close()
    return db


def test_the_payload_carries_the_upgrade_in_cores_words(tmp_path: Path) -> None:
    """The headline. Compared against core's own output, never a retyped fragment."""
    db = _behind(tmp_path)
    boot = inspect_catalog(db, explicit_db=True)

    status = library_status(db, explicit_db=True, boot_catalog=boot)

    assert status["catalog_upgrade"] == schema_upgrade_notice(boot.opening)
    assert str(BEHIND) in status["catalog_upgrade"]
    assert "refuse" in status["catalog_upgrade"]


def test_it_survives_the_requests_that_come_after_the_migration(tmp_path: Path) -> None:
    """⚠ **The assertion with teeth, and the one a live reading fails.**

    `library_status` inspects the catalog again on every request. By the second one the schema is
    current, so an implementation that read the fresh inspection would go silent the moment the
    page reloaded - which is exactly when a user would look.
    """
    db = _behind(tmp_path)
    boot = inspect_catalog(db, explicit_db=True)

    first = library_status(db, explicit_db=True, boot_catalog=boot)
    second = library_status(db, explicit_db=True, boot_catalog=boot)

    assert second["catalog_upgrade"] == first["catalog_upgrade"] != ""


def test_an_ordinary_boot_says_nothing(tmp_path: Path) -> None:
    """The cry-wolf half: empty, so the browser renders no banner at all."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    boot = inspect_catalog(db, explicit_db=True)

    assert library_status(db, explicit_db=True, boot_catalog=boot)["catalog_upgrade"] == ""


def test_the_field_is_required_so_the_type_checker_guards_it() -> None:
    """⚠ **`(aky)`'s finding, applied rather than re-learned.**

    A `NotRequired` payload field is invisible to mypy when its line is deleted from the builder,
    and `(aky)` names four such fields that are drawn on a screen with nothing asserting them.
    This one is `str` and required, so deleting its line is a type error before it is a missing
    banner.

    ⚠ **ASKED OF THE COMMITTED SPEC, NOT OF `__required_keys__`, AND THE FIRST DRAFT ASKED THE
    WRONG ONE.** Under `from __future__ import annotations` on 3.14 a TypedDict's
    `__optional_keys__` is EMPTY, so `__required_keys__` holds every field and the assertion
    passes against `NotRequired[str]` - proved by a mutation that did exactly that.
    `scripts/emit_openapi.py` rebuilds each TypedDict with `get_type_hints(include_extras=True)`
    for this precise reason, and `openapi.json`'s `required` list is the result. This repo already
    records the same trap twice, in `test_migrate_reports_its_stop` and
    `test_no_thirty_fifth_dead_payload_key`.
    """
    assert "catalog_upgrade" in LibraryStatus.__annotations__
    spec = json.loads(
        (Path(__file__).resolve().parents[1] / "openapi.json").read_text(encoding="utf-8")
    )
    schema = spec["components"]["schemas"]["LibraryStatus"]
    assert "catalog_upgrade" in schema["properties"]
    assert "catalog_upgrade" in schema["required"], (
        "the field is NotRequired, so mypy cannot see its line being deleted from the builder"
    )


def test_both_surfaces_word_it_once() -> None:
    """The anti-drift assertion, read from source rather than trusted to a reviewer.

    The browser renderer must read the payload field and must not build a sentence; the terminal
    goes through `format_startup_lines`. Neither may grow its own wording.
    """
    root = Path(__file__).resolve().parents[3]
    app_js = (root / "packages/truestill-app/src/truestill_app/static/app.js").read_text(
        encoding="utf-8"
    )
    core = (root / "packages/truestill-core/src/truestill_core/catalog_startup.py").read_text(
        encoding="utf-8"
    )

    assert "s.catalog_upgrade" in app_js, "the browser does not read the field"
    assert "upgraded from version" not in app_js, "the browser composed its own sentence"
    assert "upgraded from version" in core, "core is no longer the one home for the wording"
