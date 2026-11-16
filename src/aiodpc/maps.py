"""Bulletins of the whole of Italy, downloaded once and read at any location."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DEFAULT_PHENOMENA_RADIUS_KM
from .models import CriticalityBulletin, VigilanceBulletin
from .parsers import (
    GeoJsonFeatures,
    check_phenomena_distance,
    compact_criticality,
    compact_vigilance,
    parse_criticality_day,
    parse_criticality_id,
    parse_phenomena,
    parse_vigilance_day,
    parse_vigilance_id,
)

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterable

    from .compact import CompactCriticality, CompactVigilance
    from .models import Location


class CriticalityMap:
    """The criticality bulletin of the whole of Italy, to read at any location.

    Get it from :meth:`aiodpc.DpcClient.get_criticality_map`. Its files are
    downloaded once and :meth:`at` reads them without any request, so several
    locations cost a single download::

        criticality = await dpc.get_criticality_map()
        for place in (home, office):
            print(criticality.at(place).today)

    The map holds the decoded files, tens of MB: keep it only while reading it.
    """

    __slots__ = ("_days", "id", "published")

    def __init__(self, bulletin_id: str, files: Iterable[tuple[int, object]]) -> None:
        """Initialize the map from the decoded GeoJSON of each day, by offset.

        Raises :class:`aiodpc.DpcParseError` when a file has an unexpected
        shape, ``ValueError`` for an invalid bulletin ID.
        """
        self.id = bulletin_id
        """Bulletin ID, e.g. ``"20261114_1430"``."""
        self.published: dt.datetime = parse_criticality_id(bulletin_id)
        """Publication time in the ID (Europe/Rome)."""
        self._days = tuple(
            (offset, GeoJsonFeatures.of(geojson)) for offset, geojson in files
        )

    def at(self, location: Location) -> CriticalityBulletin:
        """Return the bulletin of a location: its alert levels, day by day.

        Raises :class:`aiodpc.DpcLocationError` when the location is in no
        zone; the other locations can still be read.
        """
        days = tuple(
            parse_criticality_day(
                features, bulletin_id=self.id, offset=offset, location=location
            )
            for offset, features in self._days
        )
        return CriticalityBulletin(id=self.id, published=self.published, days=days)

    def compact(self) -> CompactCriticality:
        """Return the bulletin of every zone as numeric codes.

        About 7 kB of CSV for two days, instead of 11 MB of GeoJSON; see
        :mod:`aiodpc.compact`.
        """
        return compact_criticality(self.id, self._days)

    def __repr__(self) -> str:
        """Return the representation of the map."""
        return f"CriticalityMap(id={self.id!r}, days={len(self._days)})"


class VigilanceMap:
    """The weather vigilance bulletin of the whole of Italy, to read anywhere.

    Get it from :meth:`aiodpc.DpcClient.get_vigilance_map`. Like
    :class:`CriticalityMap`, it is downloaded once and :meth:`at` reads it at
    each location, each with its own distance for the phenomena::

        vigilance = await dpc.get_vigilance_map()
        home_weather = vigilance.at(home, phenomena_within_km=50)
        office_weather = vigilance.at(office, phenomena_within_km=10)

    The map holds the decoded files, tens of MB: keep it only while reading it.
    """

    __slots__ = ("_days", "date", "id")

    def __init__(
        self, bulletin_id: str, files: Iterable[tuple[int, object, object]]
    ) -> None:
        """Initialize the map from the decoded GeoJSON of each day.

        ``files`` holds the offset of each day, the GeoJSON of its zones and
        the GeoJSON of its phenomena. Raises :class:`aiodpc.DpcParseError`
        when a file has an unexpected shape, ``ValueError`` for an invalid
        bulletin ID.
        """
        self.id = bulletin_id
        """Bulletin ID, e.g. ``"20261114"``."""
        self.date: dt.date = parse_vigilance_id(bulletin_id)
        """Publication day in the ID."""
        self._days = tuple(
            (offset, GeoJsonFeatures.of(zones), GeoJsonFeatures.of(phenomena))
            for offset, zones, phenomena in files
        )

    def at(
        self,
        location: Location,
        *,
        phenomena_within_km: float = DEFAULT_PHENOMENA_RADIUS_KM,
    ) -> VigilanceBulletin:
        """Return the bulletin of a location, with the phenomena near it.

        Each day includes the phenomena within ``phenomena_within_km`` of the
        location. Raises :class:`aiodpc.DpcLocationError` when the location is
        in no zone, ``ValueError`` for an invalid distance.
        """
        within_km = check_phenomena_distance(phenomena_within_km)
        days = tuple(
            parse_vigilance_day(
                zones,
                bulletin_id=self.id,
                offset=offset,
                location=location,
                phenomena=parse_phenomena(
                    phenomena, location=location, within_km=within_km
                ),
            )
            for offset, zones, phenomena in self._days
        )
        return VigilanceBulletin(id=self.id, date=self.date, days=days)

    def compact(self) -> CompactVigilance:
        """Return the precipitation of every zone and every phenomenon as codes.

        See :mod:`aiodpc.compact`.
        """
        return compact_vigilance(self.id, self._days)

    def __repr__(self) -> str:
        """Return the representation of the map."""
        return f"VigilanceMap(id={self.id!r}, days={len(self._days)})"
