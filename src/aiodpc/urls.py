"""URLs of the DPC bulletin files.

The day of a file is its ``offset`` from the publication day: the criticality
bulletin has offsets 0-1 ("today", "tomorrow"), the vigilance bulletin 0-2
("oggi", "domani", "dopodomani").
"""

from __future__ import annotations

from typing import Final

from .const import CRITICALITY_FILES_URL, VIGILANCE_FILES_URL

CRITICALITY_DAYS: Final = ("today", "tomorrow")
"""Day names of the criticality GeoJSON files, by offset."""

VIGILANCE_DAYS: Final = ("oggi", "domani", "dopodomani")
"""Day names of the vigilance GeoJSON files, by offset."""

# Preview images use the Italian day names; there is none for "dopodomani".
_CRITICALITY_PREVIEW_DAYS: Final = ("oggi", "domani")
_VIGILANCE_PREVIEW_DAYS: Final = ("oggi", "domani")


def _day(days: tuple[str, ...], offset: int) -> str:
    if not 0 <= offset < len(days):
        msg = f"Day offset must be between 0 and {len(days) - 1}, got {offset}"
        raise ValueError(msg)
    return days[offset]


def criticality_geojson_url(bulletin_id: str, offset: int) -> str:
    """Return the GeoJSON URL of a day of a criticality bulletin."""
    day = _day(CRITICALITY_DAYS, offset)
    return f"{CRITICALITY_FILES_URL}/geojson/{bulletin_id}_{day}.json"


def criticality_preview_url(bulletin_id: str, offset: int) -> str:
    """Return the preview image URL of a day of a criticality bulletin."""
    day = _day(_CRITICALITY_PREVIEW_DAYS, offset)
    return f"{CRITICALITY_FILES_URL}/preview/{bulletin_id}_{day}.png"


def vigilance_geojson_url(bulletin_id: str, offset: int) -> str:
    """Return the GeoJSON URL of the zones of a day of a vigilance bulletin."""
    day = _day(VIGILANCE_DAYS, offset)
    return f"{VIGILANCE_FILES_URL}/geojson/{bulletin_id}_{day}.json"


def phenomena_geojson_url(bulletin_id: str, offset: int) -> str:
    """Return the GeoJSON URL of the phenomena of a day of a vigilance bulletin."""
    day = _day(VIGILANCE_DAYS, offset)
    return f"{VIGILANCE_FILES_URL}/geojson/{bulletin_id}_fenomeni_{day}.json"


def vigilance_preview_url(bulletin_id: str, offset: int) -> str | None:
    """Return the preview image URL of a day of a vigilance bulletin, if any."""
    _day(VIGILANCE_DAYS, offset)
    if offset >= len(_VIGILANCE_PREVIEW_DAYS):
        return None
    day = _VIGILANCE_PREVIEW_DAYS[offset]
    return f"{VIGILANCE_FILES_URL}/preview/{bulletin_id}_{day}.png"
