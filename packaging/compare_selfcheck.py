"""Compare an artifact's self-check against the repository it was built from.

**This is the half the artifact cannot do, and the split is the whole design.** A frozen build
reports what it *holds* - each font's size and sha256, the resolved exiftool, the trash backend -
but it cannot know what it was *supposed* to hold: a truncated font and a correct one are both "a
file that is here". So the artifact reports, and this script - which runs in the checkout, beside
the source of truth - decides whether the reported bytes are the right bytes. That is what makes
`(aad)`'s *"the byte count of the source file"* answerable from inside a bundle at all.

**It is deliberately NOT a test and does not import pytest.** It runs against a findings file
produced minutes earlier by a different executable on a different filesystem layout, which is a
thing no test lane can produce. Its output is a verdict a packaging job exits on.

Usage: ``python packaging/compare_selfcheck.py <findings.json> [more.json ...]``
Exit code 0 when every artifact's self-check passed **and** matched the repository; 1 otherwise.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

#: The checkout this script lives in. `parents[1]` is the repository root - `packaging/` is one
#: level down - and it is resolved from `__file__` rather than the working directory because a job
#: step's cwd is a thing that changes without anyone editing this file.
_ROOT = Path(__file__).resolve().parents[1]
_STATIC = _ROOT / "packages" / "truestill-app" / "src" / "truestill_app" / "static"


def _repository_digests() -> dict[str, tuple[int, str]]:
    """Size and sha256 of every file the artifact is expected to carry, read from the checkout."""
    fonts = _STATIC / "fonts"
    expected: dict[str, tuple[int, str]] = {}
    for path in sorted(fonts.iterdir()):
        if path.suffix in {".ttf", ".txt"}:
            payload = path.read_bytes()
            expected[path.name] = (len(payload), hashlib.sha256(payload).hexdigest())
    return expected


def _compare(findings_path: Path) -> list[str]:
    """Every way this artifact disagrees with the repository, as sentences. Empty means agreed."""
    problems: list[str] = []
    try:
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{findings_path.name}: could not be read ({exc})"]

    selfcheck = payload.get("selfcheck")
    if not isinstance(selfcheck, dict):
        # NOT the same as "the checks failed". A findings file without this key came from a build
        # that never ran them, and reporting that as a pass is the exact ambiguity this rig has
        # already paid for once.
        return [f"{findings_path.name}: no self-check in the findings - the artifact never ran it"]

    findings = selfcheck.get("findings", [])
    for finding in findings:
        if finding.get("status") in {"degraded", "missing"}:
            problems.append(
                f"{findings_path.name}: {finding['name']} is {finding['status']} - "
                f"{finding['detail']}"
            )

    expected = _repository_digests()
    reported = {
        Path(str(f["evidence"]["path"])).name: f["evidence"]
        for f in findings
        if f["name"].startswith("font ") and "sha256" in f.get("evidence", {})
    }
    for name, (size, digest) in expected.items():
        seen = reported.get(name)
        if seen is None:
            problems.append(f"{findings_path.name}: {name} was never reported by the artifact")
            continue
        if seen["bytes"] != size or seen["sha256"] != digest:
            problems.append(
                f"{findings_path.name}: {name} is not the file this repository built - "
                f"repository {size} bytes / {digest[:12]}, artifact {seen['bytes']} bytes / "
                f"{str(seen['sha256'])[:12]}"
            )
    return problems


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: compare_selfcheck.py <findings.json> [...]", file=sys.stderr)
        return 2
    problems: list[str] = []
    for name in argv:
        problems.extend(_compare(Path(name)))
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        return 1
    print(f"self-check matched the repository for {len(argv)} artifact(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
