"""The three run gates read the completion marker, never prose the preview already shows.

Run 33947262070 (2026-09-05, webkit): `tests/e2e/test_the_confirm_word_names_the_run.py` waited
for "organized" in `#org-result` after clicking the run, and the preview card had already written
"3 files will be organized." into that region. The wait passed before the run was posted, the
second duplicate check was refused with `DriveBusy` while the first run held the drive, and the
assertion that mattered polled text that could never change. `test_busy_state.py` had the same
gate; `test_ui_regressions.py` waited on "3 photos · 1 video", which the backup preview writes
into `#bk-result` before the run.

The gates now wait on `.done-mark`, emitted only by `completionCard` in `app.js`, whose only
callers are the two completion renderers. This pins them there.

**Here, not in `tests/e2e/`.** It reads three test files as source and needs no browser, so
`make check` sees a gate reverted to prose on every push; in the browser lane it would be seen
nightly. `tests/e2e/test_the_preview_does_not_pre_satisfy_the_run_gate.py` holds the other half
of the class and stays where it is, because it drives a page. `ENGINEERING_STANDARD.md` §4,
eighty-seventh member.
"""

from __future__ import annotations

from pathlib import Path

E2E = Path(__file__).resolve().parents[3] / "tests/e2e"

GATES = (
    ("test_the_confirm_word_names_the_run.py", "#org-result .done-mark"),
    ("test_busy_state.py", "#org-result .done-mark"),
    ("test_ui_regressions.py", "#bk-result .done-mark"),
)


def test_the_three_run_gates_read_the_marker() -> None:
    for name, marker in GATES:
        text = (E2E / name).read_text(encoding="utf-8")
        assert f'expect(ui.locator("{marker}"))' in text, (
            f"{name}: the run gate no longer waits on {marker}"
        )
