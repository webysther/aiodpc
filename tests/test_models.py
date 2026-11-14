"""Tests of the models."""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from aiodpc import (
    ROME_TZ,
    AlertLevel,
    Assessment,
    CriticalityBulletin,
    CriticalityDay,
    Risk,
    VigilanceBulletin,
    VigilanceDay,
    rome_date,
)
from aiodpc.parsers import day_expires

from . import rome

GREEN = Assessment(
    "Assenza di fenomeni significativi prevedibili", "NESSUNA ALLERTA", AlertLevel.NONE
)


def criticality_day(
    day: dt.date, offset: int, risks: dict[Risk, Assessment] | None = None
) -> CriticalityDay:
    """Return a criticality day with green assessments by default."""
    return CriticalityDay(
        date=day,
        offset=offset,
        expires=day_expires(day),
        zone_name="Bacini di Roma",
        summary=GREEN,
        risks=risks or dict.fromkeys(Risk, GREEN),
        image_url="https://example.invalid/preview.png",
    )


def vigilance_day(day: dt.date, offset: int) -> VigilanceDay:
    """Return a vigilance day without phenomena."""
    return VigilanceDay(
        date=day,
        offset=offset,
        expires=day_expires(day),
        zone_name="Lazio centrale",
        level=2,
        precipitation="Deboli",
        image_url=None,
        phenomena=(),
    )


def test_alert_level_order() -> None:
    """Test that levels compare by severity, also with integer thresholds."""
    assert AlertLevel.UNKNOWN < AlertLevel.NONE < AlertLevel.YELLOW
    assert AlertLevel.YELLOW < AlertLevel.ORANGE < AlertLevel.RED
    assert AlertLevel.ORANGE >= 2
    assert [level.value for level in AlertLevel] == [0, 1, 2, 3, 4]


def test_risk_codes() -> None:
    """Test that risks map to the DPC codes."""
    assert Risk("idraulico") is Risk.HYDRAULIC
    assert Risk("temporali") is Risk.THUNDERSTORMS
    assert Risk("idrogeologico") is Risk.HYDROGEOLOGICAL


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


def test_criticality_bulletin_lookup() -> None:
    """Test the lookup of the days of a criticality bulletin by date."""
    today = criticality_day(dt.date(2026, 11, 14), 0)
    tomorrow = criticality_day(dt.date(2026, 11, 15), 1)
    bulletin = CriticalityBulletin(
        id="20261114_1430", published=rome(2026, 11, 14, 14, 30), days=(today, tomorrow)
    )

    assert bulletin.day_for(dt.date(2026, 11, 15)) is tomorrow
    assert bulletin.day_for(dt.date(2026, 11, 16)) is None
    assert bulletin.today(rome(2026, 11, 14, 17)) is today
    assert bulletin.tomorrow(rome(2026, 11, 14, 17)) is tomorrow
    # After midnight the second day is today and there is no tomorrow yet
    assert bulletin.today(rome(2026, 11, 15, 0, 10)) is tomorrow
    assert bulletin.tomorrow(rome(2026, 11, 15, 0, 10)) is None


def test_vigilance_bulletin_lookup() -> None:
    """Test the lookup of the days of a vigilance bulletin by date."""
    days = tuple(
        vigilance_day(dt.date(2026, 11, 14) + dt.timedelta(days=offset), offset)
        for offset in range(3)
    )
    bulletin = VigilanceBulletin(id="20261114", date=dt.date(2026, 11, 14), days=days)

    assert bulletin.day_for(dt.date(2026, 11, 16)) is days[2]
    assert bulletin.today(rome(2026, 11, 15, 8)) is days[1]
    assert bulletin.tomorrow(rome(2026, 11, 15, 8)) is days[2]
    assert bulletin.tomorrow(rome(2026, 11, 16, 8)) is None


def test_max_level() -> None:
    """Test the highest level of a day, across the summary and the risks."""
    orange = Assessment("Moderata", "ALLERTA ARANCIONE", AlertLevel.ORANGE)
    day = criticality_day(
        dt.date(2026, 11, 14), 0, {**dict.fromkeys(Risk, GREEN), Risk.HYDRAULIC: orange}
    )

    assert day.max_level is AlertLevel.ORANGE


def test_models_are_hashable_and_convertible() -> None:
    """Test that the frozen models hash and convert to dicts."""
    day = criticality_day(dt.date(2026, 11, 14), 0)

    assert hash(day) == hash(criticality_day(dt.date(2026, 11, 14), 0))
    assert dataclasses.asdict(day)["risks"][Risk.HYDRAULIC]["level"] is AlertLevel.NONE
    with pytest.raises(dataclasses.FrozenInstanceError):
        day.zone_name = "Altro"  # type: ignore[misc]
