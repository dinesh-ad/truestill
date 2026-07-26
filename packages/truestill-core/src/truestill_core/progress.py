"""Cooperative progress + cancellation for the long operations.

A :data:`ProgressCallback` is invoked ``(done, total)`` as work completes -- the CLI prints a
counter, the web UI streams it over SSE. Cancellation is a stdlib ``threading.Event``: long ops
check it between items and stop early, returning what finished. truestill is copy-only and
resumable, so a cancelled run is always safe to re-run.
"""

from __future__ import annotations

from collections.abc import Callable

#: Called ``(done, total)`` as items complete.
ProgressCallback = Callable[[int, int], None]
