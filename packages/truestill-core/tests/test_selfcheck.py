"""`truestill_core.selfcheck` - and above all, that it can say NOT ok.

**Why these tests are shaped around failure rather than success.** A self-check that has only ever
been seen to print `ok` on a working install is not known to be able to do anything else; it would
pass on a bundle with nothing in it, and `(aad)`'s two acceptance criteria exist precisely because
a green tick had been standing in for an unmeasured artifact. So every degraded and missing branch
here is produced deliberately, and the complete-install case is kept beside them as the cry-wolf
half - without it the checks could be made unconditionally red and every failure test would still
pass.

**The techniques are the ones already in this repo, not new ones.**
``monkeypatch.setitem(sys.modules, "send2trash", None)`` is how
`test_trash_backend_is_available.py` makes an import fail without touching the filesystem, and
`TRUESTILL_EXIFTOOL` pointing at nothing is how `test_exiftool_missing_message.py` reaches the
override branch.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from truestill_core import app_paths, selfcheck
from truestill_core.exif import EXIFTOOL_BIN_ENV
from truestill_core.selfcheck import (
    Finding,
    Status,
    core_findings,
    exiftool_finding,
    is_complete,
    location_findings,
    not_checked_finding,
    render,
    trash_finding,
    worst,
    write_findings,
)


def _named(findings: list[Finding], name: str) -> Finding:
    matched = [f for f in findings if f.name == name]
    assert len(matched) == 1, f"expected exactly one {name!r} finding, got {len(matched)}"
    return matched[0]


# --------------------------------------------------------------------------- the trash backend


def test_a_complete_install_reports_the_declared_backend() -> None:
    """THE CRY-WOLF HALF. Without it every failure test below is satisfied by a check that can
    only ever fail, which is the same defect in the other direction."""
    finding = trash_finding()

    assert finding.status is Status.OK
    assert finding.evidence["backend"] == "send2trash"


def test_no_trash_backend_at_all_is_reported_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The failure `(aad)`'s acceptance criterion was written for.

    A bundler's static analysis misses an import inside a ``try``, and on Windows there is no
    `gio` to fall back to - so `clean-empty` refuses every folder on every run
    (`IMPLEMENTATION_STANDARDS.md` §1). The self-check has to be able to see that from inside the
    artifact, because nothing reading the source tree ever will.
    """
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    finding = trash_finding()

    assert finding.status is Status.MISSING
    assert "refuse" in finding.detail


def test_falling_back_to_gio_is_degraded_rather_than_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dangerous middle state, and the reason the check asserts IDENTITY.

    A bundle that lost `send2trash` still answers on a Linux desktop with `gio` on PATH. Reported
    as `ok` it would say the install is fine while the same bundle is broken on the two platforms
    that have no `gio` at all - which is exactly what a bare ``is not None`` would have done.
    """
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/gio" if name == "gio" else None)

    finding = trash_finding()

    assert finding.status is Status.DEGRADED
    assert finding.evidence["backend"] == "gio"
    assert "Windows or macOS" in finding.detail


# ------------------------------------------------------------------------------------ exiftool


def test_a_missing_exiftool_is_reported_with_the_message_the_user_would_have_met(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The self-check must fail here for the same reason an organize would, not a different one.

    Reusing `ensure_exiftool` rather than re-implementing the search is what makes that true: a
    check with its own lookup could pass while the code path that matters fails.
    """
    monkeypatch.setenv(EXIFTOOL_BIN_ENV, "/nowhere/at/all/exiftool")

    finding = exiftool_finding()

    assert finding.status is Status.MISSING
    assert EXIFTOOL_BIN_ENV in finding.detail


def test_an_exiftool_that_resolves_but_cannot_run_is_degraded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**Resolving is not running**, and a bundle can ship the first without the second.

    Measured on a real artifact 2026-08-13: PyInstaller's `--add-binary` copies one file, and on
    Linux `exiftool` is a Perl script whose modules live in the distro's `/usr/share/perl5`. The
    bundle carried the script and none of the modules, so the artifact resolved a path, reported
    `ok`, and would have failed on the first photo opened by any user without exiftool already
    installed - the user the bundle exists for.

    The fixture is a file that exists and is not runnable, which is that artifact's shape without
    needing Perl to reproduce it.
    """
    broken = tmp_path / "exiftool"
    broken.write_text("#!/nonexistent/interpreter\n", encoding="utf-8")
    broken.chmod(0o755)
    monkeypatch.setenv(EXIFTOOL_BIN_ENV, str(broken))

    finding = exiftool_finding()

    assert finding.status is Status.DEGRADED
    assert "will not run" in finding.detail or "failed to run" in finding.detail
    assert finding.evidence["path"] == str(broken)


def test_an_exiftool_that_ran_on_the_host_modules_is_degraded_not_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**Running is not running from what we shipped**, and this is where the criteria live.

    `exiftool` is a script that silently falls back to the HOST's `Image::ExifTool` when its own
    module tree is absent: it exits 0 and mentions the substitution only as a warning. Measured
    2026-08-13 on a real bundle stripped of its `lib/` - it reported `ok` with
    ``13.59 [Warning: Library version is 13.50]``, which is exactly the works-here-fails-there
    defect these criteria exist for, passing the check written to catch it.

    Stubbed at `binaries.run` rather than built from a real exiftool, because the subject is what
    **we** do with the output - a fixture needing Perl would test the tool instead.
    """
    binary = tmp_path / "exiftool"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setenv(EXIFTOOL_BIN_ENV, str(binary))
    monkeypatch.setattr(
        selfcheck.binaries,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess(
            [], 0, stdout="13.59 [Warning: Library version is 13.50]", stderr=""
        ),
    )

    finding = exiftool_finding()

    assert finding.status is Status.DEGRADED
    assert "warned" in finding.detail


def test_a_bundled_exiftool_with_no_module_tree_is_degraded_even_when_it_runs_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The branch the warning hides, and it survived a mutation until this existed.

    In the wild the version warning fires first, so the module-tree check never decided anything
    and deleting it changed no test. But the warning is exiftool's courtesy, not our guarantee: a
    host whose installed modules happen to match the shipped version produces **no warning at
    all**, and the bundle is still borrowing them. This asserts the structural half on its own.
    """
    bundled = tmp_path / "bin"
    bundled.mkdir()
    binary = bundled / "exiftool"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setenv("TRUESTILL_BIN_DIR", str(bundled))
    monkeypatch.setenv(EXIFTOOL_BIN_ENV, str(binary))
    monkeypatch.setattr(
        selfcheck.binaries,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, stdout="13.59", stderr=""),
    )

    finding = exiftool_finding()

    assert finding.status is Status.DEGRADED, "a bundle with no modules of its own reported ok"
    assert "module tree is missing" in finding.detail

    # THE CRY-WOLF HALF, in the same test because it is the same fixture one directory later:
    # give it the tree it should have shipped and it passes.
    (bundled / "lib" / "Image").mkdir(parents=True)
    assert exiftool_finding().status is Status.OK


def test_the_module_tree_is_only_demanded_of_a_bundled_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE CRY-WOLF HALF: a system exiftool is the distro's business and has no tree of ours.

    Demanding one of every copy would fail on a developer's machine and on the Linux `.deb`'s own
    dependency - the guard would be switched off within a day, taking its real coverage with it.
    """
    outside = tmp_path / "usr-bin" / "exiftool"
    outside.parent.mkdir()
    outside.write_text("", encoding="utf-8")
    assert selfcheck._shipped_module_tree(outside) is None

    # Beside a bundled directory, both shapes are demanded - `lib/` on Unix, and the Windows
    # package's `exiftool_files/` tree, which upstream ships instead.
    bundled = tmp_path / "bin"
    bundled.mkdir()
    monkeypatch.setenv("TRUESTILL_BIN_DIR", str(bundled))
    assert selfcheck._shipped_module_tree(bundled / "exiftool") == bundled / "lib" / "Image"
    (bundled / "exiftool_files").mkdir()
    assert (
        selfcheck._shipped_module_tree(bundled / "exiftool.exe")
        == bundled / "exiftool_files" / "lib" / "Image"
    )


def test_a_resolved_exiftool_carries_its_path_as_evidence() -> None:
    """The cry-wolf half, and the evidence a packaging job reads to know WHICH copy answered."""
    finding = exiftool_finding()

    assert finding.status is Status.OK
    assert Path(str(finding.evidence["path"])).is_file()
    # The version proves the binary was INVOKED rather than merely found - the whole point of
    # the check, and the half a path assertion cannot carry.
    assert finding.evidence["version"], "no version, so exiftool was never run"


# ----------------------------------------------------------------------------------- locations


def test_the_locations_are_reported_as_facts_and_never_as_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Three paths written down nowhere a user can reach, and none of them is a pass or a fail.

    Filed as `INFO` deliberately: a catalog in an unusual place is not a defect, and reporting it
    as one would train a reader to ignore the line. They are here because an uninstall has to know
    which of them is unrecoverable, and because `session-url.txt` is the only way back into a
    running app whose browser did not open.

    **THE `chdir` IS LOAD-BEARING, and its absence was invisible until the cache line was fixed.**
    `conftest.py` isolates the data and cache directories but not the working directory, and
    `LEGACY_CATALOG_PATH` is relative - so run from this repo, where `reports/catalog.sqlite` is a
    real file, `default_catalog_path()` returned the DEVELOPER's catalog and this test was
    describing it. Nothing noticed while the cache line ignored the catalog; the moment it stopped
    ignoring it, this failed. The subject here is the OS-conventional install, so the working
    directory has to be one with no legacy catalog in it.
    """
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRUESTILL_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)

    findings = location_findings()

    assert {f.name for f in findings} == {"catalog", "cache", "session url"}
    assert all(f.status is Status.INFO for f in findings)
    assert is_complete(findings), "a fact must never fail the check"
    assert str(tmp_path / "cache") in _named(findings, "cache").detail
    assert str(tmp_path / "data") in _named(findings, "session url").detail


def test_the_cache_named_is_the_one_belonging_to_the_catalog_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE PAIRING, and the case the test above cannot reach.

    That one sets both overrides, so the catalog resolves to the OS-conventional path and
    `cache_path_for` returns the OS cache directory - the two answers agree there whatever the
    code does, which is why it stayed green while this was wrong.

    A **legacy** `reports/catalog.sqlite` is where they diverge: its cache is a sidecar beside it,
    not the OS cache directory. Found on a real machine, where the report named a `~/.cache`
    file that did not exist one line below the catalog it was supposedly describing.
    """
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRUESTILL_CACHE_DIR", str(tmp_path / "cache"))
    legacy = tmp_path / "checkout" / app_paths.LEGACY_CATALOG_PATH
    legacy.parent.mkdir(parents=True)
    legacy.touch()
    monkeypatch.chdir(tmp_path / "checkout")

    findings = location_findings()
    catalog = Path(str(_named(findings, "catalog").evidence["path"]))
    cache = Path(str(_named(findings, "cache").evidence["path"]))

    assert catalog == legacy.resolve(), "the legacy catalog should have won"
    assert cache == app_paths.cache_path_for(catalog), (
        f"the report names {cache}, which is not the cache belonging to {catalog}"
    )
    assert cache.parent == legacy.parent, "a legacy catalog's cache sits beside it"
    assert str(tmp_path / "cache") not in str(cache), (
        "the OS cache directory was named for a catalog that does not use it"
    )


# ------------------------------------------------------------- severity, exit codes, rendering


def test_worst_ranks_by_severity_and_not_alphabetically() -> None:
    """A failure outranks a pass, whatever the members happen to spell.

    `Status` is a `StrEnum`, so an unranked ``max`` compares **text**: alphabetically `ok` is the
    largest member of the whole enum, and `worst([ok, missing])` would answer `ok` - a report
    naming its own state as fine while carrying a missing dependency. That is the pair asserted
    here rather than a pair the alphabet happens to order correctly.
    """
    assert worst([]) is Status.OK, "nothing asked is not a claim that anything passed"
    assert worst([Finding("a", Status.OK, ""), Finding("b", Status.MISSING, "")]) is Status.MISSING
    assert worst([Finding("a", Status.OK, ""), Finding("b", Status.DEGRADED, "")]) is (
        Status.DEGRADED
    )
    assert worst([Finding("a", Status.DEGRADED, ""), Finding("b", Status.MISSING, "")]) is (
        Status.MISSING
    )


def test_a_fact_and_an_unchecked_surface_never_fail_the_check() -> None:
    """`INFO` and `NOT_CHECKED` are the two statuses that are neither passes nor failures.

    Separated from the ranking test above because it is a different promise: ranking is about
    which status is reported, this is about which ones may set an exit code. An install whose
    catalog sits in an unusual place has nothing wrong with it, and a surface nobody looked at
    has not been observed to be wrong.
    """
    assert is_complete([Finding("a", Status.INFO, "")])
    assert is_complete([Finding("a", Status.NOT_CHECKED, "")])
    assert not is_complete([Finding("a", Status.DEGRADED, "")])
    assert not is_complete([Finding("a", Status.MISSING, "")])


def test_a_surface_that_was_not_checked_cannot_be_read_as_one_that_passed() -> None:
    """**Silence and "ok" are the same thing to a reader**, and this is the third state.

    The rule this pins: an entry point that cannot see a surface says so, with a mark of its own,
    and repeats it in the closing line - because the closing line is what people actually read.
    It must not fail the check either; claiming a failure nobody observed is the same dishonesty
    pointing the other way.
    """
    findings = [
        Finding("trash", Status.OK, "send2trash"),
        not_checked_finding("app fonts", "truestill-app --self-check"),
    ]

    lines = render(findings)
    body = "\n".join(lines)

    assert "not checked here - run `truestill-app --self-check`" in body
    assert "Not checked: app fonts." in body
    assert "This install looks complete." not in body, (
        "the closing line claimed a complete install while a surface was never looked at"
    )
    assert is_complete(findings), "an unchecked surface must not be reported as a failure"


def test_a_complete_report_says_so_without_a_not_checked_clause() -> None:
    """The cry-wolf half of the test above: the caveat must not appear when nothing was skipped."""
    body = "\n".join(render([Finding("trash", Status.OK, "send2trash")]))

    assert "This install looks complete." in body
    assert "Not checked" not in body


def test_an_incomplete_report_says_what_the_bundled_message_already_promised() -> None:
    """`exif.py` tells a packaged user *"this installation looks incomplete"* and gives them
    nothing to run. This is what they run, so it has to close with the same words rather than a
    second vocabulary for the same state."""
    body = "\n".join(render([Finding("trash", Status.MISSING, "no trash backend")]))

    assert "This install looks incomplete." in body


# ------------------------------------------------------------------------------- findings file


def test_the_findings_file_is_written_whole_or_not_at_all(tmp_path: Path) -> None:
    """A windowed build has no console, so the FILE is the delivery mechanism, not a convenience.

    Atomic for the reason the windowed-launch probe already established: a half-written JSON file
    is worse than none, because a job would parse what it could and report a result nobody
    measured. Asserted by there being no leftover partial beside it.
    """
    destination = tmp_path / "nested" / "findings.json"

    written = write_findings([Finding("trash", Status.MISSING, "gone")], destination)

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert payload["worst"] == "missing"
    assert payload["findings"][0]["name"] == "trash"
    assert list(destination.parent.iterdir()) == [destination], "a partial file was left behind"


def test_core_findings_covers_every_check_core_can_answer_for() -> None:
    """The shape a packaging job reads. Pinned so a check cannot be dropped silently - the
    failure mode being a findings file that looks clean because it stopped asking."""
    names = [f.name for f in core_findings()]

    assert names == ["install", "exiftool", "trash", "catalog", "cache", "session url"]
