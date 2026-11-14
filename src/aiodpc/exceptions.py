"""Exceptions raised by aiodpc."""

from __future__ import annotations


class DpcError(Exception):
    """Base class of the aiodpc errors."""


class DpcConnectionError(DpcError):
    """DPC could not be reached: network error, HTTP error status or timeout."""


class DpcParseError(DpcError):
    """DPC returned data that is not valid JSON or has an unexpected format."""


class DpcLocationError(DpcError):
    """The location is not inside any alert zone of the bulletin.

    This is permanent for the given coordinates (for example a location outside
    Italy or at sea), so retrying does not help.
    """
