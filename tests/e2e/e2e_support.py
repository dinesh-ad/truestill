"""Types and helpers the browser tests **import**, as opposed to fixtures pytest injects.

Split out of ``conftest.py`` deliberately - see ``test_shared_test_helpers.py`` for the rule and
for the reproduction of what the shared bare name ``conftest`` did when both suites were
collected at once. Fixtures stay in ``conftest.py``; anything a test imports lives here, under a
basename no other test directory claims.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True, slots=True)
class AppServer:
    """A running app instance, and the catalog behind it."""

    base_url: str
    token: str
    db: Path

    @property
    def url(self) -> str:
        """The page URL a user would open, token included -- exactly as the app prints it."""
        return f"{self.base_url}/?token={self.token}"


# --- synthetic fixtures ------------------------------------------------------------------
# Generated, never committed. Media files do not belong in git whatever their provenance, and
# generating them keeps each test's corpus exactly the shape that test needs.


def make_photo(path: Path, seed: int, *, size: tuple[int, int] = (320, 240)) -> Path:
    """A JPEG with unique content, so dedup treats every generated file as its own file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, ((seed * 37) % 256, (seed * 91) % 256, (seed * 13) % 256)).save(
        path, "JPEG", quality=90
    )
    return path


def stamp_capture_date(paths: list[Path], when: str = "2021:06:15 10:30:00") -> None:
    """Give files a real embedded capture date, so they land in dated folders like real photos.

    Skipped silently when exiftool is absent: the tests that need dating declare it, and the
    rest do not care.
    """
    if not paths:
        return
    subprocess.run(
        [
            "exiftool",
            "-q",
            "-m",
            "-overwrite_original",
            f"-DateTimeOriginal={when}",
            *map(str, paths),
        ],
        check=False,
    )
