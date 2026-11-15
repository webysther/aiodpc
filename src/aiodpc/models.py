"""Typed models of the DPC bulletins."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum
from typing import TYPE_CHECKING, Final, Protocol

from .const import ROME_TZ

if TYPE_CHECKING:
    from collections.abc import Iterator

_MAX_LATITUDE: Final = 90.0
_MAX_LONGITUDE: Final = 180.0


class _NamedLevel(IntEnum):
    """Ordered level shown by its lower-case name: ``str(level) == "yellow"``."""

    def __str__(self) -> str:
        return self.name.lower()

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)


class AlertLevel(_NamedLevel):
    """Alert level of the criticality bulletin, ordered by severity.

    Levels compare with each other (``level >= AlertLevel.ORANGE``) and print
    as their color (``"yellow"``).
    """

    UNKNOWN = 0
    """The assessment is missing or not recognised."""
    GREEN = 1
    """No alert ("NESSUNA ALLERTA")."""
    YELLOW = 2
    """Yellow alert ("ALLERTA GIALLA")."""
    ORANGE = 3
    """Orange alert ("ALLERTA ARANCIONE")."""
    RED = 4
    """Red alert ("ALLERTA ROSSA")."""

    @property
    def is_alert(self) -> bool:
        """Return whether the level is an alert: yellow or higher."""
        return self >= AlertLevel.YELLOW


class Precipitation(_NamedLevel):
    """Expected daily precipitation of the vigilance bulletin, ordered by amount.

    The value is the DPC class (``id_classificazione``); levels print as their
    name (``"moderate"``).
    """

    UNKNOWN = 0
    """The class is missing or not recognised."""
    NONE = 1
    """"Assenti o non rilevanti": none or not significant."""
    LIGHT = 2
    """"Deboli"."""
    MODERATE = 3
    """"Moderati"."""
    HEAVY = 4
    """"Elevati"."""
    VERY_HEAVY = 5
    """"Molto elevati"."""


class RiskType(StrEnum):
    """Risk assessed by the criticality bulletin."""

    HYDRAULIC = "hydraulic"
    """Rischio idraulico: flooding of the main rivers."""
    THUNDERSTORMS = "thunderstorms"
    """Rischio temporali: effects of thunderstorms on the ground."""
    HYDROGEOLOGICAL = "hydrogeological"
    """Rischio idrogeologico: landslides and flooding of the minor streams."""


class PhenomenonCategory(StrEnum):
    """Category of a weather phenomenon of the vigilance bulletin."""

    PRECIPITATION = "precipitation"
    WIND = "wind"
    FROST = "frost"
    FOG = "fog"
    SEA = "sea"
    WAVE_MOTION = "wave_motion"
    TEMPERATURE = "temperature"


class BulletinKind(StrEnum):
    """Kind of DPC bulletin."""

    CRITICALITY = "criticality"
    """Bollettino di criticità idrogeologica e idraulica: the alert levels."""
    VIGILANCE = "vigilance"
    """Bollettino di vigilanza meteorologica: the expected weather."""


def rome_date(now: dt.datetime | None = None) -> dt.date:
    """Return the Italian calendar date at ``now`` (default: the current time).

    A naive ``now`` is taken as Italian local time.
    """
    if now is None:
        return dt.datetime.now(ROME_TZ).date()
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(ROME_TZ).date()


class Day(Enum):
    """A day relative to the current Italian date."""

    TODAY = 0
    TOMORROW = 1

    def date(self, now: dt.datetime | None = None) -> dt.date:
        """Return the calendar date of the day at ``now`` (default: now)."""
        return rome_date(now) + dt.timedelta(days=self.value)


def calendar_date(day: Day | dt.date) -> dt.date:
    """Return the date of ``Day.TODAY``/``Day.TOMORROW``; a datetime in Rome."""
    if isinstance(day, Day):
        return day.date()
    if isinstance(day, dt.datetime):
        return rome_date(day)
    return day


@dataclass(frozen=True, slots=True)
class Location:
    """A place in Italy: coordinates and, optionally, the municipality.

    With a ``municipality`` (e.g. ``"Roma"``), every zone listing it near the
    coordinates (see :data:`aiodpc.parsers.MUNICIPALITY_RADIUS_KM`) is
    considered and the one with the highest level is used, since large
    municipalities span several zones. In South Tyrol either the Italian or
    the German name works (``"Bolzano"`` or ``"Bozen"``). Raises
    ``ValueError`` for invalid coordinates.
    """

    latitude: float
    longitude: float
    municipality: str | None = None

    def __post_init__(self) -> None:
        """Check the coordinates."""
        if not (
            math.isfinite(self.latitude)
            and -_MAX_LATITUDE <= self.latitude <= _MAX_LATITUDE
        ):
            msg = f"Invalid latitude: {self.latitude}"
            raise ValueError(msg)
        if not (
            math.isfinite(self.longitude)
            and -_MAX_LONGITUDE <= self.longitude <= _MAX_LONGITUDE
        ):
            msg = f"Invalid longitude: {self.longitude}"
            raise ValueError(msg)

    @property
    def coordinates(self) -> tuple[float, float]:
        """Return the (latitude, longitude) pair."""
        return self.latitude, self.longitude


@dataclass(frozen=True, slots=True)
class AlertZone:
    """A DPC alert zone: its name and the municipalities it spans."""

    name: str
    """Name of the zone, e.g. ``"Bacini di Roma"``."""
    municipalities: tuple[str, ...]
    """Municipalities of the zone as DPC writes them, e.g. ``"Bolzano/Bozen"``.

    A municipality that spans several zones is listed in each of them.
    """

    def __str__(self) -> str:
        """Return the name of the zone."""
        return self.name


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """The alert level of one risk type, e.g. hydrogeological: yellow."""

    type: RiskType
    level: AlertLevel
    description: str
    """Criticality as written by DPC, in Italian (e.g. ``"Ordinaria"``)."""

    @property
    def is_alert(self) -> bool:
        """Return whether the level is an alert: yellow or higher."""
        return self.level.is_alert

    def __str__(self) -> str:
        """Return e.g. ``"hydrogeological: yellow"``."""
        return f"{self.type}: {self.level}"


@dataclass(frozen=True, slots=True)
class CriticalityDay:
    """The alert levels of a location for one day."""

    date: dt.date
    """Calendar day covered by the assessment."""
    offset: int
    """Day of the bulletin: 0 for the publication day, 1 for the next day."""
    valid_until: dt.datetime
    """End of validity: the midnight (Europe/Rome) that ends ``date``."""
    zone: str
    """Name of the DPC alert zone (e.g. ``"Bacini di Roma"``)."""
    level: AlertLevel
    """Highest alert level of the zone, across every risk type."""
    description: str
    """Summary written by DPC, in Italian (e.g. ``"Ordinaria per rischio
    idrogeologico"``)."""
    hydraulic: RiskAssessment
    thunderstorms: RiskAssessment
    hydrogeological: RiskAssessment
    image_url: str
    """Preview image of the national map for this day."""

    @property
    def is_alert(self) -> bool:
        """Return whether any risk has an alert: yellow or higher."""
        return self.level.is_alert

    @property
    def risks(self) -> tuple[RiskAssessment, ...]:
        """Return the assessment of every risk type."""
        return self.hydraulic, self.thunderstorms, self.hydrogeological

    def assessment(self, risk_type: RiskType) -> RiskAssessment:
        """Return the assessment of a risk type."""
        return next(item for item in self.risks if item.type is risk_type)


@dataclass(frozen=True, slots=True)
class Phenomenon:
    """A significant weather phenomenon expected near the location."""

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

    def __str__(self) -> str:
        """Return e.g. ``"precipitation: rovesci o temporali..., 39.1 km SSE"``."""
        what = (
            f"{self.category}: {self.description}"
            if self.category is not None
            else f"phenomenon {self.code}"
        )
        return f"{what}, {self.distance_km} km {self.direction}"


@dataclass(frozen=True, slots=True)
class VigilanceDay:
    """The expected weather at a location for one day."""

    date: dt.date
    """Calendar day covered by the forecast."""
    offset: int
    """Day of the bulletin: 0 publication day, 1 next day, 2 the day after."""
    valid_until: dt.datetime
    """End of validity: the midnight (Europe/Rome) that ends ``date``."""
    zone: str
    """Name of the DPC vigilance zone (e.g. ``"Comune di Roma"``)."""
    precipitation: Precipitation
    """Expected daily precipitation of the zone."""
    image_url: str | None
    """Preview image of the national map; DPC publishes none for offset 2."""
    phenomena: tuple[Phenomenon, ...]
    """Significant weather phenomena near the location."""


class _Dated(Protocol):
    @property
    def date(self) -> dt.date: ...


class _Days[DayT: _Dated]:
    """Days of a bulletin, looked up by date rather than by position."""

    __slots__ = ()
    days: tuple[DayT, ...]

    def __iter__(self) -> Iterator[DayT]:
        """Iterate over the days, in order."""
        return iter(self.days)

    def __len__(self) -> int:
        """Return the number of days."""
        return len(self.days)

    def on(self, day: Day | dt.date) -> DayT | None:
        """Return the day covering a date (or ``Day.TODAY``), if any."""
        date = calendar_date(day)
        return next((item for item in self.days if item.date == date), None)

    @property
    def today(self) -> DayT | None:
        """Return the current Italian day, if the bulletin covers it."""
        return self.on(Day.TODAY)

    @property
    def tomorrow(self) -> DayT | None:
        """Return the next Italian day, if the bulletin covers it."""
        return self.on(Day.TOMORROW)


@dataclass(frozen=True, slots=True)
class CriticalityBulletin(_Days[CriticalityDay]):
    """A criticality bulletin for a location: its alert levels, day by day.

    Iterate over it for the days, or look one up with :attr:`today`,
    :attr:`tomorrow` or :meth:`on`. After midnight the bulletin published the
    day before still answers :attr:`today` with its second day.
    """

    id: str
    """Bulletin ID, e.g. ``"20261114_1430"``."""
    published: dt.datetime
    """Publication time in the ID (Europe/Rome)."""
    days: tuple[CriticalityDay, ...]
    """Assessed days, in order; expired days may have been skipped."""


@dataclass(frozen=True, slots=True)
class VigilanceBulletin(_Days[VigilanceDay]):
    """A weather vigilance bulletin for a location, day by day.

    Iterate over it for the days, or look one up with :attr:`today`,
    :attr:`tomorrow` or :meth:`on`.
    """

    id: str
    """Bulletin ID, e.g. ``"20261114"``."""
    date: dt.date
    """Publication day in the ID."""
    days: tuple[VigilanceDay, ...]
    """Forecast days, in order; expired days may have been skipped."""


@dataclass(frozen=True, slots=True)
class Risk:
    """The answer to "what is the risk here?" for one day."""

    level: AlertLevel
    """Highest alert level at the location."""
    types: tuple[RiskType, ...]
    """Risk types at ``level`` when it is an alert, otherwise empty."""
    description: str
    """Summary written by DPC, in Italian."""
    valid_until: dt.datetime
    """End of validity: the midnight (Europe/Rome) that ends the day."""
    day: CriticalityDay
    """The complete assessment of the day, with every risk type."""

    @classmethod
    def of(cls, day: CriticalityDay) -> Risk:
        """Return the risk of a criticality day."""
        types = tuple(
            item.type for item in day.risks if item.is_alert and item.level is day.level
        )
        return cls(
            level=day.level,
            types=types,
            description=day.description,
            valid_until=day.valid_until,
            day=day,
        )

    @property
    def is_alert(self) -> bool:
        """Return whether there is an alert: yellow or higher."""
        return self.level.is_alert

    def __str__(self) -> str:
        """Return e.g. ``"orange (hydrogeological)"`` or ``"green"``."""
        if not self.types:
            return str(self.level)
        return f"{self.level} ({', '.join(self.types)})"
