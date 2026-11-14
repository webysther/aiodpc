"""Tests of the parsing of the DPC data."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import pytest

from aiodpc import (
    AlertLevel,
    Assessment,
    DpcLocationError,
    DpcParseError,
    PhenomenonCategory,
    Risk,
)
from aiodpc.parsers import (
    day_expires,
    location_in_zones,
    parse_assessment,
    parse_criticality_day,
    parse_criticality_id,
    parse_phenomena,
    parse_vigilance_day,
    parse_vigilance_id,
)
from aiodpc.urls import (
    CRITICALITY_DAYS,
    VIGILANCE_DAYS,
    criticality_geojson_url,
    criticality_preview_url,
    phenomena_geojson_url,
    vigilance_geojson_url,
    vigilance_preview_url,
)

from . import CRIT_ID, LATITUDE, LONGITUDE, OUTSIDE, VIGI_ID, load_json, rome

if TYPE_CHECKING:
    from aiodpc.models import CriticalityDay, VigilanceDay

GITHUB = "https://raw.githubusercontent.com/pcm-dpc"
CRIT_FILES = f"{GITHUB}/DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files"
VIGI_FILES = f"{GITHUB}/DPC-Bollettini-Vigilanza-Meteorologica/master/files"

# Assessments of the fixtures
GREEN = Assessment(
    "Assenza di fenomeni significativi prevedibili", "NESSUNA ALLERTA", AlertLevel.NONE
)
YELLOW = Assessment("Ordinaria", "ALLERTA GIALLA", AlertLevel.YELLOW)
RED = Assessment("Elevata", "ALLERTA ROSSA", AlertLevel.RED)


def square(south: float, west: float, north: float, east: float) -> dict[str, Any]:
    """Return a rectangular Polygon geometry."""
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def zone(
    name: str,
    geometry: dict[str, Any] | None,
    municipalities: object,
    summary: str = "Ordinaria / ALLERTA GIALLA",
) -> dict[str, Any]:
    """Return a criticality feature."""
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "Rappresentata nella mappa": summary,
            "Per rischio idraulico": summary,
            "Nome zona": name,
            "Comuni": municipalities,
        },
    }


def collection(*features: object) -> dict[str, Any]:
    """Return a GeoJSON FeatureCollection."""
    return {"type": "FeatureCollection", "features": list(features)}


def criticality(
    geojson: object, offset: int = 0, municipality: str | None = None
) -> CriticalityDay:
    """Parse a criticality day at the default location."""
    return parse_criticality_day(
        geojson,
        bulletin_id=CRIT_ID,
        offset=offset,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        municipality=municipality,
    )


def vigilance(
    geojson: object, offset: int = 0, municipality: str | None = None
) -> VigilanceDay:
    """Parse a vigilance day at the default location."""
    return parse_vigilance_day(
        geojson,
        bulletin_id=VIGI_ID,
        offset=offset,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        municipality=municipality,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA",
            GREEN,
        ),
        ("Ordinaria / ALLERTA GIALLA", YELLOW),
        (
            "Moderata per rischio idrogeologico / ALLERTA ARANCIONE",
            Assessment(
                "Moderata per rischio idrogeologico",
                "ALLERTA ARANCIONE",
                AlertLevel.ORANGE,
            ),
        ),
        ("Elevata / ALLERTA ROSSA", RED),
        # Case and spacing of the alert do not matter; the text is kept as is
        (
            "Elevata /  Allerta   Rossa ",
            Assessment("Elevata", "Allerta   Rossa", AlertLevel.RED),
        ),
        # Only the first slash separates the alert
        (
            "A/B / ALLERTA GIALLA",
            Assessment("A", "B / ALLERTA GIALLA", AlertLevel.UNKNOWN),
        ),
        ("Senza allerta", Assessment("Senza allerta", "", AlertLevel.UNKNOWN)),
        (None, Assessment("", "", AlertLevel.UNKNOWN)),
        (42, Assessment("42", "", AlertLevel.UNKNOWN)),
    ],
)
def test_parse_assessment(value: object, expected: Assessment) -> None:
    """Test the parsing of a DPC criticality value."""
    assert parse_assessment(value) == expected


def test_parse_ids() -> None:
    """Test the dates in the bulletin IDs."""
    assert parse_criticality_id("20261114_1430") == rome(2026, 11, 14, 14, 30)
    assert parse_vigilance_id("20261114") == dt.date(2026, 11, 14)


@pytest.mark.parametrize(
    "bulletin_id", ["", "2026111_1430", "20261114", "20261332_1430", "20261114_1430x"]
)
def test_invalid_criticality_id(bulletin_id: str) -> None:
    """Test that invalid criticality IDs are rejected."""
    with pytest.raises(ValueError, match="Invalid criticality bulletin ID"):
        parse_criticality_id(bulletin_id)


@pytest.mark.parametrize("bulletin_id", ["", "2026111", "20261114_1430", "20260230"])
def test_invalid_vigilance_id(bulletin_id: str) -> None:
    """Test that invalid vigilance IDs are rejected."""
    with pytest.raises(ValueError, match="Invalid vigilance bulletin ID"):
        parse_vigilance_id(bulletin_id)


@pytest.mark.parametrize(
    ("day", "expected", "utc_offset"),
    [
        (dt.date(2026, 11, 14), rome(2026, 11, 15), dt.timedelta(hours=1)),
        # Days around the end of summer time (2026-10-25)
        (dt.date(2026, 10, 24), rome(2026, 10, 25), dt.timedelta(hours=2)),
        (dt.date(2026, 10, 25), rome(2026, 10, 26), dt.timedelta(hours=1)),
    ],
)
def test_day_expires(
    day: dt.date, expected: dt.datetime, utc_offset: dt.timedelta
) -> None:
    """Test that a day expires at the midnight that ends it, in Rome."""
    expires = day_expires(day)

    assert expires == expected
    assert expires.utcoffset() == utc_offset


def test_urls() -> None:
    """Test the URLs of the bulletin files."""
    assert CRITICALITY_DAYS == ("today", "tomorrow")
    assert VIGILANCE_DAYS == ("oggi", "domani", "dopodomani")
    assert criticality_geojson_url(CRIT_ID, 1) == (
        f"{CRIT_FILES}/geojson/20261114_1430_tomorrow.json"
    )
    assert criticality_preview_url(CRIT_ID, 0) == (
        f"{CRIT_FILES}/preview/20261114_1430_oggi.png"
    )
    assert vigilance_geojson_url(VIGI_ID, 2) == (
        f"{VIGI_FILES}/geojson/20261114_dopodomani.json"
    )
    assert phenomena_geojson_url(VIGI_ID, 0) == (
        f"{VIGI_FILES}/geojson/20261114_fenomeni_oggi.json"
    )
    assert vigilance_preview_url(VIGI_ID, 1) == (
        f"{VIGI_FILES}/preview/20261114_domani.png"
    )
    assert vigilance_preview_url(VIGI_ID, 2) is None


@pytest.mark.parametrize("offset", [-1, 2])
def test_invalid_offset(offset: int) -> None:
    """Test that the criticality bulletin has only two days."""
    with pytest.raises(ValueError, match="between 0 and 1"):
        criticality(load_json("criticality_today.json"), offset)


def test_criticality_today() -> None:
    """Test the criticality of the publication day at the location."""
    day = criticality(load_json("criticality_today.json"))

    assert day.date == dt.date(2026, 11, 14)
    assert day.offset == 0
    assert day.expires == rome(2026, 11, 15)
    assert day.zone_name == "Bacini di Roma"
    assert day.summary == Assessment(
        "Ordinaria per rischio temporali", "ALLERTA GIALLA", AlertLevel.YELLOW
    )
    assert day.risks == {
        Risk.HYDRAULIC: GREEN,
        Risk.THUNDERSTORMS: YELLOW,
        Risk.HYDROGEOLOGICAL: YELLOW,
    }
    assert day.max_level is AlertLevel.YELLOW
    assert day.image_url == f"{CRIT_FILES}/preview/20261114_1430_oggi.png"


def test_criticality_tomorrow() -> None:
    """Test the criticality of the day after the publication."""
    day = criticality(load_json("criticality_tomorrow.json"), 1)

    assert day.date == dt.date(2026, 11, 15)
    assert day.expires == rome(2026, 11, 16)
    assert day.risks[Risk.HYDROGEOLOGICAL].level is AlertLevel.ORANGE
    assert day.image_url == f"{CRIT_FILES}/preview/20261114_1430_domani.png"


def test_location_outside() -> None:
    """Test that a location outside every zone raises a location error."""
    with pytest.raises(DpcLocationError):
        parse_criticality_day(
            load_json("criticality_today.json"),
            bulletin_id=CRIT_ID,
            offset=0,
            latitude=OUTSIDE[0],
            longitude=OUTSIDE[1],
        )


@pytest.mark.parametrize("municipality", ["Roma", "roma", "  ROMA "])
def test_municipality(municipality: str) -> None:
    """Test the lookup by municipality, ignoring case and spacing."""
    day = criticality(load_json("criticality_today.json"), municipality=municipality)

    assert day.zone_name == "Bacini di Roma"
    assert day.summary.level is AlertLevel.YELLOW


def test_municipality_of_another_zone() -> None:
    """Test a municipality whose zones do not contain the coordinates."""
    day = criticality(load_json("criticality_today.json"), municipality="Como")

    assert day.zone_name == "Lario e Prealpi occidentali"
    assert day.risks == dict.fromkeys(Risk, RED)


def test_municipality_in_several_zones() -> None:
    """Test that the highest zone of the municipality wins, named by the point."""
    geojson = collection(
        zone(
            "Nord", square(42.3, 12.0, 43.0, 13.0), ["Roma"], "Elevata / ALLERTA ROSSA"
        ),
        zone("Centro", square(41.5, 12.0, 42.3, 13.0), ["Roma"]),
        zone("Altrove", square(45.0, 8.0, 46.0, 9.0), ["Como"], "X / ALLERTA ROSSA"),
        zone("Sud", square(41.0, 12.0, 41.5, 13.0), "Roma", "Seconda / ALLERTA ROSSA"),
    )

    day = criticality(geojson, municipality="Roma")

    assert day.zone_name == "Centro"
    assert day.summary == Assessment("Elevata", "ALLERTA ROSSA", AlertLevel.RED)
    # The first zone with the highest level wins
    assert day.risks[Risk.HYDRAULIC].info == "Elevata"
    # Risks missing from the data are unknown
    assert day.risks[Risk.THUNDERSTORMS] == Assessment("", "", AlertLevel.UNKNOWN)


def test_municipality_not_found(caplog: pytest.LogCaptureFixture) -> None:
    """Test that an unknown municipality falls back to the coordinates."""
    day = criticality(load_json("criticality_today.json"), municipality="Atlantide")

    assert day.zone_name == "Bacini di Roma"
    assert "Atlantide" in caplog.text


def test_municipality_not_found_outside() -> None:
    """Test an unknown municipality with coordinates outside every zone."""
    with pytest.raises(DpcLocationError):
        parse_criticality_day(
            load_json("criticality_today.json"),
            bulletin_id=CRIT_ID,
            offset=0,
            latitude=OUTSIDE[0],
            longitude=OUTSIDE[1],
            municipality="Atlantide",
        )


def test_unusual_features_are_skipped() -> None:
    """Test features without geometry, area or municipalities."""
    geojson = collection(
        zone("Senza geometria", None, None),
        zone("Punto", {"type": "Point", "coordinates": [12.5, 41.9]}, 42),
        {
            "type": "Feature",
            "geometry": square(41.5, 12.0, 42.3, 13.0),
            "properties": None,
        },
    )

    day = criticality(geojson, municipality="Roma")

    assert day.zone_name == ""
    assert day.summary.level is AlertLevel.UNKNOWN


@pytest.mark.parametrize(
    "geojson",
    [
        None,
        [],
        {"type": "FeatureCollection"},
        {"features": {"type": "Feature"}},
        collection("feature"),
        collection({"properties": "x", "geometry": None}),
        collection({"properties": {}, "geometry": [12.5, 41.9]}),
        collection({"properties": {}, "geometry": {"type": "Polygon"}}),
        collection(
            {"properties": {}, "geometry": {"type": "Polygon", "coordinates": []}}
        ),
    ],
)
def test_unexpected_format(geojson: object) -> None:
    """Test that unexpected data raises a parse error."""
    with pytest.raises(DpcParseError):
        criticality(geojson)


def test_location_in_zones() -> None:
    """Test whether locations are inside the zones of a bulletin."""
    geojson = load_json("criticality_today.json")

    assert location_in_zones(geojson, LATITUDE, LONGITUDE)
    assert not location_in_zones(geojson, *OUTSIDE)


@pytest.mark.parametrize(
    ("offset", "date", "level", "precipitation", "image"),
    [
        (0, dt.date(2026, 11, 14), 2, "Deboli", "oggi"),
        (1, dt.date(2026, 11, 15), 3, "Moderati", "domani"),
        (2, dt.date(2026, 11, 16), 1, "Assenti o non rilevanti", None),
    ],
)
def test_vigilance(
    offset: int,
    date: dt.date,
    level: int,
    precipitation: str,
    image: str | None,
) -> None:
    """Test the vigilance of each day at the location."""
    day = vigilance(load_json(f"vigilance_{VIGILANCE_DAYS[offset]}.json"), offset)

    assert day.date == date
    assert day.offset == offset
    assert day.expires == day_expires(date)
    assert day.zone_name == "Lazio centrale"
    assert day.level == level
    assert day.precipitation == precipitation
    assert day.image_url == (
        f"{VIGI_FILES}/preview/20261114_{image}.png" if image else None
    )
    assert day.phenomena == ()


def test_vigilance_municipality() -> None:
    """Test the vigilance looked up by municipality."""
    day = vigilance(load_json("vigilance_oggi.json"), municipality="Como")

    assert day.zone_name == "Lombardia centrale settore occidentale"
    assert day.level == 5


@pytest.mark.parametrize(
    ("value", "expected"),
    [(3, 3), (3.0, 3), ("3", 3), (2.5, 0), ("tre", 0), (True, 0), (None, 0)],
)
def test_vigilance_level(value: object, expected: int) -> None:
    """Test the parsing of the precipitation class of a zone."""
    geojson = collection(
        {
            "geometry": square(41.5, 12.0, 42.3, 13.0),
            "properties": {
                "Nome_Zona": "Lazio",
                "id_classificazione": value,
                "Quantitativi_previsti": 3,
            },
        }
    )

    day = vigilance(geojson)

    assert day.level == expected
    assert day.precipitation is None


def phenomena(geojson: object, radius_km: float = 50) -> list[tuple[object, ...]]:
    """Parse phenomena at the default location, as comparable tuples."""
    return [
        (
            item.code,
            item.category,
            item.description,
            item.latitude,
            item.longitude,
            item.distance_km,
            item.direction,
            item.degrees,
            item.bulletin_id,
            item.bulletin_date,
        )
        for item in parse_phenomena(
            geojson, latitude=LATITUDE, longitude=LONGITUDE, radius_km=radius_km
        )
    ]


def test_phenomena() -> None:
    """Test the phenomena within the radius, with distance and direction."""
    geojson = load_json("phenomena_oggi.json")

    assert phenomena(geojson) == [
        (
            5,
            PhenomenonCategory.PRECIPITATION,
            "rovesci o temporali a carattere isolato",
            41.573134169859415,
            12.674774846264892,
            39.1,
            "SSE",
            158,
            202611141,
            "2026-11-14Z",
        )
    ]
    # A larger radius includes the sea storm near Naples
    assert [item[0] for item in phenomena(geojson, 300)] == [5, 41]
    assert phenomena(load_json("phenomena_dopodomani.json")) == []


def point_feature(properties: dict[str, Any], geometry: object = None) -> object:
    """Return a phenomenon feature."""
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def test_phenomena_unusual_data() -> None:
    """Test unknown codes, missing positions and unusual values."""
    geojson = collection(
        # Unknown code: kept without category
        point_feature({"id_fenomeno": 99, "lat": 41.95, "lon": 12.5}),
        # Position from the geometry; invalid bulletin ID and date
        point_feature(
            {"id_fenomeno": 40, "id_bollettino": True, "data_bollettino": 1},
            {"type": "Point", "coordinates": [12.5, 41.85]},
        ),
        # Skipped: no code, boolean code, no usable position
        point_feature({"lat": 41.9, "lon": 12.5}),
        point_feature({"id_fenomeno": True, "lat": 41.9, "lon": 12.5}),
        point_feature({"id_fenomeno": 1, "lat": "41.9", "lon": 12.5}),
        point_feature({"id_fenomeno": 1}, {"type": "Polygon", "coordinates": []}),
        point_feature({"id_fenomeno": 1}, {"type": "Point", "coordinates": [12.5]}),
        point_feature(
            {"id_fenomeno": 1}, {"type": "Point", "coordinates": [12.5, float("nan")]}
        ),
    )

    assert phenomena(geojson) == [
        (99, None, None, 41.95, 12.5, 5.6, "N", 0, None, None),
        (
            40,
            PhenomenonCategory.SEA,
            "molto mosso",
            41.85,
            12.5,
            5.6,
            "S",
            180,
            None,
            None,
        ),
    ]


def test_phenomena_unexpected_format() -> None:
    """Test that unexpected phenomena data raises a parse error."""
    with pytest.raises(DpcParseError):
        parse_phenomena({}, latitude=LATITUDE, longitude=LONGITUDE, radius_km=50)
