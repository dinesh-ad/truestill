"""Filename convention for organized copies.

A copy is named ``YYYYMMDD_HHMMSS_<original-filename>`` so it sorts chronologically wherever
it ends up -- folder context is lost when files move, but a date-prefixed name is not. The
date/time come from the *same* evidence chain used for folder placement (see
:mod:`truestill_core.dates`), so a file's name and its ``YYYY/MM`` folder can never disagree.

Rules:

* Time-of-day known (an embedded-metadata date) -> stamp ``YYYYMMDD_HHMMSS``.
* Time-of-day unknown (a filename-convention date, which has no reliable time) -> ``YYYYMMDD``.
* No date at all, or renaming disabled -> the original name, untouched.
* **Suppression:** if the *exact* stamp we would prepend already appears somewhere in the
  original name, the name is left unchanged -- no point stating the same timestamp twice.
  This is deliberately exact: a mismatch (e.g. the filename says ``...000515`` but metadata
  says ``000516``) still gets the prefix, because the metadata-derived timestamp is
  authoritative.
* **Replacement:** a stamp *we* wrote is upgraded in place rather than prefixed again. Two
  stamp shapes exist, so suppression alone was never enough to keep renaming idempotent: a
  file organized from a filename or Takeout date is named ``20140815_x.jpg``, and organizing
  it again once EXIF is readable derives ``20140815_143022``, which is **not** a substring of
  the shorter form. That produced ``20140815_143022_20140815_x.jpg``, and again on every
  later pass. Fixed 2026-08-03.

  **The rule is anchored, and widening it to a substring search would be a worse bug.** A
  date-only stamp appears *inside* most vendor filenames -- ``VID-20250804-WA0020.mp4``,
  ``IMG_20140815_143000.jpg``, ``Screenshot_20260721_000515_...`` -- so matching one anywhere
  would suppress the prefix across most of a real library and silently discard a time we do
  know. Only a stamp at the **start** is one we wrote. It must also be for the **same date**:
  ``20140815_wedding.jpg`` may be the user's own name, and when the evidence says another day
  we have no standing to delete theirs, so that case is prefixed exactly as before.

The original file is never renamed and its name is never modified; this only decides the
name of the *copy* written to the destination. The catalog records original <-> new.
"""

from __future__ import annotations

import re
from datetime import datetime

#: A stamp of either shape at the **start** of a name, i.e. one this module wrote. Anchored on
#: purpose -- see the module docstring for why a search anywhere in the name is not equivalent.
_OWN_STAMP_PREFIX = re.compile(r"^(\d{8})(?:_\d{6})?_")


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
    own = _OWN_STAMP_PREFIX.match(original_name)
    if own is not None and own.group(1) == stamp_for(captured_at, time_known=False):
        return f"{stamp}_{original_name[own.end() :]}"
    return f"{stamp}_{original_name}"
