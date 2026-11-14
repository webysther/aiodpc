"""Tests on excerpts of real DPC data, to guard the real format.

The fixtures in ``fixtures/real`` are unmodified features of the bulletins of
2026-11-13 (criticality 20261113_1434 "today", vigilance 20261113 "oggi" and
its phenomena, complete) and the elements of the DPC map pages that link
them. The expected values were computed with the DPC Alert integration code on
the complete files.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from aiodpc import AlertLevel, Location, PhenomenonCategory, Precipitation, RiskType
from aiodpc.parsers import (
    Assessment,
    parse_criticality_day,
    parse_phenomena,
    parse_vigilance_day,
)

from . import ROME, load_json, rome

if TYPE_CHECKING:
    from aiodpc import CriticalityDay

CRIT_ID = "20261113_1434"
VIGI_ID = "20261113"
# In the "Chiani - Paglia" zone, near Città della Pieve, which is also listed by
# the "Trasimeno - Nestore" zone
CHIANI = (42.91, 11.98)

GREEN = Assessment(AlertLevel.GREEN, "Assenza di fenomeni significativi prevedibili")
YELLOW = Assessment(AlertLevel.YELLOW, "Ordinaria")
ORANGE = Assessment(AlertLevel.ORANGE, "Moderata")


def assessments(day: CriticalityDay) -> dict[RiskType, Assessment]:
    """Return the level and description of each risk type of a day."""
    return {item.type: Assessment(item.level, item.description) for item in day.risks}


def criticality_today() -> object:
    """Return the excerpt of the criticality file."""
    return load_json("real/criticality_20261113_1434_today.json")


def test_criticality_by_coordinates() -> None:
    """Test the criticality at Rome."""
    day = parse_criticality_day(
        criticality_today(), bulletin_id=CRIT_ID, offset=0, location=ROME
    )

    assert day.date == dt.date(2026, 11, 13)
    assert day.valid_until == rome(2026, 11, 14)
    assert day.zone == "Bacini di Roma"
    assert day.level is AlertLevel.YELLOW
    assert day.description == "Ordinaria per rischio idrogeologico"
    assert assessments(day) == {
        RiskType.HYDRAULIC: GREEN,
        RiskType.THUNDERSTORMS: GREEN,
        RiskType.HYDROGEOLOGICAL: YELLOW,
    }


@pytest.mark.parametrize(
    ("municipality", "summary", "risks"),
    [
        (
            None,
            Assessment(AlertLevel.YELLOW, "Ordinaria per rischio idraulico"),
            dict.fromkeys(RiskType, YELLOW),
        ),
        # The municipality is also in an orange zone, which wins
        (
            "Città della Pieve",
            Assessment(AlertLevel.ORANGE, "Moderata per rischio idrogeologico"),
            {
                RiskType.HYDRAULIC: YELLOW,
                RiskType.THUNDERSTORMS: YELLOW,
                RiskType.HYDROGEOLOGICAL: ORANGE,
            },
        ),
    ],
)
def test_criticality_by_municipality(
    municipality: str | None, summary: Assessment, risks: dict[RiskType, Assessment]
) -> None:
    """Test a municipality spanning two zones with different levels."""
    day = parse_criticality_day(
        criticality_today(),
        bulletin_id=CRIT_ID,
        offset=0,
        location=Location(*CHIANI, municipality=municipality),
    )

    assert day.zone == "Chiani - Paglia"
    assert (day.level, day.description) == summary
    assert assessments(day) == risks


@pytest.mark.parametrize(
    ("municipality", "precipitation"),
    [(None, Precipitation.LIGHT), ("Roma", Precipitation.MODERATE)],
)
def test_vigilance(municipality: str | None, precipitation: Precipitation) -> None:
    """Test the vigilance at Rome; Roma also lies in a zone with more rain."""
    day = parse_vigilance_day(
        load_json("real/vigilance_20261113_oggi.json"),
        bulletin_id=VIGI_ID,
        offset=0,
        location=Location(*ROME.coordinates, municipality=municipality),
    )

    assert day.zone == "Comune di Roma"
    assert day.precipitation is precipitation


def test_phenomena() -> None:
    """Test the phenomena within 50 km of Rome."""
    phenomena = parse_phenomena(
        load_json("real/phenomena_20261113_oggi.json"), location=ROME, within_km=50
    )

    assert [
        (
            item.code,
            item.category,
            item.latitude,
            item.longitude,
            item.distance_km,
            item.direction,
            item.degrees,
            item.bulletin_id,
            item.bulletin_date,
        )
        for item in phenomena
    ] == [
        (
            5,
            PhenomenonCategory.PRECIPITATION,
            41.573134169859415,
            12.674774846264892,
            39.1,
            "SSE",
            158,
            202611131,
            "2026-11-13Z",
        ),
        (
            1,
            PhenomenonCategory.PRECIPITATION,
            42.12771583180782,
            12.272329816299779,
            31.5,
            "NW",
            323,
            202611131,
            "2026-11-13Z",
        ),
        (
            10,
            PhenomenonCategory.WIND,
            41.81354327276826,
            12.151596307310248,
            30.4,
            "WSW",
            251,
            202611131,
            "2026-11-13Z",
        ),
    ]
    assert phenomena[2].description == "forti"


def test_all_phenomena_codes_are_known() -> None:
    """Test that every phenomenon of the real file has a known code."""
    phenomena = parse_phenomena(
        load_json("real/phenomena_20261113_oggi.json"), location=ROME, within_km=2000
    )

    assert len(phenomena) == 70
    assert all(item.category is not None for item in phenomena)
