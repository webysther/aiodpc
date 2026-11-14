"""Typed DTOs of the DPC GeoJSON files, exactly as DPC publishes them.

Optional: requires ``pip install "aiodpc[schema]"`` (msgspec).

The DTOs give the raw files clean, typed names (``zone_name`` for DPC's
``"Nome zona"``) and validate them strictly: a missing field or a value of an
unexpected type raises :class:`aiodpc.DpcParseError` naming its location, e.g.
``Object missing required field `Nome zona` - at `$.features[1].properties```.
New fields added by DPC are ignored.

That strictness is the point: it detects any change of the DPC format. The
rest of aiodpc does not use these DTOs and keeps working, leniently, when the
data is incomplete.
"""

from __future__ import annotations

from typing import Final

try:
    import msgspec
except ImportError as err:
    msg = 'aiodpc.schema requires msgspec: pip install "aiodpc[schema]"'
    raise ImportError(msg) from err

from msgspec import Struct, field

from .exceptions import DpcParseError

# GeoJSON coordinates are [longitude, latitude].
type Position = list[float]


class Point(Struct, frozen=True, tag="Point", tag_field="type"):
    """GeoJSON Point."""

    coordinates: Position


class Polygon(Struct, frozen=True, tag="Polygon", tag_field="type"):
    """GeoJSON Polygon: an exterior ring, then the holes."""

    coordinates: list[list[Position]]


class MultiPolygon(Struct, frozen=True, tag="MultiPolygon", tag_field="type"):
    """GeoJSON MultiPolygon."""

    coordinates: list[list[list[Position]]]


type Geometry = Point | Polygon | MultiPolygon


class CriticalityProperties(Struct, frozen=True):
    """Properties of a zone of the criticality file."""

    zone_name: str = field(name="Nome zona")
    municipalities: list[str] = field(name="Comuni")
    summary: str = field(name="Rappresentata nella mappa")
    """E.g. ``"Ordinaria per rischio idrogeologico / ALLERTA GIALLA"``."""
    hydraulic: str = field(name="Per rischio idraulico")
    """E.g. ``"Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA"``."""
    thunderstorms: str = field(name="Per rischio temporali")
    hydrogeological: str = field(name="Per rischio idrogeologico")


class CriticalityFeature(Struct, frozen=True):
    """A zone of the criticality file."""

    properties: CriticalityProperties
    geometry: Geometry | None


class CriticalityFile(Struct, frozen=True):
    """A day of the criticality bulletin: every alert zone of Italy."""

    features: list[CriticalityFeature]


class VigilanceProperties(Struct, frozen=True):
    """Properties of a zone of the vigilance file."""

    zone_name: str = field(name="Nome_Zona")
    municipalities: list[str] = field(name="comuni")
    precipitation_class: int = field(name="id_classificazione")
    """DPC class, 1 ("assenti o non rilevanti") to 5 ("molto elevati")."""
    precipitation: str = field(name="Quantitativi_previsti")
    """E.g. ``"Deboli"``."""


class VigilanceFeature(Struct, frozen=True):
    """A zone of the vigilance file."""

    properties: VigilanceProperties
    geometry: Geometry | None


class VigilanceFile(Struct, frozen=True):
    """A day of the vigilance bulletin: every vigilance zone of Italy."""

    features: list[VigilanceFeature]


class PhenomenonProperties(Struct, frozen=True):
    """Properties of a phenomenon of the vigilance bulletin."""

    code: int = field(name="id_fenomeno")
    """DPC phenomenon code, see :data:`aiodpc.parsers.PHENOMENON_TYPES`."""
    latitude: float = field(name="lat")
    longitude: float = field(name="lon")
    bulletin_id: int = field(name="id_bollettino")
    bulletin_date: str = field(name="data_bollettino")
    """E.g. ``"2026-11-14Z"``."""


class PhenomenonFeature(Struct, frozen=True):
    """A phenomenon of the vigilance bulletin."""

    properties: PhenomenonProperties
    geometry: Geometry | None


class PhenomenaFile(Struct, frozen=True):
    """The phenomena of a day of the vigilance bulletin."""

    features: list[PhenomenonFeature]


_CRITICALITY_DECODER: Final = msgspec.json.Decoder(CriticalityFile)
_VIGILANCE_DECODER: Final = msgspec.json.Decoder(VigilanceFile)
_PHENOMENA_DECODER: Final = msgspec.json.Decoder(PhenomenaFile)


def decode_criticality_file(data: bytes | str) -> CriticalityFile:
    """Decode a criticality GeoJSON file.

    Raises :class:`aiodpc.DpcParseError` when it does not match the DTOs.
    """
    return _decode(_CRITICALITY_DECODER, data)


def decode_vigilance_file(data: bytes | str) -> VigilanceFile:
    """Decode a vigilance GeoJSON file (the zones).

    Raises :class:`aiodpc.DpcParseError` when it does not match the DTOs.
    """
    return _decode(_VIGILANCE_DECODER, data)


def decode_phenomena_file(data: bytes | str) -> PhenomenaFile:
    """Decode a phenomena GeoJSON file of the vigilance bulletin.

    Raises :class:`aiodpc.DpcParseError` when it does not match the DTOs.
    """
    return _decode(_PHENOMENA_DECODER, data)


def _decode[T](decoder: msgspec.json.Decoder[T], data: bytes | str) -> T:
    try:
        return decoder.decode(data)
    except msgspec.ValidationError as err:
        msg = f"DPC data does not match the schema: {err}"
        raise DpcParseError(msg) from err
    except msgspec.DecodeError as err:
        msg = f"Invalid JSON from DPC: {err}"
        raise DpcParseError(msg) from err
