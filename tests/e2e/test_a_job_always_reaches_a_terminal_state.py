"""A job that ends on the server always ends on the screen.

**The defect, from a real CI trace.** `streamJob`'s ``es.onerror = () => es.close()`` closed the
event stream and **never called ``onDone``**, so `awaitJob`'s promise never resolved and
`runJob` awaited it forever: `progress.stop()`, `setJob(null)` and the whole
onCancelled/onSuccess/onError branch never ran. The screen stayed on the card it had before the
run started - **no outcome, no error, and no way for the person to learn the job was gone**.

Observed as: `POST /api/ingest/archives/run` 200, `POST /api/jobs/<id>/cancel` **202 accepted**,
and then **no `/api/jobs/<id>/events` request at all**. The cancel is awaited BEFORE the stream is
opened, so a job that finishes first is already reaped when the stream is attempted, the
EventSource errors, and the silence begins.

**Why this is not the archive screen's test.** `runJob` and `streamJob` are shared by every job
surface - organize, backup, verify, migrate, rescan, ingest, thirteen call sites by the module's
own count. The defect lives in the shared skeleton, so it is asserted here through organize: if
it were pinned only where it surfaced, the other twelve would stay silent.

**The invariant, not the incident.** The reproduction does not race a cancel - a timing test
would pass on a fast machine and prove nothing. It makes the stream fail outright, which is the
general case the incident was one instance of, and asserts the screen still reaches a terminal
state. It fails on `cf4b1af` because the screen FREEZES, not because a timeout expired.

**Checked against §4's sixteenth member.** Every assertion waits on something that can only
BECOME true - a result card's text after a run that had none. Nothing here waits on
`to_have_count(0)`, on a cleared container, or on text a previous render could have left: the
organize result is empty until this run writes it.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect


def test_a_run_whose_event_stream_dies_still_reports_an_outcome(
    ui: Page, tmp_path: Path, library
) -> None:
    """THE INVARIANT. The stream is killed outright; the screen must still say something."""
    source = library(3, name="Lib")
    ui.route("**/api/jobs/*/events*", lambda route: route.abort())

    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")

    # `#org-result` holds the preview card here, so this waits on a WORD that only a terminal
    # outcome can add - not on the element, which already exists and is already populated.
    expect(ui.locator("#org-result")).to_contain_text(
        "lost contact", timeout=30_000, ignore_case=True
    )


def test_the_trigger_is_released_when_the_stream_dies(ui: Page, tmp_path: Path, library) -> None:
    """A frozen promise also leaves the button dead forever, which is the same silence wearing
    another face: nothing to read, and nothing to press."""
    source = library(3, name="Lib")
    ui.route("**/api/jobs/*/events*", lambda route: route.abort())

    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")

    expect(ui.locator("#org-dedup")).to_be_enabled(timeout=30_000)


def test_an_ordinary_run_is_unaffected(ui: Page, tmp_path: Path, library) -> None:
    """The cry-wolf half. A fix that reported lost contact on every run would satisfy both tests
    above and destroy the product."""
    source = library(3, name="Lib")
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")

    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    expect(ui.locator("#org-result")).not_to_contain_text("lost contact")
