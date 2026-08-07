"""Cancel clicked before the server names the job is queued, never dropped.

**Found from the first CI trace this project ever captured** (2026-08-07). A "flaky"
`test_cancelling_leaves_a_staging_tree_the_next_run_can_clear` turned out to be a product race:
every click landed, and `POST /api/jobs/{id}/cancel` was **never sent**.

`runJob` reveals the progress card - which contains the Cancel button - and then awaits the
start request. `setJob` only lands when that request returns, so for its whole duration the
handler's `if (<job>) return api(...)` read a null id and returned having done nothing: no
request, no message, no trace. The job ran to completion.

The window is milliseconds on a fast machine and nobody reaches it; it is wide on a loaded
machine, a large archive or a cloud mount - which is when stopping matters most.

**Asserted on the REQUEST, not on the run ending cancelled.** Whether the work stops in time is
a second race owned by the server - a small archive can finish first, which is honest and is why
`onSuccess` still renders. What this fixes is whether the user's click is HONOURED, and the
request is that property exactly. Asserting the downstream outcome would make the test depend on
the machine again, which is the mistake that let this hide for four runs.

**The window is constructed, not waited for**, by delaying the start response inside the page.
The click itself stays exactly as a user makes it.

**What is deliberately NOT asserted here.** That the intent does not survive a run - `runJob`
clears it in a `finally`, so a refusal, an abort and a throw are one line - is real and is not
tested through a completed run: widening the window also delays when the client subscribes to
the job's event stream, so a completing run becomes an artifact of the construction rather than
a property of the product. Asserting it that way would be measuring the test.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from playwright.sync_api import Page, Request, expect

_RUN = "/api/ingest/archives/run"


def _zip(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)
    path.write_bytes(buf.getvalue())


def _hold_the_start_response(ui: Page, ms: int) -> None:
    """Delay the start RESPONSE in the page, so the no-job-yet window is a known length.

    Page-side rather than `page.route`: a sync route handler runs on the test thread, so
    sleeping in it races the very click being measured.
    """
    ui.evaluate(
        """([needle, ms]) => {
            const original = window.fetch;
            window.fetch = (...args) => {
                const url = String(args[0] && args[0].url ? args[0].url : args[0]);
                if (url.includes(needle)) {
                    return new Promise((r) => setTimeout(() => r(original(...args)), ms));
                }
                return original(...args);
            };
        }""",
        [_RUN, ms],
    )


def _cancels(ui: Page) -> list[str]:
    """Every cancel request the page makes, recorded as it happens."""
    seen: list[str] = []
    ui.on("request", lambda r: seen.append(r.url) if _is_cancel(r) else None)
    return seen


def _is_cancel(request: Request) -> bool:
    return request.method == "POST" and "/cancel" in request.url


def _to_the_confirm(ui: Page, tmp_path: Path, *, photos: int = 60) -> None:
    source, destination = tmp_path / "src", tmp_path / "dest"
    _zip(
        source / "photos.zip",
        {
            f"Takeout/a/IMG_{i:04d}.jpg": b"\xff\xd8" + bytes([i % 251]) * 90_000
            for i in range(photos)
        },
    )
    ui.click('button[data-screen="import"]')
    ui.fill("#rc-takeout", str(source))
    ui.fill("#rc-dest", str(destination))
    ui.click("#rc-preview")
    expect(ui.locator("[data-testid='rc-confirm']")).to_be_visible(timeout=30_000)


def test_a_cancel_clicked_before_the_job_exists_is_still_sent(ui: Page, tmp_path: Path) -> None:
    """THE DEFECT. Before the fix this sent nothing at all, silently."""
    _to_the_confirm(ui, tmp_path)
    sent = _cancels(ui)
    _hold_the_start_response(ui, 1_500)

    ui.click("[data-testid='rc-confirm']")
    expect(ui.locator("#rc-cancel")).to_be_visible()  # the card is up; the job has no name yet
    ui.click("#rc-cancel")

    # Fires the instant `setJob` lands, which is when the held response arrives.
    expect(ui.locator("#rc-cancel")).to_have_text("Stopping…", timeout=2_000)
    ui.wait_for_timeout(3_000)
    assert sent, "the click was dropped: no cancel request was ever sent for this job"
    assert "/cancel" in sent[0]


def test_the_click_is_acknowledged_before_the_cancel_can_land(ui: Page, tmp_path: Path) -> None:
    """Silence is what hid this for four CI runs, so the click answers when it is ACCEPTED.

    Asserted while the start response is still held, so the acknowledgement cannot be coming
    from the cancel having taken effect.
    """
    _to_the_confirm(ui, tmp_path)
    _hold_the_start_response(ui, 4_000)

    ui.click("[data-testid='rc-confirm']")
    ui.click("#rc-cancel")

    expect(ui.locator("#rc-cancel")).to_have_text("Stopping…", timeout=2_000)
    expect(ui.locator("#rc-cancel")).to_be_disabled()


def test_no_cancel_button_is_wired_outside_create_progress() -> None:
    """One home, so a tenth run block cannot arrive with the old `if (<job>) return` shape.

    Nine buttons carried it - organize, verify, import, trips, backup, migrate, bake and both
    undo paths - because each was wired where its job variable lived. `createProgress` owns the
    button inside the card it shows, which is the only place that knows a run is in flight
    before the server has named it.
    """
    source = (
        Path(__file__).resolve().parents[2]
        / "packages/truestill-app/src/truestill_app/static/app.js"
    )
    text = source.read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in text.splitlines()
        if '-cancel").onclick' in line
        and "pk-cancel" not in line
        and not line.lstrip().startswith("//")
    ]
    assert not offenders, (
        "a cancel button is wired outside createProgress, so it cannot see a run that has "
        "started but is not yet named:\n  " + "\n  ".join(offenders)
    )


def test_every_run_block_has_a_wired_cancel_button(ui: Page) -> None:
    """The cry-wolf half: proves the guard above is not satisfied by wiring NOTHING.

    Reads the live page rather than the source - a handler assigned to an id that no block
    stamps would satisfy a grep and reach no button.
    """
    wired = ui.evaluate(
        """() => Array.from(document.querySelectorAll('.progress-wrap'))
              .map((c) => {
                  const b = c.querySelector('button');
                  return { id: b && b.id, wired: !!(b && b.onclick) };
              })"""
    )
    assert wired, "no run blocks were found at all - this asserts nothing"
    unwired = [w["id"] for w in wired if not w["wired"]]
    assert not unwired, f"run blocks whose Cancel does nothing: {unwired}"
