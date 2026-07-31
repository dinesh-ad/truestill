"""Pluggable storage backends.

The organizer talks only to the :class:`Destination` interface; a cloud remote is one
implementation, not a built-in assumption. Adding another remote, an object store or a NAS
means writing one new class here and nothing else.
"""

from __future__ import annotations

from truestill_core.destinations.base import Destination
from truestill_core.destinations.local import LocalDestination
from truestill_core.destinations.rclone import RcloneDestination

__all__ = ["Destination", "LocalDestination", "RcloneDestination"]
