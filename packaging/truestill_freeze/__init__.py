"""Packaging-layer shim: the perceptual algorithms a frozen build does not carry.

**Why this exists.** `imagehash` declares `scipy` and `PyWavelets` as hard requirements with no
extras split, and they are **81 MB and 8.6 MB** that truestill never imports: they back `phash`,
`phash_simple` and `whash`, and truestill hashes with `dhash`. Measured on a real PyInstaller
build, Linux, 2026-08-01: **208.1 MiB baseline, 125.9 MiB with both excluded - 82.2 MiB, 39.5%
of the download.**

**Why a shim and not only `--exclude-module`.** The exclusion alone works - measured, scipy and
pywt do leave the bundle - but what a user then meets is ``ModuleNotFoundError: No module named
'scipy'`` raised four frames deep inside a vendored library. That names an internal package the
user never chose, does not say which algorithm failed, and offers no alternative. The exclusion
buys the bytes; this buys the sentence.

**This is packaging-layer only.** It is applied by a PyInstaller runtime hook and by nothing
else. A source checkout, a `pip install truestill-core`, and the test suite all keep `phash`,
`phash_simple` and `whash` working exactly as `imagehash` ships them - which is why the shim
must never be imported from `truestill_core`.

**The failure is loud on purpose, and it covers every affected function rather than the one
that is called today.** A perceptual hash that silently returned a *different* value would be
the worst defect this product can have: the catalog stores hash output as identity, so a wrong
value is a wrong duplicate verdict that persists. Verified against `imagehash` 4.3.2: none of
the three has a fallback path - each does a bare `import scipy.fftpack` / `import pywt` and
raises - so removing the module cannot produce a wrong number, only an exception. This turns
that exception into one a person can act on.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

#: The algorithm a frozen build does carry. Named in every message, because "which one can I
#: use" is the only question the reader actually has.
SUPPORTED = "dhash"

#: Every `imagehash` entry point that needs `scipy` or `PyWavelets`, with the dependency each
#: one reaches for. Verified against imagehash 4.3.2 by reading the function bodies rather than
#: the package metadata: all three import lazily, inside the function.
#:
#: `dhash_int` is deliberately **absent** - it does not exist in this library. It was raised as
#: the most dangerous case on the belief that it falls back to NumPy and returns a wrong value;
#: `imagehash` 4.3.2 has no such function and no such fallback. Kept as a comment rather than
#: dropped silently, so the concern is not re-raised from memory later.
UNAVAILABLE: dict[str, str] = {
    "phash": "scipy",
    "phash_simple": "scipy",
    "whash": "PyWavelets",
}


class PerceptualAlgorithmUnavailableError(RuntimeError):
    """A perceptual algorithm this build does not ship was called.

    A `RuntimeError` rather than an `ImportError`: what went wrong is a *build* decision, not a
    failed import, and callers that catch `ImportError` to mean "optional dependency missing"
    should not treat this as recoverable.
    """


def _message(algorithm: str) -> str:
    """The sentence a user reads. Names the algorithm and the alternative, never the module."""
    return (
        f"The {algorithm!r} perceptual algorithm is not available in this build of truestill. "
        f"This build supports {SUPPORTED!r}, which is what it uses for duplicate detection. "
        f"To use {algorithm!r}, run truestill from a source install."
    )


def _refuse(algorithm: str) -> Callable[..., Any]:
    def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise PerceptualAlgorithmUnavailableError(_message(algorithm))

    unavailable.__name__ = algorithm
    unavailable.__doc__ = _message(algorithm)
    return unavailable


def install() -> list[str]:
    """Replace every unavailable algorithm on the imported `imagehash` module.

    Returns the names replaced, so the runtime hook can be asserted on rather than trusted.
    Importing `imagehash` here is cheap: it pulls `numpy` and `PIL` at module level and nothing
    else - `scipy` and `pywt` are reached only from inside the functions being replaced.
    """
    import imagehash  # noqa: PLC0415 - a packaging hook, resolved at freeze time

    replaced = []
    for algorithm in UNAVAILABLE:
        if hasattr(imagehash, algorithm):
            setattr(imagehash, algorithm, _refuse(algorithm))
            replaced.append(algorithm)
    return replaced
