"""Tests of the parsing of the DPC data."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import pytest

from aiodpc import (
    AlertLevel,
    DpcLocationError,
    DpcParseError,
    Location,
    PhenomenonCategory,
    Precipitation,
    RiskAssessment,
    RiskType,
)
from aiodpc.parsers import (
    Assessment,
    end_of_day,
    location_in_zones,
    parse_alert_zone,
    parse_assessment,
    parse_criticality_day,
    parse_criticality_id,
    parse_phenomena,
    parse_precipitation,
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

from . import CRIT_ID, LATITUDE, LONGITUDE, PARIS, ROME, VIGI_ID, load_json, rome

if TYPE_CHECKING:
    from aiodpc.models import CriticalityDay, VigilanceDay

GITHUB = "https://raw.githubusercontent.com/pcm-dpc"
CRIT_FILES = f"{GITHUB}/DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files"
VIGI_FILES = f"{GITHUB}/DPC-Bollettini-Vigilanza-Meteorologica/master/files"

# Assessments of the fixtures
GREEN = Assessment(AlertLevel.GREEN, "Assenza di fenomeni significativi prevedibili")
YELLOW = Assessment(AlertLevel.YELLOW, "Ordinaria")
RED = Assessment(AlertLevel.RED, "Elevata")


def assessments(day: CriticalityDay) -> dict[RiskType, Assessment]:
    """Return the level and description of each risk type of a day."""
    return {item.type: Assessment(item.level, item.description) for item in day.risks}


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
        location=Location(LATITUDE, LONGITUDE, municipality),
    )


def vigilance(
    geojson: object, offset: int = 0, municipality: str | None = None
) -> VigilanceDay:
    """Parse a vigilance day at the default location."""
    return parse_vigilance_day(
        geojson,
        bulletin_id=VIGI_ID,
        offset=offset,
        location=Location(LATITUDE, LONGITUDE, municipality),
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
            Assessment(AlertLevel.ORANGE, "Moderata per rischio idrogeologico"),
        ),
        ("Elevata / ALLERTA ROSSA", RED),
        # Case and spacing of the alert do not matter
        ("Elevata /  Allerta   Rossa ", RED),
        # Only the first slash separates the alert
        ("A/B / ALLERTA GIALLA", Assessment(AlertLevel.UNKNOWN, "A")),
        ("Senza allerta", Assessment(AlertLevel.UNKNOWN, "Senza allerta")),
        (None, Assessment(AlertLevel.UNKNOWN, "")),
        (42, Assessment(AlertLevel.UNKNOWN, "42")),
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
def test_end_of_day(
    day: dt.date, expected: dt.datetime, utc_offset: dt.timedelta
) -> None:
    """Test that a day is valid until the midnight that ends it, in Rome."""
    valid_until = end_of_day(day)

    assert valid_until == expected
    assert valid_until.utcoffset() == utc_offset


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
    assert day.valid_until == rome(2026, 11, 15)
    assert day.zone == "Bacini di Roma"
    assert day.level is AlertLevel.YELLOW
    assert day.description == "Ordinaria per rischio temporali"
    assert day.hydraulic == RiskAssessment(
        RiskType.HYDRAULIC,
        AlertLevel.GREEN,
        "Assenza di fenomeni significativi prevedibili",
    )
    assert assessments(day) == {
        RiskType.HYDRAULIC: GREEN,
        RiskType.THUNDERSTORMS: YELLOW,
        RiskType.HYDROGEOLOGICAL: YELLOW,
    }
    assert day.image_url == f"{CRIT_FILES}/preview/20261114_1430_oggi.png"


def test_criticality_tomorrow() -> None:
    """Test the criticality of the day after the publication."""
    day = criticality(load_json("criticality_tomorrow.json"), 1)

    assert day.date == dt.date(2026, 11, 15)
    assert day.valid_until == rome(2026, 11, 16)
    assert day.hydrogeological.level is AlertLevel.ORANGE
    assert day.level is AlertLevel.ORANGE
    assert day.image_url == f"{CRIT_FILES}/preview/20261114_1430_domani.png"


def test_location_outside() -> None:
    """Test that a location outside every zone raises a location error."""
    with pytest.raises(DpcLocationError):
        parse_criticality_day(
            load_json("criticality_today.json"),
            bulletin_id=CRIT_ID,
            offset=0,
            location=PARIS,
        )


@pytest.mark.parametrize("municipality", ["Roma", "roma", "  ROMA "])
def test_municipality(municipality: str) -> None:
    """Test the lookup by municipality, ignoring case and spacing."""
    day = criticality(load_json("criticality_today.json"), municipality=municipality)

    assert day.zone == "Bacini di Roma"
    assert day.level is AlertLevel.YELLOW


def test_municipality_of_another_zone() -> None:
    """Test a municipality whose zones do not contain the coordinates."""
    day = criticality(load_json("criticality_today.json"), municipality="Como")

    assert day.zone == "Lario e Prealpi occidentali"
    assert assessments(day) == dict.fromkeys(RiskType, RED)


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

    assert day.zone == "Centro"
    assert (day.level, day.description) == (AlertLevel.RED, "Elevata")
    # The first zone with the highest level wins
    assert day.hydraulic.description == "Elevata"
    # Risks missing from the data are unknown
    assert day.thunderstorms == RiskAssessment(
        RiskType.THUNDERSTORMS, AlertLevel.UNKNOWN, ""
    )


def test_municipality_not_found(caplog: pytest.LogCaptureFixture) -> None:
    """Test that an unknown municipality falls back to the coordinates."""
    day = criticality(load_json("criticality_today.json"), municipality="Atlantide")

    assert day.zone == "Bacini di Roma"
    assert "Atlantide" in caplog.text


def test_municipality_not_found_outside() -> None:
    """Test an unknown municipality with coordinates outside every zone."""
    with pytest.raises(DpcLocationError):
        parse_criticality_day(
            load_json("criticality_today.json"),
            bulletin_id=CRIT_ID,
            offset=0,
            location=Location(*PARIS.coordinates, municipality="Atlantide"),
        )


# Far from the default location, in Rome: zones found there are found by name
SOUTH_TYROL = square(46.4, 11.2, 46.6, 11.5)
ABRUZZO = square(42.2, 13.8, 42.4, 14.0)
VICENZA = square(45.5, 11.5, 45.7, 11.7)
LAZIO = square(41.5, 12.0, 42.3, 13.0)


def vigilance_zone(
    name: str, geometry: dict[str, Any], municipalities: list[str], level: int
) -> dict[str, Any]:
    """Return a vigilance feature."""
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "Nome_Zona": name,
            "comuni": municipalities,
            "id_classificazione": level,
        },
    }


@pytest.mark.parametrize(
    "municipality", ["Bolzano", "Bozen", "Bolzano/Bozen", "  bozen "]
)
def test_bilingual_municipality(municipality: str) -> None:
    """Test a municipality of South Tyrol by its Italian or German name.

    The criticality bulletin writes "Bolzano/Bozen", the vigilance one "Bolzano".
    """
    criticality_zones = collection(
        zone("Vicenza", VICENZA, ["Bolzano Vicentino"], "Elevata / ALLERTA ROSSA"),
        zone("Alto Adige", SOUTH_TYROL, ["Merano/Meran", "Bolzano/Bozen"]),
        zone("Bacini di Roma", LAZIO, ["Roma"]),
    )
    vigilance_zones = collection(
        vigilance_zone("Vicenza", VICENZA, ["Bolzano Vicentino"], 5),
        vigilance_zone("Alto Adige", SOUTH_TYROL, ["Merano", "Bolzano"], 3),
        vigilance_zone("Lazio", LAZIO, ["Roma"], 2),
    )

    assert criticality(criticality_zones, municipality=municipality).zone == (
        "Alto Adige"
    )
    assert vigilance(vigilance_zones, municipality=municipality).zone == "Alto Adige"


@pytest.mark.parametrize(
    ("municipality", "listed"),
    [
        ("Rasun-Anterselva", "Rasun Anterselva"),
        ("Salorno sulla strada del vino", "Salorno"),
        ("Völs am Schlern", "Fi allo Sciliar"),
    ],
)
def test_municipality_written_differently(municipality: str, listed: str) -> None:
    """Test municipalities that the vigilance bulletin writes differently."""
    geojson = collection(
        vigilance_zone("Alto Adige", SOUTH_TYROL, [listed], 3),
        vigilance_zone("Lazio", LAZIO, ["Roma"], 2),
    )

    assert vigilance(geojson, municipality=municipality).zone == "Alto Adige"


@pytest.mark.parametrize(
    ("municipality", "south_tyrol_alert", "abruzzo_alert", "expected"),
    [
        # Listed as written in Abruzzo: South Tyrol is not a candidate
        ("Corvara", "ALLERTA ROSSA", "ALLERTA GIALLA", "Abruzzo"),
        # Its other names do not include the Corvara of Abruzzo
        ("Corvara in Badia", "ALLERTA GIALLA", "ALLERTA ROSSA", "Alto Adige"),
    ],
)
def test_municipality_as_written_first(
    municipality: str, south_tyrol_alert: str, abruzzo_alert: str, expected: str
) -> None:
    """Test that a name listed as written wins over the other names."""
    geojson = collection(
        zone(
            "Alto Adige",
            SOUTH_TYROL,
            ["Corvara in Badia/Corvara"],
            f"Ordinaria / {south_tyrol_alert}",
        ),
        zone("Abruzzo", ABRUZZO, ["Corvara"], f"Ordinaria / {abruzzo_alert}"),
    )

    assert criticality(geojson, municipality=municipality).zone == expected


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

    assert day.zone == ""
    assert day.level is AlertLevel.UNKNOWN


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

    assert location_in_zones(geojson, ROME)
    assert not location_in_zones(geojson, PARIS)


@pytest.mark.parametrize(
    ("offset", "date", "precipitation", "image"),
    [
        (0, dt.date(2026, 11, 14), Precipitation.LIGHT, "oggi"),
        (1, dt.date(2026, 11, 15), Precipitation.MODERATE, "domani"),
        (2, dt.date(2026, 11, 16), Precipitation.NONE, None),
    ],
)
def test_vigilance(
    offset: int,
    date: dt.date,
    precipitation: Precipitation,
    image: str | None,
) -> None:
    """Test the vigilance of each day at the location."""
    day = vigilance(load_json(f"vigilance_{VIGILANCE_DAYS[offset]}.json"), offset)

    assert day.date == date
    assert day.offset == offset
    assert day.valid_until == end_of_day(date)
    assert day.zone == "Lazio centrale"
    assert day.precipitation is precipitation
    assert day.image_url == (
        f"{VIGI_FILES}/preview/20261114_{image}.png" if image else None
    )
    assert day.phenomena == ()


def test_vigilance_municipality() -> None:
    """Test the vigilance looked up by municipality."""
    day = vigilance(load_json("vigilance_oggi.json"), municipality="Como")

    assert day.zone == "Lombardia centrale settore occidentale"
    assert day.precipitation is Precipitation.HEAVY


@pytest.mark.parametrize(
    ("class_value", "text", "expected"),
    [
        (3, None, Precipitation.MODERATE),
        (3.0, None, Precipitation.MODERATE),
        (" 5 ", None, Precipitation.VERY_HEAVY),
        # The class wins over the text
        (2, "Elevati", Precipitation.LIGHT),
        # Without a known class, the text is used, ignoring case and spacing
        (None, "Molto  elevati", Precipitation.VERY_HEAVY),
        (9, "deboli", Precipitation.LIGHT),
        (2.5, "Assenti o non rilevanti", Precipitation.NONE),
        # Unrecognised
        (0, None, Precipitation.UNKNOWN),
        (True, None, Precipitation.UNKNOWN),
        ("tre", "Abbondanti", Precipitation.UNKNOWN),
        (None, 3, Precipitation.UNKNOWN),
    ],
)
def test_parse_precipitation(
    class_value: object, text: object, expected: Precipitation
) -> None:
    """Test the parsing of the precipitation of a zone."""
    assert parse_precipitation(class_value, text) is expected


def test_vigilance_unrecognised_precipitation() -> None:
    """Test a zone whose precipitation is not recognised."""
    geojson = collection(
        {
            "geometry": square(41.5, 12.0, 42.3, 13.0),
            "properties": {
                "Nome_Zona": "Lazio",
                "id_classificazione": "tre",
                "Quantitativi_previsti": 3,
            },
        }
    )

    assert vigilance(geojson).precipitation is Precipitation.UNKNOWN


def phenomena(geojson: object, within_km: float = 50) -> list[tuple[object, ...]]:
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
        for item in parse_phenomena(geojson, location=ROME, within_km=within_km)
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
        parse_phenomena({}, location=ROME, within_km=50)


def test_alert_zone_of_a_location() -> None:
    """Test the zone containing a location; its municipality is not used."""
    geojson = load_json("criticality_today.json")

    zone = parse_alert_zone(geojson, Location(LATITUDE, LONGITUDE, "Como"))

    assert (zone.name, zone.municipalities) == (
        "Bacini di Roma",
        ("Fiumicino", "Roma", "Tivoli"),
    )


def test_alert_zone_outside() -> None:
    """Test that a location outside every zone raises a location error."""
    with pytest.raises(DpcLocationError):
        parse_alert_zone(load_json("criticality_today.json"), PARIS)
