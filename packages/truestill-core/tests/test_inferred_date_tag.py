"""Provenance ``date_tag`` for inferred-local / not-proven-UTC CreateDate decisions.

Pins the machine-parseable format a later pass must read.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from truestill_core.dates import (
    DATE_TAGS,
    INFERRED_DATE_TAG_SEP,
    NOT_PROVEN_UTC,
    format_inferred_date_tag,
    format_not_proven_utc_tag,
    format_offset,
    parse_inferred_date_tag,
    parse_offset,
)
from truestill_core.models import DateSource


def test_inferred_local_is_a_distinct_date_source() -> None:
    assert DateSource.INFERRED_LOCAL.value == "inferred_local"
    assert DateSource.INFERRED_LOCAL is not DateSource.EXIF


def test_pipe_separator_cannot_collide_with_date_tag_names() -> None:
    # Exiftool Group:Tag uses colon; our DATE_TAGS and MakerNotes evidence use colon too.
    # The provenance field separator must stay out of every name we put in field 0 / 1.
    for name in (
        *DATE_TAGS,
        "TimeZone",
        "Canon:TimeZone",
        "MakerNotes:TimeZone",
        "GPSDateStamp",
        "GPSTimeStamp",
        "filename:VID_",
        "filename:IMG_",
        "GPSDateStamp+filename:VID_",
        NOT_PROVEN_UTC,
    ):
        assert INFERRED_DATE_TAG_SEP not in name


@pytest.mark.parametrize(
    ("offset", "text"),
    [
        (timedelta(hours=5, minutes=30), "+05:30"),
        (timedelta(hours=6, minutes=30), "+06:30"),
        (timedelta(hours=-5), "-05:00"),
        (timedelta(0), "+00:00"),
        (timedelta(hours=14), "+14:00"),
    ],
)
def test_offset_round_trip(offset: timedelta, text: str) -> None:
    assert format_offset(offset) == text
    assert parse_offset(text) == offset


def test_create_date_filename_vid_round_trips() -> None:
    # Ruling example: must survive encode -> decode -> encode unchanged.
    tagged = format_inferred_date_tag("CreateDate", "filename:VID_", timedelta(hours=5, minutes=30))
    assert tagged == "CreateDate|filename:VID_|+05:30"
    parsed = parse_inferred_date_tag(tagged)
    assert parsed is not None
    assert parsed.container_tag == "CreateDate"
    assert parsed.evidence == "filename:VID_"
    assert parsed.offset == timedelta(hours=5, minutes=30)
    assert format_inferred_date_tag(parsed.container_tag, parsed.evidence, parsed.offset) == tagged


def test_timezone_evidence_round_trips() -> None:
    tagged = format_inferred_date_tag("CreateDate", "TimeZone", timedelta(hours=6, minutes=30))
    assert tagged == "CreateDate|TimeZone|+06:30"
    parsed = parse_inferred_date_tag(tagged)
    assert parsed is not None
    assert parsed.evidence == "TimeZone"
    assert parsed.offset == timedelta(hours=6, minutes=30)


def test_combined_gps_and_filename_evidence_uses_plus_not_pipe() -> None:
    tagged = format_inferred_date_tag(
        "CreateDate",
        "GPSDateStamp+filename:VID_",
        timedelta(hours=5, minutes=30),
    )
    assert tagged == "CreateDate|GPSDateStamp+filename:VID_|+05:30"
    assert tagged.count(INFERRED_DATE_TAG_SEP) == 2
    parsed = parse_inferred_date_tag(tagged)
    assert parsed is not None
    assert parsed.evidence == "GPSDateStamp+filename:VID_"


def test_not_proven_utc_is_recorded_not_absent_and_not_alarming() -> None:
    tagged = format_not_proven_utc_tag("CreateDate")
    assert tagged == "CreateDate|not_proven_utc"
    assert "no_utc_evidence" not in tagged
    parsed = parse_inferred_date_tag(tagged)
    assert parsed is not None
    assert parsed.container_tag == "CreateDate"
    assert parsed.evidence == NOT_PROVEN_UTC
    assert parsed.offset is None
    assert format_not_proven_utc_tag(parsed.container_tag) == tagged


def test_plain_exif_tags_are_not_inferred_provenance() -> None:
    for tag in ("CreationDate", "DateTimeOriginal", "CreateDate", "MediaCreateDate"):
        assert parse_inferred_date_tag(tag) is None


def test_format_rejects_pipe_inside_fields() -> None:
    with pytest.raises(ValueError, match="must not contain"):
        format_inferred_date_tag("Create|Date", "filename:VID_", timedelta(hours=5))
    with pytest.raises(ValueError, match="must not contain"):
        format_not_proven_utc_tag("Create|Date")


def test_format_inferred_refuses_not_proven_utc_token() -> None:
    with pytest.raises(ValueError, match="format_not_proven_utc_tag"):
        format_inferred_date_tag("CreateDate", NOT_PROVEN_UTC, timedelta(hours=5))
