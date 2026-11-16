"""Tests of the models."""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import TYPE_CHECKING

import pytest

from aiodpc import (
    ROME_TZ,
    AlertLevel,
    BulletinKind,
    CompassPoint,
    Criticality,
    CriticalityBulletin,
    CriticalityDay,
    Day,
    Location,
    Phenomenon,
    PhenomenonCategory,
    PhenomenonType,
    Precipitation,
    Risk,
    RiskAssessment,
    RiskType,
    VigilanceBulletin,
    VigilanceDay,
    rome_date,
)
from aiodpc.models import PHENOMENON_TYPE_CODES
from aiodpc.parsers import PHENOMENON_TYPES, end_of_day

from . import rome

if TYPE_CHECKING:
    from enum import Enum

NO_PHENOMENA = "Assenza di fenomeni significativi prevedibili"


def assessment(risk_type: RiskType, level: AlertLevel) -> RiskAssessment:
    """Return the assessment of a risk type."""
    return RiskAssessment(risk_type, level, NO_PHENOMENA)


def criticality_day(
    day: dt.date,
    offset: int = 0,
    levels: dict[RiskType, AlertLevel] | None = None,
) -> CriticalityDay:
    """Return a criticality day, green unless levels are given."""
    levels = {**dict.fromkeys(RiskType, AlertLevel.GREEN), **(levels or {})}
    return CriticalityDay(
        date=day,
        offset=offset,
        valid_until=end_of_day(day),
        zone="Bacini di Roma",
        level=max(levels.values()),
        description="Sintesi",
        hydraulic=assessment(RiskType.HYDRAULIC, levels[RiskType.HYDRAULIC]),
        thunderstorms=assessment(
            RiskType.THUNDERSTORMS, levels[RiskType.THUNDERSTORMS]
        ),
        hydrogeological=assessment(
            RiskType.HYDROGEOLOGICAL, levels[RiskType.HYDROGEOLOGICAL]
        ),
        image_url="https://example.invalid/preview.png",
    )


def vigilance_day(day: dt.date, offset: int) -> VigilanceDay:
    """Return a vigilance day without phenomena."""
    return VigilanceDay(
        date=day,
        offset=offset,
        valid_until=end_of_day(day),
        zone="Lazio centrale",
        precipitation=Precipitation.LIGHT,
        image_url=None,
        phenomena=(),
    )


def test_alert_level_order() -> None:
    """Test that levels compare by severity, also with integer thresholds."""
    assert AlertLevel.UNKNOWN < AlertLevel.GREEN < AlertLevel.YELLOW
    assert AlertLevel.YELLOW < AlertLevel.ORANGE < AlertLevel.RED
    assert AlertLevel.ORANGE >= 2
    assert [level.value for level in AlertLevel] == [0, 1, 2, 3, 4]


def test_alert_level_is_alert() -> None:
    """Test that yellow and higher are alerts."""
    assert [level.is_alert for level in AlertLevel] == [
        False,
        False,
        True,
        True,
        True,
    ]


def test_levels_print_as_names() -> None:
    """Test that the ordered levels print as their lower-case name."""
    assert str(AlertLevel.ORANGE) == "orange"
    assert f"{AlertLevel.YELLOW}|{AlertLevel.RED:>5}|" == "yellow|  red|"
    assert str(Precipitation.VERY_HEAVY) == "very_heavy"
    assert repr(AlertLevel.GREEN) == "<AlertLevel.GREEN: 1>"


def test_precipitation_order() -> None:
    """Test that the precipitation classes are the DPC classes, in order."""
    assert [level.value for level in Precipitation] == [0, 1, 2, 3, 4, 5]
    assert Precipitation.MODERATE > Precipitation.LIGHT


def test_enums_print_as_values() -> None:
    """Test the English values of the risk types and phenomena categories."""
    assert [str(item) for item in RiskType] == [
        "hydraulic",
        "thunderstorms",
        "hydrogeological",
    ]
    assert PhenomenonCategory("wave_motion") is PhenomenonCategory.WAVE_MOTION


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # Naive: Italian local time
        (dt.datetime(2026, 11, 14, 23, 30), dt.date(2026, 11, 14)),  # noqa: DTZ001
        # 23:30 UTC is 00:30 in Rome
        (dt.datetime(2026, 11, 14, 23, 30, tzinfo=dt.UTC), dt.date(2026, 11, 15)),
        (rome(2026, 11, 15, 0, 5), dt.date(2026, 11, 15)),
    ],
)
def test_rome_date(now: dt.datetime, expected: dt.date) -> None:
    """Test the Italian calendar date of a time."""
    assert rome_date(now) == expected


def test_rome_date_now() -> None:
    """Test the Italian calendar date of the current time."""
    assert rome_date() == dt.datetime.now(ROME_TZ).date()


def test_relative_days() -> None:
    """Test the dates of today, tomorrow and the day after."""
    late = rome(2026, 11, 14, 23, 30)

    assert Day.TODAY.date(late) == dt.date(2026, 11, 14)
    assert Day.TOMORROW.date(late) == dt.date(2026, 11, 15)
    assert Day.AFTER_TOMORROW.date(late) == dt.date(2026, 11, 16)
    assert Day.TODAY.date() == rome_date()


def test_location() -> None:
    """Test a location and its coordinates."""
    location = Location(41.9, 12.5, municipality="Roma")

    assert location.coordinates == (41.9, 12.5)
    assert location.municipality == "Roma"
    assert Location(41.9, 12.5).municipality is None


@pytest.mark.parametrize(
    ("latitude", "longitude", "error"),
    [
        (91.0, 12.5, "Invalid latitude"),
        (float("nan"), 12.5, "Invalid latitude"),
        (41.9, -180.5, "Invalid longitude"),
        (41.9, float("inf"), "Invalid longitude"),
    ],
)
def test_invalid_location(latitude: float, longitude: float, error: str) -> None:
    """Test that invalid coordinates are rejected."""
    with pytest.raises(ValueError, match=error):
        Location(latitude, longitude)


def test_criticality_day() -> None:
    """Test the risks of a day, as attributes, in order and by type."""
    day = criticality_day(
        dt.date(2026, 11, 14),
        levels={
            RiskType.HYDRAULIC: AlertLevel.YELLOW,
            RiskType.HYDROGEOLOGICAL: AlertLevel.ORANGE,
        },
    )

    assert day.is_alert
    assert [str(item) for item in day.risks] == [
        "hydraulic: yellow",
        "thunderstorms: green",
        "hydrogeological: orange",
    ]
    assert day.assessment(RiskType.HYDROGEOLOGICAL) is day.hydrogeological
    assert day.hydraulic.is_alert
    assert not day.thunderstorms.is_alert
    assert not criticality_day(dt.date(2026, 11, 14)).is_alert


def test_criticality_bulletin_lookup() -> None:
    """Test the days of a criticality bulletin, iterated and by date."""
    today = criticality_day(dt.date(2026, 11, 14), 0)
    tomorrow = criticality_day(dt.date(2026, 11, 15), 1)
    bulletin = CriticalityBulletin(
        id="20261114_1430", published=rome(2026, 11, 14, 14, 30), days=(today, tomorrow)
    )

    assert list(bulletin) == [today, tomorrow]
    assert len(bulletin) == 2
    assert bulletin.on(dt.date(2026, 11, 15)) is tomorrow
    assert bulletin.on(dt.date(2026, 11, 16)) is None
    # A datetime counts by its Italian date: 23:30 UTC is already the 15th
    assert bulletin.on(dt.datetime(2026, 11, 14, 23, 30, tzinfo=dt.UTC)) is tomorrow


def test_bulletin_today_and_tomorrow() -> None:
    """Test today and tomorrow, relative to the current Italian date."""
    current = rome_date()
    days = tuple(
        criticality_day(current + dt.timedelta(days=offset), offset)
        for offset in (-1, 0, 1)
    )
    bulletin = CriticalityBulletin(
        id="20261114_1430", published=rome(2026, 11, 14, 14, 30), days=days
    )

    assert bulletin.today is days[1]
    assert bulletin.on(Day.TODAY) is days[1]
    assert bulletin.tomorrow is days[2]

    empty = CriticalityBulletin(id="20200101_1430", published=rome(2020, 1, 1), days=())

    assert empty.today is None
    assert empty.tomorrow is None
    assert not empty


def test_vigilance_bulletin_lookup() -> None:
    """Test the lookup of the days of a vigilance bulletin by date."""
    days = tuple(
        vigilance_day(dt.date(2026, 11, 14) + dt.timedelta(days=offset), offset)
        for offset in range(3)
    )
    bulletin = VigilanceBulletin(id="20261114", date=dt.date(2026, 11, 14), days=days)

    assert bulletin.on(dt.date(2026, 11, 16)) is days[2]
    assert [day.precipitation for day in bulletin] == [Precipitation.LIGHT] * 3


def test_vigilance_bulletin_relative_days() -> None:
    """Test today, tomorrow and the day after, relative to the current date."""
    current = rome_date()
    days = tuple(
        vigilance_day(current + dt.timedelta(days=offset), offset)
        for offset in (-1, 0, 1, 2)
    )
    bulletin = VigilanceBulletin(id="20261114", date=dt.date(2026, 11, 14), days=days)

    assert bulletin.today is days[1]
    assert bulletin.tomorrow is days[2]
    assert bulletin.after_tomorrow is days[3]
    assert bulletin.on(Day.AFTER_TOMORROW) is days[3]

    # After midnight, until the next bulletin, the third day is tomorrow
    shifted = VigilanceBulletin(
        id="20261114", date=dt.date(2026, 11, 14), days=days[:3]
    )
    assert shifted.after_tomorrow is None


@pytest.mark.parametrize(
    ("levels", "expected_types", "text"),
    [
        ({}, (), "green"),
        (
            {
                RiskType.HYDRAULIC: AlertLevel.YELLOW,
                RiskType.HYDROGEOLOGICAL: AlertLevel.ORANGE,
            },
            (RiskType.HYDROGEOLOGICAL,),
            "orange (hydrogeological)",
        ),
        (
            dict.fromkeys(RiskType, AlertLevel.RED),
            tuple(RiskType),
            "red (hydraulic, thunderstorms, hydrogeological)",
        ),
    ],
)
def test_risk(
    levels: dict[RiskType, AlertLevel],
    expected_types: tuple[RiskType, ...],
    text: str,
) -> None:
    """Test the risk of a day: its level and the risk types at that level."""
    day = criticality_day(dt.date(2026, 11, 14), levels=levels)

    risk = Risk.of(day)

    assert risk.level is day.level
    assert risk.types == expected_types
    assert risk.is_alert is bool(expected_types)
    assert risk.description == "Sintesi"
    assert risk.valid_until == rome(2026, 11, 15)
    assert risk.day is day
    assert str(risk) == text


def test_phenomenon_text() -> None:
    """Test the readable text of phenomena, known or not."""
    known = Phenomenon(
        code=10,
        category=PhenomenonCategory.WIND,
        description="forti",
        latitude=41.8,
        longitude=12.1,
        distance_km=30.4,
        direction=CompassPoint.WSW,
        degrees=251,
        bulletin_id=None,
        bulletin_date=None,
    )
    unknown = dataclasses.replace(known, code=99, category=None, description=None)

    assert str(known) == "wind: forti, 30.4 km WSW"
    assert str(unknown) == "phenomenon 99, 30.4 km WSW"
    assert known.type is PhenomenonType.STRONG_WIND
    assert unknown.type is None


def test_every_phenomenon_code_has_a_type() -> None:
    """Test that the types cover exactly the codes of the DPC legend."""
    assert PHENOMENON_TYPE_CODES.keys() == PHENOMENON_TYPES.keys()
    assert len(set(PHENOMENON_TYPE_CODES.values())) == len(PhenomenonType)
    assert PhenomenonType.of(40) is PhenomenonType.MODERATE_SEA
    assert PhenomenonType.of(99) is None
    assert str(PhenomenonType.LIGHT_SNOW) == "light_snow"


def test_phenomenon_key() -> None:
    """Test that the code and position identify a phenomenon, not the distance."""
    showers = Phenomenon(
        code=5,
        category=PhenomenonCategory.PRECIPITATION,
        description="rovesci o temporali a carattere isolato",
        latitude=41.57313417,
        longitude=12.67477485,
        distance_km=39.1,
        direction=CompassPoint.SSE,
        degrees=158,
        bulletin_id=202611141,
        bulletin_date="2026-11-14Z",
    )
    # The same phenomenon in the next bulletin, read at another place
    elsewhere = dataclasses.replace(
        showers,
        distance_km=12.0,
        direction=CompassPoint.N,
        degrees=2,
        bulletin_id=202611152,
    )

    assert showers.key == "5@41.57313417,12.67477485"
    assert elsewhere.key == showers.key
    assert dataclasses.replace(showers, code=6).key != showers.key
    assert dataclasses.replace(showers, longitude=12.7).key != showers.key


def test_models_are_hashable_and_convertible() -> None:
    """Test that the frozen models hash and convert to dicts."""
    day = criticality_day(dt.date(2026, 11, 14), 0)

    assert hash(day) == hash(criticality_day(dt.date(2026, 11, 14), 0))
    assert dataclasses.asdict(day)["hydraulic"]["level"] is AlertLevel.GREEN
    with pytest.raises(dataclasses.FrozenInstanceError):
        day.zone = "Altro"  # type: ignore[misc]


CODED: tuple[type[Enum], ...] = (
    AlertLevel,
    BulletinKind,
    CompassPoint,
    Criticality,
    Day,
    PhenomenonCategory,
    PhenomenonType,
    Precipitation,
    RiskType,
)


@pytest.mark.parametrize("enum", CODED)
def test_codes(enum: type[Enum]) -> None:
    """Every value has its own numeric code, and the code gives the value back."""
    codes = [member.code for member in enum]  # type: ignore[attr-defined] # every enum of CODED has codes
    assert len(set(codes)) == len(codes)
    for member in enum:
        assert enum.from_code(member.code) is member  # type: ignore[attr-defined] # as above
    assert enum.from_code(-1) is None  # type: ignore[attr-defined] # as above


def test_codes_of_dpc() -> None:
    """The codes DPC publishes are the codes of the values."""
    for code, (category, _legend) in PHENOMENON_TYPES.items():
        phenomenon_type = PhenomenonType.of(code)
        assert phenomenon_type is not None
        assert phenomenon_type.code == code
        assert PhenomenonType.from_code(code) is phenomenon_type
        assert category.code == code // 10
    assert [level.code for level in Precipitation] == [0, 1, 2, 3, 4, 5]
    assert [point.code for point in CompassPoint][:5] == [0, 1, 2, 3, 4]
    assert CompassPoint.from_code(12) is CompassPoint.W
    assert Day.from_code(1) is Day.TOMORROW
