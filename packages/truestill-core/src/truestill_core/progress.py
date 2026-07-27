"""Cooperative progress + cancellation for the long operations.

A :data:`ProgressCallback` receives a :class:`Progress` as work completes -- the CLI prints a
counter, the web UI streams it over SSE. Cancellation is a stdlib ``threading.Event``: long ops
check it between items and stop early, returning what finished. truestill is copy-only and
resumable, so a cancelled run is always safe to re-run.

**Why an update carries more than ``done``/``total``.** A multi-minute run over thousands of
files that shows only a bar and a fraction gives a user no way to tell working from wedged.
Each op therefore reports:

* the **phase** it is in, so two phases with different per-item costs (hashing, then copying)
  are never blended into one misleading pace;
* the **item** it is on, which is what makes a long single file visibly alive rather than
  frozen;
* a running **tally** of outcomes, so the wait shows the work rather than only its length.

Rate and time-remaining are deliberately *not* computed here. They are presentation concerns
that need smoothing and a stability gate, and belong to whichever surface is displaying them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


class Phase:
    """Names for the phases a run passes through, as shown to a user.

    Deliberately verbs in the continuous tense: they are rendered directly ("hashing 412 of
    2,275"), so they must read as something happening rather than as a subsystem name.
    """

    SCANNING = "scanning"
    HASHING = "hashing"
    ORGANIZING = "organizing"
    MOVING = "moving"
    COPYING = "copying"
    VERIFYING = "verifying"
    RESTORING = "restoring"
    FREEING = "freeing"


@dataclass(frozen=True, slots=True)
class Progress:
    """One progress tick from a long-running operation."""

    done: int
    total: int
    phase: str = ""
    #: The file currently being worked on -- a bare name, never a full path (which would leak
    #: directory structure into a UI that only needs to prove something is happening).
    item: str = ""
    #: Running outcome counts, so a summary can fill in live instead of only at the end.
    tally: Mapping[str, int] = field(default_factory=dict)

    @property
    def fraction(self) -> float:
        return self.done / self.total if self.total else 0.0


#: Called with a :class:`Progress` as items complete.
ProgressCallback = Callable[[Progress], None]
