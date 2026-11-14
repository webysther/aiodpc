"""Async client of the DPC bulletins."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import TYPE_CHECKING, Any, Self

import aiohttp

from .const import DEFAULT_PHENOMENA_RADIUS_KM, DEFAULT_REQUEST_TIMEOUT, ROME_TZ
from .discovery import BulletinIdSource, MapPageIdSource
from .exceptions import DpcConnectionError, DpcError, DpcParseError
from .maps import CriticalityMap, VigilanceMap
from .models import (
    AlertZone,
    BulletinKind,
    CriticalityBulletin,
    Location,
    VigilanceBulletin,
)
from .monitor import MonitoredLocation
from .parsers import (
    check_phenomena_distance,
    end_of_day,
    location_in_zones,
    parse_alert_zone,
    parse_criticality_id,
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
    from collections.abc import Callable, Coroutine, Iterable

    from .schema import CriticalityFile, PhenomenaFile, VigilanceFile

_LOGGER = logging.getLogger(__name__)


class DpcClient:
    """Async client of the DPC criticality and weather vigilance bulletins.

    Pass the ``aiohttp.ClientSession`` of the application (it is never closed
    by the client), or use the client as an async context manager to let it
    manage its own session.

    The API has three levels, from the simplest:

    - :meth:`location`: answers "is there a risk here?" and "which one?".
    - :meth:`get_criticality` and :meth:`get_vigilance`: the bulletins for a
      location, day by day, parsed leniently. For several locations,
      :meth:`get_criticality_map` and :meth:`get_vigilance_map` download the
      bulletins once and read them at each location.
    - :meth:`get_criticality_file` and the other ``*_file`` methods: the raw
      DPC files as strict DTOs (optional, ``aiodpc[schema]``).

    The bulletin files are large (a few MB per day): to poll the bulletins,
    compare :meth:`latest_bulletin_id` with the ID of the bulletin already
    fetched and fetch it again only when it changed. :meth:`location` does it
    for you.
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

    def location(
        self, latitude: float, longitude: float, *, municipality: str | None = None
    ) -> MonitoredLocation:
        """Return a location answering whether it has a risk, and which one.

        See :class:`aiodpc.Location` for ``municipality``. Raises
        ``ValueError`` for invalid coordinates.
        """
        return MonitoredLocation(
            self, Location(latitude, longitude, municipality=municipality)
        )

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
        location: Location,
        *,
        bulletin_id: str | None = None,
        skip_expired: bool = True,
        now: dt.datetime | None = None,
    ) -> CriticalityBulletin:
        """Return the criticality bulletin for a location: its alert levels.

        ``bulletin_id`` defaults to the latest bulletin. With ``skip_expired``,
        days already over at ``now`` (default: the current time) are not
        downloaded and are missing from the bulletin. For several locations,
        read a :meth:`get_criticality_map` instead: it downloads once.

        Raises :class:`DpcConnectionError`, :class:`DpcParseError` or
        :class:`DpcLocationError`; ``ValueError`` for an invalid bulletin ID.
        """
        criticality_map = await self.get_criticality_map(
            bulletin_id=bulletin_id, skip_expired=skip_expired, now=now
        )
        return criticality_map.at(location)

    async def get_criticality_map(
        self,
        *,
        bulletin_id: str | None = None,
        skip_expired: bool = True,
        now: dt.datetime | None = None,
    ) -> CriticalityMap:
        """Return the criticality bulletin of Italy, to read at any location.

        Its files are downloaded once; :meth:`CriticalityMap.at` then reads
        them for each location without any request. The arguments are as in
        :meth:`get_criticality`.

        Raises :class:`DpcConnectionError` or :class:`DpcParseError`;
        ``ValueError`` for an invalid bulletin ID.
        """
        if bulletin_id is None:
            bulletin_id = await self.latest_bulletin_id(BulletinKind.CRITICALITY)
        published = parse_criticality_id(bulletin_id)
        offsets = _offsets(
            published.date(),
            len(CRITICALITY_DAYS),
            skip_expired=skip_expired,
            now=now,
        )
        files = await _gather(
            self._fetch_json(criticality_geojson_url(bulletin_id, offset))
            for offset in offsets
        )
        return CriticalityMap(bulletin_id, zip(offsets, files, strict=True))

    async def get_vigilance(
        self,
        location: Location,
        *,
        phenomena_within_km: float = DEFAULT_PHENOMENA_RADIUS_KM,
        bulletin_id: str | None = None,
        skip_expired: bool = True,
        now: dt.datetime | None = None,
    ) -> VigilanceBulletin:
        """Return the weather vigilance bulletin for a location.

        Each day includes the phenomena within ``phenomena_within_km`` of the
        coordinates. The other arguments are as in :meth:`get_criticality`.
        For several locations, read a :meth:`get_vigilance_map` instead.

        Raises :class:`DpcConnectionError`, :class:`DpcParseError` or
        :class:`DpcLocationError`; ``ValueError`` for invalid arguments.
        """
        check_phenomena_distance(phenomena_within_km)
        vigilance_map = await self.get_vigilance_map(
            bulletin_id=bulletin_id, skip_expired=skip_expired, now=now
        )
        return vigilance_map.at(location, phenomena_within_km=phenomena_within_km)

    async def get_vigilance_map(
        self,
        *,
        bulletin_id: str | None = None,
        skip_expired: bool = True,
        now: dt.datetime | None = None,
    ) -> VigilanceMap:
        """Return the weather vigilance bulletin of Italy, to read anywhere.

        Its files are downloaded once; :meth:`VigilanceMap.at` then reads them
        for each location, with its own distance for the phenomena. The
        arguments are as in :meth:`get_criticality`.

        Raises :class:`DpcConnectionError` or :class:`DpcParseError`;
        ``ValueError`` for an invalid bulletin ID.
        """
        if bulletin_id is None:
            bulletin_id = await self.latest_bulletin_id(BulletinKind.VIGILANCE)
        published = parse_vigilance_id(bulletin_id)
        offsets = _offsets(
            published, len(VIGILANCE_DAYS), skip_expired=skip_expired, now=now
        )
        files = await _gather(
            self._fetch_json(url(bulletin_id, offset))
            for offset in offsets
            for url in (vigilance_geojson_url, phenomena_geojson_url)
        )
        zones, phenomena = files[::2], files[1::2]
        return VigilanceMap(bulletin_id, zip(offsets, zones, phenomena, strict=True))

    async def is_location_covered(self, location: Location) -> bool:
        """Return whether a location is inside a DPC alert zone.

        The zones of the latest criticality bulletin are used, or those of the
        vigilance bulletin when the former cannot be fetched.

        Raises the first :class:`DpcError` when no bulletin could be used.
        """
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
                    return location_in_zones(geojson, location)
                except DpcError as err:
                    errors.append(err)
        raise errors[0]

    async def get_alert_zone(self, location: Location) -> AlertZone:
        """Return the alert zone of a location, with its municipalities.

        It is the zone of the latest criticality bulletin containing the
        coordinates, for example to offer the municipalities of the place when
        configuring it. One file of the bulletin is downloaded.

        Raises :class:`DpcLocationError` when the location is in no zone, or
        :class:`DpcConnectionError` or :class:`DpcParseError`.
        """
        bulletin_id = await self.latest_bulletin_id(BulletinKind.CRITICALITY)
        try:
            geojson = await self._fetch_json(criticality_geojson_url(bulletin_id, 0))
        except DpcConnectionError:
            # The first day of a bulletin may already be gone: the zones are
            # the same on the second day
            geojson = await self._fetch_json(criticality_geojson_url(bulletin_id, 1))
        return parse_alert_zone(geojson, location)

    async def get_criticality_file(
        self, bulletin_id: str | None = None, offset: int = 0
    ) -> CriticalityFile:
        """Return a day of the criticality bulletin as a strict DTO.

        Requires ``aiodpc[schema]``. ``bulletin_id`` defaults to the latest
        bulletin and ``offset`` is the day: 0 (publication day) or 1.

        Raises :class:`DpcParseError` when the file does not match the DTO,
        :class:`DpcConnectionError`, or ``ValueError`` for invalid arguments.
        """
        from .schema import decode_criticality_file  # noqa: PLC0415 - optional

        return await self._get_file(
            BulletinKind.CRITICALITY,
            criticality_geojson_url,
            decode_criticality_file,
            bulletin_id,
            offset,
        )

    async def get_vigilance_file(
        self, bulletin_id: str | None = None, offset: int = 0
    ) -> VigilanceFile:
        """Return the zones of a day of the vigilance bulletin as a strict DTO.

        Requires ``aiodpc[schema]``. ``offset`` is the day: 0 (publication
        day), 1 or 2. See :meth:`get_criticality_file`.
        """
        from .schema import decode_vigilance_file  # noqa: PLC0415 - optional

        return await self._get_file(
            BulletinKind.VIGILANCE,
            vigilance_geojson_url,
            decode_vigilance_file,
            bulletin_id,
            offset,
        )

    async def get_phenomena_file(
        self, bulletin_id: str | None = None, offset: int = 0
    ) -> PhenomenaFile:
        """Return the phenomena of a day of the vigilance bulletin as a DTO.

        Requires ``aiodpc[schema]``. See :meth:`get_vigilance_file`.
        """
        from .schema import decode_phenomena_file  # noqa: PLC0415 - optional

        return await self._get_file(
            BulletinKind.VIGILANCE,
            phenomena_geojson_url,
            decode_phenomena_file,
            bulletin_id,
            offset,
        )

    async def _get_file[FileT](
        self,
        kind: BulletinKind,
        url: Callable[[str, int], str],
        decode: Callable[[bytes], FileT],
        bulletin_id: str | None,
        offset: int,
    ) -> FileT:
        if bulletin_id is None:
            bulletin_id = await self.latest_bulletin_id(kind)
        elif kind is BulletinKind.CRITICALITY:
            parse_criticality_id(bulletin_id)
        else:
            parse_vigilance_id(bulletin_id)
        return decode(await self._request(url(bulletin_id, offset)))

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
        """Return the decoded JSON at a URL, decoded in a worker thread.

        The bulletin files are several MB, too large to decode in the event loop.
        """
        body = await self._request(url)
        try:
            data: object = await asyncio.to_thread(json.loads, body)
        except ValueError as err:
            msg = f"Invalid JSON from {url}"
            raise DpcParseError(msg) from err
        return data


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
        if end_of_day(first_day + dt.timedelta(days=offset)) > now
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
