"""Tests of the bulletins downloaded once and read at several locations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from aiodpc import (
    CriticalityMap,
    DpcClient,
    DpcLocationError,
    DpcParseError,
    VigilanceMap,
)
from aiodpc.parsers import GeoJsonFeatures, parse_criticality_day
from aiodpc.urls import criticality_geojson_url

from . import (
    CRIT_ID,
    NEAR_COMO,
    PARIS,
    PUBLICATION_DAY,
    ROME,
    VIGI_ID,
    load_json,
    rome,
    serve_criticality,
    serve_vigilance,
)

if TYPE_CHECKING:
    from .server import FakeDpc


async def test_criticality_map_is_downloaded_once(
    client: DpcClient, dpc: FakeDpc
) -> None:
    """Test that reading several locations makes no request."""
    serve_criticality(dpc)

    criticality = await client.get_criticality_map(now=PUBLICATION_DAY)
    downloads = list(dpc.requests)
    rome_bulletin = criticality.at(ROME)
    como_bulletin = criticality.at(NEAR_COMO)

    assert dpc.requests == downloads
    assert len(downloads) == 3  # the page and the 2 days
    assert rome_bulletin == await client.get_criticality(ROME, now=PUBLICATION_DAY)
    assert [day.zone for day in rome_bulletin] == ["Bacini di Roma"] * 2
    assert [day.zone for day in como_bulletin] == ["Lario e Prealpi occidentali"] * 2
    assert criticality.id == CRIT_ID
    assert criticality.published == rome(2026, 11, 14, 14, 30)
    assert repr(criticality) == f"CriticalityMap(id='{CRIT_ID}', days=2)"


async def test_vigilance_map_distance_per_location(
    client: DpcClient, dpc: FakeDpc
) -> None:
    """Test that each reading of the vigilance has its own distance."""
    serve_vigilance(dpc)

    vigilance = await client.get_vigilance_map(now=PUBLICATION_DAY)
    downloads = list(dpc.requests)
    near = vigilance.at(ROME)
    far = vigilance.at(ROME, phenomena_within_km=300)

    assert dpc.requests == downloads
    assert len(downloads) == 7  # the page, and the zones and phenomena of 3 days
    assert near == await client.get_vigilance(ROME, now=PUBLICATION_DAY)
    assert [item.code for item in near.days[0].phenomena] == [5]
    assert [item.code for item in far.days[0].phenomena] == [5, 41]
    assert vigilance.id == VIGI_ID
    assert repr(vigilance) == f"VigilanceMap(id='{VIGI_ID}', days=3)"


@pytest.mark.parametrize("distance", [-1, float("nan"), float("inf")])
async def test_vigilance_map_invalid_distance(
    client: DpcClient, dpc: FakeDpc, distance: float
) -> None:
    """Test that an invalid distance raises ValueError."""
    serve_vigilance(dpc)
    vigilance = await client.get_vigilance_map(now=PUBLICATION_DAY)

    with pytest.raises(ValueError, match="phenomena distance"):
        vigilance.at(ROME, phenomena_within_km=distance)


async def test_location_outside_does_not_affect_the_others(
    client: DpcClient, dpc: FakeDpc
) -> None:
    """Test that a location outside every zone fails alone."""
    serve_criticality(dpc)
    serve_vigilance(dpc)
    criticality = await client.get_criticality_map(now=PUBLICATION_DAY)
    vigilance = await client.get_vigilance_map(now=PUBLICATION_DAY)

    with pytest.raises(DpcLocationError):
        criticality.at(PARIS)
    with pytest.raises(DpcLocationError):
        vigilance.at(PARIS)
    # By date, not .today: the fixtures are of a fixed day
    assert criticality.at(ROME).on(PUBLICATION_DAY.date()) is not None
    assert vigilance.at(ROME).on(PUBLICATION_DAY.date()) is not None


async def test_map_skips_expired_days(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that the days already over are not downloaded."""
    serve_criticality(dpc)

    criticality = await client.get_criticality_map(now=rome(2026, 11, 15, 8))

    assert criticality_geojson_url(CRIT_ID, 0) not in dpc.requests
    assert [day.offset for day in criticality.at(ROME)] == [1]


async def test_map_with_unexpected_data(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a file with an unexpected shape fails when it is downloaded."""
    serve_criticality(dpc)
    dpc.add(criticality_geojson_url(CRIT_ID, 0), body='{"error": "not found"}')

    with pytest.raises(DpcParseError):
        await client.get_criticality_map(now=PUBLICATION_DAY)


def test_maps_from_decoded_files() -> None:
    """Test maps built from files decoded by other means."""
    criticality = CriticalityMap(CRIT_ID, [(0, load_json("criticality_today.json"))])
    vigilance = VigilanceMap(
        VIGI_ID,
        [(0, load_json("vigilance_oggi.json"), load_json("phenomena_oggi.json"))],
    )

    assert (
        criticality.at(ROME).on(PUBLICATION_DAY.date()) == criticality.at(ROME).days[0]
    )
    assert [day.offset for day in vigilance.at(ROME)] == [0]


def test_parse_functions_accept_checked_features() -> None:
    """Test that a file checked once parses like the decoded GeoJSON."""
    geojson = load_json("criticality_today.json")
    features = GeoJsonFeatures.of(geojson)

    assert GeoJsonFeatures.of(features) is features
    assert parse_criticality_day(
        features, bulletin_id=CRIT_ID, offset=0, location=ROME
    ) == parse_criticality_day(geojson, bulletin_id=CRIT_ID, offset=0, location=ROME)
