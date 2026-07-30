"""Video UTC CreateDate ladder (backlog ``(uu)``).

Rungs 1 (CreationDate), 2 (TimeZone), 4 (filename+duration) are live.
Rung 3 (GPS) is wired but unexercised by the soak corpus - synthetic only.
Rung 5 corroborates only and never chooses an offset alone.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from truestill_core.dates import (
    FILENAME_OFFSET_EPSILON,
    FILENAME_OFFSET_MAX,
    FILENAME_OFFSET_STEP,
    NOT_PROVEN_UTC,
    LadderHit,
    gps_confirms_utc,
    parse_duration,
    parse_inferred_date_tag,
    resolve_capture_datetime,
    stills_corroborate_local,
    try_rung_filename_duration,
    try_rung_timezone,
    unique_filename_offset,
)
from truestill_core.exif import REQUESTED_TAGS
from truestill_core.models import DateSource


def test_ladder_tag_requests_are_wired() -> None:
    for tag in ("TimeZone", "GPSDateStamp", "GPSTimeStamp", "Duration"):
        assert tag in REQUESTED_TAGS


def test_safety_bounds_are_the_documented_values() -> None:
    # Half-hour grid, ±14 h, ε = 3 s - the safety of this feature.
    assert timedelta(minutes=30) == FILENAME_OFFSET_STEP
    assert timedelta(hours=14) == FILENAME_OFFSET_MAX
    assert timedelta(seconds=3) == FILENAME_OFFSET_EPSILON


def test_rung1_creationdate_still_wins() -> None:
    when, source, tag = resolve_capture_datetime(
        Path("IMG_1234.mov"),
        {
            "CreationDate": "2014:08:17 14:28:39+05:30",
            "CreateDate": "2014:08:17 08:58:39",
            "TimeZone": "+05:30",
            "MIMEType": "video/quicktime",
        },
    )
    assert when == datetime(2014, 8, 17, 14, 28, 39)
    assert source is DateSource.EXIF
    assert tag == "CreationDate"


def test_rung2_timezone_shifts_container_utc() -> None:
    when, source, tag = resolve_capture_datetime(
        Path("MVI_2550.MOV"),
        {
            "CreateDate": "2014:08:17 07:58:39",
            "TimeZone": "+06:30",
            "Duration": "1.46 s",
            "MIMEType": "video/quicktime",
        },
    )
    assert when == datetime(2014, 8, 17, 14, 28, 39)
    assert source is DateSource.INFERRED_LOCAL
    assert tag == "CreateDate|TimeZone|+06:30"


def test_canon_mvi_2550_stays_at_142839_regression() -> None:
    """REGRESSION: Canon ``MVI_2550.MOV`` must stay 14:28:39 through the (uu) change.

    DateTimeOriginal wins over CreateDate+TimeZone. A feature that fixes two Android clips
    and moves this file is not a fix.
    """
    when, source, tag = resolve_capture_datetime(
        Path("MVI_2550.MOV"),
        {
            "DateTimeOriginal": "2014:08:17 14:28:39",
            "CreateDate": "2014:08:17 07:58:39",
            "TimeZone": "+06:30",
            "Duration": "1.46 s",
            "MIMEType": "video/quicktime",
        },
    )
    assert when == datetime(2014, 8, 17, 14, 28, 39)
    assert source is DateSource.EXIF
    assert tag == "DateTimeOriginal"


def test_rung4_android_filename_plus_duration() -> None:
    # Soak VID_20140817_102145: CreateDate is UTC end; filename is local start.
    when, source, tag = resolve_capture_datetime(
        Path("VID_20140817_102145.mp4"),
        {
            "CreateDate": "2014:08:17 04:54:24",
            "Duration": "0:02:38",
            "MIMEType": "video/mp4",
        },
    )
    assert when == datetime(2014, 8, 17, 10, 21, 45)
    assert source is DateSource.INFERRED_LOCAL
    parsed = parse_inferred_date_tag(tag or "")
    assert parsed is not None
    assert parsed.evidence == "filename:VID_"
    assert parsed.offset == timedelta(hours=5, minutes=30)


def test_rung4_works_under_organized_filename_prefix() -> None:
    when, source, _ = resolve_capture_datetime(
        Path("20140817_045424_VID_20140817_102145.mp4"),
        {
            "CreateDate": "2014:08:17 04:54:24",
            "Duration": "0:02:38",
            "MIMEType": "video/mp4",
        },
    )
    assert when == datetime(2014, 8, 17, 10, 21, 45)
    assert source is DateSource.INFERRED_LOCAL


def test_rung4_second_android_clip() -> None:
    when, source, tag = resolve_capture_datetime(
        Path("VID_20140817_155317.mp4"),
        {
            "CreateDate": "2014:08:17 10:25:33",
            "Duration": "0:02:14",
            "MIMEType": "video/mp4",
        },
    )
    assert when == datetime(2014, 8, 17, 15, 53, 17)
    assert source is DateSource.INFERRED_LOCAL
    assert tag == "CreateDate|filename:VID_|+05:30"


def test_messenger_wa_filename_is_not_an_offset_source() -> None:
    # Native WhatsApp dash form has no HHMMSS device stamp - stays not_proven_utc.
    when, source, tag = resolve_capture_datetime(
        Path("VID-20140817-WA0001.mp4"),
        {
            "CreateDate": "2014:08:17 04:54:24",
            "Duration": "0:02:38",
            "MIMEType": "video/mp4",
        },
    )
    assert when == datetime(2014, 8, 17, 4, 54, 24)
    assert source is DateSource.EXIF
    assert tag == f"CreateDate|{NOT_PROVEN_UTC}"


def test_messenger_embedded_device_stamp_is_refused_as_offset_source() -> None:
    # FB_VID_YYYYMMDD_HHMMSS is a messenger name that *contains* a device-local stamp.
    # Without the messenger refusal it would become an offset source (mutation-tested).
    when, source, tag = resolve_capture_datetime(
        Path("FB_VID_20140817_102145.mp4"),
        {
            "CreateDate": "2014:08:17 04:54:24",
            "Duration": "0:02:38",
            "MIMEType": "video/mp4",
        },
    )
    assert when == datetime(2014, 8, 17, 4, 54, 24)
    assert source is DateSource.EXIF
    assert tag == f"CreateDate|{NOT_PROVEN_UTC}"


def test_not_proven_utc_fallthrough_keeps_digits_as_local() -> None:
    when, source, tag = resolve_capture_datetime(
        Path("clip.mp4"),
        {"CreateDate": "2025:08:04 11:16:38", "MIMEType": "video/mp4"},
    )
    assert when == datetime(2025, 8, 4, 11, 16, 38)
    assert source is DateSource.EXIF
    assert tag == "CreateDate|not_proven_utc"


def test_still_createdate_is_untouched_by_the_ladder() -> None:
    when, source, tag = resolve_capture_datetime(
        Path("IMG_0001.jpg"),
        {"CreateDate": "2025:08:04 11:16:38", "MIMEType": "image/jpeg"},
    )
    assert when == datetime(2025, 8, 4, 11, 16, 38)
    assert source is DateSource.EXIF
    assert tag == "CreateDate"


def test_rung3_gps_alone_does_not_choose_an_offset() -> None:
    # Synthetic: corpus has no GPS time. GPS proves UTC but cannot invent a zone.
    when, source, tag = resolve_capture_datetime(
        Path("clip.mp4"),
        {
            "CreateDate": "2014:08:17 04:54:24",
            "GPSDateStamp": "2014:08:17",
            "GPSTimeStamp": "04:54:24",
            "MIMEType": "video/mp4",
        },
    )
    assert when == datetime(2014, 8, 17, 4, 54, 24)
    assert source is DateSource.EXIF
    assert tag == "CreateDate|not_proven_utc"
    assert gps_confirms_utc(
        {"GPSDateStamp": "2014:08:17", "GPSTimeStamp": "04:54:24"},
        datetime(2014, 8, 17, 4, 54, 24),
    )


def test_rung3_gps_enriches_filename_evidence_synthetically() -> None:
    # Synthetic only - unexercised by the soak corpus.
    when, source, tag = resolve_capture_datetime(
        Path("VID_20140817_102145.mp4"),
        {
            "CreateDate": "2014:08:17 04:54:24",
            "Duration": "0:02:38",
            "GPSDateStamp": "2014:08:17",
            "GPSTimeStamp": "04:54:24",
            "MIMEType": "video/mp4",
        },
    )
    assert when == datetime(2014, 8, 17, 10, 21, 45)
    assert source is DateSource.INFERRED_LOCAL
    assert tag == "CreateDate|GPSDateStamp+filename:VID_|+05:30"


def test_rung5_corroborates_but_never_returns_an_offset() -> None:
    local = datetime(2014, 8, 17, 10, 21, 45)
    still = datetime(2014, 8, 17, 10, 21, 29)
    assert stills_corroborate_local(local, [still]) is True
    assert stills_corroborate_local(local, [datetime(2014, 8, 17, 12, 0, 0)]) is False
    assert stills_corroborate_local(local, []) is None
    # The helper's return type is bool|None - never a timedelta / offset.
    result = stills_corroborate_local(local, [still])
    assert not isinstance(result, timedelta)


def test_unique_match_refuses_when_two_offsets_fit() -> None:
    create = datetime(2014, 8, 17, 4, 54, 24)
    filename = datetime(2014, 8, 17, 10, 21, 45)
    duration = timedelta(minutes=2, seconds=38)
    assert unique_filename_offset(create, filename, duration) == timedelta(hours=5, minutes=30)
    # Widen epsilon until a neighbouring half-hour also fits -> refuse.
    wide = timedelta(minutes=35)
    assert unique_filename_offset(create, filename, duration, epsilon=wide) is None


def test_rungs_are_independent_typed_attempts() -> None:
    """Each converting rung returns LadderHit | None; orchestration is a sequence, not nests."""
    create = datetime(2014, 8, 17, 7, 58, 39)
    tz_hit = try_rung_timezone({"TimeZone": "+06:30"}, create)
    assert isinstance(tz_hit, LadderHit)
    assert tz_hit.local == datetime(2014, 8, 17, 14, 28, 39)
    assert tz_hit.evidence == "TimeZone"

    assert try_rung_timezone({}, create) is None

    fn_hit = try_rung_filename_duration(
        Path("VID_20140817_102145.mp4"),
        {"CreateDate": "2014:08:17 04:54:24", "Duration": "0:02:38"},
        datetime(2014, 8, 17, 4, 54, 24),
    )
    assert isinstance(fn_hit, LadderHit)
    assert fn_hit.offset == timedelta(hours=5, minutes=30)
    assert fn_hit.evidence == "filename:VID_"


def test_parse_duration_shapes() -> None:
    assert parse_duration("0:02:38") == timedelta(minutes=2, seconds=38)
    assert parse_duration("1.46 s") == timedelta(seconds=1.46)
    assert parse_duration(2.52) == timedelta(seconds=2.52)
