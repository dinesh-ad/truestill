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


#: The placeholder `index.html:102` ships in the markup, before `library/status` has answered.
_STILL_LOADING = "Checking your library…"


def _strip(ui: Page) -> str:
    """The rail's sentence, read only once the load that fills it has finished.

    **§3's auto-waiting rule, on the READ side.** `#custody-line` carries a placeholder from the
    markup and is overwritten when `library/status` returns, so a one-shot `eval_on_selector`
    after `ui.reload()` samples whichever happens to be there. On a laptop that is the answer; on
    a loaded CI runner it is the placeholder, and the test fails claiming the sentence is wrong
    when it simply had not arrived. Observed on run 31368093253.

    **Sound as a `not_to_have_text` even though §4 warns about absences**, and the distinction is
    the point: the placeholder IS present at load, so this transitions false -> true. An absence
    that is already true when the page opens would prove nothing; this one cannot be satisfied
    until the load has replaced it.
    """
    expect(ui.locator("#custody-line")).not_to_have_text(_STILL_LOADING)
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


def test_a_file_with_no_copy_at_all_reads_as_progress_on_the_rail(ui: Page, app_server) -> None:
    """REWRITTEN 2026-08-05. It asserted the RAIL named files with no copy; that moved to Stats.

    The promise it was written for still holds and is stronger, not weaker: such a file used to
    be invisible everywhere, because `single_copy_count` reads FROM file_copies and cannot see
    it. It is now counted, and reported where something can be done about it - the Stats screen,
    pinned by `test_the_orphan_count_is_still_reachable_on_stats`.

    What changed is where. A file with no copy cannot be acted on from the rail, and after the
    CLI began registering its destination this state is also the permanent normal for an rclone
    user. A standing amber line about a condition the reader cannot clear is the nagging the
    risk-first ruling exists to avoid.
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
    assert "not on a backup drive yet" in text, f"the neutral state is missing: {text!r}"
    assert "⚠" not in text, "a state the reader cannot clear was rendered as a warning"
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


def _pips(ui: Page) -> str:
    return ui.eval_on_selector("#custody-pips", "el => el.textContent")


def test_a_library_with_no_registered_drive_reads_as_progress_not_risk(
    ui: Page, app_server
) -> None:
    """The neutral state, and it is reachable by a NEW user - not legacy-only.

    `organizer.py` has ONE `record_uploaded` call site, so a `files` row with no copy can only
    come from `execute(drive_uuid=None)`. After the CLI began registering its destination the
    single remaining caller that passes `None` is the **rclone** path, excluded on purpose:
    "always-online cloud, not drives-in-a-drawer". An rclone user therefore has *every* file in
    this state, permanently. Telling them their photos are at risk would be nagging them about
    a choice they made.
    """
    with Catalog(app_server.db) as catalog:
        _record(catalog, "sha-a", "A", "a.jpg")
        catalog._conn.execute("DELETE FROM file_copies")
        catalog._conn.execute("DELETE FROM drives")
        catalog._conn.commit()

    ui.reload()
    text = _strip(ui)
    assert "not on a backup drive yet" in text, f"neutral state missing: {text!r}"
    # Neutral, not amber: no warning marker, and not the at-risk tone.
    assert "⚠" not in text, f"progress was rendered as risk: {text!r}"
    assert (
        ui.eval_on_selector("#custody-line .safe, #custody-line .neutral", "el => el.className")
        != "at-risk"
    )


def test_risk_and_progress_are_told_apart_by_more_than_colour(ui: Page, app_server) -> None:
    """Colour alone cannot carry the distinction, so a marker does too."""
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        _record(catalog, "sha-a", "A", "a.jpg")

    ui.reload()
    risky = _strip(ui)
    assert "in only one place" in risky
    assert "⚠" in risky, f"the amber state carries no non-colour marker: {risky!r}"


def test_orphans_do_not_drag_the_strip_but_are_not_papered_over(ui: Page, app_server) -> None:
    """The gap this state machine had to close.

    Files with no copy at all are a Stats finding, so they must not hold the rail's floor at
    zero and leave it with nothing to say. But excluding them from the floor and keeping the
    word "every" would claim something false about them - the original defect, one level down.
    So a library with orphans keeps the COUNT wording; only a clean one gets the universal.
    """
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        catalog.upsert_drive(uuid="B", label="Drive B")
        _record(catalog, "sha-a", "A", "a.jpg")
        _record(catalog, "sha-a", "B", "a.jpg")
        _record(catalog, "sha-orphan", "A", "orphan.jpg")
        catalog._conn.execute("DELETE FROM file_copies WHERE sha256 = 'sha-orphan'")
        catalog._conn.commit()

    ui.reload()
    text = _strip(ui)
    assert "every file" not in text, (
        f"a universal was claimed while a file has no copy at all: {text!r}"
    )
    assert "1 file in 2 places" in text, f"the drive-held files are not reported: {text!r}"
    # The orphan COUNT belongs to Stats, not the rail.
    assert "not on a drive yet" not in text


def test_the_orphan_count_is_still_reachable_on_stats(ui: Page, app_server) -> None:
    """It found a real defect on its first day; moving it off the rail must not bury it."""
    with Catalog(app_server.db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        _record(catalog, "sha-a", "A", "a.jpg")
        _record(catalog, "sha-orphan", "A", "orphan.jpg")
        catalog._conn.execute("DELETE FROM file_copies WHERE sha256 = 'sha-orphan'")
        catalog._conn.commit()

    ui.reload()
    ui.click('button[data-screen="stats"]')
    stats = ui.locator("#screen-stats")
    expect(stats).to_contain_text("not on a registered drive")
    assert "at risk (0 drives)" not in stats.text_content(), (
        "still worded as an incomplete step rather than as the inconsistency it now is"
    )


def test_the_number_is_the_file_floor_even_when_a_third_drive_exists(ui: Page, app_server) -> None:
    """The guard that can actually catch the original defect coming back.

    Every other test here has `places == floor`, so swapping one for the other renders the same
    string and nothing goes red - proved by mutation. Three registered drives all holding
    copies, with every file on only two of them, is the smallest fixture where the per-drive
    count and the per-file floor disagree: `places` is 3, the floor is 2. "every file in 3
    places" would be false for every file in the library.
    """
    with Catalog(app_server.db) as catalog:
        for uuid in ("A", "B", "C"):
            catalog.upsert_drive(uuid=uuid, label=f"Drive {uuid}")
        # a.jpg on A+B, b.jpg on B+C: all three drives hold copies, no file is on three.
        _record(catalog, "sha-a", "A", "a.jpg")
        _record(catalog, "sha-a", "B", "a.jpg")
        _record(catalog, "sha-b", "B", "b.jpg")
        _record(catalog, "sha-b", "C", "b.jpg")

    ui.reload()
    text = _strip(ui)
    assert "every file in 2 places" in text, f"the file floor is not the number: {text!r}"
    assert "3 places" not in text, f"the per-drive count is the number again: {text!r}"
    assert _pips(ui).count("▪") == 2, "the pips followed the drive count, not the weakest file"
