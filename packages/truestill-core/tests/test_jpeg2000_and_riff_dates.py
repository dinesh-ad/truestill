"""Two depth/breadth gaps found in the sample corpora. `(acl)` and `(acm)`.

Both were recorded 2026-08-10 with a stated precondition, and both preconditions were checked
against the real files before anything was added here - see each test.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.dates import resolve_capture_datetime
from truestill_core.exif import REQUESTED_TAGS
from truestill_core.models import DateSource
from truestill_core.organizer import IMAGE_EXTENSIONS, MEDIA_EXTENSIONS


@pytest.mark.parametrize("ext", [".jp2", ".jpf", ".j2k"])
def test_jpeg_2000_reaches_the_pipeline_at_all(ext: str) -> None:
    """`(acl)`. Absent from the gate, such a file was never handed to exiftool: not dated, not
    categorised, not organised - silently skipped rather than reported.

    **The entry's precondition, checked before adding these:** recognition is one answer and
    *hashing* is another (`format-coverage-audit.md` records RAW differing on exactly that).
    Pillow was confirmed to open the real `jpg2000/balloon.jp2` and downsample it for a
    perceptual hash, so near-duplicate detection works rather than merely not crashing.
    """
    assert ext in IMAGE_EXTENSIONS
    assert ext in MEDIA_EXTENSIONS


def test_a_riff_date_is_requested_scoped_to_riff_and_not_globally() -> None:
    """`(acm)`. The entry's warning, honoured: `DateCreated` is **also** an IPTC field on stills
    where it means something else, so a bare request would feed the resolver a value it was never
    designed to weigh - and the corpora do contain IPTC `DateCreated`, including a malformed
    `2010:00:00`. Requesting `RIFF:DateCreated` returns nothing on those stills; verified against
    a real still that carries one.
    """
    assert "RIFF:DateCreated" in REQUESTED_TAGS
    assert "DateCreated" not in REQUESTED_TAGS, "an unscoped request would pull IPTC's field too"


def test_an_avi_with_only_a_riff_date_is_dated_by_it() -> None:
    """The real file: `avi/100_0306.AVI` carries `[RIFF] Date Created: 2020:08:28` and nothing
    else. One of the two AVIs in the corpora, so the rate is per-AVI rather than per-file.

    Date-only, which is why this waited: adopting it needed the resolver to accept a
    dayless-precision value, and `(add)` made it parse.
    """
    when, source, tag = resolve_capture_datetime(
        Path("100_0306.AVI"), {"DateCreated": "2020:08:28"}
    )
    assert when == datetime(2020, 8, 28)
    assert source is DateSource.EXIF
    assert tag == "DateCreated"


def test_a_riff_date_never_outranks_a_real_capture_time() -> None:
    """**CRY-WOLF HALF.** It is the weakest entry in the chain and must stay last: the other AVI
    in the corpora (`MVI_4823.AVI`) carries a precise `CreateDate` and no RIFF date, and a file
    carrying both must keep the time rather than collapsing to midnight.
    """
    when, source, tag = resolve_capture_datetime(
        Path("MVI_4823.AVI"),
        {"CreateDate": "2012:09:10 20:52:00", "DateCreated": "2020:08:28"},
    )
    assert when == datetime(2012, 9, 10, 20, 52), "the RIFF day overwrote a real capture time"
    assert source is DateSource.EXIF
    # `CreateDate` on a VIDEO is a UTC container stamp, so the existing evidence ladder marks it
    # `CreateDate|not_proven_utc` - untouched by this change and asserted loosely for that reason.
    # The tag matters here only as proof that the RIFF date did not win.
    assert tag is not None
    assert tag.startswith("CreateDate")


def test_a_riff_date_is_still_subject_to_the_sentinel_rules() -> None:
    """It enters the same chain, not beside it."""
    when, source, _ = resolve_capture_datetime(
        Path("c.AVI"), {"DateCreated": "1970:01:01 00:00:00"}
    )
    assert when is None
    assert source is DateSource.REJECTED_SENTINEL
