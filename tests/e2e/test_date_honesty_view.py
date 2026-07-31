"""What the honesty view actually says on screen (audit (n), step 2).

Asserted through the browser because every claim here is a rendered sentence, and §6 gives that
to this lane. Two cases, both taken from the real library rather than invented: a catalog where
every row predates the record (the maintainer's, 2,300 of them), and a group so small its share
rounds to zero (2 undated files in a 600-file sample).
"""

from __future__ import annotations

import json
import re

from playwright.sync_api import Page, expect

#: A share of exactly zero, and NOT the "0%" inside "100%" - which is what a naive substring
#: assertion matches, and did while this test was being written. The guard has to be as precise
#: as the thing it guards.
ZERO_SHARE = re.compile(r"(?<!\d)0%")


def _stats(route, dates: dict) -> None:
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "safety": {
                    "total_files": 10,
                    "total_size": 1,
                    "photos": 10,
                    "videos": 0,
                    "audio": 0,
                    "files_on_two_plus_drives": 0,
                    "files_on_one_drive": 10,
                    "files_on_zero_drives": 0,
                    "never_verified_files": 0,
                    "drives": [],
                    "zero_drive_samples": [],
                },
                "completeness": {
                    "undated_files": 0,
                    "timeline_files": 10,
                    "side_bin_files": 0,
                    "near_duplicates_flagged": 0,
                    "undated_samples": [],
                    "exact_duplicates_note": "",
                },
                "shape": {
                    "by_year": [],
                    "by_format": {"photos": {}, "videos": {}},
                    "oldest_capture": None,
                    "newest_capture": None,
                },
                "dates": dates,
                "complexity": "test",
            }
        ),
    )


def test_a_library_that_predates_the_record_reads_as_normal_not_broken(ui: Page) -> None:
    """The real-catalog case. It must not look like damage, a gap, or the user's mistake."""
    ui.route(
        "**/api/library/stats",
        lambda r: _stats(
            r,
            {
                "rows": [
                    {
                        "label": "Not recorded",
                        "detail": "These were organized before truestill "
                        "started keeping this note. Their dates are unaffected - only the record of "
                        "where each date came from is missing.",
                        "files": 2300,
                        "review": False,
                        "evidence": None,
                        "not_recorded": True,
                    }
                ],
                "total": 2300,
                "recorded": 0,
                "not_recorded": 2300,
            },
        ),
    )
    ui.click('button[data-screen="stats"]')

    result = ui.locator("#stats-result")
    expect(result).to_contain_text("How your dates were determined", timeout=30_000)
    expect(result).to_contain_text("Not recorded")
    expect(result).to_contain_text("That is normal and nothing is wrong with them")
    expect(result).to_contain_text("dates are unaffected")
    # The one number that must NOT appear: a share for a group that has no share.
    expect(result).not_to_contain_text(ZERO_SHARE)


def test_a_group_too_small_to_round_still_shows_a_share(ui: Page) -> None:
    """Found on the real library: 2 undated of 600 rendered as "0%" - "none" for something listed."""
    ui.route(
        "**/api/library/stats",
        lambda r: _stats(
            r,
            {
                "rows": [
                    {
                        "label": "From the photo's own data",
                        "detail": "The camera recorded it.",
                        "files": 598,
                        "review": False,
                        "evidence": "tag: DateTimeOriginal",
                        "not_recorded": False,
                    },
                    {
                        "label": "No date found",
                        "detail": "Filed under Undated.",
                        "files": 2,
                        "review": True,
                        "evidence": None,
                        "not_recorded": False,
                    },
                ],
                "total": 600,
                "recorded": 600,
                "not_recorded": 0,
            },
        ),
    )
    ui.click('button[data-screen="stats"]')

    result = ui.locator("#stats-result")
    expect(result).to_contain_text("2 files", timeout=30_000)
    expect(result).to_contain_text("<1%")
    expect(result).not_to_contain_text(ZERO_SHARE)
    # And the evidence rides along with the tier, which is the point of showing it at all.
    expect(result).to_contain_text("tag: DateTimeOriginal")
