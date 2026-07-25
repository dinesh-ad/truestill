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
#: by 0-6 bits, while genuinely different photos differ by 20+. The risk is asymmetric --
#: a false positive means a real, distinct photo is treated as a duplicate and never
#: backed up (silent data loss), whereas a false negative merely keeps a redundant copy.
#: So the default is deliberately conservative; raise it only after reviewing a dry run.
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
    in perceptual dedup and are matched on SHA-256 alone.
    """
    try:
        with Image.open(path) as image:
            image.draft("L", (64, 64))  # hint the decoder toward a cheap grayscale read
            func = imagehash.phash if algorithm == "phash" else imagehash.dhash
            return str(func(image, hash_size=_HASH_SIDE))
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def hamming_distance(hex_a: str, hex_b: str) -> int:
    """Bit-difference between two equal-width hex hash strings."""
    return (int(hex_a, 16) ^ int(hex_b, 16)).bit_count()
