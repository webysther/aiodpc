"""Tests on excerpts of real DPC data, to guard the real format.

The fixtures in ``fixtures/real`` are unmodified features of the bulletins of
2026-11-13 (criticality 20261113_1434 "today", vigilance 20261113 "oggi" and
its phenomena, complete) and the elements of the DPC map pages that link
them. The expected values were computed with the DPC Alert integration code on
the complete files.
"""

from __future__ import annotations

import datetime as dt

import pytest

from aiodpc import AlertLevel, Assessment, PhenomenonCategory, Risk
from aiodpc.parsers import parse_criticality_day, parse_phenomena, parse_vigilance_day

from . import load_json, rome

CRIT_ID = "20261113_1434"
VIGI_ID = "20261113"
ROME = (41.9, 12.5)
# In the "Chiani - Paglia" zone, near Città della Pieve, which is also listed by
# the "Trasimeno - Nestore" zone
CHIANI = (42.91, 11.98)

NONE = "Assenza di fenomeni significativi prevedibili"
GREEN = Assessment(NONE, "NESSUNA ALLERTA", AlertLevel.NONE)
YELLOW = Assessment("Ordinaria", "ALLERTA GIALLA", AlertLevel.YELLOW)
ORANGE = Assessment("Moderata", "ALLERTA ARANCIONE", AlertLevel.ORANGE)


def criticality_today() -> object:
    """Return the excerpt of the criticality file."""
    return load_json("real/criticality_20261113_1434_today.json")


def test_criticality_by_coordinates() -> None:
    """Test the criticality at Rome."""
    day = parse_criticality_day(
        criticality_today(),
        bulletin_id=CRIT_ID,
        offset=0,
        latitude=ROME[0],
        longitude=ROME[1],
    )

    assert day.date == dt.date(2026, 11, 13)
    assert day.expires == rome(2026, 11, 14)
    assert day.zone_name == "Bacini di Roma"
    assert day.summary == Assessment(
        "Ordinaria per rischio idrogeologico", "ALLERTA GIALLA", AlertLevel.YELLOW
    )
    assert day.risks == {
        Risk.HYDRAULIC: GREEN,
        Risk.THUNDERSTORMS: GREEN,
        Risk.HYDROGEOLOGICAL: YELLOW,
    }


@pytest.mark.parametrize(
    ("municipality", "summary", "risks"),
    [
        (
            None,
            Assessment(
                "Ordinaria per rischio idraulico", "ALLERTA GIALLA", AlertLevel.YELLOW
            ),
            dict.fromkeys(Risk, YELLOW),
        ),
        # The municipality is also in an orange zone, which wins
        (
            "Città della Pieve",
            Assessment(
                "Moderata per rischio idrogeologico",
                "ALLERTA ARANCIONE",
                AlertLevel.ORANGE,
            ),
            {
                Risk.HYDRAULIC: YELLOW,
                Risk.THUNDERSTORMS: YELLOW,
                Risk.HYDROGEOLOGICAL: ORANGE,
            },
        ),
    ],
)
def test_criticality_by_municipality(
    municipality: str | None, summary: Assessment, risks: dict[Risk, Assessment]
) -> None:
    """Test a municipality spanning two zones with different levels."""
    day = parse_criticality_day(
        criticality_today(),
        bulletin_id=CRIT_ID,
        offset=0,
        latitude=CHIANI[0],
        longitude=CHIANI[1],
        municipality=municipality,
    )

    assert day.zone_name == "Chiani - Paglia"
    assert day.summary == summary
    assert day.risks == risks


@pytest.mark.parametrize(
    ("municipality", "level", "precipitation"),
    [(None, 2, "Deboli"), ("Roma", 3, "Moderati")],
)
def test_vigilance(municipality: str | None, level: int, precipitation: str) -> None:
    """Test the vigilance at Rome; Roma also lies in a zone with more rain."""
    day = parse_vigilance_day(
        load_json("real/vigilance_20261113_oggi.json"),
        bulletin_id=VIGI_ID,
        offset=0,
        latitude=ROME[0],
        longitude=ROME[1],
        municipality=municipality,
    )

    assert day.zone_name == "Comune di Roma"
    assert day.level == level
    assert day.precipitation == precipitation


def test_phenomena() -> None:
    """Test the phenomena within 50 km of Rome."""
    phenomena = parse_phenomena(
        load_json("real/phenomena_20261113_oggi.json"),
        latitude=ROME[0],
        longitude=ROME[1],
        radius_km=50,
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
        load_json("real/phenomena_20261113_oggi.json"),
        latitude=ROME[0],
        longitude=ROME[1],
        radius_km=2000,
    )

    assert len(phenomena) == 70
    assert all(item.category is not None for item in phenomena)
