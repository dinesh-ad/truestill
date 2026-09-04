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

Usage: ``python packaging/compare_selfcheck.py [--expect-version X.Y.Z] <findings.json> ...``
Exit code 0 when every artifact's self-check passed **and** matched the repository; 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path

#: The checkout this script lives in. `parents[1]` is the repository root - `packaging/` is one
#: level down - and it is resolved from `__file__` rather than the working directory because a job
#: step's cwd is a thing that changes without anyone editing this file.
_ROOT = Path(__file__).resolve().parents[1]
_STATIC = _ROOT / "packages" / "truestill-app" / "src" / "truestill_app" / "static"


#: The bundle files the artifact must carry, relative to the static root. Built by Vite in the
#: same job before PyInstaller runs, so the checkout holds the bytes the artifact should hold.
#: `(ajv)`: v0.1.0 shipped without them and nothing compared, because nothing expected them.
_BUNDLE = ("dist/main.js", "dist/main.css")


class UnbuiltBundleError(RuntimeError):
    """The checkout has no built bundle to compare against - the comparison cannot run."""


class UndeclaredVersionError(RuntimeError):
    """The checkout declares no version for a distribution the artifact carries."""


#: The distributions the frozen app actually contains, and therefore the versions it must be able
#: to report. **`truestill-cli` is deliberately absent and that is a measurement, not an
#: oversight**: PyInstaller's `Analysis-00.toc` and `PYZ-00.toc` for this artifact hold **zero**
#: `truestill_cli` entries (2026-09-04), because the frozen entry point is
#: `truestill_app/__main__.py` and nothing it imports reaches the CLI. Copying metadata for code
#: that is not in the bundle would ship a claim about something that is not there - the same
#: shape as a guard that cannot fire.
_DISTRIBUTIONS = ("truestill-app", "truestill-core")

#: The one whose version **is** the artifact's identity: `truestill_app.__version__` is what
#: `templates/index.html`'s `id="app-version"` renders, so it is the string a tag is compared
#: against. `(ajw)`.
_IDENTITY = "truestill-app"


def _repository_digests() -> dict[str, tuple[int, str]]:
    """Size and sha256 of every file the artifact is expected to carry, read from the checkout.

    ⚠ Raises rather than returning a shorter expectation when the checkout's own bundle is
    missing: an expectation that silently shrinks to what happens to be on disk is how the
    bundle went unchecked for nineteen days.
    """
    fonts = _STATIC / "fonts"
    expected: dict[str, tuple[int, str]] = {}
    for path in sorted(fonts.iterdir()):
        if path.suffix in {".ttf", ".txt"}:
            payload = path.read_bytes()
            expected[path.name] = (len(payload), hashlib.sha256(payload).hexdigest())
    for name in _BUNDLE:
        path = _STATIC / name
        if not path.is_file():
            msg = f"{path} is not built in this checkout; run `make frontend` before comparing"
            raise UnbuiltBundleError(msg)
        payload = path.read_bytes()
        expected[path.name] = (len(payload), hashlib.sha256(payload).hexdigest())
    return expected


def _declared_versions() -> dict[str, str]:
    """The version each distribution declares in **this checkout**, from its `pyproject.toml`.

    The same move `_repository_digests` makes for the assets: the expectation comes from the
    source of truth beside this script, never from the artifact. A directory name and a
    distribution name are the same string here (`packages/truestill-app` declares
    `truestill-app`), which is what lets one loop serve both.

    ⚠ Raises rather than skipping a distribution it cannot find. A comparison that quietly drops
    an expectation it could not read is how the bundle went unchecked for nineteen days - the
    reason already written above this function's neighbour.
    """
    declared: dict[str, str] = {}
    for distribution in _DISTRIBUTIONS:
        path = _ROOT / "packages" / distribution / "pyproject.toml"
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            msg = f"{path} could not be read ({exc}); the version cannot be compared"
            raise UndeclaredVersionError(msg) from exc
        project = data.get("project")
        version = project.get("version") if isinstance(project, dict) else None
        if not isinstance(version, str) or not version:
            msg = f"{path} declares no [project] version; the version cannot be compared"
            raise UndeclaredVersionError(msg)
        declared[distribution] = version
    return declared


def _reported_versions(findings: list[dict[str, object]]) -> dict[str, str]:
    """Every ``version <distribution>`` finding, by distribution.

    Keyed on the **evidence**, not on the human sentence: `truestill_core.selfcheck.Finding`
    exists precisely so a job never has to regex prose. A finding whose evidence carries no
    distribution is not indexed, and therefore reads as *never reported* below - which is the
    honest answer, because nothing identifiable was.
    """
    reported: dict[str, str] = {}
    for finding in findings:
        evidence = _evidence(finding)
        distribution = evidence.get("distribution")
        version = evidence.get("version")
        if isinstance(distribution, str) and isinstance(version, str):
            reported[distribution] = version
    return reported


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


def _reported_assets(findings: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Every asset finding by file name - fonts and bundle files alike.

    Keyed on every asset finding, not only the ones carrying a digest. A file the artifact
    reported as MISSING has no sha256, and treating that as "never reported" printed a second,
    wrong sentence underneath the true one - burying the finding it was meant to support.
    """
    reported: dict[str, dict[str, object]] = {}
    for finding in findings:
        evidence = _evidence(finding)
        path = evidence.get("path")
        if str(finding.get("name", "")).startswith(("font ", "bundle ")) and path is not None:
            reported[Path(str(path)).name] = evidence
    return reported


def _compare(findings_path: Path, expect_version: str | None = None) -> list[str]:
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

    try:
        expected = _repository_digests()
    except UnbuiltBundleError as exc:
        return [*problems, f"{findings_path.name}: THE CHECKOUT CANNOT COMPARE - {exc}"]
    reported = _reported_assets(findings)
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
    return [*problems, *_version_problems(findings_path, findings, expect_version)]


def _version_problems(
    findings_path: Path, findings: list[dict[str, object]], expect_version: str | None
) -> list[str]:
    """Does the artifact know what it is, and is that what this checkout and the tag say?

    **Two questions, and only the first one runs on every path - which is the point.** The
    artifact's version is compared against the checkout's `pyproject.toml` **always**, so a
    `workflow_dispatch` dry run exercises this exactly as a tag push does. The tag comparison
    needs a tag and is therefore passed in only when there is one; if it were the only check,
    `(ajw)` would have survived the rehearsal a third time, because a rehearsal has no tag.

    ⚠ **A version that is merely PRESENT is not a pass, and neither is one this script could not
    read.** The `unknown (not installed)` case is caught upstream by the artifact's own finding
    (`DEGRADED`, so the self-check exits non-zero before this runs), and it is caught again here
    because that string equals no declared version. Two independent failures for the defect that
    shipped twice.
    """
    problems: list[str] = []
    try:
        declared = _declared_versions()
    except UndeclaredVersionError as exc:
        return [f"{findings_path.name}: THE CHECKOUT CANNOT COMPARE - {exc}"]
    reported = _reported_versions(findings)
    for distribution, expected in declared.items():
        actual = reported.get(distribution)
        if actual is None:
            problems.append(
                f"{findings_path.name}: THE ARTIFACT NEVER REPORTED ITS VERSION for "
                f"'{distribution}' - this repository declares {expected} and nothing in the "
                f"findings says what the artifact thinks it is"
            )
            continue
        if actual != expected:
            problems.append(
                f"{findings_path.name}: {distribution} is not the version this repository "
                f"declares - repository {expected}, artifact {actual}"
            )
    if expect_version is not None:
        identity = reported.get(_IDENTITY)
        if identity != expect_version:
            problems.append(
                f"{findings_path.name}: THE ARTIFACT DISAGREES WITH THE TAG - the tag says "
                f"{expect_version} and the artifact calls itself {identity}. These bytes were "
                f"not built from the checkout this tag names"
            )
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="compare_selfcheck.py",
        description="Compare an artifact's self-check against the repository it was built from.",
    )
    parser.add_argument("findings", nargs="+", help="findings JSON written by --self-check")
    parser.add_argument(
        "--expect-version",
        default=None,
        metavar="X.Y.Z",
        # Passed by `release.yml` ONLY on a tag, because a dispatch build's version is
        # `0.0.0-dev.<run id>` and the artifact's metadata comes from `pyproject.toml`; requiring
        # them to agree would fail every dry run for a reason that is not a defect. The
        # checkout comparison above runs on both paths and is what the rehearsal exercises.
        help="the version this artifact must call itself - the tag, without its leading v",
    )
    args = parser.parse_args(argv)
    problems: list[str] = []
    for name in args.findings:
        problems.extend(_compare(Path(name), args.expect_version))
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        return 1
    considered = [n for n in args.findings if _is_selfcheck(Path(n))]
    skipped = len(args.findings) - len(considered)
    note = f" ({skipped} other report(s) skipped)" if skipped else ""
    against = f" against {args.expect_version}" if args.expect_version else ""
    print(f"self-check matched the repository{against} for {len(considered)} artifact(s)" + note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
