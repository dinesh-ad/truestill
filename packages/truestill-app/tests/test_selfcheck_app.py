"""The app's half of the self-check: the bundled typefaces and the notice that binds them.

**What makes this different from `test_bundled_font_ships_with_its_licence.py`, which already
exists.** That test resolves `parents[1] / "src" / ...` and therefore asks about the **checkout**.
`(aad)`'s criterion is about the **artifact**, and its own warning is that a green source-tree
suite plus a bundle that dropped the file is exactly the state that reads as verified. The module
under test here reads `server._STATIC` - the directory Starlette actually mounts - so in a bundle
it asks about the bundle. The source-tree test keeps its own job; this one is not a replacement
for it.

**Every failure below is produced by pointing the check at a directory missing something**, which
is the only way to prove a check can report `MISSING` without breaking the real install. The
complete case sits beside them as the cry-wolf half.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from truestill_app.selfcheck import FACES, LICENCE_NAME, app_findings, font_findings
from truestill_app.server import _STATIC
from truestill_core.selfcheck import Finding, Status, is_complete

_REAL_FONTS = _STATIC / "fonts"


def _named(findings: list[Finding], name: str) -> Finding:
    matched = [f for f in findings if f.name == name]
    assert len(matched) == 1, f"expected exactly one {name!r} finding, got {len(matched)}"
    return matched[0]


def _static_copy(tmp_path: Path, *, drop: str | None = None) -> Path:
    """A copy of the served static tree, optionally missing one file."""
    fonts = tmp_path / "fonts"
    shutil.copytree(_REAL_FONTS, fonts)
    if drop is not None:
        (fonts / drop).unlink()
    return tmp_path


# ------------------------------------------------------------------------------ the cry-wolf half


def test_this_install_carries_both_faces_and_the_notice() -> None:
    """Without this, every failure test below is satisfied by a check that can only fail."""
    findings = font_findings()

    assert is_complete(findings)
    assert [f.name for f in findings] == [
        f"font {FACES[0]}",
        f"font {FACES[1]}",
        "font licence",
    ]


def test_each_face_is_reported_by_size_and_digest_so_the_caller_can_judge_the_bytes() -> None:
    """**The artifact reports what it holds; whether that is RIGHT is the caller's question.**

    A frozen build cannot know what it was supposed to contain - a truncated font and a correct
    one are both "a file that is here" - so the check reports size and sha256 and the packaging
    job diffs them against the repository's own bytes. That split is the only reason `(aad)`'s
    *"the byte count of the source file"* is answerable from inside a bundle at all, and this test
    is what keeps the evidence in the payload for the job to read.
    """
    finding = _named(font_findings(), f"font {FACES[0]}")
    real = (_REAL_FONTS / FACES[0]).read_bytes()

    assert finding.evidence["bytes"] == len(real)
    assert finding.evidence["sha256"] == hashlib.sha256(real).hexdigest()


# ------------------------------------------------------------------------------- the failures


def test_a_face_the_bundler_did_not_collect_is_reported_missing(tmp_path: Path) -> None:
    """The defect the criterion exists for: a data file no bundler collects unless told to.

    Bundlers follow *imports*; a font is neither imported nor referenced by any Python name, so
    dropping it is the ordinary outcome of a spec file that says nothing about it.
    """
    findings = font_findings(_static_copy(tmp_path, drop=FACES[1]))

    assert not is_complete(findings)
    assert _named(findings, f"font {FACES[1]}").status is Status.MISSING
    assert _named(findings, f"font {FACES[0]}").status is Status.OK, (
        "one missing face must not be reported as both"
    )


def test_a_file_that_is_not_a_truetype_at_all_is_degraded_rather_than_ok(tmp_path: Path) -> None:
    """`is_file()` is satisfied by an LFS pointer, a zero-length placeholder or an HTML error page.

    The magic-number check is what separates *collected* from *collected and usable*, and it is
    the case a size comparison alone would pass if the wrong file happened to be the right length.
    """
    root = _static_copy(tmp_path)
    (root / "fonts" / FACES[0]).write_bytes(b"version https://git-lfs.github.com/spec/v1\n")

    finding = _named(font_findings(root), f"font {FACES[0]}")

    assert finding.status is Status.DEGRADED
    assert "TrueType" in finding.detail


def test_a_notice_missing_its_binding_clause_is_a_licence_defect(tmp_path: Path) -> None:
    """Bitstream Vera binds the notice to *copies of the typefaces*, so content is the check.

    A notice that exists but has lost the clause discharges nothing, and it is the shape a
    well-meaning edit produces - which is why this asserts on the clause rather than on the file.
    """
    root = _static_copy(tmp_path)
    (root / "fonts" / LICENCE_NAME).write_text(
        "Permission is hereby granted, free of charge, to any person obtaining a copy",
        encoding="utf-8",
    )

    finding = _named(font_findings(root), "font licence")

    assert finding.status is Status.DEGRADED
    assert "binds it" in finding.detail


def test_a_notice_that_never_shipped_is_reported_missing(tmp_path: Path) -> None:
    """Shipping the typefaces without the notice is a licence defect, not a missing extra."""
    findings = font_findings(_static_copy(tmp_path, drop=LICENCE_NAME))

    assert _named(findings, "font licence").status is Status.MISSING


def test_the_notice_is_measured_as_bytes_so_a_crlf_checkout_reports_its_real_size(
    tmp_path: Path,
) -> None:
    """A Windows-only defect, given a detector that runs on every lane.

    `read_text` applies universal newlines, so a CRLF file decodes to LF and the reported length
    is the translated one. Run 31671053639 measured it: the artifact said **4007** bytes for a
    file the checkout held at **4080**, and the comparison against the repository failed on a
    file that was byte-for-byte correct.

    Written with an explicit CRLF fixture rather than left to the platform, which is the point -
    `ENGINEERING_STANDARD.md` §4, thirty-ninth member: a measurement that only differs on one OS
    needs a fixture that reproduces that OS's shape, or only that OS's lane can catch it.
    """
    root = _static_copy(tmp_path)
    notice = root / "fonts" / LICENCE_NAME
    crlf = notice.read_bytes().replace(b"\n", b"\r\n")
    notice.write_bytes(crlf)

    finding = _named(font_findings(root), "font licence")

    assert finding.status is Status.OK, "a CRLF notice is still a valid notice"
    assert finding.evidence["bytes"] == len(crlf), (
        "the reported size is the newline-translated one, not the file's"
    )
    assert finding.evidence["sha256"] == hashlib.sha256(crlf).hexdigest()


# ------------------------------------------------------------------------------- composition


def test_app_findings_is_core_plus_the_assets_only_the_app_can_see() -> None:
    """The composition `IMPLEMENTATION_STANDARDS.md` §2 forces: core cannot import the app, so the
    app adds its own findings to core's rather than core reaching for the static tree."""
    names = [f.name for f in app_findings()]

    assert names[:6] == ["install", "exiftool", "trash", "catalog", "cache", "session url"]
    assert names[6:] == [f"font {FACES[0]}", f"font {FACES[1]}", "font licence"]
