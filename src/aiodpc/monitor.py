"""High-level API: answers about the risk at a location."""

from __future__ import annotations

import asyncio
import math
import time
from typing import TYPE_CHECKING, Final

from .exceptions import DpcNoDataError
from .models import BulletinKind, Day, Risk, calendar_date

if TYPE_CHECKING:
    import datetime as dt

    from .client import DpcClient
    from .models import CriticalityBulletin, Location

LATEST_ID_CHECK_INTERVAL: Final = 60.0
"""Seconds during which the latest bulletin ID is not checked again."""


class MonitoredLocation:
    """A location whose DPC alerts are answered in one call.

    Get it from :meth:`aiodpc.DpcClient.location`::

        home = dpc.location(41.9, 12.5)

        if await home.has_risk():
            risk = await home.risk()
            print(risk.level, risk.types)  # orange (RiskType.HYDROGEOLOGICAL,)

    The criticality bulletin of the location is kept between calls and
    downloaded again only when DPC publishes a new one, so the methods can be
    called as often as needed, e.g. at every update of a Home Assistant
    coordinator. The latest bulletin ID is checked at most once a minute.
    """

    def __init__(self, client: DpcClient, location: Location) -> None:
        """Initialize the monitored location; use DpcClient.location instead."""
        self._client = client
        self._location = location
        self._bulletin: CriticalityBulletin | None = None
        self._checked_at = -math.inf
        self._lock = asyncio.Lock()

    @property
    def location(self) -> Location:
        """Return the location."""
        return self._location

    async def has_risk(self, on: Day | dt.date = Day.TODAY) -> bool:
        """Return whether there is an alert (yellow or higher) on a day.

        ``on`` is ``Day.TODAY`` (default), ``Day.TOMORROW`` or a date. A level
        written by DPC in an unrecognised way (``AlertLevel.UNKNOWN``) is not
        an alert: check :meth:`risk` to tell it from green.

        Raises :class:`aiodpc.DpcNoDataError` when no bulletin covers the day,
        or another :class:`aiodpc.DpcError` when DPC cannot be used.
        """
        return (await self.risk(on)).is_alert

    async def risk(self, on: Day | dt.date = Day.TODAY) -> Risk:
        """Return the risk on a day: its level, the risk types and more.

        ``on`` is ``Day.TODAY`` (default), ``Day.TOMORROW`` or a date.

        Raises :class:`aiodpc.DpcNoDataError` when no bulletin covers the day,
        or another :class:`aiodpc.DpcError` when DPC cannot be used.
        """
        bulletin = await self.criticality()
        date = calendar_date(on)
        day = bulletin.on(date)
        if day is None:
            msg = (
                f"The latest criticality bulletin ({bulletin.id}) does not cover {date}"
            )
            raise DpcNoDataError(msg)
        return Risk.of(day)

    async def criticality(self) -> CriticalityBulletin:
        """Return the latest criticality bulletin of the location.

        It is downloaded only when DPC has published a new one since the
        previous call.
        """
        async with self._lock:
            if self._bulletin is None or self._latest_id_is_due():
                latest = await self._client.latest_bulletin_id(BulletinKind.CRITICALITY)
                if self._bulletin is None or self._bulletin.id != latest:
                    self._bulletin = await self._client.get_criticality(
                        self._location, bulletin_id=latest
                    )
                self._checked_at = time.monotonic()
            return self._bulletin

    def _latest_id_is_due(self) -> bool:
        return time.monotonic() - self._checked_at >= LATEST_ID_CHECK_INTERVAL

    def __repr__(self) -> str:
        """Return the representation of the monitored location."""
        return f"MonitoredLocation({self._location!r})"
