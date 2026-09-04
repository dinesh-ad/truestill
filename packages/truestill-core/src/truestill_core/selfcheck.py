"""What this installation actually contains, asked from inside the installation.

**The defect this closes ((aad)).** Two acceptance criteria are on the **frozen artifact** - it
must resolve a real trash backend, and it must carry the bundled font and its licence - and every
guard that existed read the **source tree**: `test_trash_backend_is_available.py` runs against the
checkout on the three-OS matrix, `test_bundled_font_ships_with_its_licence.py` resolves a path
relative to `packages/`, and the browser lane fetches from a dev server. `(aad)` states the
consequence itself: *a green matrix plus a broken bundle is exactly the state that would read as
verified*.

**So the one rule this module lives or dies by: every finding resolves through the RUNNING CODE'S
OWN LOCATION or a LIVE CALL, never through a repo-relative path.** `ensure_exiftool` searches
`_MEIPASS` and the directory beside the executable before PATH; `trash_backend` performs the real
import; `default_catalog_path` resolves per call. If a check here can pass in a developer's tree
while the bundle beside it is broken, it has reproduced the defect it exists to close.

**What this must NOT try to decide: whether the bytes it found are the RIGHT bytes.** An artifact
cannot know what it was supposed to contain - a truncated font and a correct one are both "a file
that is here". So a finding reports **what it holds** (size, sha256, resolved path) and the
comparison against the source of truth belongs to the **caller**: the packaging job diffs the
reported digest against the repository's own file. That split is the only reason `(aad)`'s "the
byte count of the source file" is checkable from inside a bundle at all.

**Why the output has two homes and one wording.** `render` lives here rather than in either
front-end because §9 forbids the CLI and the app wording one outcome differently, and this is an
outcome both of them report. The same reasoning that gave `models.status_label` one home.

**Why a findings FILE and not print.** Inherited rather than rediscovered, from the windowed-launch
probe: a windowed Windows build has ``sys.stdout is None`` and `print` is a silent no-op, so a
self-check that only printed would report nothing at all on the exact platform it exists for.
`write_findings` therefore writes to a path the caller names, atomically - a half-written JSON file
is worse than none, because a reader would parse what it could and report a result nobody measured.

**Complexity: O(1)** - one `shutil.which` sweep, one import probe, and string joins. No walk, no
catalog open, and deliberately nothing that could modify the install it is describing.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from truestill_core import __version__, app_paths, binaries
from truestill_core.binaries import bundled_bin_dirs, is_bundled_install
from truestill_core.cleanup import trash_backend
from truestill_core.exif import ExiftoolMissingError, ensure_exiftool
from truestill_core.safe_copy import staging_path
from truestill_core.version import UNKNOWN_VERSION

#: The backend `cleanup` is *declared* to use. Asserted by **identity**, never as "something
#: non-empty": `gio` answers on a Linux desktop while telling you nothing about Windows or macOS,
#: which is the whole argument `test_trash_backend_is_available.py` was written around. A bundle
#: that answers `gio` has dropped the declared dependency and is reported as degraded, not ok.
DECLARED_TRASH_BACKEND = "send2trash"


class Status(StrEnum):
    """How a single finding came out.

    `INFO` and `NOT_CHECKED` are deliberately **not** passes. `INFO` states a fact with no pass
    or fail available (where the catalog lives). `NOT_CHECKED` says a surface exists that this
    entry point cannot speak for - it must never be rendered as though it had been checked and
    found good, which is the difference between an honest boundary and a false reassurance.
    """

    OK = "ok"
    INFO = "info"
    NOT_CHECKED = "not_checked"
    DEGRADED = "degraded"
    MISSING = "missing"


#: Only `DEGRADED` and `MISSING` are failures. Ranked rather than compared as strings so adding a
#: member forces a decision here instead of silently sorting alphabetically.
_SEVERITY: dict[Status, int] = {
    Status.OK: 0,
    Status.INFO: 0,
    Status.NOT_CHECKED: 0,
    Status.DEGRADED: 1,
    Status.MISSING: 2,
}


@dataclass(frozen=True, slots=True)
class Finding:
    """One line of the answer.

    ``detail`` is the sentence a person reads; ``evidence`` is what a job parses. Both, because
    the two audiences need different things from the same check and giving a machine prose to
    regex is how a report becomes unmaintainable.
    """

    name: str
    status: Status
    detail: str
    evidence: dict[str, str | int] = field(default_factory=dict)

    def as_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": str(self.status),
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


def worst(findings: list[Finding]) -> Status:
    """The most serious status present - what an exit code is derived from.

    Returns `Status.OK` for an empty list, which is not a claim that anything passed; it is the
    only honest answer when nothing was asked.
    """
    return max((f.status for f in findings), key=lambda s: _SEVERITY[s], default=Status.OK)


def is_complete(findings: list[Finding]) -> bool:
    """Whether this install looks complete: nothing degraded, nothing missing."""
    return _SEVERITY[worst(findings)] == 0


def _shipped_module_tree(binary: Path) -> Path | None:
    """Where a **bundled** exiftool's own modules must sit, or ``None`` when it is not bundled.

    Both platforms ship the same shape and it is the shape upstream's README describes: *"if you
    move the exiftool script to a different directory, you must also either move the contents of
    the lib directory or install the Image::ExifTool package"*. On Unix that is `lib/` beside the
    script; on Windows the package is a 57 KB launcher plus an `exiftool_files/` tree holding
    `perl.exe`, its DLLs and the same modules.

    ``None`` for a copy resolved from PATH - a system exiftool is the distro's business and has no
    tree of ours to check.
    """
    if not any(binary.parent == d for d in bundled_bin_dirs()):
        return None
    windows_tree = binary.parent / "exiftool_files" / "lib" / "Image"
    if (binary.parent / "exiftool_files").is_dir():
        return windows_tree
    return binary.parent / "lib" / "Image"


def exiftool_finding() -> Finding:
    """Does this install find the exiftool it shipped with - **and can it actually run it?**

    Resolved through `ensure_exiftool`, so the search order is the real one: the override, the
    bundled directories, then PATH. A bundle that shipped exiftool and cannot find it fails here
    for the same reason it would fail mid-organize.

    **RESOLVING IS NOT RUNNING, and the difference is a shipped defect rather than a nicety.**
    Measured 2026-08-13 while exercising the release lane: PyInstaller's `--add-binary` copies
    **one file**, and on Linux `exiftool` is a Perl script whose `Image::ExifTool` modules live in
    the distro's `/usr/share/perl5`. The bundle carries none of them. The artifact therefore
    resolved a path, reported `ok`, and would have failed on the first photo any user without
    exiftool already installed opened - **which is precisely the user the bundle exists for.**
    A check that only resolves is a check that passes on that artifact.

    So the binary is invoked. `-ver` is the cheapest call that proves the whole chain - the
    interpreter, the modules, the executable bit - and it prints one line.
    """
    try:
        resolved = ensure_exiftool()
    except ExiftoolMissingError as exc:
        return Finding("exiftool", Status.MISSING, str(exc))

    evidence: dict[str, str | int] = {"path": resolved}
    try:
        proc = binaries.run(
            [resolved, "-ver"], capture_output=True, text=True, check=False, timeout=30
        )
    except OSError as exc:  # not executable, bad interpreter, wrong architecture
        return Finding(
            "exiftool",
            Status.DEGRADED,
            f"found at {resolved} but it will not run ({exc})",
            evidence,
        )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return Finding(
            "exiftool",
            Status.DEGRADED,
            f"found at {resolved} but it failed to run: {detail[0] if detail else 'no output'}",
            evidence,
        )
    version = (proc.stdout or "").strip()
    evidence["version"] = version

    # RUNNING IS NOT RUNNING FROM WHAT WE SHIPPED. `exiftool` is a script that falls back to the
    # HOST's `Image::ExifTool` when its own module tree is absent - it exits 0 and mentions the
    # substitution only as a warning. Measured 2026-08-13: a bundle stripped of its entire `lib/`
    # reported `ok` with `13.59 [Warning: Library version is 13.50]`, which is precisely the
    # bundle-works-here-fails-there defect these criteria exist for, passing the check written to
    # catch it. So the modules are looked for beside the binary, and a version warning is treated
    # as the substitution it announces.
    if "warning" in version.lower():
        return Finding(
            "exiftool",
            Status.DEGRADED,
            f"ran, but warned rather than answering cleanly: {version}",
            evidence,
        )
    modules = _shipped_module_tree(Path(resolved))
    if modules is not None and not modules.is_dir():
        return Finding(
            "exiftool",
            Status.DEGRADED,
            f"found at {resolved} but its module tree is missing ({modules}); it is running on "
            f"whatever this machine happens to have installed",
            evidence,
        )
    return Finding("exiftool", Status.OK, f"{version} at {resolved}", evidence)


def trash_finding() -> Finding:
    """Is the declared trash backend importable **here**, in this install?

    The severity ladder is the safety argument, not tidiness. `send2trash` is the declared
    dependency and works on every platform. `gio` is a GLib tool absent from stock Windows and
    macOS, so an install answering `gio` has lost the dependency and only happens to work on this
    machine - degraded. Nothing at all means `clean-empty` refuses every folder
    (`IMPLEMENTATION_STANDARDS.md` §1: an absent backend is a refusal), which is a shipped feature
    that never works.

    **`DEGRADED` IS NOT A PASS, AND THE NEXT PERSON WILL WANT TO MAKE IT ONE** - it works here,
    after all. It is the same shape as `drive.DriveReach.OFFLINE` versus a drive that is gone:
    both fail to answer right now, and folding them together loses the only distinction that
    decides what to do about it. A `gio` answer means *this bundle has lost the declared
    dependency and is being carried by the developer's desktop*, which is a statement about the
    **bundle** on every platform, not about this machine. Reported as `OK` it would be a green
    tick on Linux for a build that has no trash at all on the platform D9 launches first.
    """
    backend = trash_backend()
    if backend == DECLARED_TRASH_BACKEND:
        return Finding("trash", Status.OK, backend, {"backend": backend})
    if backend is not None:
        return Finding(
            "trash",
            Status.DEGRADED,
            f"falling back to '{backend}' - '{DECLARED_TRASH_BACKEND}' is not importable here, "
            f"so this install would have no trash on Windows or macOS",
            {"backend": backend},
        )
    return Finding(
        "trash",
        Status.MISSING,
        "no trash backend - Truestill will refuse to remove empty folders rather than delete "
        "them outright",
        {"backend": ""},
    )


def location_findings() -> list[Finding]:
    """Where this install keeps its own files. Facts, not passes - hence `INFO`.

    **Three of these are written down nowhere a user can reach**, which is why they are reported
    rather than assumed. The catalog is unrecoverable user data and the cache is disposable
    (`(aae)`), a distinction anything that ever uninstalls Truestill has to respect; and
    `session-url.txt` is the only way back into a running app whose browser did not open, on a
    windowed launch where the message saying so goes nowhere.

    **THE CACHE LINE IS THE COUNTERPART OF THE CATALOG LINE ABOVE IT, never the OS default.**
    `app_paths.cache_path_for` is the rule - the OS cache directory for the OS-conventional
    catalog, and a sidecar beside anything else - and this reported `default_cache_path()`
    instead, so the two adjacent lines described different installs whenever a legacy
    `reports/catalog.sqlite` was in use. Observed on a real machine 2026-08-13: the report named
    `~/.cache/Truestill/hashes.cache.sqlite`, **a directory that did not exist**, one line under
    the catalog whose actual cache was `reports/catalog.cache.sqlite` and 1.6 MB. A report whose
    purpose is telling somebody which file is disposable must not name a file nothing uses.
    """
    catalog = app_paths.default_catalog_path()
    cache = app_paths.cache_path_for(catalog)
    return [
        Finding(
            "catalog",
            Status.INFO,
            # ⚠ The suffix here was `'' if catalog == standard else ' (older location, still in
            # use)'`, comparing this path against `standard_catalog_path()`. `(adw)` removed the
            # only state in which those could differ, so the test was left comparing two spellings
            # of one file - and a symlinked data directory made it label the live catalog as an
            # older location, which is the one thing a report about what is disposable must not
            # get wrong. `(aeb)`.
            str(catalog),
            {"path": str(catalog)},
        ),
        Finding(
            "cache",
            Status.INFO,
            f"{cache} (safe to delete; costs only time)",
            {"path": str(cache)},
        ),
        Finding(
            "session url",
            Status.INFO,
            f"{app_paths.session_url_path()} (the address of a running app)",
            {"path": str(app_paths.session_url_path())},
        ),
    ]


def install_finding() -> Finding:
    """Packaged or a source checkout, and the executable this process is running from.

    `is_bundled_install` reads `sys.frozen`, so it is a statement about the **kind of process**
    rather than about what could be found - and its known limit is recorded at its definition: a
    Briefcase-style install ships an ordinary interpreter and reads `False`. Reported rather than
    relied on, so a findings file from a bundle that answers `False` shows that fact instead of
    hiding it inside another check's verdict.
    """
    bundled = is_bundled_install()
    return Finding(
        "install",
        Status.INFO,
        f"{'packaged' if bundled else 'source checkout'} - {sys.executable}",
        {"bundled": int(bundled), "executable": sys.executable},
    )


def version_finding(distribution: str, reported: str) -> Finding:
    """What this install believes its own version to be - and `DEGRADED` when it cannot say.

    **`reported` is the RUNNING module's `__version__`, never a fresh lookup, and that is the
    whole point of the argument.** `truestill_app.__version__` is computed once at import and is
    the exact string the settings screen renders and `--version` prints; a lookup performed here
    would answer a different question and could agree while the screen disagreed. This module's
    one rule is that a finding resolves through the running code, and passing the attribute in is
    how that rule reaches a value core cannot import for itself (`IMPLEMENTATION_STANDARDS.md`
    §2 - core never imports the app).

    **`UNKNOWN_VERSION` IS `DEGRADED`, NOT `INFO`, AND THAT IS THE ENTIRE GUARD.** `(ajw)`:
    v0.1.0 and v0.1.1 both shipped a settings screen reading *"truestill unknown (not
    installed)"* on an installed copy, because `release.yml` collected the package's data and
    never its metadata, so `importlib.metadata` found no `.dist-info` in the frozen tree. Nothing
    noticed for two releases - the self-check reported `install: packaged` and said nothing about
    the version at all. A finding that reported the unknown value and passed would reproduce
    exactly that: `worst` would stay `OK`, the release gate would stay green, and the artifact
    would go on being unable to name itself. `DEGRADED` makes it an artifact this project does
    not publish.

    Complexity: O(1) - a string comparison.
    """
    name = f"version {distribution}"
    evidence: dict[str, str | int] = {"distribution": distribution, "version": reported}
    if reported == UNKNOWN_VERSION:
        return Finding(
            name,
            Status.DEGRADED,
            f"this install cannot say what version it is - no metadata for '{distribution}' is "
            f"reachable here, so every screen, every --version and every bug report reads "
            f"'{UNKNOWN_VERSION}'",
            evidence,
        )
    return Finding(name, Status.OK, reported, evidence)


def core_findings() -> list[Finding]:
    """Everything `truestill-core` can answer for on its own.

    It cannot answer for the app's static assets - the fonts and their licence live in
    `truestill-app`, and core importing the app is forbidden (`IMPLEMENTATION_STANDARDS.md` §2).
    A caller that cannot reach them must say so with `not_checked_finding`, never by omission.
    """
    return [
        install_finding(),
        version_finding("truestill-core", __version__),
        exiftool_finding(),
        trash_finding(),
        *location_findings(),
    ]


def not_checked_finding(name: str, run_instead: str) -> Finding:
    """A surface this entry point cannot speak for, said out loud.

    **Silence and "ok" are the same thing to a reader**, which is the whole reason this exists.
    `truestill self-check` runs in a package that depends on core only, so it can say nothing
    about the app's fonts - and a report that simply omitted them would let someone conclude
    their install is complete when a third of it was never looked at.
    """
    return Finding(name, Status.NOT_CHECKED, f"not checked here - run `{run_instead}`")


#: Rendered in front of each line. `NOT_CHECKED` gets a mark of its own rather than sharing
#: `INFO`'s, so it cannot be skimmed as a neutral fact about the install.
_MARKS: dict[Status, str] = {
    Status.OK: "ok",
    Status.INFO: "--",
    Status.NOT_CHECKED: "??",
    Status.DEGRADED: "!!",
    Status.MISSING: "!!",
}


def render(findings: list[Finding]) -> list[str]:
    """The human form, in one home so the CLI and the app cannot word it differently (§9).

    The closing sentence is deliberately about *this* report: an entry point that skipped a
    surface says so again at the end, because the summary line is the one people read.
    """
    width = max((len(f.name) for f in findings), default=0)
    lines = [f"  {_MARKS[f.status]:<2}  {f.name:<{width}}  {f.detail}" for f in findings]
    skipped = [f.name for f in findings if f.status is Status.NOT_CHECKED]
    if not is_complete(findings):
        lines.append("")
        lines.append("This install looks incomplete. Installing Truestill again should fix it.")
    elif skipped:
        lines.append("")
        lines.append(f"Everything checked here looks right. Not checked: {', '.join(skipped)}.")
    else:
        lines.append("")
        lines.append("This install looks complete.")
    return lines


def write_findings(findings: list[Finding], destination: Path) -> Path:
    """Write the report **atomically**, so a partial file can never read as a pass.

    Written to a sibling and renamed, so no reader ever opens a half-written file. The reason
    this exists at all rather than printing: a windowed build has no console and `print` is a
    silent no-op there, which is the platform this whole check was written for.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "complete": is_complete(findings),
        "worst": str(worst(findings)),
        "findings": [f.as_json() for f in findings],
    }
    # `(aaw)`: one home, and never shared between processes.
    partial = staging_path(destination)
    partial.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    partial.replace(destination)
    return destination
