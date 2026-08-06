"""No developer language in anything a person can read.

Two were found by eye, on two screens - "Query cost: O(n) aggregate SQL over catalog tables;
grouped rollups only.." on Stats, and "In the CLI, this is --in-place." on Organize (twice, not
once). Two found by looking at two screens means the real number was unknown, so this is a sweep
with a gate rather than two fixes.

WHY THIS READS THE RENDERED PAGE AND NOT THE SOURCE, which is the part worth reading.

I wrote the source scanner first. It has to find string literals in `app.js`, and it desynced
twice, silently:

  1. `esc()` contains the regex `/[&<>"']/g`. A scanner that does not know JS regex literals
     starts a string on that quote and mis-parses everything after it.
  2. Fixing that, it still missed the Stats `--rclone` sentence, because that string is a
     TEMPLATE LITERAL NESTED INSIDE `${...}` of another template literal. Handling that needs a
     real JS parser, not a heuristic.

Both failures are silent: the scanner reported "3 hits, sweep clean" while blind to part of the
file. A guard that under-reports is worse than none, because it is believed. And even with a
perfect parser, "is this literal user-visible?" is undecidable from source - most literals are
ids, selectors and API paths.

The rendered page has neither problem. `innerText` is the definition of user-visible, so there
are no false positives from code and no parsing at all.

**The limit, stated rather than hidden:** this covers the states it navigates to. A string that
only appears in a rare branch - the no-trash refusal, a specific error - is not covered here.
That is a real gap and the trade is deliberate: complete coverage of what a user actually sees on
the seven screens beats a source scan that silently misses whole regions of the file.
"""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page

SCREENS = ("organize", "events", "import", "backups", "find", "stats", "settings")

#: Shapes that mean "this describes how we built it" rather than "this helps you decide or act".
DEVELOPER_LANGUAGE = re.compile(
    r"(?<![\w-])--[a-z][a-z-]{2,}"  # a flag offered as guidance
    r"|\bO\(\s*[n1]\s*\)"  # complexity annotation
    r"|\baggregate SQL\b|\bgrouped rollups?\b|\bquery (?:cost|plan)\b"
    r"|\bpayload\b|\bsha256\b|\bexit code\b|\bstderr\b|\bstdout\b|\btraceback\b"
    r"|\bin the CLI\b|\bon the command line\b"
    r"|\bfile_copies\b|\bcatalog schema\b|\bendpoint\b",
    re.I,
)

#: Deliberate, and the distinction the sweep turns on: a command someone is MEANT TO TYPE is not
#: jargon, it is the only route out. The no-trash refusal names `truestill clean-empty ...
#: --apply --permanent` because nothing else will remove those folders. `--rclone` names a path
#: the user chose themselves. Neither describes how we built anything.
ALLOWED = (
    "truestill clean-empty",
    "--rclone",
)


def _visible(ui: Page, screen: str) -> str:
    ui.click(f'.nav-item[data-screen="{screen}"]')
    ui.wait_for_timeout(400)
    return ui.eval_on_selector(f"#screen-{screen}", "el => el.innerText")


def _offences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if any(allowed in line for allowed in ALLOWED):
            continue
        match = DEVELOPER_LANGUAGE.search(line)
        if match:
            out.append(f"{match.group(0)!r} in: {line.strip()[:120]}")
    return out


@pytest.mark.parametrize("screen", SCREENS)
def test_no_screen_shows_developer_language(ui: Page, screen: str) -> None:
    ui.route(
        "**/api/library/stats**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "safety": {
                        "total_files": 12,
                        "files_one_drive": 3,
                        "files_two_plus": 9,
                        "files_on_zero_drives": 0,
                        "photos": 12,
                        "videos": 0,
                        "total_size": 5_298_094_843,
                        "never_verified_files": 0,
                        "drives": [],
                    },
                    "completeness": {},
                    "shape": {},
                    "dates": {"rows": [], "total": 0},
                }
            ),
        ),
    )
    offences = _offences(_visible(ui, screen))
    assert not offences, f"developer language on {screen}:\n  " + "\n  ".join(offences)


def test_the_organize_mode_hints_are_swept_in_every_mode(ui: Page) -> None:
    """The two known strings were BOTH on Organize and both behind a mode change, so the resting
    screen alone would not have caught either."""
    ui.click('.nav-item[data-screen="organize"]')
    for mode in ("copy", "move", "inplace"):
        ui.click(f'input[name="org-mode"][value="{mode}"]')
        ui.wait_for_timeout(300)
        offences = _offences(ui.eval_on_selector("#screen-organize", "el => el.innerText"))
        assert not offences, f"developer language in {mode} mode:\n  " + "\n  ".join(offences)


def test_the_guard_catches_the_two_that_were_actually_shipped() -> None:
    """A guard is not known to work until it has been seen to fail, and these are the real
    strings, not synthetic ones."""
    assert _offences("In the CLI, this is --in-place.")
    assert _offences("Query cost: O(n) aggregate SQL over catalog tables; grouped rollups only..")


def test_the_guard_spares_the_commands_a_user_is_meant_to_type() -> None:
    """The other half, and the one that decides whether this survives: a guard that fires on the
    no-trash refusal would be turned off, taking its real coverage with it."""
    assert not _offences("truestill clean-empty /home/you/Pictures --apply --permanent")
    assert not _offences("the destination is a cloud remote reached with --rclone, not a drive")
    for benign in (
        "Copy into an organized folder",
        "Same-drive: rename. Cross-drive: copy, verify, then delete source.",
        "2019-07-04 - Beach",
        "Files already sorted stay put.",
    ):
        assert not _offences(benign), benign
