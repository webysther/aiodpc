"""Discovery of the ID of the latest bulletins.

The ID is what names the bulletin files, so it must be found before anything
else. The default :class:`MapPageIdSource` reads it from the DPC map pages
with a regular expression. Another source (for example the GitHub contents
API, which is rate-limited to 60 requests per hour without a token) can be
plugged into :class:`aiodpc.DpcClient` by implementing
:class:`BulletinIdSource`.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Final, Protocol

from .const import CRITICALITY_PAGE_URL, VIGILANCE_PAGE_URL
from .exceptions import DpcParseError
from .models import BulletinKind
from .parsers import parse_criticality_id, parse_vigilance_id

type TextFetcher = Callable[[str], Awaitable[str]]
"""Coroutine function returning the text at a URL.

It raises :class:`aiodpc.DpcConnectionError` when the URL cannot be fetched.
"""

# 20261114_1430 (criticality) and 20261114.json (vigilance), as linked by the
# map pages; the lookarounds keep them from matching inside longer numbers.
_ID_PATTERNS: Final = {
    BulletinKind.CRITICALITY: re.compile(r"(?<!\d)(\d{8}_\d{4})(?!\d)"),
    BulletinKind.VIGILANCE: re.compile(r"(?<!\d)(\d{8})\.json", re.IGNORECASE),
}
_ID_PARSERS: Final[Mapping[BulletinKind, Callable[[str], object]]] = {
    BulletinKind.CRITICALITY: parse_criticality_id,
    BulletinKind.VIGILANCE: parse_vigilance_id,
}


def extract_bulletin_id(kind: BulletinKind, text: str) -> str:
    """Return the latest bulletin ID of a kind found in a text (a DPC map page).

    Matches that are not valid dates are ignored. When the text links more than
    one bulletin (e.g. an "Aggiornamento" re-issue), the latest one is returned.

    Raises :class:`aiodpc.DpcParseError` when the text contains no valid ID.
    """
    ids: set[str] = set()
    for bulletin_id in _ID_PATTERNS[kind].findall(text):
        try:
            _ID_PARSERS[kind](bulletin_id)
        except ValueError:
            continue
        ids.add(bulletin_id)
    if not ids:
        msg = f"No {kind} bulletin ID found in the DPC page"
        raise DpcParseError(msg)
    # The fixed-width IDs sort chronologically.
    return max(ids)


class BulletinIdSource(Protocol):
    """Strategy that finds the ID of the latest bulletin of a kind."""

    async def latest_id(self, kind: BulletinKind, fetch_text: TextFetcher) -> str:
        """Return the ID of the latest bulletin of ``kind``.

        ``fetch_text`` performs the HTTP requests with the client's session and
        timeout. Raise :class:`aiodpc.DpcConnectionError` or
        :class:`aiodpc.DpcParseError` when the ID cannot be found.
        """
        ...


class MapPageIdSource:
    """Find the latest bulletin IDs in the DPC map pages (the default source)."""

    def __init__(self, page_urls: Mapping[BulletinKind, str] | None = None) -> None:
        """Initialize the source, optionally with other page URLs."""
        self._page_urls: Mapping[BulletinKind, str] = page_urls or {
            BulletinKind.CRITICALITY: CRITICALITY_PAGE_URL,
            BulletinKind.VIGILANCE: VIGILANCE_PAGE_URL,
        }

    async def latest_id(self, kind: BulletinKind, fetch_text: TextFetcher) -> str:
        """Return the ID of the latest bulletin of ``kind`` linked by its page."""
        return extract_bulletin_id(kind, await fetch_text(self._page_urls[kind]))
