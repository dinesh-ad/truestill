"""Settings: event/everyday preferences and layout template preview/set.

Self-contained surface: Catalog + layout/event settings from core.
Trip proposal payloads (``EventProposal*``, ``invalid_event_proposal_payload``)
stay on the facade with the Trips surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.events import EVENT_MIN_FILES_KEY, EventSettings, InvalidEventSettingsError
from truestill_core.layout import (
    DEFAULT_PRESET,
    DEFAULT_TEMPLATE_STRING,
    EVERYDAY_DAY_THRESHOLD_KEY,
    EVERYDAY_DAY_THRESHOLD_MIGRATE_ANCHOR,
    EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING,
    LAYOUT_TEMPLATE_KEY,
    PRESETS,
    EverydayDaySettings,
    InvalidEverydayDaySettingsError,
    LayoutScheme,
    LayoutTemplate,
    TemplateError,
    parse_timeline_template,
    preview_scheme,
)
from truestill_core.layout_settings import effective_layout_string, resolve_scheme


class EventSettingsPayload(TypedDict):
    valid: Literal[True]
    min_files: int
    default_min_files: int
    is_default: bool


class InvalidEventSettingsPayload(TypedDict):
    valid: Literal[False]
    error: str


def event_settings(db: Path) -> EventSettings:
    """Read the validated preference once through the catalog's existing settings seam."""
    with Catalog(db) as catalog:
        return EventSettings.from_catalog(catalog)


def event_settings_payload(settings: EventSettings) -> EventSettingsPayload:
    return {
        "valid": True,
        "min_files": settings.min_files,
        "default_min_files": EventSettings().min_files,
        "is_default": settings.is_default,
    }


def invalid_event_settings_payload(error: str) -> InvalidEventSettingsPayload:
    return {"valid": False, "error": error}


def set_event_settings(min_files: object, db: Path) -> EventSettings:
    """Persist a positive proposal-size floor, rejecting malformed API input without writing."""
    if isinstance(min_files, bool) or not isinstance(min_files, int) or min_files < 1:
        raise InvalidEventSettingsError.submitted()
    settings = EventSettings(min_files=min_files, is_default=False)
    with Catalog(db) as catalog:
        catalog.set_setting(EVENT_MIN_FILES_KEY, str(min_files))
    return settings


class EverydayDaySettingsPayload(TypedDict):
    valid: Literal[True]
    threshold: int
    default_threshold: int
    is_default: bool
    migrate_warning: str | None
    migrate_anchor: str


class InvalidEverydayDaySettingsPayload(TypedDict):
    valid: Literal[False]
    error: str


def everyday_day_settings(db: Path) -> EverydayDaySettings:
    """Read the validated Everyday day-folder threshold through the catalog settings seam."""
    with Catalog(db) as catalog:
        return EverydayDaySettings.from_catalog(catalog)


def everyday_day_settings_payload(
    settings: EverydayDaySettings, *, changed: bool = False
) -> EverydayDaySettingsPayload:
    return {
        "valid": True,
        "threshold": settings.threshold,
        "default_threshold": EverydayDaySettings().threshold,
        "is_default": settings.is_default,
        "migrate_warning": EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING if changed else None,
        "migrate_anchor": EVERYDAY_DAY_THRESHOLD_MIGRATE_ANCHOR,
    }


def invalid_everyday_day_settings_payload(error: str) -> InvalidEverydayDaySettingsPayload:
    return {"valid": False, "error": error}


def set_everyday_day_settings(threshold: object, db: Path) -> EverydayDaySettingsPayload:
    """Persist the day-folder threshold; warn when the value actually changes (migrate needed)."""
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
        raise InvalidEverydayDaySettingsError.submitted()
    settings = EverydayDaySettings(threshold=threshold, is_default=False)
    with Catalog(db) as catalog:
        prior = EverydayDaySettings.from_catalog(catalog)
        catalog.set_setting(EVERYDAY_DAY_THRESHOLD_KEY, str(threshold))
    changed = prior.threshold != threshold
    return everyday_day_settings_payload(settings, changed=changed)


class LayoutPreviewRow(TypedDict):
    description: str
    when: str
    path: str
    warnings: list[str]


class LayoutState(TypedDict):
    """Settings layout payload. ``presets`` values are timeline *strings*, never preset objects."""

    template: str
    is_default: bool
    presets: dict[str, str]
    preset_titles: dict[str, str]
    default_preset: str
    preview: list[LayoutPreviewRow]


class PreviewLayoutOk(TypedDict):
    valid: Literal[True]
    preview: list[LayoutPreviewRow]


class PreviewLayoutErr(TypedDict):
    valid: Literal[False]
    error: str


class SetLayoutOk(TypedDict):
    valid: Literal[True]
    template: str
    is_default: bool
    presets: dict[str, str]
    preset_titles: dict[str, str]
    default_preset: str
    preview: list[LayoutPreviewRow]


class SetLayoutErr(TypedDict):
    valid: Literal[False]
    error: str


def _render_preview(scheme: LayoutScheme) -> list[LayoutPreviewRow]:
    """The sample rows rendered through a whole scheme, so the preview shows the routing split."""
    return [
        {
            "description": row.description,
            "when": row.context.captured_at.strftime("%Y-%m-%d")
            if row.context.captured_at
            else "undated",
            "path": rendered.path.as_posix(),
            "warnings": list(rendered.warnings),
        }
        for row, rendered in preview_scheme(scheme)
    ]


def layout_state(db: Path) -> LayoutState:
    """What layout is actually in force for this library, plus the presets and a live preview.

    Everything here is derived from `effective_layout_string`, which is **pure** - opening
    Settings must not write a setting, and previewing must not pin a layout. A legacy library
    therefore shows its real (category-first) shape truthfully rather than being shown the new
    default it has not adopted.
    """
    with Catalog(db) as catalog:
        stored = effective_layout_string(catalog)
        scheme = resolve_scheme(catalog)
    return {
        "template": stored or DEFAULT_TEMPLATE_STRING,
        "is_default": stored is None,
        # str -> str, deliberately: the payload is JSON and app.js iterates it. Handing it
        # preset objects would serialize dataclasses into the API. Pinned by a test.
        "presets": {name: p.timeline for name, p in PRESETS.items()},
        "preset_titles": {name: p.title for name, p in PRESETS.items()},
        "default_preset": DEFAULT_PRESET.key,
        "preview": _render_preview(scheme),
    }


def _scheme_for_timeline(template: LayoutTemplate) -> LayoutScheme:
    """A scheme for previewing a typed timeline template: fixed side bin, events appended."""
    return LayoutScheme.of(timeline=template, timeline_evented=template)


def preview_layout(template_str: str) -> PreviewLayoutOk | PreviewLayoutErr:
    """Validate a template and render the samples; report the error instead of raising."""
    try:
        template = parse_timeline_template(template_str)
    except TemplateError as exc:
        return {"valid": False, "error": str(exc)}
    return {"valid": True, "preview": _render_preview(_scheme_for_timeline(template))}


def set_layout(template_str: str, db: Path) -> SetLayoutOk | SetLayoutErr:
    """Persist a template after validating it; returns the new :func:`layout_state` or an error."""
    try:
        parse_timeline_template(template_str)
    except TemplateError as exc:
        return {"valid": False, "error": str(exc)}
    with Catalog(db) as catalog:
        catalog.set_setting(LAYOUT_TEMPLATE_KEY, template_str)
    state = layout_state(db)
    return {
        "valid": True,
        "template": state["template"],
        "is_default": state["is_default"],
        "presets": state["presets"],
        "preset_titles": state["preset_titles"],
        "default_preset": state["default_preset"],
        "preview": state["preview"],
    }
