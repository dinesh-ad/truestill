"""Pluggable storage backends.

The organizer talks only to the :class:`Destination` interface; pCloud is one
implementation, not a built-in assumption. Adding Dropbox, S3 or a NAS means writing one
new class here and nothing else.
"""

from __future__ import annotations

from vaeon_core.destinations.base import Destination
from vaeon_core.destinations.local import LocalDestination
from vaeon_core.destinations.rclone import RcloneDestination

__all__ = ["Destination", "LocalDestination", "RcloneDestination"]
