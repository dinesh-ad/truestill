"""What the expensive tiers will cost, predicted from the free one.

Tier 0 reads directory entries and one ``stat``. That is already everything needed to predict
tier 2a's read cost, because the size pre-filter is a pure function of the size census -- so a
user can be told what the identical-copy check will cost **before** deciding to wait for it,
at no extra cost at all.

The look-alike forecast is a different shape and deliberately weaker: it depends on the format
mix, and HEIC decodes ~52x slower than JPEG (`PERFORMANCE.md` §3.1, 319.5 ms against 6.2 ms
median on photo-like content, n=7). We report the user's own proportion rather than
generalising from any one library -- ours is 100% JPEG, which is a fact about one person.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.insights import forecast_exact_duplicate_read, forecast_lookalike_cost
from truestill_core.scan import _needs_sha

# --- tier 2a: exactly the files whose size collides ------------------------------------------


def test_only_size_colliding_files_would_be_read() -> None:
    """The size pre-filter's own rule: a unique size cannot have an identical twin."""
    sizes = {Path("/a"): 100, Path("/b"): 100, Path("/c"): 250, Path("/d"): 900}

    forecast = forecast_exact_duplicate_read(sizes)

    assert forecast.files == 4
    assert forecast.colliding_files == 2
    assert forecast.bytes_to_read == 200
    assert forecast.total_bytes == 1350  # 100 + 100 + 250 + 900


def test_a_library_of_unique_sizes_would_read_nothing() -> None:
    """The best case, and it must read as zero rather than as unknown."""
    forecast = forecast_exact_duplicate_read({Path("/a"): 1, Path("/b"): 2, Path("/c"): 3})
    assert forecast.colliding_files == 0
    assert forecast.bytes_to_read == 0
    assert forecast.share == 0.0


def test_a_library_of_identical_sizes_would_read_everything() -> None:
    """The worst case. `share` is the number a user actually acts on."""
    forecast = forecast_exact_duplicate_read({Path("/a"): 50, Path("/b"): 50, Path("/c"): 50})
    assert forecast.colliding_files == 3
    assert forecast.bytes_to_read == 150
    assert forecast.share == 1.0


def test_an_empty_source_forecasts_nothing_without_dividing_by_zero() -> None:
    forecast = forecast_exact_duplicate_read({})
    assert forecast.files == 0
    assert forecast.bytes_to_read == 0
    assert forecast.share == 0.0


def test_the_forecast_matches_what_the_pre_filter_actually_selects() -> None:
    """Provenance, not coincidence: the forecast must agree with the code it predicts.

    A forecast derived from its own idea of the rule would drift the first time the pre-filter
    changed, and nothing would say so. This compares against `_needs_sha` itself.
    """
    sizes = {Path(f"/f{i}"): i % 4 for i in range(20)}
    forecast = forecast_exact_duplicate_read(sizes)
    assert forecast.colliding_files == len(_needs_sha(sizes, frozenset()))


# --- tier 2b: the format mix decides, so report the user's own -------------------------------


def test_a_jpeg_library_is_forecast_as_cheap() -> None:
    forecast = forecast_lookalike_cost({"jpg": 1000, "png": 20})
    assert forecast.images == 1020
    assert forecast.slow_images == 0
    assert forecast.slow_share == 0.0
    assert not forecast.materially_slower


def test_a_heic_library_is_forecast_as_materially_slower() -> None:
    """The case our own corpus cannot show us: an iPhone library straight off the cable."""
    forecast = forecast_lookalike_cost({"heic": 900, "jpg": 100})
    assert forecast.slow_images == 900
    assert forecast.slow_share == pytest.approx(0.9)
    assert forecast.materially_slower


@pytest.mark.parametrize("extension", ["heic", "heif", "hif", "HEIC"])
def test_every_heif_spelling_counts(extension: str) -> None:
    """A census keys on the extension as written, and HEIF arrives under several."""
    assert forecast_lookalike_cost({extension: 10}).slow_images == 10


def test_a_small_heic_share_is_not_called_materially_slower() -> None:
    """Cry-wolf. A warning that fires on two stray files gets ignored on the run that matters."""
    forecast = forecast_lookalike_cost({"jpg": 1000, "heic": 5})
    assert forecast.slow_images == 5
    assert not forecast.materially_slower


def test_an_empty_census_forecasts_nothing() -> None:
    forecast = forecast_lookalike_cost({})
    assert forecast.images == 0
    assert forecast.slow_share == 0.0
    assert not forecast.materially_slower
