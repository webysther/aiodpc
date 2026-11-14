"""Typed models of the DPC bulletins."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Protocol

from .const import ROME_TZ


class AlertLevel(IntEnum):
    """Alert level of the criticality bulletin, ordered by severity.

    Being an ``IntEnum``, levels compare with each other and with integer
    thresholds (``level >= AlertLevel.YELLOW``).
    """

    UNKNOWN = 0
    """The assessment is missing or not recognised."""
    NONE = 1
    """Green: no alert ("NESSUNA ALLERTA")."""
    YELLOW = 2
    """Yellow alert ("ALLERTA GIALLA")."""
    ORANGE = 3
    """Orange alert ("ALLERTA ARANCIONE")."""
    RED = 4
    """Red alert ("ALLERTA ROSSA")."""


class Risk(StrEnum):
    """Risk assessed by the criticality bulletin; the value is the DPC code."""

    HYDRAULIC = "idraulico"
    THUNDERSTORMS = "temporali"
    HYDROGEOLOGICAL = "idrogeologico"


class BulletinKind(StrEnum):
    """Kind of DPC bulletin."""

    CRITICALITY = "criticality"
    """Bollettino di criticità idrogeologica e idraulica."""
    VIGILANCE = "vigilance"
    """Bollettino di vigilanza meteorologica."""


class PhenomenonCategory(StrEnum):
    """Category of a weather phenomenon; the value is the DPC code."""

    PRECIPITATION = "PRECIPITAZIONI"
    WIND = "VENTI"
    FROST = "GELATE"
    FOG = "NEBBIE"
    SEA = "MARI"
    WAVE_MOTION = "MOTO_ONDOSO"
    TEMPERATURE = "TEMPERATURE"


def rome_date(now: dt.datetime | None = None) -> dt.date:
    """Return the Italian calendar date at ``now`` (default: the current time).

    A naive ``now`` is taken as Italian local time.
    """
    if now is None:
        return dt.datetime.now(ROME_TZ).date()
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(ROME_TZ).date()


@dataclass(frozen=True, slots=True)
class Assessment:
    """A DPC assessment such as ``"Ordinaria / ALLERTA GIALLA"``."""

    info: str
    """Criticality as written by DPC, in Italian (e.g. ``"Ordinaria"``)."""
    alert: str
    """Alert as written by DPC, in Italian (e.g. ``"ALLERTA GIALLA"``)."""
    level: AlertLevel
    """Alert level parsed from ``alert``."""


@dataclass(frozen=True, slots=True)
class CriticalityDay:
    """The criticality assessment of a location for one day."""

    date: dt.date
    """Calendar day covered by the assessment."""
    offset: int
    """Day of the bulletin: 0 for the publication day, 1 for the next day."""
    expires: dt.datetime
    """End of validity: the midnight (Europe/Rome) that ends ``date``."""
    zone_name: str
    """Name of the DPC alert zone, as provided by DPC."""
    summary: Assessment
    """Overall assessment of the zone ("Rappresentata nella mappa")."""
    risks: Mapping[Risk, Assessment] = field(hash=False)
    """Assessment of each risk ("Per rischio ...")."""
    image_url: str
    """Preview image of the national map for this day."""

    @property
    def max_level(self) -> AlertLevel:
        """Return the highest level between the summary and the risks."""
        return max((self.summary.level, *(item.level for item in self.risks.values())))


@dataclass(frozen=True, slots=True)
class Phenomenon:
    """A weather phenomenon of the vigilance bulletin near the location."""

    code: int
    """DPC phenomenon code (``id_fenomeno``), e.g. 5."""
    category: PhenomenonCategory | None
    """Category of the code; ``None`` when the code is unknown to aiodpc."""
    description: str | None
    """DPC legend of the code, in Italian; ``None`` when the code is unknown."""
    latitude: float
    longitude: float
    distance_km: float
    """Distance from the location, in km, rounded to 0.1 km."""
    direction: str
    """Compass point from the location to the phenomenon (e.g. ``"NNE"``)."""
    degrees: int
    """Initial bearing from the location to the phenomenon (0-359)."""
    bulletin_id: int | None
    """DPC ``id_bollettino`` of the phenomenon, as provided."""
    bulletin_date: str | None
    """DPC ``data_bollettino`` of the phenomenon, as provided."""


@dataclass(frozen=True, slots=True)
class VigilanceDay:
    """The weather vigilance of a location for one day."""

    date: dt.date
    """Calendar day covered by the forecast."""
    offset: int
    """Day of the bulletin: 0 publication day, 1 next day, 2 the day after."""
    expires: dt.datetime
    """End of validity: the midnight (Europe/Rome) that ends ``date``."""
    zone_name: str
    """Name of the DPC vigilance zone, as provided by DPC."""
    level: int
    """DPC precipitation class of the zone (``id_classificazione``), 0 if missing."""
    precipitation: str | None
    """Expected precipitation (``Quantitativi_previsti``), in Italian."""
    image_url: str | None
    """Preview image of the national map; DPC publishes none for offset 2."""
    phenomena: tuple[Phenomenon, ...]
    """Weather phenomena within the requested radius."""


class _Day(Protocol):
    @property
    def date(self) -> dt.date: ...


def _find_day[DayT: _Day](days: Sequence[DayT], day: dt.date) -> DayT | None:
    return next((item for item in days if item.date == day), None)


@dataclass(frozen=True, slots=True)
class CriticalityBulletin:
    """A criticality bulletin for a location.

    Every day carries its calendar ``date``: use :meth:`day_for`, :meth:`today`
    or :meth:`tomorrow` instead of relying on the position in ``days``.
    """

    id: str
    """Bulletin ID, e.g. ``"20261114_1430"``."""
    published: dt.datetime
    """Publication time in the ID (Europe/Rome)."""
    days: tuple[CriticalityDay, ...]
    """Assessed days, in order; expired days may have been skipped."""

    def day_for(self, day: dt.date) -> CriticalityDay | None:
        """Return the assessment for a calendar day, if the bulletin covers it."""
        return _find_day(self.days, day)

    def today(self, now: dt.datetime | None = None) -> CriticalityDay | None:
        """Return the assessment for the current Italian day."""
        return self.day_for(rome_date(now))

    def tomorrow(self, now: dt.datetime | None = None) -> CriticalityDay | None:
        """Return the assessment for the next Italian day."""
        return self.day_for(rome_date(now) + dt.timedelta(days=1))


@dataclass(frozen=True, slots=True)
class VigilanceBulletin:
    """A weather vigilance bulletin for a location.

    Every day carries its calendar ``date``: use :meth:`day_for`, :meth:`today`
    or :meth:`tomorrow` instead of relying on the position in ``days``.
    """

    id: str
    """Bulletin ID, e.g. ``"20261114"``."""
    date: dt.date
    """Publication day in the ID."""
    days: tuple[VigilanceDay, ...]
    """Forecast days, in order; expired days may have been skipped."""

    def day_for(self, day: dt.date) -> VigilanceDay | None:
        """Return the forecast for a calendar day, if the bulletin covers it."""
        return _find_day(self.days, day)

    def today(self, now: dt.datetime | None = None) -> VigilanceDay | None:
        """Return the forecast for the current Italian day."""
        return self.day_for(rome_date(now))

    def tomorrow(self, now: dt.datetime | None = None) -> VigilanceDay | None:
        """Return the forecast for the next Italian day."""
        return self.day_for(rome_date(now) + dt.timedelta(days=1))
