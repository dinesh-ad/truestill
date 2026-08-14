"""The served React bundle was built from the sources currently on disk.

**The whole proof of the migration's seam, and the reason it is content-based.** The bundle is a
build artifact: `static/dist/` is gitignored, so what a browser executes is whatever the last
`vite build` produced. Nothing else in this repo can tell you whether that matches the TypeScript
beside it - `ruff`, `mypy` and 2385 pytest cases never read it, and the e2e suite would happily
assert against a month-old bundle and pass.

**Not a timestamp.** "The bundle is newer than its sources" is a clock comparison, and
`ENGINEERING_STANDARD.md` §4's forty-ninth member is a worked example of exactly that failing: a
same-second, same-byte-size restore left CPython running a mutant because `.pyc` validation
compares mtime in whole seconds. A build one second before an edit would pass a newer-than check
while serving the wrong code. So the sources are hashed, the digest is compiled into the bundle,
and this compares the two.

**It also proves the seam end to end, which is why it stands in for a first island.** It can only
pass if the toolchain built, the bundle landed where Starlette serves it, the page loaded it as a
module, and the browser executed it. Any one of those broken and the attribute is absent or stale.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from playwright.sync_api import Page

pytestmark = pytest.mark.shell

FRONTEND = Path(__file__).resolve().parents[2] / "packages/truestill-app/frontend"

#: Everything that decides the bundle's bytes. Must match `HASHED` in `vite.config.ts`; the two
#: implementations are deliberately dull so that agreeing is easy.
HASHED = ("src", "vite.config.ts", "package.json", "package-lock.json")


def source_hash() -> str:
    """sha256 over sorted (relative path, contents), truncated - the same recipe as the build.

    `package-lock.json` is skipped when absent on both sides rather than treated as empty, so a
    checkout without `npm install` produces the same digest in Python and in Vite instead of two
    different ones that look like staleness.
    """
    files: list[Path] = []
    for name in HASHED:
        target = FRONTEND / name
        if not target.exists():
            continue
        if target.is_dir():
            files.extend(p for p in target.rglob("*") if p.is_file())
        else:
            files.append(target)

    digest = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.relative_to(FRONTEND).as_posix()):
        digest.update(path.relative_to(FRONTEND).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def test_the_frontend_is_built_at_all() -> None:
    """The cry-wolf guard. Without it, a missing bundle and a stale one fail the same way, and
    the message sends you looking for a mismatch when the answer is `npm run build`."""
    bundle = FRONTEND.parent / "src/truestill_app/static/dist/main.js"
    assert bundle.is_file(), (
        f"no bundle at {bundle}. Run `make frontend` - `static/dist/` is a build artifact and is "
        "not in git, so a fresh clone has none until it is built."
    )


def test_the_served_bundle_was_built_from_these_sources(ui: Page) -> None:
    """THE GUARD. A stale bundle is invisible to every other check in this repository."""
    served = ui.evaluate("() => document.documentElement.dataset.bundle")
    assert served, (
        "the page exposes no bundle hash: the module did not load or did not execute. "
        "Check that index.html loads /static/dist/main.js and that the build succeeded."
    )
    expected = source_hash()
    assert served == expected, (
        f"the served bundle was built from different sources: page says {served}, the frontend "
        f"on disk hashes to {expected}. Run `make frontend`."
    )


def test_editing_a_source_changes_the_expected_hash() -> None:
    """The other direction, and the one that decides whether the guard is worth having.

    A hash that did not move when a source changed would pass forever and prove nothing. Asserted
    by hashing a real directory twice with one byte different, rather than by trusting sha256 -
    what is under test is that the FILE SET is the right one, not that hashing works.
    """
    before = source_hash()
    probe = FRONTEND / "src" / "__hash_probe__.ts"
    probe.write_text("export const probe = 1;\n")
    try:
        after = source_hash()
    finally:
        probe.unlink()

    assert after != before, "adding a source file did not change the hash; the file set is wrong"
    assert source_hash() == before, "removing it did not restore the hash"
