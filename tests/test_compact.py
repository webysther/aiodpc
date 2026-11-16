"""Tests of the compact bulletins: the whole of Italy as numeric codes."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from aiodpc import (
    AlertLevel,
    BulletinKind,
    Criticality,
    CriticalityMap,
    PhenomenonType,
    Precipitation,
    RiskType,
    VigilanceMap,
)
from aiodpc.compact import (
    SCHEMA_VERSION,
    CriticalityRecord,
    PhenomenonRecord,
    VigilanceRecord,
    ZoneTable,
)
from aiodpc.parsers import (
    RISK_PROPERTIES,
    SUMMARY_PROPERTY,
    compact_criticality,
    compact_vigilance,
    parse_assessment,
    parse_precipitation,
)

from . import load_json

CRIT_ID = "20261113_1434"
VIGI_ID = "20261113"


def real(name: str) -> dict[str, Any]:
    """Return a real DPC file of the fixtures."""
    data = load_json(f"real/{name}")
    assert isinstance(data, dict)
    return data


def criticality() -> dict[str, Any]:
    """Return the excerpt of the real criticality file (three zones)."""
    return real("criticality_20261113_1434_today.json")


def vigilance() -> dict[str, Any]:
    """Return the excerpt of the real vigilance file (two zones)."""
    return real("vigilance_20261113_oggi.json")


def phenomena() -> dict[str, Any]:
    """Return the real phenomena file (complete)."""
    return real("phenomena_20261113_oggi.json")


def one_line(document: str) -> dict[str, Any]:
    """Return a JSON document after checking that it is a line of JSON Lines."""
    assert "\n" not in document
    data = json.loads(document)
    assert isinstance(data, dict)
    return data


def test_criticality_records_are_the_dpc_values() -> None:
    """Each record holds the codes of what DPC writes for its zone and day."""
    geojson = criticality()
    compact = compact_criticality(CRIT_ID, [(0, geojson), (1, geojson)])
    features = geojson["features"]
    assert len(compact.records) == 2 * len(features)
    names = sorted(feature["properties"]["Nome zona"] for feature in features)
    assert [zone.name for zone in compact.zones.zones] == names
    for record, feature in zip(compact.records, features * 2, strict=True):
        properties = feature["properties"]
        summary = parse_assessment(properties[SUMMARY_PROPERTY])
        mapped = RiskType.named_in(summary.description)
        assert compact.zones.zones[record.zone - 1].name == properties["Nome zona"]
        assert record.level == summary.level.code
        assert record.criticality == Criticality.of(summary.description).code
        assert record.mapped_risk == (mapped.code if mapped else 0)
        levels = [
            parse_assessment(properties[RISK_PROPERTIES[risk_type]]).level.code
            for risk_type in RiskType
        ]
        assert [
            record.hydraulic,
            record.thunderstorms,
            record.hydrogeological,
        ] == levels
    assert {record.day for record in compact.records} == {0, 1}


def test_criticality_record_of_rome() -> None:
    """The yellow hydrogeological alert of Rome on 2026-11-13, as codes."""
    compact = compact_criticality(CRIT_ID, [(0, criticality())])
    rome = compact.zones.code_of("Bacini di Roma")
    (record,) = (record for record in compact.records if record.zone == rome)
    assert record == CriticalityRecord(
        day=0,
        zone=rome,
        level=AlertLevel.YELLOW.code,
        criticality=Criticality.ORDINARY.code,
        mapped_risk=RiskType.HYDROGEOLOGICAL.code,
        hydraulic=AlertLevel.GREEN.code,
        thunderstorms=AlertLevel.GREEN.code,
        hydrogeological=AlertLevel.YELLOW.code,
    )


def test_criticality_json() -> None:
    """The JSON document holds the same rows as the records, on one line."""
    compact = compact_criticality(CRIT_ID, [(0, criticality())])
    document = one_line(compact.to_json())
    assert document["schema"] == SCHEMA_VERSION
    assert document["kind"] == BulletinKind.CRITICALITY.code
    assert document["bulletin"] == CRIT_ID
    assert document["zone_set"] == compact.zones.fingerprint
    assert document["columns"] == list(CriticalityRecord._fields)
    assert document["rows"] == [list(record) for record in compact.records]


def test_vigilance_records_and_phenomena() -> None:
    """The precipitation of each zone and every phenomenon, as codes."""
    zones, events = vigilance(), phenomena()
    compact = compact_vigilance(VIGI_ID, [(0, zones, events)])
    for record in compact.records:
        (feature,) = (
            feature
            for feature in zones["features"]
            if feature["properties"]["Nome_Zona"]
            == compact.zones.zones[record.zone - 1].name
        )
        properties = feature["properties"]
        expected = parse_precipitation(
            properties["id_classificazione"], properties["Quantitativi_previsti"]
        )
        assert record == VigilanceRecord(0, record.zone, expected.code)
        assert Precipitation.from_code(record.precipitation) is expected
    assert len(compact.phenomena) == len(events["features"])
    first = events["features"][0]["properties"]
    assert compact.phenomena[0] == PhenomenonRecord(
        day=0,
        code=first["id_fenomeno"],
        latitude=round(first["lat"], 5),
        longitude=round(first["lon"], 5),
    )
    for event in compact.phenomena:
        assert PhenomenonType.from_code(event.code) is not None


def test_vigilance_json() -> None:
    """The JSON document of the vigilance bulletin, with its phenomena."""
    compact = compact_vigilance(VIGI_ID, [(0, vigilance(), phenomena())])
    document = one_line(compact.to_json())
    assert document["kind"] == BulletinKind.VIGILANCE.code
    assert document["columns"] == list(VigilanceRecord._fields)
    assert document["rows"] == [list(record) for record in compact.records]
    assert document["phenomena"]["columns"] == list(PhenomenonRecord._fields)
    assert document["phenomena"]["rows"] == [
        list(record) for record in compact.phenomena
    ]


def test_invalid_phenomena_are_left_out() -> None:
    """A phenomenon without a code or a position is not a record."""
    events = {
        "features": [
            {"properties": {"id_fenomeno": 5}, "geometry": None},
            {"properties": {"id_fenomeno": True, "lat": 41.0, "lon": 12.0}},
            {"properties": {"lat": 41.0, "lon": 12.0}},
            {"properties": {"id_fenomeno": 10, "lat": 41.123456, "lon": 12.0}},
        ]
    }
    compact = compact_vigilance(VIGI_ID, [(1, vigilance(), events)])
    assert compact.phenomena == (PhenomenonRecord(1, 10, 41.12346, 12.0),)


def test_maps_are_compacted() -> None:
    """The maps give their bulletin as codes, without any request."""
    criticality_map = CriticalityMap(CRIT_ID, [(0, criticality())])
    assert criticality_map.compact() == compact_criticality(
        CRIT_ID, [(0, criticality())]
    )
    vigilance_map = VigilanceMap(VIGI_ID, [(0, vigilance(), phenomena())])
    assert vigilance_map.compact() == compact_vigilance(
        VIGI_ID, [(0, vigilance(), phenomena())]
    )


def test_zone_fingerprint_ignores_order() -> None:
    """The fingerprint is the same whatever the order of zones and municipalities."""
    geojson = criticality()
    shuffled = copy.deepcopy(geojson)
    shuffled["features"].reverse()
    for feature in shuffled["features"]:
        feature["properties"]["Comuni"].reverse()
    table = compact_criticality(CRIT_ID, [(0, geojson)]).zones
    assert compact_criticality(CRIT_ID, [(0, shuffled)]).zones == table
    assert (
        compact_criticality(CRIT_ID, [(0, shuffled)]).zones.fingerprint
        == table.fingerprint
    )


@pytest.mark.parametrize("change", ["name", "municipalities", "geometry"])
def test_zone_fingerprint_changes_with_the_zones(change: str) -> None:
    """A renamed zone, another municipality or another shape change the zones."""
    geojson = criticality()
    changed = copy.deepcopy(geojson)
    properties = changed["features"][0]["properties"]
    if change == "name":
        properties["Nome zona"] = properties["Nome zona"].upper()
    elif change == "municipalities":
        properties["Comuni"].append("Nuovo Comune")
    else:
        changed["features"][0]["geometry"]["coordinates"][0][0][0][0] += 0.001
    before = compact_criticality(CRIT_ID, [(0, geojson)]).zones.fingerprint
    after = compact_criticality(CRIT_ID, [(0, changed)]).zones.fingerprint
    assert before != after


def test_zone_table() -> None:
    """A zone table codes its zones by name and exports them."""
    square = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    table = ZoneTable.of(
        [
            ("Zona B", ["Comune 2", "Comune 1", "Comune 2"], square),
            ("Zona A", ["Comune 3"], None),
            ("Zona B", ["Altro"], None),
        ]
    )
    assert [(zone.code, zone.name) for zone in table.zones] == [
        (1, "Zona A"),
        (2, "Zona B"),
    ]
    assert table.zones[1].municipalities == ("Comune 1", "Comune 2")
    assert table.code_of("Zona B") == 2
    with pytest.raises(KeyError):
        table.code_of("Zona C")
    document = one_line(table.to_json())
    assert document["columns"] == ["code", "name", "municipalities"]
    assert document["zone_set"] == table.fingerprint
    assert document["rows"] == [
        [1, "Zona A", ["Comune 3"]],
        [2, "Zona B", ["Comune 1", "Comune 2"]],
    ]
    geojson = table.to_geojson()
    assert geojson["zone_set"] == table.fingerprint
    assert [feature["properties"] for feature in geojson["features"]] == [
        {"code": 1, "name": "Zona A"},
        {"code": 2, "name": "Zona B"},
    ]
    assert geojson["features"][1]["geometry"] == square


def test_json_stays_on_one_line() -> None:
    """A line break in a name is escaped: each document is one JSON line."""
    table = ZoneTable.of([("Zona\nA", ["Comune\r\n1"], None)])
    document = one_line(table.to_json())
    assert document["rows"] == [[1, "Zona\nA", ["Comune\r\n1"]]]
