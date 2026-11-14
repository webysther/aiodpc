"""Tests of the optional strict DTOs of the raw DPC files."""

from __future__ import annotations

import importlib
import json
import sys
from typing import TYPE_CHECKING

import pytest

from aiodpc import DpcParseError
from aiodpc.schema import (
    MultiPolygon,
    Point,
    Polygon,
    decode_criticality_file,
    decode_phenomena_file,
    decode_vigilance_file,
)
from aiodpc.urls import criticality_geojson_url

from . import CRIT_ID, VIGI_ID, load_fixture, serve_criticality, serve_vigilance

if TYPE_CHECKING:
    from aiodpc import DpcClient

    from .server import FakeDpc


def test_criticality_file() -> None:
    """Test the DTO of a real criticality file."""
    file = decode_criticality_file(
        load_fixture("real/criticality_20261113_1434_today.json")
    )

    zone = file.features[0]
    assert isinstance(zone.geometry, MultiPolygon)
    assert zone.properties.zone_name == "Bacini di Roma"
    assert "Roma" in zone.properties.municipalities
    assert zone.properties.summary == (
        "Ordinaria per rischio idrogeologico / ALLERTA GIALLA"
    )
    assert zone.properties.hydrogeological == "Ordinaria / ALLERTA GIALLA"
    assert [item.properties.zone_name for item in file.features] == [
        "Bacini di Roma",
        "Trasimeno - Nestore",
        "Chiani - Paglia",
    ]


def test_vigilance_file() -> None:
    """Test the DTO of a real vigilance file."""
    file = decode_vigilance_file(load_fixture("real/vigilance_20261113_oggi.json"))

    zone = file.features[0].properties
    assert (zone.zone_name, zone.precipitation_class, zone.precipitation) == (
        "Comune di Roma",
        2,
        "Deboli",
    )


def test_phenomena_file() -> None:
    """Test the DTO of a real phenomena file."""
    file = decode_phenomena_file(load_fixture("real/phenomena_20261113_oggi.json"))

    phenomenon = file.features[0]
    assert len(file.features) == 70
    assert isinstance(phenomenon.geometry, Point)
    assert phenomenon.properties.code == 5
    assert phenomenon.properties.bulletin_id == 202611131
    assert phenomenon.properties.bulletin_date == "2026-11-13Z"
    assert phenomenon.properties.latitude == pytest.approx(42.3363, abs=1e-4)


def test_polygon_and_missing_geometry() -> None:
    """Test a Polygon zone and a zone without geometry."""
    data = json.loads(load_fixture("criticality_today.json"))
    data["features"][1]["geometry"] = None

    file = decode_criticality_file(json.dumps(data).encode())

    assert isinstance(file.features[0].geometry, Polygon)
    assert file.features[1].geometry is None


def test_new_fields_are_ignored() -> None:
    """Test that fields added by DPC do not break the DTOs."""
    data = json.loads(load_fixture("vigilance_oggi.json"))
    data["features"][0]["properties"]["Nuovo campo"] = 1

    assert decode_vigilance_file(json.dumps(data)).features[0].properties


def test_renamed_field() -> None:
    """Test that a renamed DPC field is reported with its location."""
    data = json.loads(load_fixture("criticality_today.json"))
    properties = data["features"][1]["properties"]
    properties["NomeZona"] = properties.pop("Nome zona")

    with pytest.raises(
        DpcParseError,
        match=r"missing required field `Nome zona` - at `\$.features\[1\].properties`",
    ):
        decode_criticality_file(json.dumps(data))


def test_unexpected_type() -> None:
    """Test that a value of another type is reported."""
    data = json.loads(load_fixture("vigilance_oggi.json"))
    data["features"][0]["properties"]["id_classificazione"] = "2"

    with pytest.raises(DpcParseError, match="Expected `int`, got `str`"):
        decode_vigilance_file(json.dumps(data))


def test_invalid_json() -> None:
    """Test that invalid JSON raises a parse error."""
    with pytest.raises(DpcParseError, match="Invalid JSON"):
        decode_phenomena_file(b"{not json")


def test_msgspec_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the hint given when the optional dependency is missing."""
    monkeypatch.setitem(sys.modules, "msgspec", None)
    monkeypatch.delitem(sys.modules, "aiodpc.schema")

    with pytest.raises(ImportError, match=r"pip install \"aiodpc\[schema\]\""):
        importlib.import_module("aiodpc.schema")


async def test_client_files(client: DpcClient, dpc: FakeDpc) -> None:
    """Test the DTOs of the latest bulletins, fetched by the client."""
    serve_criticality(dpc)
    serve_vigilance(dpc)

    criticality = await client.get_criticality_file()
    tomorrow = await client.get_criticality_file(CRIT_ID, offset=1)
    vigilance = await client.get_vigilance_file(offset=2)
    phenomena = await client.get_phenomena_file(VIGI_ID)

    assert criticality.features[0].properties.zone_name == "Bacini di Roma"
    assert tomorrow.features[0].properties.hydrogeological == (
        "Moderata / ALLERTA ARANCIONE"
    )
    assert vigilance.features[0].properties.precipitation_class == 1
    assert [item.properties.code for item in phenomena.features] == [5, 41]


async def test_client_file_changed(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a file that no longer matches the DTO raises a parse error."""
    serve_criticality(dpc)
    dpc.add(criticality_geojson_url(CRIT_ID, 0), body='{"features": [{}]}')

    with pytest.raises(DpcParseError, match="missing required field `properties`"):
        await client.get_criticality_file()


@pytest.mark.parametrize(
    ("bulletin_id", "offset", "error"),
    [
        ("latest", 0, "Invalid criticality bulletin ID"),
        (CRIT_ID, 2, "between 0 and 1"),
    ],
)
async def test_client_file_invalid_arguments(
    client: DpcClient, dpc: FakeDpc, bulletin_id: str, offset: int, error: str
) -> None:
    """Test that invalid arguments raise ValueError before any request."""
    with pytest.raises(ValueError, match=error):
        await client.get_criticality_file(bulletin_id, offset)
    with pytest.raises(ValueError, match="Invalid vigilance bulletin ID"):
        await client.get_vigilance_file("latest")
    assert dpc.requests == []
