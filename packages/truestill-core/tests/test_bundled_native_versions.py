"""The C libraries inside the `pillow-heif` wheel are recorded, and the record is true.

**The blind spot this closes.** `pip-audit` is handed a locked requirements list. It reads
`pillow-heif==1.5.0` and stops. That wheel carries ~26 MB of native code - libheif, libde265,
x265 - whose versions appear nowhere in the audit input (measured: zero mentions). So the gate
can report a clean build while shipping a vulnerable decoder, and **libheif is what parses
untrusted user media**, which is the one thing this product does to files it did not create.
Checked 2026-08-02 and the answer was clean; the gap is structural and outlives the good news.

**Two assertions, because they answer different questions and neither covers the other.**

1. *The record equals what ships.* Catches a wheel upgrade silently changing the decoder. This
   is not a cry-wolf risk: `pillow-heif` is pinned in `uv.lock`, so the bundled version can only
   move through a deliberate `uv lock --upgrade` review - and "a human looks at the native
   decoder version" is exactly what should happen at that moment. The remedy is a one-line doc
   edit in the same commit, which is the same bargain `test_dependency_floors` already strikes
   with the lockfile.
2. *What ships is at or above the security floor.* The safety claim, and the reason a floor-only
   check would not have been enough on its own: a floor tolerates any upgrade silently, so a bump
   into a version with a **new** advisory would pass unnoticed - which is precisely the recurrence
   this guard exists for. Equally, assertion 1 alone would notice the change but say nothing about
   whether the new version is safe. Together they mean: we know what we ship, and we know it is
   above the line we last checked.

**Scoped to libheif deliberately.** It is the library with a CVE history that reaches us and the
only one with a clean version accessor (`libheif_version()`). libde265 and x265 are reported by
`libheif_info()` only inside descriptive strings ("libde265 HEVC decoder, version 1.1.1"), and
parsing those would be a brittle guard dressed as a strict one. They are recorded in §7.1 for a
human; only libheif is asserted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pillow_heif

_CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "IMPLEMENTATION_STANDARDS.md"

#: The §7.1 line recording libheif. Anchored on the whole sentence rather than a bare number, so
#: a stray version elsewhere in the contract cannot answer for this one.
_RECORDED = re.compile(
    r"\*\*`libheif`\*\* - shipped \*\*([0-9][0-9.]*)\*\*, security floor \*\*([0-9][0-9.]*)\*\*"
)


def _version_tuple(version: str) -> tuple[int, ...]:
    """Numeric release segments, enough to order the versions libheif actually publishes."""
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _recorded() -> tuple[str, str]:
    """``(shipped, floor)`` as §7.1 records them."""
    found = _RECORDED.findall(_CONTRACT.read_text(encoding="utf-8"))
    assert len(found) == 1, (
        f"expected exactly one recorded libheif line in {_CONTRACT.name}, found {len(found)}: "
        f"{found}. This guard reads that sentence; if it moved or was reworded, the check is no "
        "longer looking at anything."
    )
    return found[0]


def test_the_contract_records_the_libheif_version_that_actually_ships() -> None:
    """Notice-on-change: the recorded version equals the one in the wheel."""
    runtime = pillow_heif.libheif_version()

    # Anti-vacuity: a stubbed or empty accessor must not let this pass on nothing.
    assert _version_tuple(runtime), f"libheif_version() returned no version: {runtime!r}"

    shipped, _floor = _recorded()
    assert shipped == runtime, (
        f"§7.1 records libheif {shipped}; the wheel actually bundles {runtime}. A dependency "
        "upgrade changed the native decoder - which `pip-audit` cannot see, and is exactly the "
        "event worth stopping for. Check the new version against current advisories, then update "
        "§7.1 (and the floor, if the reason for the bump was a fix)."
    )


def test_the_shipped_libheif_is_at_or_above_the_recorded_security_floor() -> None:
    """The safety claim: at or above the version that closed the advisories we checked."""
    runtime = pillow_heif.libheif_version()
    _shipped, floor = _recorded()

    assert _version_tuple(runtime) >= _version_tuple(floor), (
        f"libheif {runtime} is BELOW the recorded security floor {floor}. The floor is where the "
        "2026 advisory cluster was fixed (CVE-2026-32740, -32814, -49271 and neighbours), and "
        "libheif is what parses untrusted user media here. Do not lower the floor to make this "
        "pass."
    )


def test_the_reader_found_a_real_record_and_a_real_runtime() -> None:
    """Anti-vacuity from both ends: the doc block resolved, and the library answered.

    Either side silently returning nothing would make both checks above vacuous - the failure
    mode this repo has hit often enough to write down.
    """
    shipped, floor = _recorded()
    assert _version_tuple(shipped), f"recorded shipped version did not parse: {shipped!r}"
    assert _version_tuple(floor), f"recorded floor did not parse: {floor!r}"

    info = pillow_heif.libheif_info()
    assert info.get("libheif"), f"libheif_info() carries no version: {info!r}"
    assert info["libheif"] == pillow_heif.libheif_version(), (
        "the two accessors disagree about the bundled version; one of them is not reading the "
        "library this process loaded"
    )
