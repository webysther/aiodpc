"""Tests of the discovery of the bulletin IDs."""

from __future__ import annotations

import pytest

from aiodpc import BulletinKind, DpcParseError, MapPageIdSource
from aiodpc.discovery import extract_bulletin_id

from . import bulletin_page, load_fixture


def test_real_pages() -> None:
    """Test the IDs linked by excerpts of the real DPC map pages."""
    criticality = load_fixture("real/criticality_page.html")
    vigilance = load_fixture("real/vigilance_page.html")

    assert extract_bulletin_id(BulletinKind.CRITICALITY, criticality) == "20261113_1434"
    assert extract_bulletin_id(BulletinKind.VIGILANCE, vigilance) == "20261113"


@pytest.mark.parametrize(
    ("kind", "page"),
    [
        (BulletinKind.CRITICALITY, "real/vigilance_page.html"),
        (BulletinKind.VIGILANCE, "real/criticality_page.html"),
    ],
)
def test_page_of_the_other_bulletin(kind: BulletinKind, page: str) -> None:
    """Test that a page of the other bulletin yields no ID."""
    with pytest.raises(DpcParseError, match=f"No {kind} bulletin ID"):
        extract_bulletin_id(kind, load_fixture(page))


def test_latest_id_wins() -> None:
    """Test that a re-issued bulletin ("Aggiornamento") wins over the first one."""
    page = bulletin_page("20261114_1430") + bulletin_page("20261114_1830")

    assert extract_bulletin_id(BulletinKind.CRITICALITY, page) == "20261114_1830"


@pytest.mark.parametrize(
    ("kind", "text"),
    [
        # Not a valid date
        (BulletinKind.CRITICALITY, "files/20261399_1430.json"),
        (BulletinKind.VIGILANCE, "files/20261132.json"),
        (BulletinKind.CRITICALITY, "files/20261114_2460.json"),
        # Part of longer numbers
        (BulletinKind.CRITICALITY, "id=120261114_1430"),
        (BulletinKind.CRITICALITY, "id=20261114_14300"),
        (BulletinKind.VIGILANCE, "id=120261114.json"),
        # Not a link to a JSON file
        (BulletinKind.VIGILANCE, "tel. 20261114"),
        (BulletinKind.VIGILANCE, ""),
    ],
)
def test_no_valid_id(kind: BulletinKind, text: str) -> None:
    """Test that texts without a valid ID raise a parse error."""
    with pytest.raises(DpcParseError):
        extract_bulletin_id(kind, text)


def test_invalid_matches_are_skipped() -> None:
    """Test that invalid dates do not hide a valid ID."""
    text = "files/20269999_1430.json files/20261114_1430.json"

    assert extract_bulletin_id(BulletinKind.CRITICALITY, text) == "20261114_1430"


async def test_map_page_source_with_custom_urls() -> None:
    """Test the map page source with other page URLs."""
    fetched: list[str] = []

    async def fetch_text(url: str) -> str:
        fetched.append(url)
        return bulletin_page("20261114")

    source = MapPageIdSource({BulletinKind.VIGILANCE: "https://example.invalid/v"})

    assert await source.latest_id(BulletinKind.VIGILANCE, fetch_text) == "20261114"
    assert fetched == ["https://example.invalid/v"]
