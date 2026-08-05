"""The custody strip states custody, risk first, and its sentence matches its number.

**What was wrong.** The strip read `safe in N places`, where N was
`len([drives with any recorded copy])` - a per-DRIVE count under a per-FILE sentence. They agree
on a tidy library and diverge exactly where it matters: organize into drive A, then into drive B
with no overlap, and every file is in one place while the strip says "safe in 2 places". The
number that contradicts it, `single_copy`, was computed on the same request and dropped.

Three records described the intent correctly and the code did something else - the contract
(§8), the design note (`ui-v2-research`), and `single_copy_count`'s own docstring. All three are
corrected in the commit that adds this file.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect
from truestill_core.catalog import Catalog


def _record(catalog: Catalog, sha: str, drive: str, name: str) -> None:
    catalog.record_uploaded(
        source_path=f"/src/{name}",
        original_name=name,
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=100,
        captured_at="2020-01-01T10:00:00",
        category="Camera",
        relative=f"2020/2020-01/{name}",
        drive_uuid=drive,
    )


def _strip(ui: Page) -> str:
    return ui.eval_on_selector("#custody-line", "el => el.textContent")


def test_two_drives_with_no_overlap_are_not_reported_as_safe(ui: Page, app_server) -> None:
    """The exact case the old wording got wrong, and the reason this file exists.

    Two registered drives, both holding copies, and not one file on both. The old strip said
    "safe in 2 places". Every file is in exactly one.
    """
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        catalog.upsert_drive(uuid="B", label="Drive B")
        _record(catalog, "sha-a", "A", "a.jpg")
        _record(catalog, "sha-b", "B", "b.jpg")

    ui.reload()
    text = _strip(ui)
    assert "in only one place" in text, f"the strip does not name the risk: {text!r}"
    assert "safe in 2 places" not in text
    assert "2 places" not in text, f"a per-drive count is still being claimed: {text!r}"

    # And the pips must not promise two either - they follow the weakest file now.
    assert ui.eval_on_selector("#custody-pips", "el => el.textContent").count("▪") == 1


def test_a_file_with_no_copy_at_all_is_named(ui: Page, app_server) -> None:
    """`single_copy_count` reads FROM file_copies, so a file with no copy row is invisible to it.

    That file is the most exposed thing in the library, and under the old strip it counted as
    neither safe nor at risk - it simply was not represented.
    """
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        _record(catalog, "sha-a", "A", "a.jpg")
        # Drop the copy row and keep the file row: a state the schema permits and
        # `forget_organized` deliberately does not produce (it removes the file row too).
        catalog._conn.execute("DELETE FROM file_copies WHERE sha256 = 'sha-a'")
        catalog._conn.commit()

    ui.reload()
    text = _strip(ui)
    assert "not on a drive yet" in text or "in only one place" in text, (
        f"a file with no copy is unrepresented: {text!r}"
    )
    assert ui.eval_on_selector("#custody-pips", "el => el.textContent").count("▪") == 0


def test_a_genuinely_redundant_library_may_say_so(ui: Page, app_server) -> None:
    """Risk-first does not mean never reassuring: with no exposure the reassurance is true."""
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        catalog.upsert_drive(uuid="B", label="Drive B")
        _record(catalog, "sha-a", "A", "a.jpg")
        _record(catalog, "sha-a", "B", "a.jpg")

    ui.reload()
    text = _strip(ui)
    assert "only one place" not in text
    # "safe in 2 places" also contains "2 places", so the old wording would pass a looser
    # assertion. The per-file sentence is what this pins.
    assert "safe in" not in text, f"the per-drive sentence survived: {text!r}"
    assert "every file" in text, f"the per-file sentence is missing: {text!r}"
    assert "2 places" in text, f"a fully redundant library is not stated: {text!r}"
    assert ui.eval_on_selector("#custody-pips", "el => el.textContent").count("▪") == 2


def test_the_inventory_line_is_gone(ui: Page, app_server) -> None:
    """It never changed, asked nothing, and after the first day it was furniture."""
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        _record(catalog, "sha-a", "A", "a.jpg")

    ui.reload()
    text = _strip(ui)
    assert "photo" not in text.lower() or "file" in text.lower()
    assert "·" not in text, f"the photos/videos inventory line is still here: {text!r}"


def test_the_catalog_path_is_not_eaten_down_to_a_fragment(ui: Page, app_server) -> None:
    """The `…e` defect: a middle-ellipsis that degenerates to one character.

    `fitCatalogPath`'s last resort strips the FILENAME a character at a time while the box is
    narrower than `…filename`, which is what a measurement taken mid-animation produces. The
    full path stays in `title`/`data-full` either way; what must not happen is the painted label
    collapsing to something that identifies nothing.
    """
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        _record(catalog, "sha-a", "A", "a.jpg")

    ui.reload()
    expect(ui.locator("#custody-catalog")).to_be_visible()
    painted = ui.eval_on_selector("#custody-catalog", "el => el.textContent")
    assert len(painted) > 6, f"the catalog path collapsed to {painted!r}"
    assert painted.endswith(".sqlite"), f"the filename did not survive: {painted!r}"

    full = ui.eval_on_selector("#custody-catalog", "el => el.getAttribute('data-full')")
    assert full.endswith("catalog.sqlite"), "the stored path was shortened, not just the label"


def test_the_path_survives_collapsing_and_expanding(ui: Page, app_server) -> None:
    """Where the fragment came from: the fit was measured while the rail was mid-animation.

    **This guards a PAIR, and the mutation proof says so.** Two changes stop the fragment: a
    `ResizeObserver` that re-fits once the box settles, and a last resort that hides the label
    instead of eating the filename. Removing either alone leaves this green - each is
    sufficient - and removing both turns it red. That is the overlapping-defence case in
    `ENGINEERING_STANDARD.md` §4: the honest thing is to say the assertion covers the outcome
    rather than either mechanism, not to delete a defence so a test can be sharper.
    """
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        _record(catalog, "sha-a", "A", "a.jpg")

    ui.reload()
    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    ui.wait_for_timeout(400)
    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "false")
    ui.wait_for_timeout(500)

    painted = ui.eval_on_selector("#custody-catalog", "el => el.textContent")
    assert len(painted) > 6, f"the path collapsed after a collapse/expand cycle: {painted!r}"
