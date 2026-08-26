"""Content hashing for duplicate detection.

Two independent signals:

* **SHA-256** -- exact byte identity. Catches the same file under a different name or in
  a different folder. Cheap, deterministic, no false positives.
* **Perceptual hash (dHash)** -- visual similarity. Catches the *same picture* in
  different compression or resolution states (a camera original vs a WhatsApp-forwarded
  copy), which SHA-256 cannot, because those files differ byte-for-byte.

dHash is chosen over pHash as the default: it needs only Pillow + NumPy (no SciPy), it is
robust to the exact re-encoding/resize transforms this project cares about, and it is
fast. pHash is available in :func:`perceptual_hash` via ``algorithm="phash"`` if wanted.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import imagehash
from PIL import Image, UnidentifiedImageError

# truestill processes the user's OWN local library, not untrusted web uploads, so Pillow's ~89 MP
# "decompression bomb" guard is a false positive on legitimate large photos -- panoramas,
# medium-format, and flatbed scans routinely exceed it (the corpus has a 144 MP image). Immich and
# PhotoPrism sidestep the issue entirely by decoding through libvips, which streams arbitrarily
# large images; Pillow needs an explicit decision. We deliberately raise the ceiling to cover real
# photography, and above it a truly pathological/gigapixel image is *skipped* for perceptual
# hashing rather than risking an OOM -- SHA-256 exact dedup still applies, and the skip is never
# silent (perceptual_hash returns None, which the report surfaces).
#
# ⚠ **THE SKIP IS AT 600 MP, NOT AT THIS NUMBER.** Pillow's `_decompression_bomb_check` is TWO
# tiers: it *warns* above `MAX_IMAGE_PIXELS` and only *raises* above **2x** it. So this constant
# sets the suspicion line and the refusal is at twice it - an image between 300 and 600 MP is
# warned about and hashed anyway. `test_hashing.py` already encodes the doubling (it monkeypatches
# the limit to 100 and uses a 144-pixel image annotated "warn band"); this comment did not.
# ⚠ **Whether 300 or 600 is the intended ceiling is UNRULED** - filed separately, because a
# memory-safety number should be measured rather than picked inside a commit about flat images.
# Measured while filing it: the largest real photograph in the library is **39.5 MP**, and the only
# corpus files above 300 MP are five fuzzed TIFFs that are all above 600 too - so the 300-600 band
# is empty in practice and this falsehood has had no observed consequence.
MAX_PERCEPTUAL_PIXELS = 300_000_000  # 300 MP
Image.MAX_IMAGE_PIXELS = MAX_PERCEPTUAL_PIXELS

#: Image extensions whose perceptual dedup depends on the pillow-heif plugin (libheif).
#: TIFF-based RAW (CR2/NEF/DNG/…) opens via Pillow's own TIFF decoder and needs no plugin.
HEIF_EXTENSIONS: frozenset[str] = frozenset({".heic", ".heif", ".hif"})


def _register_heif() -> bool:
    """Register the HEIF opener so Pillow can decode HEIC/HEIF, or degrade gracefully.

    pillow-heif is a declared dependency, so this normally succeeds. If it ever fails to import
    at runtime (a broken install, or missing system libheif on an exotic platform), we do NOT
    crash: SHA-256 exact dedup keeps working for HEIC, only its *perceptual* near-dup hash is
    skipped -- and callers surface that in the report via :data:`HEIF_AVAILABLE` rather than
    dropping it silently.
    """
    try:
        import pillow_heif  # noqa: PLC0415 - optional-at-runtime plugin, imported lazily here

        pillow_heif.register_heif_opener()
    except Exception:  # any import/registration failure degrades gracefully, never crashes
        return False
    return True


#: Whether Pillow can decode HEIC/HEIF this run. False -> HEIC perceptual dedup is skipped
#: (exact dedup still applies) and the run reports it; never a silent drop.
HEIF_AVAILABLE: bool = _register_heif()

_HASH_CHUNK = 1024 * 1024

#: dHash size in bits per side. 8 -> a 64-bit hash (16 hex chars).
_HASH_SIDE = 8

#: Default Hamming-distance threshold for calling two perceptual hashes "the same photo".
#:
#: Tuning rationale: with a 64-bit dHash, re-encodes/resizes of one image typically differ
#: by 0-6 bits, while genuinely different photos differ by 20+.
#:
#: ⚠ **THIS PARAGRAPH USED TO JUSTIFY THE NUMBER 5 WITH A HARM THAT CANNOT HAPPEN.** `(ahq)` It
#: said a false positive means a photo "is treated as a duplicate and never backed up (silent data
#: loss)". A perceptual match does not suppress the copy: `models.Resolution.should_upload` is
#: `exact_duplicate is None` and never consults the near-duplicate field, and the policy is stated
#: at `models.Resolution` - "Still uploaded, only flagged, so an original can never be silently
#: dropped in favour of a lower-quality look-alike."
#:
#: **The asymmetry is real but INVERTED for this tier.** A false positive costs a wrong row in a
#: list the user cannot act on; a false negative costs a redundant kept copy. Both are cheap, and
#: **neither is data loss** - the cost is whether the near-duplicate report can be believed. That
#: sentence describes the EXACT tier, which suppresses the copy and has no threshold to tune.
#:
#: ⚠ **SO THE NUMBER ITSELF IS UNJUSTIFIED, AND THAT IS NOT THE SAME AS WRONG.** 5 may well be
#: right; the reasoning that produced it was about a different failure, so **nobody has re-derived
#: it against the harm that actually applies.** Until someone does, treat it as inherited rather
#: than chosen, and raise it only after reviewing a dry run.
DEFAULT_PHASH_THRESHOLD = 5

Algorithm = Literal["dhash", "phash"]


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in streaming chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def perceptual_hash(path: Path, algorithm: Algorithm = "dhash") -> str | None:
    """Return a hex perceptual hash for an image, or ``None`` if it is not an image.

    Videos, audio and unreadable files return ``None`` -- they simply do not participate
    in perceptual dedup and are matched on SHA-256 alone. A legitimately huge image (above
    :data:`MAX_PERCEPTUAL_PIXELS`) also returns ``None`` -- Pillow raises ``DecompressionBombError``
    and we skip *perceptual* hashing for it (SHA-256 still runs).

    ⚠ **THE LOCAL WARNING SUPPRESSION THAT USED TO BE HERE IS GONE, AND ITS DOCSTRING WAS WRONG
    IN BOTH HALVES.** It read *"the decompression-bomb warning is suppressed locally so no raw
    Pillow warning ever reaches the user's terminal"*. It filtered **one class**, so 133 other
    Pillow warnings reached the terminal in a single corpus run; and it did it with
    `warnings.catch_warnings`, which assigns process-global module attributes while this function
    runs on a `ThreadPoolExecutor` **by default** - behaviour CPython documents as *undefined*
    with two or more threads. It was unsound and ineffective at once. :mod:`decode_noise` replaces
    it with one process-wide install, and carries the full argument. `(aev)`
    """
    try:
        with Image.open(path) as image:
            image.draft("L", (64, 64))  # hint the decoder toward a cheap grayscale read
            func = imagehash.phash if algorithm == "phash" else imagehash.dhash
            return str(func(image, hash_size=_HASH_SIDE))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None


def hamming_distance(hex_a: str, hex_b: str) -> int:
    """Bit-difference between two equal-width hex hash strings.

    **No production caller since 2026-08-02, and kept deliberately - do not delete it as dead
    code.** `DedupIndex` now packs hashes to ``uint64`` and compares them vectorised, and this
    is the reference implementation its equivalence test measures that against
    (`test_dedup_vectorised.py`). Deleting it would not remove the logic, only move a copy of
    it into the test that needs it - and an oracle living beside the code it checks is how the
    two drift together and agree about being wrong. It also stays width-agnostic, which the
    packed index is not: `test_hashing` exercises it on 8-bit values.
    """
    return (int(hex_a, 16) ^ int(hex_b, 16)).bit_count()
