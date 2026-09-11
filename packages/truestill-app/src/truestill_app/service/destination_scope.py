"""What a run will write into THIS destination, as opposed to what the library already holds.

⚠ **ONE HOME, AND IT IS A NEUTRAL ONE.** Both functions here lived in `service/organize.py` until
2026-09-11, when D17 gave Import the same answer. Importing them from there created a **circular
import** - `organize.py` already imports `InferredLocalShiftPayload` from `service/takeout.py` -
which neither ruff nor mypy reports, because the cycle only exists at run time. A module that
depends on neither service removes it entirely rather than papering over it with a deferred
import.

**The idea they share** is `(aei)`: dedup is scoped **per destination**, never per catalog. A twin
the library holds on drive X is not a duplicate for a run into drive Y; it is the second copy the
run exists to make.

⚠ **These are the PROMISE's half of `DECISIONS.md` D14, never the whole answer.** The preview
resolves once, catalog-global - that pass is what names which drive already holds a file, which
`IMPLEMENTATION_STANDARDS.md` §9 requires. Scoping that single pass instead is the one-argument
fix `handoff-2026-09-05.md` measured and **rejected**: it makes the promise true and empties the
naming. Re-judging with :func:`promise_view` gives both answers from one pass.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.dedup import credible_copies
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive import read_marker
from truestill_core.models import Resolution
from truestill_core.organizer import _scope_to_destination


def promise_view(resolutions: list[Resolution], on_destination: dict[str, str]) -> list[Resolution]:
    """Re-judge each exact match against THIS destination, exactly as the run will.

    Same function, same inputs, same order as `organizer.resolve`'s own loop, so the verdicts
    are the run's verdicts: a catalog twin absent from this destination is not a duplicate for
    the promise, a twin this run is already writing here (`landing_here`) still is, and a
    within-batch twin is always honoured. Nothing is re-hashed and nothing is resolved twice;
    the near-duplicate verdict is untouched because bytes that match exactly are simply not
    here, which is not a look-alike.
    """
    landing_here: set[str] = set()
    judged: list[Resolution] = []
    for r in resolutions:
        sha = r.hashes.sha256
        exact = r.exact_duplicate
        if exact is not None:
            exact = _scope_to_destination(exact, sha, on_destination, landing_here)
        if exact is None and sha is not None:
            landing_here.add(sha)
        judged.append(replace(r, exact_duplicate=exact))
    return judged


def scope_to_marker(destination: Path, catalog: Catalog) -> dict[str, str]:
    """What this destination already holds, for `(aei)`'s per-destination dedup.

    ⚠ **Read from the MARKER, not from registration**, which is what lets `(aek)` move the marker
    write behind the space check without restoring `(aei)`. A destination that has an identity has
    it before anything here runs; one that does not provably holds no recorded copies, and `{}` is
    exactly what a freshly minted uuid would have returned.

    The app always writes to a local drive - there is no rclone path here - so
    `organizer._scope_to_destination`'s catalog-global `None` case never applies. Returning `None`
    here would make organize dedupe against the whole catalog and copy nothing onto a second
    drive, which is `(aei)` itself.
    """
    existing = read_marker(destination)
    if existing is None:
        return {}
    rows = catalog.copies_on_drive(existing.uuid)
    # ⚠ **A row is a claim; the destination is asked whether it is still true.** `(aja)`. The app
    # always writes to a local drive, so `sizes()` always answers here - there is no rclone branch
    # to fall back to. See `dedup.credible_copies`.
    return credible_copies(
        {str(r["sha256"]): str(r["relative"]) for r in rows},
        sizes=LocalDestination(destination).sizes(),
        expected={str(r["sha256"]): (None if r["size"] is None else int(r["size"])) for r in rows},
    )
