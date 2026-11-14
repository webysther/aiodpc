"""Async client of the DPC bulletins."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import math
from typing import TYPE_CHECKING, Any, Final, Self

import aiohttp

from .const import DEFAULT_PHENOMENA_RADIUS_KM, DEFAULT_REQUEST_TIMEOUT, ROME_TZ
from .discovery import BulletinIdSource, MapPageIdSource
from .exceptions import DpcConnectionError, DpcError, DpcParseError
from .models import (
    BulletinKind,
    CriticalityBulletin,
    CriticalityDay,
    VigilanceBulletin,
    VigilanceDay,
)
from .parsers import (
    day_expires,
    location_in_zones,
    parse_criticality_day,
    parse_criticality_id,
    parse_phenomena,
    parse_vigilance_day,
    parse_vigilance_id,
)
from .urls import (
    CRITICALITY_DAYS,
    VIGILANCE_DAYS,
    criticality_geojson_url,
    phenomena_geojson_url,
    vigilance_geojson_url,
)

if TYPE_CHECKING:
    from collections.abc import Coroutine, Iterable

_LOGGER = logging.getLogger(__name__)

_MAX_LATITUDE: Final = 90.0
_MAX_LONGITUDE: Final = 180.0


class DpcClient:
    """Async client of the DPC criticality and weather vigilance bulletins.

    Pass the ``aiohttp.ClientSession`` of the application (it is never closed
    by the client), or use the client as an async context manager to let it
    manage its own session::

        async with DpcClient() as client:
            bulletin = await client.get_criticality(41.9, 12.5)

    The bulletin files are large (a few MB per day): to poll, compare
    :meth:`latest_bulletin_id` with the ID of the bulletin already fetched and
    fetch the bulletin again only when it changed.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        *,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        id_source: BulletinIdSource | None = None,
    ) -> None:
        """Initialize the client.

        ``request_timeout`` applies to each HTTP request, in seconds.
        ``id_source`` finds the latest bulletin IDs (default: the DPC map pages).
        """
        self._session = session
        self._close_session = False
        self._request_timeout = request_timeout
        self._id_source: BulletinIdSource = id_source or MapPageIdSource()

    async def __aenter__(self) -> Self:
        """Enter the async context."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the async context, closing the session owned by the client."""
        await self.close()

    async def close(self) -> None:
        """Close the session if the client created it."""
        if self._session is not None and self._close_session:
            await self._session.close()
            self._session = None
            self._close_session = False

    async def latest_bulletin_id(self, kind: BulletinKind) -> str:
        """Return the ID of the latest published bulletin of a kind.

        Raises :class:`DpcConnectionError` or :class:`DpcParseError`.
        """
        kind = BulletinKind(kind)
        bulletin_id = await self._id_source.latest_id(kind, self._fetch_text)
        try:
            if kind is BulletinKind.CRITICALITY:
                parse_criticality_id(bulletin_id)
            else:
                parse_vigilance_id(bulletin_id)
        except ValueError as err:
            msg = f"Invalid {kind} bulletin ID from the ID source: {bulletin_id!r}"
            raise DpcParseError(msg) from err
        _LOGGER.debug("Latest %s bulletin: %s", kind, bulletin_id)
        return bulletin_id

    async def get_criticality(
        self,
        latitude: float,
        longitude: float,
        *,
        municipality: str | None = None,
        bulletin_id: str | None = None,
        skip_expired: bool = True,
        now: dt.datetime | None = None,
    ) -> CriticalityBulletin:
        """Return the criticality bulletin for a location.

        ``municipality`` (optional) selects, among the zones listing it, the one
        with the highest alert. ``bulletin_id`` defaults to the latest bulletin.
        With ``skip_expired``, days already over at ``now`` (default: the
        current time) are not downloaded and are missing from ``days``.

        Raises :class:`DpcConnectionError`, :class:`DpcParseError` or
        :class:`DpcLocationError`; ``ValueError`` for invalid arguments.
        """
        _check_location(latitude, longitude)
        if bulletin_id is None:
            bulletin_id = await self.latest_bulletin_id(BulletinKind.CRITICALITY)
        published = parse_criticality_id(bulletin_id)
        offsets = _offsets(
            published.date(),
            len(CRITICALITY_DAYS),
            skip_expired=skip_expired,
            now=now,
        )
        days = await _gather(
            self._criticality_day(
                bulletin_id, offset, latitude, longitude, municipality
            )
            for offset in offsets
        )
        return CriticalityBulletin(
            id=bulletin_id, published=published, days=tuple(days)
        )

    async def get_vigilance(
        self,
        latitude: float,
        longitude: float,
        *,
        municipality: str | None = None,
        phenomena_radius_km: float = DEFAULT_PHENOMENA_RADIUS_KM,
        bulletin_id: str | None = None,
        skip_expired: bool = True,
        now: dt.datetime | None = None,
    ) -> VigilanceBulletin:
        """Return the weather vigilance bulletin for a location.

        Each day includes the phenomena within ``phenomena_radius_km`` of the
        coordinates. The other arguments are as in :meth:`get_criticality`.

        Raises :class:`DpcConnectionError`, :class:`DpcParseError` or
        :class:`DpcLocationError`; ``ValueError`` for invalid arguments.
        """
        _check_location(latitude, longitude)
        if not (math.isfinite(phenomena_radius_km) and phenomena_radius_km >= 0):
            msg = f"Invalid phenomena radius: {phenomena_radius_km}"
            raise ValueError(msg)
        if bulletin_id is None:
            bulletin_id = await self.latest_bulletin_id(BulletinKind.VIGILANCE)
        published = parse_vigilance_id(bulletin_id)
        offsets = _offsets(
            published, len(VIGILANCE_DAYS), skip_expired=skip_expired, now=now
        )
        days = await _gather(
            self._vigilance_day(
                bulletin_id,
                offset,
                latitude,
                longitude,
                municipality,
                phenomena_radius_km,
            )
            for offset in offsets
        )
        return VigilanceBulletin(id=bulletin_id, date=published, days=tuple(days))

    async def is_location_covered(self, latitude: float, longitude: float) -> bool:
        """Return whether a location is inside a DPC alert zone.

        The zones of the latest criticality bulletin are used, or those of the
        vigilance bulletin when the former cannot be fetched.

        Raises the first :class:`DpcError` when no bulletin could be used.
        """
        _check_location(latitude, longitude)
        sources = (
            (BulletinKind.CRITICALITY, criticality_geojson_url),
            (BulletinKind.VIGILANCE, vigilance_geojson_url),
        )
        errors: list[DpcError] = []
        for kind, geojson_url in sources:
            try:
                bulletin_id = await self.latest_bulletin_id(kind)
            except DpcError as err:
                errors.append(err)
                continue
            for offset in (0, 1):
                try:
                    geojson = await self._fetch_json(geojson_url(bulletin_id, offset))
                    return location_in_zones(geojson, latitude, longitude)
                except DpcError as err:
                    errors.append(err)
        raise errors[0]

    async def _criticality_day(
        self,
        bulletin_id: str,
        offset: int,
        latitude: float,
        longitude: float,
        municipality: str | None,
    ) -> CriticalityDay:
        geojson = await self._fetch_json(criticality_geojson_url(bulletin_id, offset))
        return parse_criticality_day(
            geojson,
            bulletin_id=bulletin_id,
            offset=offset,
            latitude=latitude,
            longitude=longitude,
            municipality=municipality,
        )

    async def _vigilance_day(
        self,
        bulletin_id: str,
        offset: int,
        latitude: float,
        longitude: float,
        municipality: str | None,
        phenomena_radius_km: float,
    ) -> VigilanceDay:
        zones, phenomena = await _gather(
            self._fetch_json(url(bulletin_id, offset))
            for url in (vigilance_geojson_url, phenomena_geojson_url)
        )
        return parse_vigilance_day(
            zones,
            bulletin_id=bulletin_id,
            offset=offset,
            latitude=latitude,
            longitude=longitude,
            municipality=municipality,
            phenomena=parse_phenomena(
                phenomena,
                latitude=latitude,
                longitude=longitude,
                radius_km=phenomena_radius_km,
            ),
        )

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True
        return self._session

    async def _request(self, url: str) -> bytes:
        """Return the body at a URL, mapping every failure to DpcConnectionError."""
        session = self._get_session()
        _LOGGER.debug("Fetching %s", url)
        try:
            async with (
                asyncio.timeout(self._request_timeout),
                session.get(url) as response,
            ):
                response.raise_for_status()
                return await response.read()
        except TimeoutError as err:
            msg = f"Timeout fetching {url}"
            raise DpcConnectionError(msg) from err
        except aiohttp.ClientResponseError as err:
            msg = f"HTTP status {err.status} fetching {url}"
            raise DpcConnectionError(msg) from err
        except (aiohttp.ClientError, OSError) as err:
            msg = f"Error fetching {url}: {err!r}"
            raise DpcConnectionError(msg) from err

    async def _fetch_text(self, url: str) -> str:
        return (await self._request(url)).decode("utf-8", errors="replace")

    async def _fetch_json(self, url: str) -> object:
        body = await self._request(url)
        try:
            data: object = json.loads(body)
        except ValueError as err:
            msg = f"Invalid JSON from {url}"
            raise DpcParseError(msg) from err
        return data


def _check_location(latitude: float, longitude: float) -> None:
    if not (math.isfinite(latitude) and -_MAX_LATITUDE <= latitude <= _MAX_LATITUDE):
        msg = f"Invalid latitude: {latitude}"
        raise ValueError(msg)
    if not (
        math.isfinite(longitude) and -_MAX_LONGITUDE <= longitude <= _MAX_LONGITUDE
    ):
        msg = f"Invalid longitude: {longitude}"
        raise ValueError(msg)


def _offsets(
    first_day: dt.date, count: int, *, skip_expired: bool, now: dt.datetime | None
) -> list[int]:
    """Return the day offsets to fetch, without the expired days if asked."""
    if not skip_expired:
        return list(range(count))
    if now is None:
        now = dt.datetime.now(ROME_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ROME_TZ)
    return [
        offset
        for offset in range(count)
        if day_expires(first_day + dt.timedelta(days=offset)) > now
    ]


async def _gather[T](coros: Iterable[Coroutine[Any, Any, T]]) -> list[T]:
    """Run coroutines concurrently and return their results in order.

    On the first failure the other coroutines are cancelled and that exception
    is raised as is (not wrapped in an ExceptionGroup). Cancellation propagates.
    """
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(coro) for coro in coros]
    except ExceptionGroup as err:
        error = err.exceptions[0]
        raise error from error.__cause__
    return [task.result() for task in tasks]
