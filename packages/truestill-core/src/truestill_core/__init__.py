"""Categorize and date-organize a media library into a stable folder tree.

Folder labels are derived from each file's own metadata rather than chosen from a fixed
list, so new sources create new folders without a code change.
"""

from __future__ import annotations

from truestill_core.version import distribution_version

__version__ = distribution_version("truestill-core")
