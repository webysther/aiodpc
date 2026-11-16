"""Typed models of the DPC bulletins."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum
from typing import TYPE_CHECKING, Any, Final, Protocol, Self

from .const import ROME_TZ

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

_MAX_LATITUDE: Final = 90.0
_MAX_LONGITUDE: Final = 180.0


class _NamedLevel(IntEnum):
    """Ordered level shown by its lower-case name: ``str(level) == "yellow"``."""

    def __str__(self) -> str:
        return self.name.lower()

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)

    @property
    def code(self) -> int:
        """Return the numeric code of the value: its number, e.g. 2 for yellow."""
        return int(self)

    @classmethod
    def from_code(cls, code: int) -> Self | None:
        """Return the value of a numeric code; None when no value has it."""
        return next((member for member in cls if member.code == code), None)


class _Coded(StrEnum):
    """A value named by a text, with a numeric code from its table of codes."""

    @property
    def code(self) -> int:
        """Return the numeric code of the value (see the data dictionary)."""
        return _CODES[type(self)][self]

    @classmethod
    def from_code(cls, code: int) -> Self | None:
        """Return the value of a numeric code; None when no value has it."""
        return next((member for member in cls if member.code == code), None)


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


def _words(text: str) -> str:
    """Return a DPC text in lower case, with single spaces between its words."""
    return " ".join(text.split()).casefold()


class Criticality(_NamedLevel):
    """Criticality of an alert zone, as DPC writes it, ordered by severity.

    DPC states each assessment twice: as a criticality (``"Ordinaria"``) and as
    an alert (``"ALLERTA GIALLA"``). Every bulletin since 2020 pairs them the
    same way: absent with green, ordinary with yellow, moderate with orange and
    high with red. Criticalities print as their name (``"ordinary"``).
    """

    UNKNOWN = 0
    """The text is missing or not recognised."""
    ABSENT = 1
    """"Assenza di fenomeni significativi prevedibili": no significant
    phenomena expected."""
    ORDINARY = 2
    """"Ordinaria": ordinary criticality, with a yellow alert."""
    MODERATE = 3
    """"Moderata": moderate criticality, with an orange alert."""
    HIGH = 4
    """"Elevata": high criticality, with a red alert."""

    @classmethod
    def of(cls, text: str) -> Criticality:
        """Return the criticality a DPC text starts with; UNKNOWN when none.

        E.g. ordinary for ``"Ordinaria"``, ``"Ordinaria per rischio
        idrogeologico"`` or ``"ORDINARIA CRITICITA' PER RISCHIO IDRAULICO"``.
        """
        words = _words(text)
        return next(
            (
                criticality
                for prefix, criticality in CRITICALITY_TEXTS.items()
                if words == prefix or words.startswith(f"{prefix} ")
            ),
            cls.UNKNOWN,
        )


CRITICALITY_TEXTS: Final[Mapping[str, Criticality]] = {
    "assenza di fenomeni significativi prevedibili": Criticality.ABSENT,
    "ordinaria": Criticality.ORDINARY,
    "moderata": Criticality.MODERATE,
    "elevata": Criticality.HIGH,
}
"""How each criticality starts in the DPC texts, in lower case.

Measured: the summaries of the 2572 bulletins published from 2020 to November
2026, and every zone of 73 of them chosen for their red and orange alerts and
for their days with several risks, use only these four.
"""


class RiskType(_Coded):
    """Risk assessed by the criticality bulletin."""

    HYDRAULIC = "hydraulic"
    """Rischio idraulico: flooding of the main rivers."""
    THUNDERSTORMS = "thunderstorms"
    """Rischio temporali: effects of thunderstorms on the ground."""
    HYDROGEOLOGICAL = "hydrogeological"
    """Rischio idrogeologico: landslides and flooding of the minor streams."""

    @classmethod
    def named_in(cls, text: str) -> RiskType | None:
        """Return the risk a DPC text names after "per rischio", if any.

        E.g. thunderstorms for ``"Ordinaria per rischio temporali"``; None for
        ``"Ordinaria"`` or a risk unknown to aiodpc.
        """
        _before, found, after = _words(text).partition(RISK_NAME_PREFIX)
        names = after.split()
        if not found or not names:
            return None
        return RISK_TYPE_NAMES.get(names[0])


RISK_TYPE_CODES: Final[Mapping[RiskType, int]] = {
    RiskType.HYDRAULIC: 1,
    RiskType.THUNDERSTORMS: 2,
    RiskType.HYDROGEOLOGICAL: 3,
}
"""Codes of the risks, proposed by aiodpc: the order of their DPC properties
("Per rischio idraulico", "Per rischio temporali", "Per rischio
idrogeologico")."""

RISK_NAME_PREFIX: Final = "per rischio "
"""What precedes the name of a risk in the DPC texts, in lower case."""

RISK_TYPE_NAMES: Final[Mapping[str, RiskType]] = {
    "idraulico": RiskType.HYDRAULIC,
    "temporali": RiskType.THUNDERSTORMS,
    "idrogeologico": RiskType.HYDROGEOLOGICAL,
}
"""The Italian name of each risk in the DPC texts (``"per rischio temporali"``)."""


class CompassPoint(_Coded):
    """A point of the 16-point compass rose, as its English abbreviation."""

    N = "N"
    NNE = "NNE"
    NE = "NE"
    ENE = "ENE"
    E = "E"
    ESE = "ESE"
    SE = "SE"
    SSE = "SSE"
    S = "S"
    SSW = "SSW"
    SW = "SW"
    WSW = "WSW"
    W = "W"
    WNW = "WNW"
    NW = "NW"
    NNW = "NNW"


COMPASS_POINT_CODES: Final[Mapping[CompassPoint, int]] = {
    point: index for index, point in enumerate(CompassPoint)
}
"""Codes of the compass points, proposed by aiodpc: 0 for north, then
clockwise, 22.5 degrees apart."""


class PhenomenonCategory(_Coded):
    """Category of a weather phenomenon of the vigilance bulletin."""

    PRECIPITATION = "precipitation"
    WIND = "wind"
    FROST = "frost"
    FOG = "fog"
    SEA = "sea"
    WAVE_MOTION = "wave_motion"
    TEMPERATURE = "temperature"


PHENOMENON_CATEGORY_CODES: Final[Mapping[PhenomenonCategory, int]] = {
    PhenomenonCategory.PRECIPITATION: 0,
    PhenomenonCategory.WIND: 1,
    PhenomenonCategory.FROST: 2,
    PhenomenonCategory.FOG: 3,
    PhenomenonCategory.SEA: 4,
    PhenomenonCategory.WAVE_MOTION: 5,
    PhenomenonCategory.TEMPERATURE: 6,
}
"""Codes of the categories, proposed by aiodpc: the tens of the DPC codes of
their phenomena (``id_fenomeno // 10``)."""


class PhenomenonType(_Coded):
    """Type of a weather phenomenon of the vigilance bulletin, from its DPC code.

    The names say in English what the DPC legend says in Italian, which
    :attr:`Phenomenon.description` keeps as DPC writes it. Each type belongs to
    one :class:`PhenomenonCategory`.
    """

    SCATTERED_RAIN = "scattered_rain"
    """1, "piogge sparse o intermittenti": scattered or intermittent rain."""
    WIDESPREAD_RAIN = "widespread_rain"
    """2, "piogge diffuse e continue": widespread and continuous rain."""
    LIGHT_SNOW = "light_snow"
    """3, "nevicate deboli o moderate": light or moderate snowfall."""
    HEAVY_SNOW = "heavy_snow"
    """4, "nevicate abbondanti": heavy snowfall."""
    ISOLATED_THUNDERSTORMS = "isolated_thunderstorms"
    """5, "rovesci o temporali a carattere isolato": isolated showers or storms."""
    SCATTERED_THUNDERSTORMS = "scattered_thunderstorms"
    """6, "rovesci o temporali a carattere sparso": scattered showers or storms."""
    WIDESPREAD_THUNDERSTORMS = "widespread_thunderstorms"
    """7, "rovesci o temporali a carattere diffuso": widespread showers or storms."""
    STRONG_WIND = "strong_wind"
    """10, "forti": strong wind."""
    GALE = "gale"
    """11, "burrasca": gale."""
    STORM = "storm"
    """12, "tempesta": storm."""
    FREQUENT_GUSTS = "frequent_gusts"
    """13, "frequenti raffiche": frequent gusts."""
    ICE_ON_HILLS = "ice_on_hills"
    """20, "diffusa formazione di ghiaccio al suolo a quote collinari"."""
    ICE_ON_PLAINS = "ice_on_plains"
    """21, "diffusa formazione di ghiaccio al suolo a quote di pianura"."""
    NIGHT_FOG = "night_fog"
    """30, "diffuse nelle ore notturne e del primo mattino": fog at night."""
    PERSISTENT_FOG = "persistent_fog"
    """31, "diffuse e persistenti anche nelle ore diurne": fog also by day."""
    MODERATE_SEA = "moderate_sea"
    """40, "molto mosso": moderate sea, 4 on the Douglas scale."""
    ROUGH_SEA = "rough_sea"
    """41, "agitato o molto agitato": rough or very rough sea, 5 or 6."""
    HIGH_SEA = "high_sea"
    """42, "grosso o molto grosso": high or very high sea, 7 or 8."""
    RISING_WAVES = "rising_waves"
    """50, "in aumento": waves rising."""
    FALLING_WAVES = "falling_waves"
    """51, "in diminuzione": waves falling."""
    HIGH_TEMPERATURES = "high_temperatures"
    """60, "elevate o in sensibile aumento": high or noticeably rising."""
    VERY_HIGH_TEMPERATURES = "very_high_temperatures"
    """61, "molto elevate o in marcato aumento": very high or sharply rising."""
    LOW_TEMPERATURES = "low_temperatures"
    """62, "basse o in sensibile calo": low or noticeably falling."""
    VERY_LOW_TEMPERATURES = "very_low_temperatures"
    """63, "molto basse o in marcato calo": very low or sharply falling."""

    @classmethod
    def of(cls, code: int) -> PhenomenonType | None:
        """Return the type of a DPC phenomenon code; None when it is unknown."""
        return PHENOMENON_TYPE_CODES.get(code)


PHENOMENON_TYPE_CODES: Final[Mapping[int, PhenomenonType]] = {
    1: PhenomenonType.SCATTERED_RAIN,
    2: PhenomenonType.WIDESPREAD_RAIN,
    3: PhenomenonType.LIGHT_SNOW,
    4: PhenomenonType.HEAVY_SNOW,
    5: PhenomenonType.ISOLATED_THUNDERSTORMS,
    6: PhenomenonType.SCATTERED_THUNDERSTORMS,
    7: PhenomenonType.WIDESPREAD_THUNDERSTORMS,
    10: PhenomenonType.STRONG_WIND,
    11: PhenomenonType.GALE,
    12: PhenomenonType.STORM,
    13: PhenomenonType.FREQUENT_GUSTS,
    20: PhenomenonType.ICE_ON_HILLS,
    21: PhenomenonType.ICE_ON_PLAINS,
    30: PhenomenonType.NIGHT_FOG,
    31: PhenomenonType.PERSISTENT_FOG,
    40: PhenomenonType.MODERATE_SEA,
    41: PhenomenonType.ROUGH_SEA,
    42: PhenomenonType.HIGH_SEA,
    50: PhenomenonType.RISING_WAVES,
    51: PhenomenonType.FALLING_WAVES,
    60: PhenomenonType.HIGH_TEMPERATURES,
    61: PhenomenonType.VERY_HIGH_TEMPERATURES,
    62: PhenomenonType.LOW_TEMPERATURES,
    63: PhenomenonType.VERY_LOW_TEMPERATURES,
}
"""The type of each DPC phenomenon code (``id_fenomeno``), as in the legend."""

_PHENOMENON_TYPE_NUMBERS: Final[Mapping[PhenomenonType, int]] = {
    phenomenon_type: code for code, phenomenon_type in PHENOMENON_TYPE_CODES.items()
}
"""The code of each phenomenon type: the DPC ``id_fenomeno``."""


class BulletinKind(_Coded):
    """Kind of DPC bulletin."""

    CRITICALITY = "criticality"
    """Bollettino di criticità idrogeologica e idraulica: the alert levels."""
    VIGILANCE = "vigilance"
    """Bollettino di vigilanza meteorologica: the expected weather."""


BULLETIN_KIND_CODES: Final[Mapping[BulletinKind, int]] = {
    BulletinKind.CRITICALITY: 1,
    BulletinKind.VIGILANCE: 2,
}
"""Codes of the bulletins, proposed by aiodpc."""

_CODES: Final[Mapping[type[_Coded], Mapping[Any, int]]] = {
    RiskType: RISK_TYPE_CODES,
    CompassPoint: COMPASS_POINT_CODES,
    PhenomenonCategory: PHENOMENON_CATEGORY_CODES,
    PhenomenonType: _PHENOMENON_TYPE_NUMBERS,
    BulletinKind: BULLETIN_KIND_CODES,
}
"""The table of codes of each enum named by a text."""


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
    """A day relative to the current Italian date.

    The criticality bulletin covers today and tomorrow, the vigilance bulletin
    the day after tomorrow too.
    """

    TODAY = 0
    TOMORROW = 1
    AFTER_TOMORROW = 2

    def date(self, now: dt.datetime | None = None) -> dt.date:
        """Return the calendar date of the day at ``now`` (default: now)."""
        return rome_date(now) + dt.timedelta(days=self.value)

    @property
    def code(self) -> int:
        """Return the numeric code of the day: the days after today."""
        return int(self.value)

    @classmethod
    def from_code(cls, code: int) -> Day | None:
        """Return the day of a numeric code; None when no day has it."""
        return next((member for member in cls if member.code == code), None)


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

    @property
    def criticality(self) -> Criticality:
        """Return the criticality of the description (ordinary for "Ordinaria")."""
        return Criticality.of(self.description)

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
    def criticality(self) -> Criticality:
        """Return the criticality of the summary (ordinary for "Ordinaria...")."""
        return Criticality.of(self.description)

    @property
    def mapped_risk(self) -> RiskType | None:
        """Return the risk the summary names, the one the DPC map shows.

        DPC names one risk even when others have the same level (see
        :attr:`Risk.types` for all of them); None for a green zone.
        """
        return RiskType.named_in(self.description)

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
    direction: CompassPoint
    """Compass point from the location to the phenomenon (e.g. ``"NNE"``)."""
    degrees: int
    """Initial bearing from the location to the phenomenon (0-359)."""
    bulletin_id: int | None
    """DPC ``id_bollettino`` of the phenomenon, as provided."""
    bulletin_date: str | None
    """DPC ``data_bollettino`` of the phenomenon, as provided."""

    @property
    def type(self) -> PhenomenonType | None:
        """Return the type of the phenomenon, None when the code is unknown."""
        return PhenomenonType.of(self.code)

    @property
    def key(self) -> str:
        """Return what identifies the phenomenon among those of its day.

        Its code and position, e.g. ``"5@41.57313417,12.67477485"``: a later
        bulletin with the same phenomenon at the same place, for the same day,
        gives the same key. The distance and direction are not part of it:
        they depend on the location the bulletin was read at.
        """
        return f"{self.code}@{self.latitude},{self.longitude}"

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
    :attr:`tomorrow`, :attr:`after_tomorrow` or :meth:`on`.
    """

    id: str
    """Bulletin ID, e.g. ``"20261114"``."""
    date: dt.date
    """Publication day in the ID."""
    days: tuple[VigilanceDay, ...]
    """Forecast days, in order; expired days may have been skipped."""

    @property
    def after_tomorrow(self) -> VigilanceDay | None:
        """Return the day after the next Italian day, if the bulletin covers it."""
        return self.on(Day.AFTER_TOMORROW)


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

    @property
    def criticality(self) -> Criticality:
        """Return the criticality of the description (ordinary for "Ordinaria...")."""
        return Criticality.of(self.description)

    @property
    def mapped_risk(self) -> RiskType | None:
        """Return the risk the description names, the one the DPC map shows."""
        return RiskType.named_in(self.description)

    def __str__(self) -> str:
        """Return e.g. ``"orange (hydrogeological)"`` or ``"green"``."""
        if not self.types:
            return str(self.level)
        return f"{self.level} ({', '.join(self.types)})"
