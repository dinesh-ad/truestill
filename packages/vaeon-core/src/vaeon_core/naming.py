"""Filename convention for organized copies.

A copy is named ``YYYYMMDD_HHMMSS_<original-filename>`` so it sorts chronologically wherever
it ends up -- folder context is lost when files move, but a date-prefixed name is not. The
date/time come from the *same* evidence chain used for folder placement (see
:mod:`vaeon_core.dates`), so a file's name and its ``YYYY/MM`` folder can never disagree.

Rules:

* Time-of-day known (an embedded-metadata date) -> stamp ``YYYYMMDD_HHMMSS``.
* Time-of-day unknown (a filename-convention date, which has no reliable time) -> ``YYYYMMDD``.
* No date at all, or renaming disabled -> the original name, untouched.
* **Suppression:** if the *exact* stamp we would prepend already appears somewhere in the
  original name, the name is left unchanged -- no point stating the same timestamp twice.
  This is deliberately exact: a mismatch (e.g. the filename says ``...000515`` but metadata
  says ``000516``) still gets the prefix, because the metadata-derived timestamp is
  authoritative. It also makes renaming idempotent: a genuine re-run derives the same stamp,
  finds it already present, and does not stack a second prefix.

The original file is never renamed and its name is never modified; this only decides the
name of the *copy* written to the destination. The catalog records original <-> new.
"""

from __future__ import annotations

from datetime import datetime


def stamp_for(captured_at: datetime, *, time_known: bool) -> str:
    """The date stamp that would prefix a copy: ``YYYYMMDD_HHMMSS`` or ``YYYYMMDD``."""
    return captured_at.strftime("%Y%m%d_%H%M%S") if time_known else captured_at.strftime("%Y%m%d")


def dated_filename(
    original_name: str,
    captured_at: datetime | None,
    *,
    time_known: bool,
    enabled: bool = True,
) -> str:
    """Return the name for the organized copy of ``original_name``.

    ``time_known`` should be True only when ``captured_at`` came from embedded metadata;
    filename-derived dates carry no trustworthy time and get a date-only stamp.
    """
    if not enabled or captured_at is None:
        return original_name
    stamp = stamp_for(captured_at, time_known=time_known)
    if stamp in original_name:
        return original_name
    return f"{stamp}_{original_name}"
