"""Write the bulletins of a quarter as compact JSON Lines: data/YEAR-QN.

    pip install --editable .
    python data/build.py 2026-Q3

Reads every criticality and vigilance bulletin that DPC published in the
quarter (about 1.8 GB of GeoJSON for a quarter) and writes, in
``data/YEAR-QN``:

- ``criticality.jsonl`` and ``vigilance.jsonl``: one bulletin per line, in
  the order of their IDs, each line the document of
  :meth:`aiodpc.CompactCriticality.to_json` or
  :meth:`aiodpc.CompactVigilance.to_json`;
- ``zones/FINGERPRINT.json`` and ``zones/FINGERPRINT.geojson``: each zone
  table the bulletins name in their ``zone_set``, with the municipalities and
  with the shapes of the zones.

Nothing is cached: the files are read as they arrive and only the compact
bulletins are kept. The bulletins of a past quarter are fixed, so a later run
writes the same files.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import aiohttp

from aiodpc import BulletinKind, DpcClient, DpcConnectionError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from aiodpc import CompactCriticality, CompactVigilance
    from aiodpc.compact import ZoneTable

HERE: Final = Path(__file__).parent

API: Final = "https://api.github.com/repos"
REPOSITORIES: Final = {
    BulletinKind.CRITICALITY: (
        "pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica"
    ),
    BulletinKind.VIGILANCE: "pcm-dpc/DPC-Bollettini-Vigilanza-Meteorologica",
}
"""The GitHub repositories of DPC, whose ``files`` folder has a summary
``ID.json`` for every bulletin it published."""
BULLETIN_ID: Final = {
    BulletinKind.CRITICALITY: re.compile(r"\d{8}_\d{4}"),
    BulletinKind.VIGILANCE: re.compile(r"\d{8}"),
}
"""The IDs of the bulletins: the day of publication, and the time of the
criticality bulletin, which DPC may publish more than once a day."""

QUARTER: Final = re.compile(r"(\d{4})-Q([1-4])")
MONTHS_PER_QUARTER: Final = 3
QUARTERS_PER_YEAR: Final = 4
DOWNLOADS: Final = 4
"""Bulletins read at the same time; each one is up to 11 MB of GeoJSON."""
ATTEMPTS: Final = 4
"""Tries of each bulletin, waiting 1, 2 and 4 s between them."""
REQUEST_TIMEOUT: Final = 120.0
"""Seconds allowed for each file, slower than a client polling the latest."""

type Compact = CompactCriticality | CompactVigilance


def quarter_days(quarter: str) -> tuple[dt.date, dt.date]:
    """Return the first and last day of a quarter written as YEAR-QN."""
    match = QUARTER.fullmatch(quarter)
    if match is None:
        msg = f"not a quarter: {quarter!r}, write it as 2026-Q3"
        raise ValueError(msg)
    year, number = int(match[1]), int(match[2])
    first = dt.date(year, MONTHS_PER_QUARTER * (number - 1) + 1, 1)
    following = (
        dt.date(year + 1, 1, 1)
        if number == QUARTERS_PER_YEAR
        else dt.date(year, MONTHS_PER_QUARTER * number + 1, 1)
    )
    return first, following - dt.timedelta(days=1)


async def bulletin_ids(
    session: aiohttp.ClientSession, kind: BulletinKind, first: dt.date, last: dt.date
) -> list[str]:
    """Return the IDs of the bulletins of a kind published from first to last."""
    repository = REPOSITORIES[kind]
    async with session.get(f"{API}/{repository}/contents/") as response:
        response.raise_for_status()
        contents = await response.json()
    files = next(item["sha"] for item in contents if item["name"] == "files")
    async with session.get(f"{API}/{repository}/git/trees/{files}") as response:
        response.raise_for_status()
        tree = await response.json()
    days = (first.strftime("%Y%m%d"), last.strftime("%Y%m%d"))
    return sorted(
        name
        for item in tree["tree"]
        if item["type"] == "blob"
        and BULLETIN_ID[kind].fullmatch(name := item["path"].removesuffix(".json"))
        and days[0] <= name[:8] <= days[1]
    )


async def read(
    client: DpcClient, kind: BulletinKind, bulletin_id: str
) -> Compact | None:
    """Return a bulletin as codes, or None when DPC does not have its files."""
    get: Callable[..., Awaitable[Any]] = (
        client.get_criticality_map
        if kind is BulletinKind.CRITICALITY
        else client.get_vigilance_map
    )
    for attempt in range(1, ATTEMPTS + 1):
        try:
            bulletin_map = await get(bulletin_id=bulletin_id, skip_expired=False)
        except DpcConnectionError as err:
            error = err
            if attempt < ATTEMPTS:
                await asyncio.sleep(2 ** (attempt - 1))
        else:
            compact: Compact = bulletin_map.compact()
            return compact
    print(f"{kind} {bulletin_id}: left out, {error}")
    return None


async def read_all(
    client: DpcClient, kind: BulletinKind, ids: Sequence[str]
) -> tuple[list[str], dict[str, ZoneTable]]:
    """Return the bulletins that could be read as JSON lines, and their zones.

    Each bulletin is turned into its line as soon as it is read, keeping only
    the first zone table of each fingerprint: a bulletin holds the shapes of
    every zone, and a quarter of them would take gigabytes of memory.
    """
    limit = asyncio.Semaphore(DOWNLOADS)
    tables: dict[str, ZoneTable] = {}
    done = 0

    async def one(bulletin_id: str) -> str | None:
        nonlocal done
        async with limit:
            compact = await read(client, kind, bulletin_id)
        done += 1
        if done % 10 == 0 or done == len(ids):
            print(f"{kind}: {done} of {len(ids)} bulletins")
        if compact is None:
            return None
        tables.setdefault(compact.zones.fingerprint, compact.zones)
        return compact.to_json()

    lines = await asyncio.gather(*(one(bulletin_id) for bulletin_id in ids))
    return [line for line in lines if line is not None], tables


def write_text(path: Path, text: str) -> None:
    """Write a UTF-8 file with Unix line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write(
    folder: Path,
    kind: BulletinKind,
    lines: Sequence[str],
    tables: Mapping[str, ZoneTable],
) -> None:
    """Write the bulletins of a kind, one per line, and their zone tables."""
    write_text(folder / f"{kind}.jsonl", "".join(f"{line}\n" for line in lines))
    for fingerprint, table in tables.items():
        write_text(folder / "zones" / f"{fingerprint}.json", f"{table.to_json()}\n")
        geojson = json.dumps(
            table.to_geojson(), ensure_ascii=False, separators=(",", ":")
        )
        write_text(folder / "zones" / f"{fingerprint}.geojson", f"{geojson}\n")
        print(f"{kind}: zone table {fingerprint}, {len(table.zones)} zones")


async def main() -> None:
    """Read the bulletins of the quarter given and write its folder."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("quarter", help="the quarter, written as 2026-Q3")
    quarter = parser.parse_args().quarter
    try:
        first, last = quarter_days(quarter)
    except ValueError as err:
        parser.error(str(err))
    folder = HERE / quarter
    async with aiohttp.ClientSession() as session:
        client = DpcClient(session, request_timeout=REQUEST_TIMEOUT)
        for kind in BulletinKind:
            ids = await bulletin_ids(session, kind, first, last)
            print(f"{kind}: {len(ids)} bulletins from {ids[0]} to {ids[-1]}")
            lines, tables = await read_all(client, kind, ids)
            print(f"{kind}: {len(lines)} bulletins written")
            write(folder, kind, lines, tables)


if __name__ == "__main__":
    asyncio.run(main())
