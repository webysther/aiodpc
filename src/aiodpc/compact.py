"""The bulletins of the whole of Italy as numbers: small and in no language.

A compact bulletin holds, for every zone and day, the numeric ``code`` of
each value (see the data dictionary), and the zones in a table of their own.
The zones are almost all the bytes of the DPC files and change rarely (four
times from 2020 to 2026): a consumer keeps the zone table and fetches it again
only when its :attr:`ZoneTable.fingerprint` changes. A day of both bulletins
is then about 13 kB of CSV instead of 19 MB of GeoJSON, and any
:class:`aiodpc.Translator` tells it in its language.

Get one from :meth:`aiodpc.CriticalityMap.compact` or
:meth:`aiodpc.VigilanceMap.compact`; this module does no I/O.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from .models import BulletinKind

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

SCHEMA_VERSION: Final = 1
"""Version of the layout of the JSON documents; it changes with a column."""

FINGERPRINT_LENGTH: Final = 12
"""Hexadecimal digits of a zone table fingerprint (48 bits of SHA-256)."""

COORDINATE_DECIMALS: Final = 5
"""Decimals kept of the positions of the phenomena: about 1 m."""

MUNICIPALITY_SEPARATOR: Final = "|"
"""Separates the municipalities of a zone in the CSV of a zone table."""


class CriticalityRecord(NamedTuple):
    """The assessment of one zone on one day, as numeric codes."""

    day: int
    """Days after the publication day: the offset of the DPC file."""
    zone: int
    """Code of the zone in the :class:`ZoneTable` of the bulletin."""
    level: int
    """``AlertLevel`` code of the zone."""
    criticality: int
    """``Criticality`` code of the summary of the zone."""
    mapped_risk: int
    """``RiskType`` code of the risk the summary names; 0 when none."""
    hydraulic: int
    """``AlertLevel`` code of the hydraulic risk."""
    thunderstorms: int
    """``AlertLevel`` code of the thunderstorm risk."""
    hydrogeological: int
    """``AlertLevel`` code of the hydrogeological risk."""


class VigilanceRecord(NamedTuple):
    """The expected precipitation of one zone on one day, as a numeric code."""

    day: int
    """Days after the publication day: the offset of the DPC file."""
    zone: int
    """Code of the zone in the :class:`ZoneTable` of the bulletin."""
    precipitation: int
    """``Precipitation`` code: the DPC ``id_classificazione``."""


class PhenomenonRecord(NamedTuple):
    """A weather phenomenon on one day, as its code and position."""

    day: int
    """Days after the publication day: the offset of the DPC file."""
    code: int
    """``PhenomenonType`` code: the DPC ``id_fenomeno``."""
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class CompactZone:
    """A zone of a bulletin: its code, name and municipalities."""

    code: int
    """Position of the zone in its table, from 1, by name."""
    name: str
    """Name of the zone as DPC writes it."""
    municipalities: tuple[str, ...]
    """Municipalities of the zone as DPC writes them, sorted, each once."""
    geometry: Mapping[str, Any] | None = field(default=None, compare=False, repr=False)
    """GeoJSON geometry of the zone, as DPC publishes it."""


@dataclass(frozen=True, slots=True)
class ZoneTable:
    """The zones of a bulletin, coded by their position in name order.

    The codes hold for as long as the zones do not change; the
    :attr:`fingerprint` changes when they do. They are not DPC codes: DPC
    publishes none.
    """

    fingerprint: str
    """Short SHA-256 of the names, municipalities and geometries of the zones."""
    zones: tuple[CompactZone, ...]

    @classmethod
    def of(
        cls, zones: Iterable[tuple[str, Sequence[str], Mapping[str, Any] | None]]
    ) -> ZoneTable:
        """Return the table of zones given as (name, municipalities, geometry).

        A name given again is the same zone: its first occurrence is kept.
        The order of the zones and of their municipalities does not matter,
        nor a municipality listed twice (DPC files of 2020 to 2024 repeat
        some up to 62 times).
        """
        unique: dict[str, tuple[tuple[str, ...], Mapping[str, Any] | None]] = {}
        for name, municipalities, geometry in zones:
            unique.setdefault(name, (tuple(sorted(set(municipalities))), geometry))
        ordered = sorted(unique.items())
        content = json.dumps(
            [
                [name, list(municipalities), geometry]
                for name, (municipalities, geometry) in ordered
            ],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(content.encode()).hexdigest()[:FINGERPRINT_LENGTH]
        return cls(
            fingerprint=fingerprint,
            zones=tuple(
                CompactZone(code, name, municipalities, geometry)
                for code, (name, (municipalities, geometry)) in enumerate(
                    ordered, start=1
                )
            ),
        )

    def code_of(self, name: str) -> int:
        """Return the code of a zone by its name; raises KeyError when unknown."""
        for zone in self.zones:
            if zone.name == name:
                return zone.code
        raise KeyError(name)

    def to_csv(self) -> str:
        """Return the table as CSV: code, name and municipalities, joined by "|"."""
        return _csv(
            ("code", "name", "municipalities"),
            (
                (zone.code, zone.name, MUNICIPALITY_SEPARATOR.join(zone.municipalities))
                for zone in self.zones
            ),
        )

    def to_json(self) -> str:
        """Return the table as a JSON document, municipalities as lists."""
        return _json(
            {
                "schema": SCHEMA_VERSION,
                "zone_set": self.fingerprint,
                "columns": ["code", "name", "municipalities"],
                "rows": [
                    [zone.code, zone.name, list(zone.municipalities)]
                    for zone in self.zones
                ],
            }
        )

    def to_geojson(self) -> dict[str, Any]:
        """Return the shapes of the zones as a GeoJSON FeatureCollection.

        Each feature has the ``code`` and ``name`` of its zone: the reference
        to publish once for every bulletin with the same fingerprint.
        """
        return {
            "type": "FeatureCollection",
            "zone_set": self.fingerprint,
            "features": [
                {
                    "type": "Feature",
                    "properties": {"code": zone.code, "name": zone.name},
                    "geometry": zone.geometry,
                }
                for zone in self.zones
            ],
        }


@dataclass(frozen=True, slots=True)
class CompactCriticality:
    """The criticality bulletin of Italy as numeric codes, zone by zone."""

    bulletin_id: str
    zones: ZoneTable
    records: tuple[CriticalityRecord, ...]

    def to_csv(self) -> str:
        """Return the records as CSV, with a header row."""
        return _csv(CriticalityRecord._fields, self.records)

    def to_json(self) -> str:
        """Return the records as a JSON document of columns and rows."""
        return _json(
            {
                **_header(BulletinKind.CRITICALITY, self.bulletin_id, self.zones),
                "columns": list(CriticalityRecord._fields),
                "rows": [list(record) for record in self.records],
            }
        )


@dataclass(frozen=True, slots=True)
class CompactVigilance:
    """The weather vigilance bulletin of Italy as numeric codes."""

    bulletin_id: str
    zones: ZoneTable
    records: tuple[VigilanceRecord, ...]
    phenomena: tuple[PhenomenonRecord, ...]

    def to_csv(self) -> str:
        """Return the precipitation of each zone as CSV, with a header row."""
        return _csv(VigilanceRecord._fields, self.records)

    def phenomena_csv(self) -> str:
        """Return the phenomena as CSV, with a header row."""
        return _csv(PhenomenonRecord._fields, self.phenomena)

    def to_json(self) -> str:
        """Return the records and phenomena as a JSON document."""
        return _json(
            {
                **_header(BulletinKind.VIGILANCE, self.bulletin_id, self.zones),
                "columns": list(VigilanceRecord._fields),
                "rows": [list(record) for record in self.records],
                "phenomena": {
                    "columns": list(PhenomenonRecord._fields),
                    "rows": [list(record) for record in self.phenomena],
                },
            }
        )


def _header(kind: BulletinKind, bulletin_id: str, zones: ZoneTable) -> dict[str, Any]:
    """Return the fields that open the JSON document of a bulletin."""
    return {
        "schema": SCHEMA_VERSION,
        "kind": kind.code,
        "bulletin": bulletin_id,
        "zone_set": zones.fingerprint,
    }


def _csv(columns: Sequence[str], rows: Iterable[Iterable[object]]) -> str:
    """Return rows as CSV with a header row and Unix line endings."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return output.getvalue()


def _json(document: Mapping[str, Any]) -> str:
    """Return a JSON document without spaces, keeping the accents."""
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"))
