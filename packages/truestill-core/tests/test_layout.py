"""LayoutTemplate: token grammar, undated collapse, and event placement."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

import pytest
from truestill_core.layout import (
    DEFAULT_TEMPLATE,
    KNOWN_TOKENS,
    LayoutTemplate,
    RenderContext,
    TemplateError,
    preview,
    resolve_template,
)


def _render(template: str, **ctx: object) -> str:
    return LayoutTemplate.parse(template).render(RenderContext(**ctx)).as_posix()  # type: ignore[arg-type]


#: A representative side-bin template: the one place {category} is still rendered.
SIDE_BIN = LayoutTemplate.parse("{category}/{yyyy}/{yyyy}-{mm}")


def test_a_side_bin_collapses_undated_to_one_folder() -> None:
    got = SIDE_BIN.render(RenderContext(category="Camera", captured_at=None))
    assert got == PurePosixPath("Camera/Undated")  # not Camera// and not a guessed date


def test_event_member_uses_start_date_and_appends_event_folder() -> None:
    # Event start drives YYYY/MM (so a cross-month event stays whole) and the event folder is
    # appended because the default template has no explicit {event}.
    got = SIDE_BIN.render(
        RenderContext(
            category="Camera",
            captured_at=datetime(2026, 7, 2),
            event=(datetime(2026, 6, 30), "goa-trip"),
        )
    )
    assert got == PurePosixPath("Camera/2026/2026-06/20260630_goa-trip")


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


# -- validation (set/preview time) --------------------------------------------------------


def test_resolve_template_defaults_when_unset() -> None:
    assert resolve_template(None) is DEFAULT_TEMPLATE
    assert resolve_template("{category}/{yyyy}").template == "{category}/{yyyy}"


def test_parse_rejects_illegal_char_in_literal() -> None:
    with pytest.raises(TemplateError, match="not allowed in a path"):
        LayoutTemplate.parse("{category}/a:b")


def test_parse_rejects_reserved_literal_segment() -> None:
    with pytest.raises(TemplateError, match="reserved name"):
        LayoutTemplate.parse("{category}/NUL")


# -- render-time sanitization (total; never raises mid-run) -------------------------------


def test_render_sanitizes_separator_injection() -> None:
    # A slash inside a token value must not create an extra folder level.
    got = _render("{category}/{yyyy}", category="AC/DC", captured_at=datetime(2020, 1, 1))
    assert got == "AC_DC/2020"


def test_render_guards_reserved_value() -> None:
    got = _render("{category}", category="CON", captured_at=None)
    assert got == "_CON"


def test_empty_event_token_drops_its_segment() -> None:
    # A non-event file under an explicit {event} template falls back to the parent structure.
    got = _render("{category}/{yyyy}/{event}", category="Camera", captured_at=datetime(2023, 8, 20))
    assert got == "Camera/2023"


# -- preview warnings (data-dependent risks) ----------------------------------------------


def test_preview_flags_case_collision() -> None:
    rows = preview(
        LayoutTemplate.parse("{category}"),
        [RenderContext("Beach", None), RenderContext("beach", None)],
        filename="x.jpg",
    )
    assert all("case-insensitive" in " ".join(r.warnings) for r in rows)


def test_preview_flags_empty_token() -> None:
    rows = preview(LayoutTemplate.parse("{category}/{event}"), [RenderContext("Camera", None)])
    assert any("event" in w for w in rows[0].warnings)


def test_preview_flags_near_limit_path() -> None:
    rows = preview(LayoutTemplate.parse("{category}"), [RenderContext("x" * 250, None)])
    assert any("260" in w for w in rows[0].warnings)
