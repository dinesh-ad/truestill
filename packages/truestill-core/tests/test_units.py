"""One byte formatter, one unit, one answer.

The same 1,997 files rendered as "5.2 GB" in the panel and "4.9 GB" on Stats. That was never a
formatter disagreement - it was ONE formatter fed two different numbers, and the difference
(296,509,852 bytes) was exactly the size of the backup drive. `library_status` summed
`total_size` across every drive, so backing your library up made it report as bigger. That half
lives in `test_library_bytes_count_content_not_copies.py`.

This half is the formatter itself. It existed three times - once in JS and twice inline as
`f"{size / 1024**3:.1f} GB"` - and the two Python copies were 1024-based while calling the
result GB.

DECIMAL, and the one-line defence: the number a user checks a size against is their drive's
advertised capacity, and every drive is sold in decimal GB. GNOME Files and macOS Finder agree.
A 1024-based number labelled "GB" is off by 7% at that scale and reads as truestill being wrong
about their disk.
"""

from __future__ import annotations

import pytest
from truestill_core.units import format_bytes


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 B"),
        (1, "1 B"),
        (999, "999 B"),
        (1_000, "1.0 KB"),
        (1_500, "1.5 KB"),
        (1_000_000, "1.0 MB"),
        (296_509_852, "296.5 MB"),
        (1_000_000_000, "1.0 GB"),
        # THE NUMBER THIS EXISTS FOR: the real library, which read 4.9 GB (1024-based) beside
        # 5.2 GB (1024-based over a doubled byte count) for the same photos.
        (5_298_094_843, "5.3 GB"),
        (1_000_000_000_000, "1.0 TB"),
    ],
)
def test_the_scale_is_decimal(value: int, expected: str) -> None:
    assert format_bytes(value) == expected


def test_whole_bytes_carry_no_decimal_point() -> None:
    """ "1.0 B" is not a size anyone writes."""
    assert format_bytes(512) == "512 B"


def test_it_does_not_run_off_the_end_of_the_scale() -> None:
    """A petabyte library is not this product's case, and a crash there would still be ours."""
    assert format_bytes(10**18).endswith("TB")


def test_a_negative_is_not_invented_into_a_size() -> None:
    """Sizes come from `stat` and from SUM(); neither should be negative, and if one ever is,
    printing "-1.0 GB" hides the defect better than showing the raw number does."""
    assert format_bytes(-1) == "0 B"
