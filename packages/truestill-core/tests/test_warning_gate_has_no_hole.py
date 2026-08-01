"""The warnings-as-errors gate has no way for a deprecation to slip through.

**The hole this closes, which was real and demonstrated.** `filterwarnings = ["error", ...]`
makes every warning a failure, with two exemptions. The second one, for
`PytestUnraisableExceptionWarning`, was written to cover `ResourceWarning`s arriving from the
garbage collector - but that category wraps **any** unraisable exception. So a
`DeprecationWarning` raised inside a finalizer became an error (correct), was unraisable because
it came from `__del__` (correct), got wrapped by pytest (correct), and was then **exempted** -
printing to the warnings summary and passing the run. Exactly the outcome the gate exists to
prevent, measured before the fix rather than argued about.

**The fix is a narrower filter, not a conftest hook.** pytest's filter syntax turned out to
express it: the `message` field is a regex, and the inline `(?s)` flag lets it reach past the
newlines of the traceback pytest builds to the final line naming the wrapped exception. So the
exemption is now the *pairing* - unraisable **and** ResourceWarning - rather than the category.

**Why this test spawns pytest instead of asserting inline.** The thing under test is the
configuration in `pyproject.toml`, and a warning that fails the run cannot be observed from
inside the run it fails. A subprocess reads the real config and reports the real outcome; an
in-process `catch_warnings` would test a filter stack this file constructed, which is not the
one that ships.

**Both directions are asserted on purpose.** A guard that only checked the deprecation would
pass just as well if the exemption had been dropped wholesale, and "narrowed" must be
distinguishable from "removed".

**What that second direction turned out to require, and it is worth knowing.** Under the shipped
configuration the unraisable exemption is **dormant**: `default::ResourceWarning` means a
ResourceWarning never becomes an error, so it never becomes unraisable, so it never reaches this
exemption at all - measured, by deleting the exemption and watching the whole suite still pass.
The original 11 failures happened under a bare ``-W error`` with no exemptions. So the second
test below has to **force** the condition with ``-W error::ResourceWarning``; without that it
passed with the exemption deleted and was a test of nothing. The exemption is kept anyway,
because it costs one line and is the thing that absorbs this if any future plugin or invocation
does make ResourceWarning an error - but it is kept knowingly, not because it is load-bearing
today.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_CONFIG = _ROOT / "pyproject.toml"

_FROM_A_FINALIZER = """
import gc
import warnings


class _Late:
    def __del__(self) -> None:
        warnings.warn("raised from a finalizer", {category}, stacklevel=2)


def test_it() -> None:
    _Late()
    gc.collect()
"""


def _run_under_the_real_config(
    tmp_path: Path, category: str, *, extra: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    """Run one generated test in a fresh pytest, against the shipped filter configuration.

    ``-c`` points at the repo's own `pyproject.toml`, so this exercises the real
    ``filterwarnings`` rather than pytest's defaults - without it the subprocess would find its
    rootdir in the temp directory and the test would pass for the wrong reason.
    """
    target = tmp_path / "test_generated.py"
    target.write_text(_FROM_A_FINALIZER.format(category=category), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(target),
            "-c",
            str(_CONFIG),
            "-p",
            "no:cacheprovider",
            *extra,
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )


def test_a_deprecation_from_a_finalizer_fails_the_run(tmp_path: Path) -> None:
    """The hole itself. Before the filter was narrowed this passed, with the deprecation printed
    to the warnings summary - which is precisely how a real one would have been missed."""
    result = _run_under_the_real_config(tmp_path, "DeprecationWarning")

    assert result.returncode != 0, (
        "a DeprecationWarning from a finalizer passed the run - the unraisable exemption is "
        f"laundering deprecations again:\n{result.stdout[-2000:]}"
    )
    assert "DeprecationWarning" in result.stdout


def test_a_resource_warning_from_a_finalizer_still_passes(tmp_path: Path) -> None:
    """The other direction, and the reason the exemption exists at all.

    **This forces the condition rather than assuming it**, with ``-W error::ResourceWarning``.
    Without that, the run's own ``default::ResourceWarning`` means a ResourceWarning never
    becomes an error, never becomes unraisable, and never reaches the exemption under test - so
    this passed identically with the exemption deleted, which made it a test of nothing. That
    was caught by mutating the exemption away and seeing it stay green.

    With the condition forced, this is the original 11-failure scenario: ResourceWarning as an
    error inside a finalizer, wrapped by pytest, absorbed by the narrowed exemption. If it ever
    fails, the exemption has been removed rather than narrowed and the GC-timing flakiness is
    back.
    """
    result = _run_under_the_real_config(
        tmp_path, "ResourceWarning", extra=("-W", "error::ResourceWarning")
    )

    assert result.returncode == 0, (
        "a ResourceWarning from a finalizer failed the run - the exemption was dropped rather "
        f"than narrowed, and the GC-timing flakiness is back:\n{result.stdout[-2000:]}"
    )


def test_the_gate_is_configured_at_all() -> None:
    """Guards the vacuous pass: if `-c` stopped resolving, or `filterwarnings` were deleted, the
    deprecation test above would fail for the wrong reason and this says which."""
    assert _CONFIG.is_file(), f"{_CONFIG} is gone; the subprocess is testing pytest's defaults"

    text = _CONFIG.read_text(encoding="utf-8")
    assert "filterwarnings" in text, "the warnings gate has been removed from pyproject.toml"
    assert '"error",' in text, "the gate no longer turns warnings into errors"
