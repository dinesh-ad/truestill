#!/usr/bin/env python3
"""Which tests does each mutation kill, and which tests does nothing kill?

`ENGINEERING_STANDARD.md` §4 has treated mutation as the method for a while - the fifth member
asks whether the mutant was loaded, the fifteenth whether it was unique, the thirty-first whether
the proof ran in both directions. This runs the whole thing as a matrix instead of one mutation at
a time, because a single mutation only tells you about the tests it happened to touch.

**Two findings fall out, they are not the same finding, and they need opposite fixes.**

* A test killed by **no** mutation is unproven. Either it asserts a state that something other
  than the code under test also produces (§4's fiftieth member), or it fences against a change
  nobody has made. The first is worthless and gets rewritten; the second is legitimate and gets a
  mutation written for it.
* A mutation that kills **no** test is §4's thirty-first member's other outcome: either a guard is
  missing, or the code is dead. One is a test, the other a deletion.

**Not wired into `make check`.** A full matrix is minutes, not seconds, and §6.1 keeps the gate
fast on purpose. Run it when adding a body of tests, or when a guard's value is in doubt.

    uv run python scripts/mutation_matrix.py --suite thumbnails
    uv run python scripts/mutation_matrix.py --suite grid

**A stale mutation is a loud failure, deliberately.** When a target string no longer exists the
run stops and names it, rather than skipping that mutant - a silently skipped mutation reports
coverage it never measured, which is the same defect this script exists to find.
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "packages/truestill-core/src/truestill_core"
APP = ROOT / "packages/truestill-app/src/truestill_app"


@dataclass(frozen=True)
class Mutant:
    """One plausible defect: replace ``old`` with ``new`` in ``path`` and see what notices.

    ``extra`` carries further ``(path, old, new)`` edits applied together with the first.

    **It exists because a REDUNDANT PAIR cannot be killed by any single-point mutation, and that
    is not the same as being dead.** The grid's tiles get their square box from two independent
    mechanisms - the stylesheet's `aspect-ratio` and the `width`/`height` attributes - and either
    alone is sufficient. Removing one changed nothing, which reads exactly like dead code and is
    not: removing both fails two tests. Deleting the "unfired" declaration on that evidence would
    have quietly removed the fallback that covers first paint, before the stylesheet applies.
    """

    path: Path
    old: str
    new: str
    label: str
    extra: tuple[tuple[Path, str, str], ...] = ()

    @property
    def edits(self) -> tuple[tuple[Path, str, str], ...]:
        return ((self.path, self.old, self.new), *self.extra)


@dataclass(frozen=True)
class Suite:
    tests: tuple[str, ...]
    mutants: tuple[Mutant, ...]


def _thumbnails() -> Suite:
    core_thumbs = CORE / "thumbnails.py"
    svc = APP / "service/thumbs.py"
    srv = APP / "server.py"
    org = APP / "service/organize.py"
    organizer = CORE / "organizer.py"
    sec = APP / "security.py"
    m = [
        Mutant(
            core_thumbs,
            '    if not _SHA256.match(sha256):\n        message = "content id is not a '
            'sha256"\n        raise BadContentIdError(message)\n',
            "",
            "sha shape check removed",
        ),
        Mutant(
            core_thumbs,
            'sha256[:2] / f"{sha256}.webp"',
            'f"{sha256}.webp"',
            "fan-out bucket removed",
        ),
        Mutant(
            core_thumbs,
            "return cache_dir / CACHE_SUBDIR",
            "return cache_dir.parent / CACHE_SUBDIR",
            "cache entry escapes the cache dir",
        ),
        Mutant(core_thumbs, '.webp"', '.jpg"', "cache suffix changed"),
        Mutant(
            core_thumbs, '        image.draft("RGB", _fitted(*image.size))\n', "", "draft dropped"
        ),
        Mutant(
            core_thumbs,
            'image.draft("RGB", _fitted(*image.size))',
            'image.draft("RGB", (THUMB_PX, THUMB_PX))',
            "square draft target",
        ),
        Mutant(
            core_thumbs,
            "    return max(1, round(width * THUMB_PX / height)), THUMB_PX",
            "    return THUMB_PX, max(1, round(height * THUMB_PX / width))",
            "portrait branch broken",
        ),
        Mutant(
            core_thumbs,
            "image.thumbnail((THUMB_PX, THUMB_PX))",
            "image.thumbnail((THUMB_PX * 3, THUMB_PX * 3))",
            "thumbnail target enlarged",
        ),
        Mutant(
            core_thumbs,
            "image.thumbnail((THUMB_PX, THUMB_PX))",
            "image = image.resize(_fitted(*image.size))",
            "resize instead of thumbnail (upscales)",
        ),
        Mutant(
            core_thumbs,
            'image.convert("RGB").save(buffer, "WEBP", quality=_QUALITY, method=_METHOD)',
            'image.convert("RGB").save(buffer, "PNG")',
            "encoded as PNG not WEBP",
        ),
        Mutant(
            core_thumbs,
            'image.convert("RGB").save(buffer, "WEBP", quality=_QUALITY, method=_METHOD)',
            'image.convert("RGB").save(source, "JPEG")\n        buffer.write(b"x")',
            "render writes over the original",
        ),
        Mutant(
            core_thumbs,
            '        partial = target.with_name(f"{target.name}.{id(data):x}.partial")\n'
            "        partial.write_bytes(data)\n        partial.replace(target)",
            "        target.write_bytes(data)",
            "atomic rename -> direct write",
        ),
        Mutant(
            core_thumbs,
            "    data = render(source)",
            '    try:\n        data = render(source)\n    except Exception:\n        data = b""',
            "failed render cached",
        ),
        Mutant(
            core_thumbs,
            "    try:\n        return target.read_bytes()\n    except OSError:\n        pass\n",
            "",
            "cache-first read removed",
        ),
        Mutant(
            core_thumbs,
            "from truestill_core.hashing import HEIF_AVAILABLE",
            "HEIF_AVAILABLE = True",
            "hashing import dropped",
        ),
        Mutant(svc, "            check_contained(relative)\n", "", "check_contained removed"),
        Mutant(
            svc, 'CACHE_CONTROL = "private,', 'CACHE_CONTROL = "public,', "Cache-Control public"
        ),
        Mutant(
            svc,
            'CACHE_CONTROL = "private, max-age=31536000, immutable"',
            'CACHE_CONTROL = "no-store"',
            "caching disabled",
        ),
        Mutant(
            svc,
            "    try:\n        return cached.read_bytes()\n    except OSError:\n        pass\n",
            "",
            "route cache-first read removed",
        ),
        Mutant(
            svc,
            "            if candidate.is_file():\n                return candidate",
            "            return candidate",
            "unreachable file returned anyway",
        ),
        Mutant(
            sec,
            'if request.url.path.startswith("/static/"):',
            'if request.url.path.startswith(("/static/", "/api/thumb/")):',
            "thumb route exempted from the guard",
        ),
        Mutant(
            srv,
            '            return PlainTextResponse("that file is not a decodable image", '
            "status_code=415)",
            '            return PlainTextResponse("no reachable copy of that content", '
            "status_code=404)",
            "415 collapsed into 404",
        ),
        Mutant(
            srv,
            '            return PlainTextResponse("not a content id", status_code=400)',
            '            return PlainTextResponse("not a content id", status_code=404)',
            "400 collapsed into 404",
        ),
        Mutant(
            srv,
            '            data, media_type="image/webp", headers={"Cache-Control": '
            "service.THUMB_CACHE_CONTROL}",
            '            data, media_type="application/octet-stream"',
            "media type and cache header dropped",
        ),
        Mutant(
            srv,
            'Route("/api/thumb/{sha256}", thumb),',
            'Route("/api/thumb/{sha256:path}", thumb),',
            "route declared with a path converter",
        ),
        Mutant(
            srv,
            "        except service.NoReachableCopyError:\n            return "
            'PlainTextResponse("no reachable copy of that content", status_code=404)',
            "        except service.NoReachableCopyError:\n"
            "            from truestill_core.catalog_session import open_catalog as _oc\n"
            "            with _oc(_db()) as _c:\n"
            "                known = bool(_c.drives_holding([sha]))\n"
            "            return PlainTextResponse(\n"
            '                "that copy is gone" if known else "no such content",\n'
            "                status_code=410 if known else 404,\n            )",
            "unknown vs unreachable answered differently (membership oracle)",
        ),
        Mutant(
            org,
            '"total": len(photos),',
            '"total": len(organized),',
            "total counts organized not photos",
        ),
        Mutant(org, "for r in photos[:GRID_SAMPLE_LIMIT]", "for r in photos", "sample cap removed"),
        Mutant(
            org,
            'if media_kind(r.resolution.decision.source.name) == "photo" and r.sha256 is not None',
            "if r.sha256 is not None",
            "videos and audio admitted to the grid",
        ),
        Mutant(
            org,
            "        for r in organized\n        if media_kind",
            "        for r in results\n        if media_kind",
            "skipped duplicates admitted to the grid",
        ),
        Mutant(
            org,
            'if media_kind(r.resolution.decision.source.name) == "photo" and r.sha256 is not None',
            'if media_kind(r.resolution.decision.source.name) == "photo"',
            "unaddressable photo admitted",
        ),
        Mutant(
            org,
            '                    "sha256": cast("str", r.sha256),',
            '                    "sha256": cast("str", r.resolution.hashes.sha256),',
            "sample reads the pre-filter hash again",
        ),
        Mutant(
            org,
            '        "organized_sample": {\n            "total": len(photos),',
            '        "organized_sample": {} if not photos else {\n            "total": len(photos),',
            "empty sample omits its keys",
        ),
        Mutant(
            organizer,
            '"; ".join(notes), source_sha)',
            '"; ".join(notes))',
            "result stops carrying its content id",
        ),
        Mutant(
            organizer,
            "record(ActionResult(resolution, ActionStatus.FAILED, None, str(exc)))",
            'record(ActionResult(resolution, ActionStatus.FAILED, None, str(exc), "unknown"))',
            "a failed outcome claims a content id",
        ),
    ]
    return Suite(
        (
            "packages/truestill-core/tests/test_thumbnails.py",
            "packages/truestill-app/tests/test_thumb_route.py",
            "packages/truestill-app/tests/test_organized_sample.py",
            "packages/truestill-core/tests/test_a_result_knows_its_content_id.py",
        ),
        tuple(m),
    )


def _grid() -> Suite:
    j, c = APP / "static/app.js", APP / "static/app.css"
    m = [
        Mutant(j, 'loading="lazy" decoding="async"', 'decoding="async"', "loading=lazy dropped"),
        Mutant(j, 'loading="lazy" decoding="async"', 'loading="lazy"', "decoding=async dropped"),
        Mutant(j, 'width="320" height="320"', "", "intrinsic size dropped (layout shift)"),
        Mutant(j, "?token=${encodeURIComponent(TOKEN)}", "", "token dropped from the tile URL"),
        Mutant(
            j,
            'src="/api/thumb/${encodeURIComponent(t.sha256)}',
            'src="/api/thumb/${t.sha256}',
            "sha not URL-encoded",
        ),
        Mutant(j, "     ${grid}\n", "", "grid removed from the card"),
        Mutant(
            j,
            '     ${sub ? `<div class="k">${sub}</div>` : ""}\n     ${grid}',
            '     ${sub ? `<div class="k">${sub}</div>` : ""}\n'
            '     ${statRows ? `<div class="tally">${statRows}</div>` : ""}\n     ${grid}',
            "grid moved below the numbers",
        ),
        Mutant(
            j,
            'alt="${esc(t.name)}" title="${esc(t.name)}"',
            'alt="${t.name}" title="${t.name}"',
            "escaping removed from the file name",
        ),
        Mutant(
            j,
            "  const more = total > shown.length",
            "  const more = false",
            "truncation notice removed",
        ),
        Mutant(
            j,
            '  if (!shown.length) return "";',
            '  if (false) return "";',
            "empty grid frame rendered anyway",
        ),
        Mutant(c, "minmax(148px, 1fr)", "minmax(96px, 1fr)", "tiles shrunk to postage stamps"),
        Mutant(c, "minmax(148px, 1fr)", "minmax(300px, 1fr)", "tiles upscaled past the thumbnail"),
        Mutant(
            c,
            "repeat(auto-fill, minmax(148px, 1fr))",
            "repeat(6, 148px)",
            "fixed columns overflow the card",
        ),
        Mutant(c, "  object-fit: cover;\n", "", "crop dropped (a 4:3 photo is stretched)"),
        # Compound: the square box has TWO independent sources and either alone is enough, so no
        # single-point mutation can reach it. See `Mutant.extra`.
        Mutant(
            c,
            "  aspect-ratio: 1;\n",
            "",
            "the square box loses BOTH its mechanisms",
            extra=((j, 'width="320" height="320"', ""),),
        ),
    ]
    return Suite(("tests/e2e/test_the_grid_is_the_result.py",), tuple(m))


SUITES = {"thumbnails": _thumbnails, "grid": _grid}

# The gate's own §4 forty-ninth member: CPython revalidates a .pyc on the source's mtime in whole
# SECONDS plus its byte size, and a mutation cycle beats both - a same-size edit restored inside
# one second leaves the mutant running.
ENV_NOTE = "PYTHONDONTWRITEBYTECODE=1"


def _pytest(tests: tuple[str, ...]) -> tuple[set[str], int]:
    """Failing node ids, read from JUnit XML.

    Not from the summary text: a nodeid can contain spaces and the " - " that separates it from
    its message, so every regex over that output silently under-reports - and an under-reported
    failure set reads exactly like "nothing failed".
    """
    report = Path(tempfile.mkdtemp()) / "r.xml"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *tests,
            "--tb=no",
            f"--junitxml={report}",
            "--override-ini=addopts=",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if not report.exists():
        sys.exit(f"pytest produced no report:\n{proc.stdout[-3000:]}")
    failed = {
        f"{case.get('classname', '').split('.')[-1]}.py::{case.get('name')}"
        for case in ET.parse(report).iter("testcase")
        if case.find("failure") is not None or case.find("error") is not None
    }
    shutil.rmtree(report.parent, ignore_errors=True)
    return failed, proc.returncode


def _collect(tests: tuple[str, ...]) -> set[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "--collect-only", "-q", "--override-ini=addopts="],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    found = {
        f"{line.split('::', 1)[0].split('/')[-1]}::{line.split('::', 1)[1].strip()}"
        for line in proc.stdout.splitlines()
        if "::" in line
    }
    if not found:
        sys.exit(
            f"collected nothing; this run would report a clean sheet it never earned:\n"
            f"{proc.stdout[-2000:]}"
        )
    return found


def _guard(paths: set[Path]) -> Callable[..., None]:
    """Refuse to start on a dirty target, and restore through git rather than through memory.

    §4's fifty-first member: a run that is killed never reaches its `finally`, and the mutant it
    was holding stays on disk looking like ordinary work in progress. Restoring with
    `git checkout --` needs nothing of this process to still be alive.
    """
    rel = sorted(str(p.relative_to(ROOT)) for p in paths)
    dirty = subprocess.run(
        ["git", "diff", "--name-only", "--", *rel],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    if dirty:
        sys.exit(
            "REFUSING TO RUN: mutation targets already differ from HEAD:\n  "
            + "\n  ".join(dirty)
            + "\n\nIf a previous run was interrupted this is its stranded mutant. Restore with:\n"
            f"  git checkout -- {' '.join(dirty)}"
        )

    def restore(*_: object) -> None:
        subprocess.run(["git", "checkout", "--", *rel], cwd=ROOT, check=False)

    atexit.register(restore)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(1))
    return restore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    suite = SUITES[parser.parse_args().suite]()

    every = _collect(suite.tests)
    print(f"{len(every)} tests, {len(suite.mutants)} mutants, {ENV_NOTE}\n")

    restore = _guard({path for m in suite.mutants for path, _, _ in m.edits})
    baseline, code = _pytest(suite.tests)
    if code != 0:
        sys.exit(f"BASELINE IS RED, so nothing below would mean anything: {sorted(baseline)}")

    killed_by: dict[str, set[str]] = defaultdict(set)
    inert: list[str] = []
    for mutant in suite.mutants:
        for path, old, new in mutant.edits:
            source = path.read_text()
            if old not in source:
                sys.exit(f"STALE MUTANT - target gone from {path.name}: {mutant.label}")
            path.write_text(source.replace(old, new, 1))
        try:
            failed, _ = _pytest(suite.tests)
        finally:
            restore()
            for cached in ROOT.rglob("__pycache__"):
                shutil.rmtree(cached, ignore_errors=True)
        if not failed:
            inert.append(mutant.label)
        for test in failed:
            killed_by[test].add(mutant.label)
        print(f"{'kills ' + str(len(failed)):>10}  {mutant.label}")

    after, code = _pytest(suite.tests)
    if code != 0:
        sys.exit(f"NOT RESTORED after the run: {sorted(after)}")

    unproven = sorted(every - set(killed_by))
    print(f"\n{'=' * 78}")
    print(f"TESTS KILLED BY NO MUTATION ({len(unproven)}) - unproven, or fencing a future change:")
    for test in unproven:
        print("  -", test)
    print(f"\nMUTATIONS THAT KILLED NOTHING ({len(inert)}) - missing guard, or dead code:")
    for label in inert:
        print("  -", label)
    return 1 if (unproven or inert) else 0


if __name__ == "__main__":
    raise SystemExit(main())
