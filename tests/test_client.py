"""Tests of the client against a local server standing in for DPC."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest

from aiodpc import (
    CRITICALITY_PAGE_URL,
    VIGILANCE_PAGE_URL,
    AlertLevel,
    AlertZone,
    BulletinKind,
    DpcClient,
    DpcConnectionError,
    DpcLocationError,
    DpcParseError,
    Location,
    PhenomenonCategory,
    Precipitation,
)
from aiodpc.urls import (
    criticality_geojson_url,
    criticality_preview_url,
    phenomena_geojson_url,
    vigilance_geojson_url,
)

from . import (
    CRIT_ID,
    FIXTURES,
    NEAR_COMO,
    PARIS,
    PUBLICATION_DAY,
    ROME,
    VIGI_ID,
    load_fixture,
    rome,
    serve_criticality,
    serve_vigilance,
)

if TYPE_CHECKING:
    from aiodpc import CriticalityBulletin, TextFetcher

    from .server import FakeDpc

TODAY_URL = criticality_geojson_url(CRIT_ID, 0)
TOMORROW_URL = criticality_geojson_url(CRIT_ID, 1)


def valid_until(bulletin: CriticalityBulletin) -> dict[dt.date, dt.datetime]:
    """Return the end of validity of each day of a bulletin."""
    return {day.date: day.valid_until for day in bulletin}


# The criticality bulletin covers "fino alle 24.00 del giorno di emissione (oggi) e
# nelle 24 ore del giorno seguente (domani)" (pcm-dpc/DPC-Bollettini-Criticita-
# Idrogeologica-Idraulica), so each day expires at the midnight that ends it.


async def test_criticality_on_publication_day(client: DpcClient, dpc: FakeDpc) -> None:
    """Test the bulletin issued on 2026-11-14, on that day."""
    serve_criticality(dpc)

    bulletin = await client.get_criticality(ROME, now=PUBLICATION_DAY)

    assert bulletin.id == CRIT_ID
    assert bulletin.published == rome(2026, 11, 14, 14, 30)
    assert [day.offset for day in bulletin.days] == [0, 1]
    assert valid_until(bulletin) == {
        dt.date(2026, 11, 14): rome(2026, 11, 15),
        dt.date(2026, 11, 15): rome(2026, 11, 16),
    }
    today = bulletin.on(PUBLICATION_DAY)
    assert today is bulletin.days[0]
    assert today.zone == "Bacini di Roma"
    assert today.thunderstorms.level is AlertLevel.YELLOW
    tomorrow = bulletin.on(dt.date(2026, 11, 15))
    assert tomorrow is bulletin.days[1]
    assert tomorrow.level is AlertLevel.ORANGE


async def test_criticality_after_midnight(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that after midnight the second day answers for today, unchanged."""
    serve_criticality(dpc)
    bulletin = await client.get_criticality(ROME, now=PUBLICATION_DAY)

    after_midnight = rome(2026, 11, 15, 0, 10)
    today = bulletin.on(after_midnight)

    assert today is bulletin.days[1]
    assert today.valid_until == rome(2026, 11, 16)
    assert bulletin.on(dt.date(2026, 11, 16)) is None


async def test_criticality_started_before_the_new_bulletin(
    client: DpcClient, dpc: FakeDpc
) -> None:
    """Test a start in the morning, when the latest bulletin is from yesterday."""
    serve_criticality(dpc)
    morning = rome(2026, 11, 15, 8)

    bulletin = await client.get_criticality(ROME, now=morning)

    assert TODAY_URL not in dpc.requests
    assert valid_until(bulletin) == {dt.date(2026, 11, 15): rome(2026, 11, 16)}
    assert bulletin.on(morning) is bulletin.days[0]
    assert bulletin.days[0].offset == 1


async def test_criticality_next_bulletin(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that the next day's bulletin covers the next two days."""
    serve_criticality(dpc, crit_id="20261115_1500")

    bulletin = await client.get_criticality(ROME, now=rome(2026, 11, 15, 15, 30))

    assert bulletin.id == "20261115_1500"
    assert valid_until(bulletin) == {
        dt.date(2026, 11, 15): rome(2026, 11, 16),
        dt.date(2026, 11, 16): rome(2026, 11, 17),
    }


async def test_criticality_old_bulletin(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that an expired bulletin downloads nothing unless asked."""
    serve_criticality(dpc)
    later = rome(2026, 11, 17, 9)

    bulletin = await client.get_criticality(ROME, bulletin_id=CRIT_ID, now=later)

    assert bulletin.days == ()
    assert dpc.requests == []

    bulletin = await client.get_criticality(
        ROME, bulletin_id=CRIT_ID, skip_expired=False, now=later
    )

    assert [day.date for day in bulletin.days] == [
        dt.date(2026, 11, 14),
        dt.date(2026, 11, 15),
    ]


async def test_criticality_current_time(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that the current time is used by default, naive times as Italian."""
    bulletin = await client.get_criticality(ROME, bulletin_id="20200101_1430")
    assert bulletin.days == ()
    assert dpc.requests == []

    serve_criticality(dpc)
    bulletin = await client.get_criticality(
        ROME,
        now=dt.datetime(2026, 11, 15, 23, 59),  # noqa: DTZ001
    )
    assert [day.date for day in bulletin.days] == [dt.date(2026, 11, 15)]


async def test_criticality_municipality(client: DpcClient, dpc: FakeDpc) -> None:
    """Test the criticality looked up by municipality."""
    serve_criticality(dpc)

    bulletin = await client.get_criticality(NEAR_COMO, now=PUBLICATION_DAY)

    assert {day.zone for day in bulletin} == {"Lario e Prealpi occidentali"}
    assert {day.level for day in bulletin} == {AlertLevel.RED}


async def test_vigilance_on_publication_day(client: DpcClient, dpc: FakeDpc) -> None:
    """Test the vigilance bulletin issued on 2026-11-14, on that day."""
    serve_vigilance(dpc)

    bulletin = await client.get_vigilance(ROME, now=PUBLICATION_DAY)

    assert bulletin.id == VIGI_ID
    assert bulletin.date == dt.date(2026, 11, 14)
    assert [(day.date, day.precipitation, day.valid_until) for day in bulletin] == [
        (dt.date(2026, 11, 14), Precipitation.LIGHT, rome(2026, 11, 15)),
        (dt.date(2026, 11, 15), Precipitation.MODERATE, rome(2026, 11, 16)),
        (dt.date(2026, 11, 16), Precipitation.NONE, rome(2026, 11, 17)),
    ]
    assert bulletin.days[2].image_url is None
    today = bulletin.on(PUBLICATION_DAY)
    assert today is not None
    assert [item.code for item in today.phenomena] == [5]
    assert today.phenomena[0].category is PhenomenonCategory.PRECIPITATION
    tomorrow = bulletin.on(dt.date(2026, 11, 15))
    assert tomorrow is not None
    assert [(item.code, item.direction) for item in tomorrow.phenomena] == [(40, "SW")]
    assert bulletin.days[2].phenomena == ()


async def test_vigilance_distance_and_municipality(
    client: DpcClient, dpc: FakeDpc
) -> None:
    """Test the phenomena distance and the municipality of the vigilance."""
    serve_vigilance(dpc)

    bulletin = await client.get_vigilance(
        NEAR_COMO, phenomena_within_km=800, now=PUBLICATION_DAY
    )

    assert [item.code for item in bulletin.days[0].phenomena] == [5, 41]
    assert {day.precipitation for day in bulletin} == {Precipitation.HEAVY}


async def test_vigilance_after_midnight(client: DpcClient, dpc: FakeDpc) -> None:
    """Test a start after midnight with the vigilance bulletin of yesterday."""
    serve_vigilance(dpc)

    bulletin = await client.get_vigilance(ROME, now=rome(2026, 11, 15, 0, 30))

    assert [day.offset for day in bulletin.days] == [1, 2]
    assert vigilance_geojson_url(VIGI_ID, 0) not in dpc.requests
    assert phenomena_geojson_url(VIGI_ID, 0) not in dpc.requests


@pytest.mark.parametrize("kind", list(BulletinKind))
async def test_latest_bulletin_id(
    client: DpcClient, dpc: FakeDpc, kind: BulletinKind
) -> None:
    """Test the discovery of the latest bulletin IDs from the map pages."""
    serve_criticality(dpc)
    serve_vigilance(dpc)

    expected = {BulletinKind.CRITICALITY: CRIT_ID, BulletinKind.VIGILANCE: VIGI_ID}

    assert await client.latest_bulletin_id(kind) == expected[kind]
    # The plain DPC code works too
    code: Any = kind.value
    assert await client.latest_bulletin_id(code) == expected[kind]


class StaticIdSource:
    """ID source returning a fixed ID without any request."""

    def __init__(self, bulletin_id: str) -> None:
        """Initialize the source."""
        self.bulletin_id = bulletin_id

    async def latest_id(self, kind: BulletinKind, fetch_text: TextFetcher) -> str:
        """Return the fixed ID."""
        del kind, fetch_text
        return self.bulletin_id


async def test_custom_id_source(session: aiohttp.ClientSession, dpc: FakeDpc) -> None:
    """Test that another ID source replaces the map pages."""
    serve_criticality(dpc)
    client = DpcClient(session, id_source=StaticIdSource(CRIT_ID))

    bulletin = await client.get_criticality(ROME, now=PUBLICATION_DAY)

    assert bulletin.id == CRIT_ID
    assert CRITICALITY_PAGE_URL not in dpc.requests


@pytest.mark.parametrize("kind", list(BulletinKind))
async def test_invalid_id_from_source(
    session: aiohttp.ClientSession, kind: BulletinKind
) -> None:
    """Test that an invalid ID from an ID source is a parse error."""
    client = DpcClient(session, id_source=StaticIdSource("latest"))

    with pytest.raises(DpcParseError, match="Invalid"):
        await client.latest_bulletin_id(kind)


async def test_page_without_id(client: DpcClient, dpc: FakeDpc) -> None:
    """Test a map page that links no bulletin."""
    dpc.add(CRITICALITY_PAGE_URL, body="<html>Manutenzione</html>")

    with pytest.raises(DpcParseError, match="No criticality bulletin ID"):
        await client.get_criticality(ROME)


async def test_dns_error(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a host that cannot be resolved raises a connection error."""
    serve_criticality(dpc)
    dpc.unresolvable.add("mappe.protezionecivile.gov.it")

    with pytest.raises(DpcConnectionError, match="Error fetching") as err:
        await client.latest_bulletin_id(BulletinKind.CRITICALITY)

    assert isinstance(err.value.__cause__, aiohttp.ClientConnectorError)


async def test_server_disconnect(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a dropped connection raises a connection error."""
    dpc.add(CRITICALITY_PAGE_URL, disconnect=True)

    with pytest.raises(DpcConnectionError, match="Error fetching") as err:
        await client.latest_bulletin_id(BulletinKind.CRITICALITY)

    assert isinstance(err.value.__cause__, aiohttp.ClientError)


@pytest.mark.parametrize("status", [404, 500, 503])
async def test_http_error(client: DpcClient, dpc: FakeDpc, status: int) -> None:
    """Test that HTTP error statuses raise a connection error."""
    serve_criticality(dpc)
    dpc.add(TOMORROW_URL, status=status)

    with pytest.raises(DpcConnectionError, match=f"HTTP status {status}") as err:
        await client.get_criticality(ROME, now=PUBLICATION_DAY)

    assert isinstance(err.value.__cause__, aiohttp.ClientResponseError)


async def test_timeout(session: aiohttp.ClientSession, dpc: FakeDpc) -> None:
    """Test that a stalled response times out."""
    dpc.add(CRITICALITY_PAGE_URL, before=dpc.hang)
    client = DpcClient(session, request_timeout=0.1)

    with pytest.raises(DpcConnectionError, match="Timeout") as err:
        await client.latest_bulletin_id(BulletinKind.CRITICALITY)

    assert isinstance(err.value.__cause__, TimeoutError)


@pytest.mark.parametrize("body", [b"{not json", b"\xff\xfe\xfd", b""])
async def test_malformed_json(client: DpcClient, dpc: FakeDpc, body: bytes) -> None:
    """Test that invalid JSON raises a parse error."""
    serve_vigilance(dpc)
    dpc.add(phenomena_geojson_url(VIGI_ID, 1), body=body)

    with pytest.raises(DpcParseError, match="Invalid JSON"):
        await client.get_vigilance(ROME, now=PUBLICATION_DAY)


async def test_unexpected_json(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that JSON of an unexpected shape raises a parse error."""
    serve_criticality(dpc)
    dpc.add(TODAY_URL, body='{"error": "not found"}')

    with pytest.raises(DpcParseError):
        await client.get_criticality(ROME, now=PUBLICATION_DAY)


async def test_criticality_location_outside(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a location outside every zone raises a location error."""
    serve_criticality(dpc)

    with pytest.raises(DpcLocationError):
        await client.get_criticality(PARIS, now=PUBLICATION_DAY)


async def test_vigilance_location_outside(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a location outside every zone raises a location error."""
    serve_vigilance(dpc)

    with pytest.raises(DpcLocationError):
        await client.get_vigilance(PARIS, now=PUBLICATION_DAY)


async def test_invalid_bulletin_id(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that an invalid bulletin ID raises ValueError before any request."""
    with pytest.raises(ValueError, match="Invalid criticality bulletin ID"):
        await client.get_criticality(ROME, bulletin_id="latest")
    with pytest.raises(ValueError, match="Invalid vigilance bulletin ID"):
        await client.get_vigilance(ROME, bulletin_id="latest")
    assert dpc.requests == []


@pytest.mark.parametrize("distance", [-1.0, float("nan")])
async def test_invalid_phenomena_distance(client: DpcClient, distance: float) -> None:
    """Test that an invalid phenomena distance raises ValueError."""
    with pytest.raises(ValueError, match="Invalid phenomena distance"):
        await client.get_vigilance(ROME, phenomena_within_km=distance)


async def test_failure_cancels_the_other_downloads(
    client: DpcClient, dpc: FakeDpc
) -> None:
    """Test that the first failure is raised without waiting for the others."""
    serve_criticality(dpc)
    dpc.add(TODAY_URL, status=404)
    dpc.add(TOMORROW_URL, before=dpc.hang)

    async with asyncio.timeout(5):
        with pytest.raises(DpcConnectionError, match="HTTP status 404"):
            await client.get_criticality(ROME, now=PUBLICATION_DAY)

    assert TOMORROW_URL in dpc.requests


async def test_cancellation(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that cancelling the caller cancels the pending downloads."""
    started = asyncio.Event()

    async def hang() -> None:
        started.set()
        await dpc.hang()

    serve_vigilance(dpc)
    dpc.add(vigilance_geojson_url(VIGI_ID, 2), before=hang)
    task = asyncio.create_task(client.get_vigilance(ROME, now=PUBLICATION_DAY))
    await started.wait()

    task.cancel()

    async with asyncio.timeout(5):
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_cancellation_is_not_swallowed(
    client: DpcClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a cancelled request propagates out of the concurrent downloads."""

    async def cancelled(_url: str) -> bytes:
        raise asyncio.CancelledError

    monkeypatch.setattr(client, "_request", cancelled)

    with pytest.raises(asyncio.CancelledError):
        await client.get_criticality(ROME, bulletin_id=CRIT_ID, now=PUBLICATION_DAY)


@pytest.mark.parametrize(("location", "expected"), [(ROME, True), (PARIS, False)])
async def test_is_location_covered(
    client: DpcClient,
    dpc: FakeDpc,
    location: Location,
    expected: bool,  # noqa: FBT001
) -> None:
    """Test the coverage of locations by the criticality zones."""
    serve_criticality(dpc)

    assert await client.is_location_covered(location) is expected
    assert dpc.requests == [CRITICALITY_PAGE_URL, TODAY_URL]


async def test_is_location_covered_fallbacks(client: DpcClient, dpc: FakeDpc) -> None:
    """Test the next files when the first ones cannot be used."""
    serve_criticality(dpc)
    serve_vigilance(dpc)
    dpc.add(TODAY_URL, status=404)
    dpc.add(TOMORROW_URL, body="{}")
    dpc.add(vigilance_geojson_url(VIGI_ID, 0), body="not json")

    assert await client.is_location_covered(ROME)
    assert dpc.requests[-1] == vigilance_geojson_url(VIGI_ID, 1)


async def test_is_location_covered_unreachable(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that the first error is raised when DPC is unreachable."""
    dpc.unresolvable.add("mappe.protezionecivile.gov.it")

    with pytest.raises(DpcConnectionError, match="bollettino-di-criticita"):
        await client.is_location_covered(ROME)


async def test_is_location_covered_cancelled(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a cancellation is not taken for an unusable source."""
    started = asyncio.Event()

    async def hang() -> None:
        started.set()
        await dpc.hang()

    serve_criticality(dpc)
    serve_vigilance(dpc)
    dpc.add(CRITICALITY_PAGE_URL, before=hang)
    task = asyncio.create_task(client.is_location_covered(ROME))
    await started.wait()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert VIGILANCE_PAGE_URL not in dpc.requests


async def test_own_session(dpc: FakeDpc, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the client creates and closes its own session."""
    serve_criticality(dpc)
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: dpc.client_session())

    async with DpcClient() as client:
        assert await client.latest_bulletin_id(BulletinKind.CRITICALITY) == CRIT_ID
        session = client._session
        assert session is not None
        assert not session.closed

    assert session.closed
    assert client._session is None
    await client.close()


async def test_injected_session_is_not_closed(
    session: aiohttp.ClientSession, dpc: FakeDpc
) -> None:
    """Test that the client does not close a session it did not create."""
    serve_criticality(dpc)

    async with DpcClient(session) as client:
        await client.latest_bulletin_id(BulletinKind.CRITICALITY)

    assert not session.closed


async def test_close_without_requests() -> None:
    """Test closing a client that made no request."""
    client = DpcClient()

    await client.close()

    assert client._session is None


async def test_real_bulletin_served(client: DpcClient, dpc: FakeDpc) -> None:
    """Test the whole flow on excerpts of real DPC pages and files."""
    dpc.add(CRITICALITY_PAGE_URL, body=load_fixture("real/criticality_page.html"))
    dpc.add(
        criticality_geojson_url("20261113_1434", 0),
        body=load_fixture("real/criticality_20261113_1434_today.json"),
    )
    dpc.add(
        criticality_geojson_url("20261113_1434", 1),
        body=load_fixture("real/criticality_20261113_1434_today.json"),
    )

    bulletin = await client.get_criticality(ROME, now=rome(2026, 11, 13, 18))

    assert bulletin.id == "20261113_1434"
    assert [day.zone for day in bulletin] == ["Bacini di Roma"] * 2


async def test_alert_zone(client: DpcClient, dpc: FakeDpc) -> None:
    """Test the alert zone of a location, with its municipalities."""
    serve_criticality(dpc)

    zone = await client.get_alert_zone(ROME)

    assert zone == AlertZone("Bacini di Roma", ("Fiumicino", "Roma", "Tivoli"))
    assert str(zone) == "Bacini di Roma"
    assert dpc.requests == [CRITICALITY_PAGE_URL, TODAY_URL]


async def test_alert_zone_second_day(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that the second day is used when the first one is gone."""
    serve_criticality(dpc)
    dpc.add(TODAY_URL, status=404)

    zone = await client.get_alert_zone(ROME)

    assert zone.name == "Bacini di Roma"
    assert dpc.requests[-1] == TOMORROW_URL


async def test_alert_zone_location_outside(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a location outside every zone raises a location error."""
    serve_criticality(dpc)

    with pytest.raises(DpcLocationError):
        await client.get_alert_zone(PARIS)


async def test_alert_zone_unreachable(client: DpcClient, dpc: FakeDpc) -> None:
    """Test that a connection error is raised when DPC is unreachable."""
    dpc.unresolvable.add("raw.githubusercontent.com")
    serve_criticality(dpc)

    with pytest.raises(DpcConnectionError):
        await client.get_alert_zone(ROME)


PREVIEW_URL = criticality_preview_url(CRIT_ID, 0)


async def test_get_preview(dpc: FakeDpc, client: DpcClient) -> None:
    """Test that the preview of a map is returned, and a blank one is not."""
    real = FIXTURES / "real"
    preview = (real / "preview_20261115_1421_oggi.png").read_bytes()
    dpc.add(
        PREVIEW_URL, body=(real / "preview_20261115_1421_oggi_blank.png").read_bytes()
    )

    assert await client.get_preview(PREVIEW_URL) is None

    # DPC replaces it at the same address
    dpc.add(PREVIEW_URL, body=preview)

    assert await client.get_preview(PREVIEW_URL) == preview


async def test_get_preview_unreachable(dpc: FakeDpc, client: DpcClient) -> None:
    """Test that a preview that cannot be downloaded raises DpcConnectionError."""
    dpc.add(PREVIEW_URL, status=404)

    with pytest.raises(DpcConnectionError, match="HTTP status 404"):
        await client.get_preview(PREVIEW_URL)
