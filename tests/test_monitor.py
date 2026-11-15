"""Tests of the high-level API: the monitored location."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import TYPE_CHECKING

import pytest

from aiodpc import (
    CRITICALITY_PAGE_URL,
    AlertLevel,
    Day,
    DpcConnectionError,
    DpcNoDataError,
    Location,
    MonitoredLocation,
    RiskType,
    rome_date,
)
from aiodpc.monitor import LATEST_ID_CHECK_INTERVAL
from aiodpc.urls import criticality_geojson_url

from . import LATITUDE, LONGITUDE, NEAR_COMO, load_fixture, serve_criticality

if TYPE_CHECKING:
    from aiodpc import DpcClient

    from .server import FakeDpc

# The fixtures served as the bulletin published today, so that "today" and
# "tomorrow" are their two days whatever the date of the test run
TODAY_ID = f"{rome_date():%Y%m%d}_1430"
TODAY_URL = criticality_geojson_url(TODAY_ID, 0)
TOMORROW_URL = criticality_geojson_url(TODAY_ID, 1)


@pytest.fixture
def home(client: DpcClient, dpc: FakeDpc) -> MonitoredLocation:
    """Return the monitored location in Rome, with today's bulletin served."""
    serve_criticality(dpc, TODAY_ID)
    return client.location(LATITUDE, LONGITUDE)


def test_location(client: DpcClient) -> None:
    """Test the location of a monitored location."""
    home = client.location(LATITUDE, LONGITUDE, municipality="Roma")

    assert home.location == Location(LATITUDE, LONGITUDE, "Roma")
    assert repr(home) == f"MonitoredLocation({home.location!r})"


def test_invalid_location(client: DpcClient) -> None:
    """Test that invalid coordinates are rejected at once."""
    with pytest.raises(ValueError, match="Invalid latitude"):
        client.location(91, LONGITUDE)


async def test_risk_today(home: MonitoredLocation) -> None:
    """Test the risk of today: yellow for thunderstorms and hydrogeological."""
    assert await home.has_risk()

    risk = await home.risk()

    assert risk.level is AlertLevel.YELLOW
    assert risk.types == (RiskType.THUNDERSTORMS, RiskType.HYDROGEOLOGICAL)
    assert risk.description == "Ordinaria per rischio temporali"
    assert risk.day.zone == "Bacini di Roma"
    assert risk.valid_until.date() == rome_date() + dt.timedelta(days=1)
    assert str(risk) == "yellow (thunderstorms, hydrogeological)"


async def test_risk_tomorrow(home: MonitoredLocation) -> None:
    """Test the risk of tomorrow, by Day and by date."""
    tomorrow = rome_date() + dt.timedelta(days=1)

    risk = await home.risk(Day.TOMORROW)

    assert str(risk) == "orange (hydrogeological)"
    assert await home.risk(tomorrow) == risk
    assert await home.has_risk(on=Day.TOMORROW)


async def test_no_risk(client: DpcClient, dpc: FakeDpc) -> None:
    """Test a green day: no risk and no risk type."""
    green = "Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA"
    serve_criticality(dpc, TODAY_ID)
    body = load_fixture("criticality_today.json")
    for yellow in ("Ordinaria per rischio temporali", "Ordinaria"):
        body = body.replace(f"{yellow} / ALLERTA GIALLA", green)
    dpc.add(TODAY_URL, body=body)
    home = client.location(LATITUDE, LONGITUDE)

    assert not await home.has_risk()
    risk = await home.risk()
    assert risk.level is AlertLevel.GREEN
    assert risk.types == ()
    assert str(risk) == "green"


async def test_municipality(client: DpcClient, dpc: FakeDpc) -> None:
    """Test a location whose municipality is in a red zone."""
    serve_criticality(dpc, TODAY_ID)
    home = client.location(*NEAR_COMO.coordinates, municipality="Como")

    risk = await home.risk()

    assert risk.level is AlertLevel.RED
    assert risk.types == tuple(RiskType)


async def test_day_not_covered(home: MonitoredLocation) -> None:
    """Test a day that no published bulletin covers."""
    after_tomorrow = rome_date() + dt.timedelta(days=2)

    with pytest.raises(DpcNoDataError, match=f"does not cover {after_tomorrow}"):
        await home.has_risk(after_tomorrow)


async def test_bulletin_is_kept(home: MonitoredLocation, dpc: FakeDpc) -> None:
    """Test that the questions share one download of the bulletin."""
    await home.has_risk()
    await home.risk()
    await home.risk(Day.TOMORROW)

    assert dpc.requests.count(CRITICALITY_PAGE_URL) == 1
    assert dpc.requests.count(TODAY_URL) == 1


async def test_same_bulletin_is_not_downloaded_again(
    home: MonitoredLocation, dpc: FakeDpc
) -> None:
    """Test that the latest ID is checked again, but the same bulletin kept."""
    first = await home.criticality()
    home._checked_at -= LATEST_ID_CHECK_INTERVAL

    assert await home.criticality() is first
    assert dpc.requests.count(CRITICALITY_PAGE_URL) == 2
    assert dpc.requests.count(TODAY_URL) == 1


async def test_new_bulletin_is_downloaded(
    home: MonitoredLocation, dpc: FakeDpc
) -> None:
    """Test that a newly published bulletin replaces the kept one."""
    await home.risk()
    reissue = f"{rome_date():%Y%m%d}_1800"
    serve_criticality(dpc, reissue)
    dpc.add(
        criticality_geojson_url(reissue, 0),
        body=load_fixture("criticality_tomorrow.json"),
    )
    home._checked_at -= LATEST_ID_CHECK_INTERVAL

    risk = await home.risk()

    assert (await home.criticality()).id == reissue
    assert risk.level is AlertLevel.ORANGE


async def test_concurrent_questions(home: MonitoredLocation, dpc: FakeDpc) -> None:
    """Test that concurrent questions wait for a single download."""
    results = await asyncio.gather(home.has_risk(), home.risk(), home.criticality())

    assert results[0] is True
    assert dpc.requests.count(TODAY_URL) == 1


async def test_errors_propagate(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a DPC failure is raised, and retried at the next call."""
    serve_criticality(dpc, TODAY_ID)
    dpc.add(TODAY_URL, status=503)
    home = client.location(LATITUDE, LONGITUDE)

    with pytest.raises(DpcConnectionError, match="HTTP status 503"):
        await home.risk()

    serve_criticality(dpc, TODAY_ID)
    assert await home.has_risk()
