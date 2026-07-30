"""Catalog lifecycle for layout: pin, read stored template, resolve scheme.

These functions need :class:`~truestill_core.catalog.Catalog`. They lived in ``layout.py``
behind an invented ``CatalogLike`` Protocol only to dodge that import - the same boundary
tell as the duplicate offset formatter in ``models`` ((aab)). The dependency is legitimate
here: this module bridges settings storage and pure layout rendering. ``layout`` stays
grammar/routing/rendering; ``catalog`` stays persistence.
"""

from __future__ import annotations

from truestill_core.catalog import Catalog
from truestill_core.layout import (
    DEFAULT_PRESET,
    DEFAULT_SCHEME,
    DEFAULT_TEMPLATE_STRING,
    LAYOUT_EVENT_TEMPLATE_KEY,
    LAYOUT_TEMPLATE_KEY,
    LayoutScheme,
    scheme_from_string,
)


def pin_existing_layout(catalog: Catalog) -> bool:
    """Write down a library's current layout before a default change could move it.

    A layout is only ever persisted when a user explicitly sets one, so a library organized
    with the defaults stores nothing and renders through whatever :data:`DEFAULT_TEMPLATE` is
    at the time. Changing that constant would therefore silently re-shape the **next** run of
    every existing library - new files in the new structure, the existing tree in the old one,
    no prompt and no migration. That is exactly the split the "new default applies forward,
    migration offered never forced" rule exists to prevent, and the rule needs a mechanism.

    The trigger is deliberately narrow: **files have already been placed, and no layout is
    stored.** A library that has only ever been scanned or previewed has nothing on disk to
    protect and receives the new default like any fresh library
    (``catalog.has_placed_files`` documents why that signal, and not "the catalog has rows").

    Returns whether it pinned, so the caller can announce it once. Idempotent: a catalog that
    already stores a layout - pinned or chosen - is never touched again.
    """
    if catalog.get_setting(LAYOUT_TEMPLATE_KEY) is not None:
        return False
    if not catalog.has_placed_files():
        return False
    catalog.set_setting(LAYOUT_TEMPLATE_KEY, DEFAULT_TEMPLATE_STRING)
    if DEFAULT_PRESET.timeline_evented != DEFAULT_PRESET.timeline:
        catalog.set_setting(LAYOUT_EVENT_TEMPLATE_KEY, DEFAULT_PRESET.timeline_evented)
    return True


def effective_layout_string(catalog: Catalog) -> str | None:
    """The layout in force right now - **pure, never writes.**

    Nothing stored means the default is in force, and ``resolve_scheme`` falls back to the whole
    :data:`DEFAULT_SCHEME` rather than to a single string -- the default's evented and
    un-evented shapes differ, and a string cannot carry that. Returning a string here instead
    would silently flatten events into the ``Everyday`` bucket, which is exactly what it did
    when tried.

    Pure. Previews run on read-only paths where writing a setting would break the dry-run
    invariant (``IMPLEMENTATION_STANDARDS.md`` §5), so a preview cannot pin -- and if it
    resolved differently from the run that follows, the plan a user approved would not be the
    plan that executed.
    """
    return catalog.get_setting(LAYOUT_TEMPLATE_KEY)


def resolve_scheme(catalog: Catalog) -> LayoutScheme:
    """The whole layout in force for a catalog, router included. Pure; never writes.

    **The single resolution entry point.** Runs, previews and migration all come through here,
    so there is no second path that could answer differently -- the divergence the design audit
    found (a preview rendering through a scheme while runs rendered through a bare template).
    """
    stored = effective_layout_string(catalog)
    if stored is None:
        # Falls back to the whole default *scheme*, not to its timeline string: the default's
        # evented and un-evented shapes differ (events keep the month as their parent, ordinary
        # photos go to `Everyday`), and a single string cannot express that.
        return DEFAULT_SCHEME
    return scheme_from_string(stored, catalog.get_setting(LAYOUT_EVENT_TEMPLATE_KEY))
