"""Parsing of the DPC bulletin data, without any I/O.

The functions take the decoded JSON of the DPC GeoJSON files, so the same
download can be parsed for several locations.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final, NamedTuple

from .const import ROME_TZ
from .exceptions import DpcLocationError, DpcParseError
from .geo import calculate_initial_compass_bearing, distance_km, point_in_area
from .models import (
    AlertLevel,
    CriticalityDay,
    Location,
    Phenomenon,
    PhenomenonCategory,
    Precipitation,
    RiskAssessment,
    RiskType,
    VigilanceDay,
)
from .municipalities import municipality_names, normalize
from .urls import criticality_preview_url, vigilance_preview_url

_LOGGER = logging.getLogger(__name__)

ALERT_LEVELS: Final[Mapping[str, AlertLevel]] = {
    "NESSUNA ALLERTA": AlertLevel.GREEN,
    "ALLERTA GIALLA": AlertLevel.YELLOW,
    "ALLERTA ARANCIONE": AlertLevel.ORANGE,
    "ALLERTA ROSSA": AlertLevel.RED,
}
"""Alert texts of the criticality bulletin and their level."""

PRECIPITATION_TEXTS: Final[Mapping[str, Precipitation]] = {
    "ASSENTI O NON RILEVANTI": Precipitation.NONE,
    "DEBOLI": Precipitation.LIGHT,
    "MODERATI": Precipitation.MODERATE,
    "ELEVATI": Precipitation.HEAVY,
    "MOLTO ELEVATI": Precipitation.VERY_HEAVY,
}
"""Precipitation texts of the vigilance bulletin (``Quantitativi_previsti``)."""

_PRECIPITATION_CLASSES: Final = frozenset(
    level.value for level in Precipitation if level is not Precipitation.UNKNOWN
)

PHENOMENON_TYPES: Final[Mapping[int, tuple[PhenomenonCategory, str]]] = {
    1: (PhenomenonCategory.PRECIPITATION, "piogge sparse o intermittenti"),
    2: (PhenomenonCategory.PRECIPITATION, "piogge diffuse e continue"),
    3: (PhenomenonCategory.PRECIPITATION, "nevicate deboli o moderate"),
    4: (PhenomenonCategory.PRECIPITATION, "nevicate abbondanti"),
    5: (PhenomenonCategory.PRECIPITATION, "rovesci o temporali a carattere isolato"),
    6: (PhenomenonCategory.PRECIPITATION, "rovesci o temporali a carattere sparso"),
    7: (PhenomenonCategory.PRECIPITATION, "rovesci o temporali a carattere diffuso"),
    10: (PhenomenonCategory.WIND, "forti"),
    11: (PhenomenonCategory.WIND, "burrasca"),
    12: (PhenomenonCategory.WIND, "tempesta"),
    13: (PhenomenonCategory.WIND, "frequenti raffiche"),
    20: (
        PhenomenonCategory.FROST,
        "diffusa formazione di ghiaccio al suolo a quote collinari",
    ),
    21: (
        PhenomenonCategory.FROST,
        "diffusa formazione di ghiaccio al suolo a quote di pianura",
    ),
    30: (PhenomenonCategory.FOG, "diffuse nelle ore notturne e del primo mattino"),
    31: (PhenomenonCategory.FOG, "diffuse e persistenti anche nelle ore diurne"),
    40: (PhenomenonCategory.SEA, "molto mosso"),
    41: (PhenomenonCategory.SEA, "agitato o molto agitato"),
    42: (PhenomenonCategory.SEA, "grosso o molto grosso"),
    50: (PhenomenonCategory.WAVE_MOTION, "in aumento"),
    51: (PhenomenonCategory.WAVE_MOTION, "in diminuzione"),
    60: (PhenomenonCategory.TEMPERATURE, "elevate o in sensibile aumento"),
    61: (PhenomenonCategory.TEMPERATURE, "molto elevate o in marcato aumento"),
    62: (PhenomenonCategory.TEMPERATURE, "basse o in sensibile calo"),
    63: (PhenomenonCategory.TEMPERATURE, "molto basse o in marcato calo"),
}
"""DPC phenomenon codes (``id_fenomeno``): category and Italian legend."""

SUMMARY_PROPERTY: Final = "Rappresentata nella mappa"
RISK_PROPERTIES: Final[Mapping[RiskType, str]] = {
    RiskType.HYDRAULIC: "Per rischio idraulico",
    RiskType.THUNDERSTORMS: "Per rischio temporali",
    RiskType.HYDROGEOLOGICAL: "Per rischio idrogeologico",
}
"""Properties of the criticality GeoJSON holding the assessment of each risk."""
# The criticality and vigilance files spell some properties differently.
_ZONE_NAME_PROPERTIES: Final = ("Nome zona", "Nome_Zona")
_MUNICIPALITIES_PROPERTIES: Final = ("Comuni", "comuni")

_CRITICALITY_ID: Final = re.compile(r"\d{8}_\d{4}")
_VIGILANCE_ID: Final = re.compile(r"\d{8}")


def parse_criticality_id(bulletin_id: str) -> dt.datetime:
    """Return the publication time of a criticality bulletin ID (Europe/Rome).

    ``"20261114_1430"`` is the bulletin published on 2026-11-14 at 14:30.
    Raises ``ValueError`` for an invalid ID.
    """
    msg = f"Invalid criticality bulletin ID: {bulletin_id!r}"
    if not _CRITICALITY_ID.fullmatch(bulletin_id):
        raise ValueError(msg)
    try:
        published = dt.datetime.strptime(bulletin_id, "%Y%m%d_%H%M")  # noqa: DTZ007
    except ValueError as err:
        raise ValueError(msg) from err
    return published.replace(tzinfo=ROME_TZ)


def parse_vigilance_id(bulletin_id: str) -> dt.date:
    """Return the publication day of a vigilance bulletin ID.

    ``"20261114"`` is the bulletin published on 2026-11-14.
    Raises ``ValueError`` for an invalid ID.
    """
    msg = f"Invalid vigilance bulletin ID: {bulletin_id!r}"
    if not _VIGILANCE_ID.fullmatch(bulletin_id):
        raise ValueError(msg)
    try:
        return dt.date(
            int(bulletin_id[:4]), int(bulletin_id[4:6]), int(bulletin_id[6:])
        )
    except ValueError as err:
        raise ValueError(msg) from err


def end_of_day(day: dt.date) -> dt.datetime:
    """Return the end of validity of the assessment of a day.

    The criticality bulletin covers "fino alle 24.00 del giorno di emissione
    (oggi) e nelle 24 ore del giorno seguente (domani)", so a day expires at
    the midnight that ends it (Europe/Rome). The same holds for vigilance.
    """
    return dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), tzinfo=ROME_TZ)


class Assessment(NamedTuple):
    """A DPC criticality value, parsed."""

    level: AlertLevel
    description: str
    """The criticality before the alert, e.g. ``"Ordinaria"``."""


def parse_assessment(value: object) -> Assessment:
    """Parse a criticality value such as ``"Ordinaria / ALLERTA GIALLA"``.

    The part before the first ``/`` is the description, the rest the alert. An
    unrecognised alert has level :attr:`AlertLevel.UNKNOWN`.
    """
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        text = str(value)
    description, _, alert = text.partition("/")
    level = ALERT_LEVELS.get(_upper_words(alert), AlertLevel.UNKNOWN)
    return Assessment(level, description.strip())


def parse_precipitation(class_value: object, text: object = None) -> Precipitation:
    """Parse the precipitation of a vigilance zone.

    ``class_value`` is the DPC class (``id_classificazione``); when it is not a
    known class, ``text`` (``Quantitativi_previsti``, e.g. ``"Deboli"``) is
    used. Unrecognised values give :attr:`Precipitation.UNKNOWN`.
    """
    number = _integer(class_value)
    if number in _PRECIPITATION_CLASSES:
        return Precipitation(number)
    if isinstance(text, str):
        return PRECIPITATION_TEXTS.get(_upper_words(text), Precipitation.UNKNOWN)
    return Precipitation.UNKNOWN


def _upper_words(text: str) -> str:
    return " ".join(text.upper().split())


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value)
    return None


@dataclass(frozen=True, slots=True)
class _Feature:
    properties: Mapping[str, Any]
    geometry: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class _Zone:
    properties: Mapping[str, Any]
    name: str


def _features(geojson: object) -> list[_Feature]:
    """Return the features of a GeoJSON FeatureCollection, checking its shape."""
    if not isinstance(geojson, Mapping):
        msg = "DPC data is not a GeoJSON object"
        raise DpcParseError(msg)
    features = geojson.get("features")
    if not isinstance(features, list):
        msg = "DPC GeoJSON has no list of features"
        raise DpcParseError(msg)
    result = []
    for feature in features:
        if not isinstance(feature, Mapping):
            msg = "DPC GeoJSON feature is not an object"
            raise DpcParseError(msg)
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not (
            geometry is None or isinstance(geometry, Mapping)
        ):
            msg = "DPC GeoJSON feature has invalid properties or geometry"
            raise DpcParseError(msg)
        result.append(_Feature(properties, geometry))
    return result


def _contains(feature: _Feature, location: Location) -> bool:
    if feature.geometry is None:
        return False
    try:
        return point_in_area(location.latitude, location.longitude, feature.geometry)
    except (KeyError, IndexError, TypeError, ValueError) as err:
        msg = "DPC GeoJSON has an invalid zone geometry"
        raise DpcParseError(msg) from err


def _zone_name(properties: Mapping[str, Any]) -> str:
    for key in _ZONE_NAME_PROPERTIES:
        if isinstance(name := properties.get(key), str) and name:
            return name
    return ""


def _municipalities(properties: Mapping[str, Any]) -> list[str]:
    for key in _MUNICIPALITIES_PROPERTIES:
        if key in properties:
            value = properties[key]
            if isinstance(value, str):
                return [value]
            if isinstance(value, list):
                return [item for item in value if isinstance(item, str)]
            return []
    return []


def _listing(features: list[_Feature], municipality: str) -> list[_Feature]:
    """Return the features whose municipalities include ``municipality``.

    The name is looked up as written first, ignoring case and spacing. Only when
    no zone lists it are its other names tried (see :mod:`aiodpc.municipalities`):
    "Bozen" finds "Bolzano/Bozen" and "Bolzano", while "Corvara" stays the
    municipality of Abruzzo and not "Corvara in Badia/Corvara".
    """
    wanted = normalize(municipality)
    listing = [
        feature
        for feature in features
        if any(
            normalize(name) == wanted for name in _municipalities(feature.properties)
        )
    ]
    if listing:
        return listing
    names = municipality_names(municipality)
    return [
        feature
        for feature in features
        if any(
            names & municipality_names(name)
            for name in _municipalities(feature.properties)
        )
    ]


def _select_zone(
    features: list[_Feature],
    location: Location,
    level: Callable[[Mapping[str, Any]], int],
) -> _Zone:
    """Return the zone of a location.

    With a municipality, the zones listing it (see :func:`_listing`) are
    candidates and the one with the highest level wins (the first one on ties);
    its name is replaced by the name of the candidate containing the
    coordinates, if any. Without a municipality, or when no zone lists it, the
    zone containing the coordinates is used.
    """
    municipality = location.municipality
    if municipality and municipality.strip():
        best: _Feature | None = None
        best_level = 0
        point_zone_name = ""
        for feature in _listing(features, municipality):
            if not point_zone_name and _contains(feature, location):
                point_zone_name = _zone_name(feature.properties)
            feature_level = level(feature.properties)
            if best is None or feature_level > best_level:
                best, best_level = feature, feature_level
        if best is not None:
            name = point_zone_name or _zone_name(best.properties)
            return _Zone(best.properties, name)
        _LOGGER.warning(
            "Municipality %r is in no DPC zone, using the coordinates", municipality
        )
    for feature in features:
        if _contains(feature, location):
            return _Zone(feature.properties, _zone_name(feature.properties))
    msg = "The location is not inside any DPC alert zone"
    raise DpcLocationError(msg)


def _criticality_level(properties: Mapping[str, Any]) -> int:
    return parse_assessment(properties.get(SUMMARY_PROPERTY)).level


def _precipitation(properties: Mapping[str, Any]) -> Precipitation:
    return parse_precipitation(
        properties.get("id_classificazione"), properties.get("Quantitativi_previsti")
    )


def location_in_zones(geojson: object, location: Location) -> bool:
    """Return whether a location is inside any zone of a bulletin GeoJSON."""
    return any(_contains(item, location) for item in _features(geojson))


def _risk_assessment(risk_type: RiskType, value: object) -> RiskAssessment:
    assessment = parse_assessment(value)
    return RiskAssessment(risk_type, assessment.level, assessment.description)


def parse_criticality_day(
    geojson: object, *, bulletin_id: str, offset: int, location: Location
) -> CriticalityDay:
    """Parse the criticality GeoJSON of a bulletin day for a location.

    Raises :class:`aiodpc.DpcParseError` for unexpected data and
    :class:`aiodpc.DpcLocationError` when the location is in no zone.
    """
    day = parse_criticality_id(bulletin_id).date() + dt.timedelta(days=offset)
    image_url = criticality_preview_url(bulletin_id, offset)
    zone = _select_zone(_features(geojson), location, _criticality_level)
    summary = parse_assessment(zone.properties.get(SUMMARY_PROPERTY))
    risks = {
        risk_type: _risk_assessment(risk_type, zone.properties.get(key))
        for risk_type, key in RISK_PROPERTIES.items()
    }
    return CriticalityDay(
        date=day,
        offset=offset,
        valid_until=end_of_day(day),
        zone=zone.name,
        level=max(summary.level, *(item.level for item in risks.values())),
        description=summary.description,
        hydraulic=risks[RiskType.HYDRAULIC],
        thunderstorms=risks[RiskType.THUNDERSTORMS],
        hydrogeological=risks[RiskType.HYDROGEOLOGICAL],
        image_url=image_url,
    )


def parse_vigilance_day(
    geojson: object,
    *,
    bulletin_id: str,
    offset: int,
    location: Location,
    phenomena: Iterable[Phenomenon] = (),
) -> VigilanceDay:
    """Parse the vigilance GeoJSON of a bulletin day for a location.

    ``phenomena`` are attached to the day as they are (see
    :func:`parse_phenomena`).

    Raises :class:`aiodpc.DpcParseError` for unexpected data and
    :class:`aiodpc.DpcLocationError` when the location is in no zone.
    """
    day = parse_vigilance_id(bulletin_id) + dt.timedelta(days=offset)
    image_url = vigilance_preview_url(bulletin_id, offset)
    zone = _select_zone(_features(geojson), location, _precipitation)
    return VigilanceDay(
        date=day,
        offset=offset,
        valid_until=end_of_day(day),
        zone=zone.name,
        precipitation=_precipitation(zone.properties),
        image_url=image_url,
        phenomena=tuple(phenomena),
    )


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def _position(feature: _Feature) -> tuple[float, float] | None:
    """Return the (lat, lon) of a phenomenon: its properties, else its Point."""
    latitude = _number(feature.properties.get("lat"))
    longitude = _number(feature.properties.get("lon"))
    if latitude is not None and longitude is not None:
        return latitude, longitude
    geometry = feature.geometry
    if geometry is None or geometry.get("type") != "Point":
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:  # noqa: PLR2004
        return None
    longitude, latitude = _number(coordinates[0]), _number(coordinates[1])
    if latitude is None or longitude is None:
        return None
    return latitude, longitude


def parse_phenomena(
    geojson: object, *, location: Location, within_km: float
) -> tuple[Phenomenon, ...]:
    """Parse the phenomena GeoJSON, keeping those within ``within_km``.

    Phenomena keep the order of the file. Codes unknown to aiodpc are kept,
    with ``category`` and ``description`` set to ``None``.
    """
    origin = location.coordinates
    phenomena = []
    for feature in _features(geojson):
        code = feature.properties.get("id_fenomeno")
        position = _position(feature)
        if isinstance(code, bool) or not isinstance(code, int) or position is None:
            _LOGGER.debug("Skipping invalid DPC phenomenon %s", feature.properties)
            continue
        distance = distance_km(origin, position)
        if distance > within_km:
            continue
        category, description = PHENOMENON_TYPES.get(code, (None, None))
        direction, degrees = calculate_initial_compass_bearing(origin, position)
        bulletin_id = feature.properties.get("id_bollettino")
        bulletin_date = feature.properties.get("data_bollettino")
        phenomena.append(
            Phenomenon(
                code=code,
                category=category,
                description=description,
                latitude=position[0],
                longitude=position[1],
                distance_km=round(distance, 1),
                direction=direction,
                degrees=degrees,
                bulletin_id=(
                    bulletin_id
                    if isinstance(bulletin_id, int)
                    and not isinstance(bulletin_id, bool)
                    else None
                ),
                bulletin_date=bulletin_date if isinstance(bulletin_date, str) else None,
            )
        )
    return tuple(phenomena)
