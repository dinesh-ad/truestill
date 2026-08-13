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


def _findings_in(payload: dict[str, object]) -> list[dict[str, object]] | None:
    """The findings list, from **either** envelope - or ``None`` when there is not one.

    Two producers write self-check results and they wrap them differently, which is exactly the
    defect this function exists to end. ``truestill-app --self-check`` writes
    `truestill_core.selfcheck.write_findings`' own shape (``complete`` / ``worst`` / ``findings``);
    the rig's ``--probe`` nests the same list under a ``selfcheck`` key beside its other
    measurements. Reading only the second is what made the first real run report *"the artifact
    never ran it"* about an artifact that had run it and reported three missing typefaces.

    ``None`` means **no self-check is present**, which is a different fact from **it failed** -
    see `_compare`.
    """
    nested = payload.get("selfcheck")
    if isinstance(nested, dict) and isinstance(nested.get("findings"), list):
        return list(nested["findings"])
    direct = payload.get("findings")
    if isinstance(direct, list):
        return list(direct)
    return None


def _is_selfcheck(path: Path) -> bool:
    """Whether this file claims to be an artifact's self-check at all - used only for counting."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    kind = payload.get("kind")
    return kind is None or kind == "selfcheck"


def _evidence(finding: dict[str, object]) -> dict[str, object]:
    """A finding's evidence map, or an empty one. Narrowed here so every caller is typed."""
    value = finding.get("evidence")
    return value if isinstance(value, dict) else {}


def _compare(findings_path: Path) -> list[str]:
    """Every way this artifact disagrees with the repository, as sentences. Empty means agreed.

    **Three outcomes, kept apart, because collapsing them is the fault this file already
    committed once.** The rig's own scope fence says *"no file must never be ambiguous between a
    failed build and a job that never ran"*, and the first run of this script broke that rule in
    the other direction - it reported an artifact that ran the checks and failed them as one that
    never ran them, naming the wrong cause in the one line anybody reads.

    * **the build never produced an artifact** - there is nothing to have checked;
    * **the artifact never ran the checks** - a findings file with no self-check in it at all;
    * **the artifact ran them and something is wrong** - which is a real measurement and the only
      one of the three that says anything about the bundle.
    """
    problems: list[str] = []
    try:
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{findings_path.name}: could not be read ({exc})"]

    # A report of a different KIND is not an artifact that failed to self-check. Startup
    # timings live in the same directory and carry no findings; refusing them would fail the
    # gate on a measurement that has nothing to do with it.
    kind = payload.get("kind")
    if kind is not None and kind != "selfcheck":
        return []

    findings = _findings_in(payload)
    if findings is None:
        # A build that produced nothing says so in its own words; anything else is an artifact
        # that existed and was never asked. The two need different next actions - fix the build,
        # or fix the step that was supposed to ask - so they get different sentences.
        built_nothing = (
            payload.get("measured") is False
            or "build_outcome" in payload
            # An explicit `"selfcheck": null` is a producer saying "there was no artifact to ask",
            # which is not the same as never having written the key at all.
            or ("selfcheck" in payload and payload["selfcheck"] is None)
        )
        if built_nothing:
            why = payload.get("reason") or payload.get("build_outcome") or "reason not recorded"
            return [
                (
                    f"{findings_path.name}: THE BUILD PRODUCED NO ARTIFACT ({why}) - "
                    f"nothing was checked, and that is not a pass"
                )
            ]
        return [
            (
                f"{findings_path.name}: THE ARTIFACT NEVER RAN THE SELF-CHECK - a findings file "
                f"with no findings in it. Not the same as the checks failing; nothing was measured"
            )
        ]
    for finding in findings:
        if finding.get("status") in {"degraded", "missing"}:
            problems.append(
                f"{findings_path.name}: RAN AND FAILED - {finding.get('name')} is "
                f"{finding.get('status')} - {finding.get('detail')}"
            )

    expected = _repository_digests()
    # Keyed on every asset finding, not only the ones carrying a digest. A file the artifact
    # reported as MISSING has no sha256, and treating that as "never reported" printed a second,
    # wrong sentence underneath the true one - burying the finding it was meant to support.
    reported: dict[str, dict[str, object]] = {}
    for finding in findings:
        evidence = _evidence(finding)
        path = evidence.get("path")
        if str(finding.get("name", "")).startswith("font ") and path is not None:
            reported[Path(str(path)).name] = evidence

    for name, (size, digest) in expected.items():
        evidence = reported.get(name, {})
        if not evidence:
            problems.append(
                f"{findings_path.name}: {name} was never reported by the artifact - the check "
                f"does not know about a file this repository ships"
            )
            continue
        if "sha256" not in evidence:
            # Already reported above as degraded or missing; saying it twice in different words
            # is how a real finding gets lost in its own noise.
            continue
        if evidence.get("bytes") != size or evidence.get("sha256") != digest:
            problems.append(
                f"{findings_path.name}: {name} is not the file this repository built - "
                f"repository {size} bytes / {digest[:12]}, artifact "
                f"{evidence.get('bytes')} bytes / {str(evidence.get('sha256'))[:12]}"
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
    considered = [n for n in argv if _is_selfcheck(Path(n))]
    skipped = len(argv) - len(considered)
    note = f" ({skipped} other report(s) skipped)" if skipped else ""
    print(f"self-check matched the repository for {len(considered)} artifact(s)" + note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
