"""The packaging shim refuses the algorithms a frozen build drops, in words a user can act on.

**What this is for.** A frozen build excludes `scipy` and `PyWavelets` - 82.2 MiB of a 208.1 MiB
Linux build, measured. Without a shim the user meets ``ModuleNotFoundError: No module named
'scipy'`` from four frames inside a vendored library: it names a package they never chose, does
not say which algorithm failed, and offers no alternative.

**The shim is packaging-layer only, and that is asserted here rather than asserted in prose.**
A source checkout must keep `phash` and `whash` working exactly as `imagehash` ships them, so
the tests below check that the shim does nothing until it is explicitly installed, and that
`truestill_core` never imports it.
"""

from __future__ import annotations

from pathlib import Path

import imagehash
import pytest
from PIL import Image
from truestill_freeze import (
    SUPPORTED,
    UNAVAILABLE,
    PerceptualAlgorithmUnavailableError,
    install,
)


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Install the shim on a throwaway view of `imagehash`, undone after the test.

    `monkeypatch.setattr` restores the real functions, so this cannot leak into the rest of the
    suite - which would otherwise disable phash for every test that runs after it.
    """
    for algorithm in UNAVAILABLE:
        monkeypatch.setattr(imagehash, algorithm, getattr(imagehash, algorithm))
    return install()


def test_every_dropped_algorithm_is_covered_not_just_the_one_in_use(frozen: list[str]) -> None:
    """`phash` is what a caller reaches for today. `phash_simple` and `whash` are what someone
    reaches for next, and a shim covering only today's call is a landmine for them."""
    assert set(frozen) == set(UNAVAILABLE) == {"phash", "phash_simple", "whash"}


@pytest.mark.parametrize("algorithm", sorted(UNAVAILABLE))
@pytest.mark.usefixtures("frozen")
def test_calling_one_raises_rather_than_returning_a_value(algorithm: str) -> None:
    """The property that matters most: it must not return a hash.

    A perceptual hash that came back *different* would be the worst defect available here - the
    catalog stores hash output as identity, so a wrong value is a wrong duplicate verdict that
    persists after the build is fixed.
    """
    with pytest.raises(PerceptualAlgorithmUnavailableError):
        getattr(imagehash, algorithm)(Image.new("L", (64, 64)))


@pytest.mark.parametrize("algorithm", sorted(UNAVAILABLE))
@pytest.mark.usefixtures("frozen")
def test_the_message_names_the_algorithm_and_the_alternative_never_the_module(
    algorithm: str,
) -> None:
    """ "scipy is required for phash" is a developer's sentence. The reader is someone whose
    photos did not get deduplicated and who needs to know what this build can do instead."""
    with pytest.raises(PerceptualAlgorithmUnavailableError) as raised:
        getattr(imagehash, algorithm)(Image.new("L", (64, 64)))

    message = str(raised.value)
    assert algorithm in message, "the failing algorithm is not named"
    assert SUPPORTED in message, "the alternative is not named"
    for module in ("scipy", "PyWavelets", "pywt", "ModuleNotFound"):
        assert module not in message, f"the message leaks the internal name {module!r}"


def test_a_source_install_is_untouched_until_the_shim_is_installed() -> None:
    """The packaging-layer boundary, asserted rather than promised.

    Importing `truestill_freeze` must change nothing by itself - only `install()` does. If this
    ever fails, a source checkout has silently lost phash.
    """
    assert imagehash.phash(Image.new("L", (64, 64))) is not None
    assert imagehash.whash(Image.new("L", (64, 64))) is not None


def test_dhash_is_never_shimmed() -> None:
    """The algorithm the product actually uses must be untouched by any of this."""
    assert "dhash" not in UNAVAILABLE
    assert SUPPORTED == "dhash"


def test_the_shim_is_not_reachable_from_the_shipped_packages() -> None:
    """Packaging-layer only: no runtime module may import it, or a source install would inherit
    a restriction that exists solely because a bundler dropped bytes."""
    roots = [
        Path(__file__).resolve().parents[3] / "packages" / name / "src"
        for name in ("truestill-core", "truestill-cli", "truestill-app")
    ]
    offenders = [
        f"{path}:{number}"
        for root in roots
        for path in root.rglob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if "truestill_freeze" in line
    ]

    assert not offenders, f"a shipped package imports the packaging shim: {offenders}"
