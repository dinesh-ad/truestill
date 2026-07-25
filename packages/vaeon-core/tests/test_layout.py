"""LayoutTemplate: token grammar, undated collapse, and event placement."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

import pytest
from vaeon_core.layout import (
    DEFAULT_TEMPLATE,
    KNOWN_TOKENS,
    LayoutTemplate,
    RenderContext,
    TemplateError,
)


def _render(template: str, **ctx: object) -> str:
    return LayoutTemplate.parse(template).render(RenderContext(**ctx)).as_posix()  # type: ignore[arg-type]


def test_default_template_matches_historical_dated_structure() -> None:
    got = DEFAULT_TEMPLATE.render(
        RenderContext(category="WhatsApp", captured_at=datetime(2025, 8, 4, 11, 16))
    )
    assert got == PurePosixPath("WhatsApp/2025/08")


def test_default_template_collapses_undated_to_one_folder() -> None:
    got = DEFAULT_TEMPLATE.render(RenderContext(category="Camera", captured_at=None))
    assert got == PurePosixPath("Camera/Undated")  # not Camera// and not a guessed date


def test_event_member_uses_start_date_and_appends_event_folder() -> None:
    # Event start drives YYYY/MM (so a cross-month event stays whole) and the event folder is
    # appended because the default template has no explicit {event}.
    got = DEFAULT_TEMPLATE.render(
        RenderContext(
            category="Camera",
            captured_at=datetime(2026, 7, 2),
            event=(datetime(2026, 6, 30), "goa-trip"),
        )
    )
    assert got == PurePosixPath("Camera/2026/06/20260630_goa-trip")


def test_explicit_event_token_is_not_double_appended() -> None:
    got = _render(
        "{category}/{yyyy}/{event}",
        category="Camera",
        captured_at=datetime(2026, 6, 30),
        event=(datetime(2026, 6, 30), "goa-trip"),
    )
    assert got == "Camera/2026/20260630_goa-trip"


def test_alternate_date_tokens() -> None:
    got = _render("{yy}-{mon}-{dd}", category="x", captured_at=datetime(2025, 8, 4))
    assert got == "25-Aug-04"


@pytest.mark.parametrize("bad", ["", "   ", "/", "{category}//{yyyy}"])
def test_parse_rejects_empty_and_empty_segments(bad: str) -> None:
    with pytest.raises(TemplateError):
        LayoutTemplate.parse(bad)


def test_parse_rejects_unknown_token() -> None:
    with pytest.raises(TemplateError, match="unknown template token"):
        LayoutTemplate.parse("{category}/{city}")


def test_known_tokens_are_the_v1_set() -> None:
    assert {"category", "event", "yyyy", "yy", "mm", "mon", "month", "dd"} == KNOWN_TOKENS
