"""Tests of aiodpc."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import TYPE_CHECKING

from aiodpc import CRITICALITY_PAGE_URL, ROME_TZ, VIGILANCE_PAGE_URL, Location
from aiodpc.urls import (
    criticality_geojson_url,
    phenomena_geojson_url,
    vigilance_geojson_url,
)

if TYPE_CHECKING:
    from .server import FakeDpc

FIXTURES = Path(__file__).parent / "fixtures"

# A location in Rome, inside the zones of the fixtures
LATITUDE = 41.9
LONGITUDE = 12.5
ROME = Location(LATITUDE, LONGITUDE)
# A location in Paris, outside every DPC zone
PARIS = Location(48.8566, 2.3522)

# Bulletins served by default: criticality published on 2026-11-14 at 14:30
CRIT_ID = "20261114_1430"
VIGI_ID = "20261114"

CRITICALITY_FILES = ("criticality_today.json", "criticality_tomorrow.json")
VIGILANCE_FILES = (
    "vigilance_oggi.json",
    "vigilance_domani.json",
    "vigilance_dopodomani.json",
)
PHENOMENA_FILES = (
    "phenomena_oggi.json",
    "phenomena_domani.json",
    "phenomena_dopodomani.json",
)


def rome(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0
) -> dt.datetime:
    """Return an aware datetime in Europe/Rome."""
    return dt.datetime(year, month, day, hour, minute, tzinfo=ROME_TZ)


# Publication day, after both bulletins are out
PUBLICATION_DAY = rome(2026, 11, 14, 17)


def load_fixture(name: str) -> str:
    """Return the text of a fixture file."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json(name: str) -> object:
    """Return the decoded JSON of a fixture file."""
    data: object = json.loads(load_fixture(name))
    return data


def bulletin_page(bulletin_id: str) -> str:
    """Return a minimal DPC map page that links the given bulletin."""
    return (
        '<html><body><a href="https://mappe.protezionecivile.gov.it/?id='
        f'{bulletin_id}.json&amp;hidden=info,minimap,">Bollettino</a></body></html>'
    )


def serve_criticality(dpc: FakeDpc, crit_id: str = CRIT_ID) -> None:
    """Serve the criticality page and GeoJSON files of a bulletin."""
    dpc.add(CRITICALITY_PAGE_URL, body=bulletin_page(crit_id))
    for offset, name in enumerate(CRITICALITY_FILES):
        dpc.add(criticality_geojson_url(crit_id, offset), body=load_fixture(name))


def serve_vigilance(dpc: FakeDpc, vigi_id: str = VIGI_ID) -> None:
    """Serve the vigilance page and GeoJSON files of a bulletin."""
    dpc.add(VIGILANCE_PAGE_URL, body=bulletin_page(vigi_id))
    for offset, (zones, phenomena) in enumerate(
        zip(VIGILANCE_FILES, PHENOMENA_FILES, strict=True)
    ):
        dpc.add(vigilance_geojson_url(vigi_id, offset), body=load_fixture(zones))
        dpc.add(phenomena_geojson_url(vigi_id, offset), body=load_fixture(phenomena))
