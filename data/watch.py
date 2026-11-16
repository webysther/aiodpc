"""Watch the latest DPC bulletins for what aiodpc does not expect.

    pip install --editable ".[schema]"
    python data/watch.py [--issues]

Reads every day of the latest criticality and vigilance bulletins, and reports
what aiodpc would read wrong, or not at all:

- the bulletins cannot be found, or a file cannot be downloaded;
- a file is not UTF-8 or JSON, or its format changed: the strict DTOs of
  ``aiodpc.schema`` reject it;
- a text or a code aiodpc does not know: an alert, a criticality, a risk, a
  precipitation, a phenomenon;
- a name with a character lost or replaced by an encoding error, other than
  those the study measured (``docs/study/results.json``);
- zones the census has not seen: a zone set none of the quarters in ``data``
  has, with the zones and municipalities that changed.

Each problem is printed. With ``--issues`` each one opens a GitHub issue
labeled "watch", unless an open issue has its title: the title says what is
wrong, the body where. ``gh`` opens them, with the token in ``GH_TOKEN``. The
workflow ``.github/workflows/watch.yml`` runs it a few times a day.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import aiohttp

from aiodpc import (
    AlertLevel,
    BulletinKind,
    Criticality,
    DpcClient,
    DpcError,
    DpcParseError,
    PhenomenonType,
    Precipitation,
    RiskType,
)
from aiodpc.parsers import (
    RISK_PROPERTIES,
    SUMMARY_PROPERTY,
    compact_criticality,
    compact_vigilance,
    parse_assessment,
    parse_precipitation,
)
from aiodpc.schema import (
    decode_criticality_file,
    decode_phenomena_file,
    decode_vigilance_file,
)
from aiodpc.urls import (
    CRITICALITY_DAYS,
    VIGILANCE_DAYS,
    criticality_geojson_url,
    phenomena_geojson_url,
    vigilance_geojson_url,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from aiodpc.compact import ZoneTable

type Document = dict[str, Any]
"""A decoded GeoJSON file."""

HERE: Final = Path(__file__).parent
RESULTS: Final = HERE.parent / "docs" / "study" / "results.json"

LABEL: Final = "watch"
"""The label of the issues the watch opens, and of those it looks for."""

TRIES: Final = 3
"""Downloads of a file before it is reported, waiting RETRY_SECONDS between."""
RETRY_SECONDS: Final = 30.0
REQUEST_SECONDS: Final = 120.0
"""Time to download a file: the largest, a criticality day, is about 6 MB."""

LOST_CHARACTER: Final = re.compile(r"\w\?\w")
"""A character lost by an encoding error: "Valle d?Aosta" (as in the study)."""
REPLACEMENT_CHARACTER: Final = "�"
"""The character that replaces bytes that are not UTF-8: "F�nis" (Fénis)."""

RISK_NAME: Final = "per rischio"
"""How a DPC summary names its risk: "Ordinaria per rischio idrogeologico"."""

ZONE_NAMES: Final = {
    BulletinKind.CRITICALITY: "Nome zona",
    BulletinKind.VIGILANCE: "Nome_Zona",
}
MUNICIPALITIES: Final = {
    BulletinKind.CRITICALITY: "Comuni",
    BulletinKind.VIGILANCE: "comuni",
}

LISTED_CHANGES: Final = 20
"""Changed zones or municipalities listed in an issue; the rest are counted."""
LISTED_PLACES: Final = 10
"""Places listed for a problem found in many: a new text in every zone of Italy
would otherwise exceed the 65,536 characters of the body of an issue."""


@dataclass(frozen=True, slots=True)
class Problem:
    """Something aiodpc does not expect: an issue to open."""

    title: str
    """What is wrong, the same each time it is found: the title of its issue."""
    details: str
    """Where it was found, and what DPC wrote."""


@dataclass(frozen=True, slots=True)
class DayFile:
    """A file of a day of a bulletin, downloaded."""

    name: str
    """What it is, e.g. "criticality 20261116_1444, day 0"."""
    url: str
    data: bytes


def problem_of(title: str, *lines: str) -> Problem:
    """Return a problem, its details one per line."""
    return Problem(title, "\n".join(lines))


def known_damaged_names() -> frozenset[str]:
    """Return the names the study found damaged by encoding errors."""
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    return frozenset(
        name
        for part in ("sample", "census")
        for key in ("lost_characters", "replaced_characters")
        for name in results[part].get(key) or {}
    )


def known_zone_tables() -> dict[str, dict[str, set[str]]]:
    """Return the zone tables of the census: municipalities by zone, by fingerprint."""
    return {
        path.stem: {
            name: set(municipalities)
            for _code, name, municipalities in json.loads(
                path.read_text(encoding="utf-8")
            )["rows"]
        }
        for path in sorted(HERE.glob("*/zones/*.json"))
    }


async def download(session: aiohttp.ClientSession, url: str) -> bytes:
    """Return a file, trying again after a failure; the last one is raised."""
    for attempt in range(1, TRIES + 1):
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=REQUEST_SECONDS)
            ) as response:
                response.raise_for_status()
                return await response.read()
        except (aiohttp.ClientError, TimeoutError):
            if attempt == TRIES:
                raise
            await asyncio.sleep(RETRY_SECONDS)
    raise AssertionError  # pragma: no cover - the loop returns or raises


@dataclass(frozen=True, slots=True)
class Read:
    """A file of a day of a bulletin, and its JSON if it could be read."""

    file: DayFile
    document: Document | None


async def read_file(
    session: aiohttp.ClientSession,
    name: str,
    url: str,
    strict: Callable[[bytes], object],
    problems: list[Problem],
) -> Read | None:
    """Return a file and its JSON, adding its problems; None if not downloaded."""
    try:
        file = DayFile(name, url, await download(session, url))
    except (aiohttp.ClientError, TimeoutError) as err:
        problems.append(
            problem_of(
                f"A file of the {name.split()[0]} bulletin cannot be downloaded",
                f"- File: {name}, {url}",
                f"- Error: `{err!r}`",
            )
        )
        return None
    document, found = decoded(file, strict)
    problems.extend(found)
    return Read(file, document)


def decoded(
    file: DayFile, strict: Callable[[bytes], object]
) -> tuple[Document | None, list[Problem]]:
    """Return the JSON of a file, and the problems of its encoding and format."""
    kind = file.name.split()[0]
    try:
        text = file.data.decode("utf-8")
    except UnicodeDecodeError as err:
        around = file.data[max(err.start - 40, 0) : err.end + 40]
        return None, [
            problem_of(
                f"A {kind} file is not UTF-8",
                f"- File: {file.name}, {file.url}",
                f"- Error: `{err}`",
                f"- Bytes around it: `{around!r}`",
            )
        ]
    try:
        document = json.loads(text)
    except ValueError as err:
        document, error = None, str(err)
    else:
        error = f"a JSON {type(document).__name__}, not an object"
    if not isinstance(document, dict):
        return None, [
            problem_of(
                f"A {kind} file is not a JSON object",
                f"- File: {file.name}, {file.url}",
                f"- Error: `{error}`",
            )
        ]
    try:
        strict(file.data)
    except DpcParseError as err:
        # The position of the feature changes from file to file: not in the title
        message = re.sub(r"\[\d+\]", "[…]", str(err).splitlines()[0])
        return document, [
            problem_of(
                f"The format of the {kind} files changed: {message}",
                f"- File: {file.name}, {file.url}",
                f"- Error: `{err}`",
            )
        ]
    return document, []


def features(document: Document) -> list[Document]:
    """Return the properties of the features of a GeoJSON document."""
    return [
        feature.get("properties") or {}
        for feature in document.get("features") or []
        if isinstance(feature, dict)
    ]


def damaged_names(
    kind: BulletinKind,
    file: DayFile,
    document: Document,
    known: frozenset[str],
) -> list[Problem]:
    """Return a problem for each name damaged by an encoding error, if new."""
    return [
        problem_of(
            f"A name damaged by an encoding error: {name}",
            f"- File: {file.name}, {file.url}",
            f"- Zone: {properties.get(ZONE_NAMES[kind])}",
        )
        for properties in features(document)
        for name in [
            properties.get(ZONE_NAMES[kind]),
            *(properties.get(MUNICIPALITIES[kind]) or []),
        ]
        if isinstance(name, str)
        and name not in known
        and (REPLACEMENT_CHARACTER in name or LOST_CHARACTER.search(name))
    ]


def unknown_criticality_texts(file: DayFile, document: Document) -> list[Problem]:
    """Return a problem for each alert, criticality or risk aiodpc does not know."""
    problems = []
    for properties in features(document):
        zone = properties.get(ZONE_NAMES[BulletinKind.CRITICALITY])
        where = (f"- File: {file.name}, {file.url}", f"- Zone: {zone}")
        for name in (SUMMARY_PROPERTY, *RISK_PROPERTIES.values()):
            text = properties.get(name)
            assessment = parse_assessment(text)
            if assessment.level is AlertLevel.UNKNOWN:
                problems.append(
                    problem_of(
                        f'An alert aiodpc does not know: "{text}"',
                        *where,
                        f"- Property: {name}",
                    )
                )
            if Criticality.of(assessment.description) is Criticality.UNKNOWN:
                problems.append(
                    problem_of(
                        "A criticality aiodpc does not know: "
                        f'"{assessment.description}"',
                        *where,
                        f"- Property: {name}",
                    )
                )
        summary = parse_assessment(properties.get(SUMMARY_PROPERTY)).description
        if RISK_NAME in summary.lower() and RiskType.named_in(summary) is None:
            problems.append(
                problem_of(f'A risk aiodpc does not know: "{summary}"', *where)
            )
    return problems


def unknown_precipitation(file: DayFile, document: Document) -> list[Problem]:
    """Return a problem for each precipitation aiodpc does not know."""
    problems = []
    for properties in features(document):
        value, text = (
            properties.get("id_classificazione"),
            properties.get("Quantitativi_previsti"),
        )
        if parse_precipitation(value, text) is Precipitation.UNKNOWN:
            problems.append(
                problem_of(
                    f'A precipitation aiodpc does not know: {value!r}, "{text}"',
                    f"- File: {file.name}, {file.url}",
                    f"- Zone: {properties.get(ZONE_NAMES[BulletinKind.VIGILANCE])}",
                )
            )
    return problems


def unknown_phenomena(file: DayFile, document: Document) -> list[Problem]:
    """Return a problem for each phenomenon code aiodpc does not know."""
    return [
        problem_of(
            f"A phenomenon aiodpc does not know: id_fenomeno {code!r}",
            f"- File: {file.name}, {file.url}",
            f"- Properties: `{json.dumps(properties, ensure_ascii=False)}`",
        )
        for properties in features(document)
        if not (
            isinstance(code := properties.get("id_fenomeno"), int)
            and PhenomenonType.of(code) is not None
        )
    ]


def listed(items: Iterable[str]) -> str:
    """Return items as a short list: the first ones, and how many more."""
    ordered = sorted(items)
    shown = ", ".join(ordered[:LISTED_CHANGES])
    more = len(ordered) - LISTED_CHANGES
    return f"{shown} and {more} more" if more > 0 else shown


def new_zones(
    kind: BulletinKind,
    bulletin_id: str,
    table: ZoneTable,
    known: dict[str, dict[str, set[str]]],
) -> list[Problem]:
    """Return a problem when the zones of a bulletin are not those of the census.

    The changes are told against the known table that shares the most zone
    names with it: zones and municipalities added and removed, or else only
    their shapes.
    """
    if table.fingerprint in known:
        return []
    zones = {zone.name: set(zone.municipalities) for zone in table.zones}
    nearest = max(known.values(), key=lambda other: len(other.keys() & zones.keys()))
    added, removed = zones.keys() - nearest.keys(), nearest.keys() - zones.keys()
    moved = [
        f"{name}: +{listed(zones[name] - nearest[name]) or 'none'}, "
        f"-{listed(nearest[name] - zones[name]) or 'none'}"
        for name in sorted(zones.keys() & nearest.keys())
        if zones[name] != nearest[name]
    ]
    changes = [
        *([f"- Zones added: {listed(added)}"] if added else []),
        *([f"- Zones removed: {listed(removed)}"] if removed else []),
        *([f"- Municipalities of {line}" for line in moved[:LISTED_CHANGES]]),
        *(
            [f"- And {len(moved) - LISTED_CHANGES} more zones"]
            if len(moved) > LISTED_CHANGES
            else []
        ),
    ] or ["- The same zones and municipalities: only their shapes changed"]
    return [
        problem_of(
            f"The {kind} zones changed: zone set {table.fingerprint}, "
            "not in the census",
            f"- Bulletin: {bulletin_id}",
            *changes,
            "",
            "Run `python data/build.py` for the quarter to add it to the census.",
        )
    ]


async def watch_criticality(
    session: aiohttp.ClientSession,
    bulletin_id: str,
    damaged: frozenset[str],
    tables: dict[str, dict[str, set[str]]],
) -> list[Problem]:
    """Return the problems of every day of a criticality bulletin."""
    problems: list[Problem] = []
    days = []
    for offset in range(len(CRITICALITY_DAYS)):
        read = await read_file(
            session,
            f"criticality {bulletin_id}, day {offset}",
            criticality_geojson_url(bulletin_id, offset),
            decode_criticality_file,
            problems,
        )
        if read is None or read.document is None:
            continue
        problems += damaged_names(
            BulletinKind.CRITICALITY, read.file, read.document, damaged
        )
        problems += unknown_criticality_texts(read.file, read.document)
        days.append((offset, read.document))
    if days:
        table = compact_criticality(bulletin_id, days).zones
        problems += new_zones(BulletinKind.CRITICALITY, bulletin_id, table, tables)
    return problems


async def watch_vigilance(
    session: aiohttp.ClientSession,
    bulletin_id: str,
    damaged: frozenset[str],
    tables: dict[str, dict[str, set[str]]],
) -> list[Problem]:
    """Return the problems of every day of a vigilance bulletin, with its phenomena."""
    problems: list[Problem] = []
    days = []
    for offset in range(len(VIGILANCE_DAYS)):
        zones = await read_file(
            session,
            f"vigilance {bulletin_id}, day {offset}",
            vigilance_geojson_url(bulletin_id, offset),
            decode_vigilance_file,
            problems,
        )
        phenomena = await read_file(
            session,
            f"phenomena {bulletin_id}, day {offset}",
            phenomena_geojson_url(bulletin_id, offset),
            decode_phenomena_file,
            problems,
        )
        if zones is not None and zones.document is not None:
            problems += damaged_names(
                BulletinKind.VIGILANCE, zones.file, zones.document, damaged
            )
            problems += unknown_precipitation(zones.file, zones.document)
        if phenomena is not None and phenomena.document is not None:
            problems += unknown_phenomena(phenomena.file, phenomena.document)
        if (
            zones is not None
            and zones.document is not None
            and phenomena is not None
            and phenomena.document is not None
        ):
            days.append((offset, zones.document, phenomena.document))
    if days:
        table = compact_vigilance(bulletin_id, days).zones
        problems += new_zones(BulletinKind.VIGILANCE, bulletin_id, table, tables)
    return problems


async def watch() -> list[Problem]:
    """Return the problems of the latest bulletins."""
    damaged, tables = known_damaged_names(), known_zone_tables()
    async with aiohttp.ClientSession() as session:
        client = DpcClient(session)
        try:
            criticality_id = await client.latest_bulletin_id(BulletinKind.CRITICALITY)
            vigilance_id = await client.latest_bulletin_id(BulletinKind.VIGILANCE)
        except DpcError as err:
            return [
                problem_of(
                    "The latest bulletin IDs cannot be found",
                    f"- Error: `{err!r}`",
                    "",
                    "aiodpc reads them from the DPC map pages (aiodpc.discovery).",
                )
            ]
        print(f"Criticality {criticality_id}, vigilance {vigilance_id}")
        return [
            *await watch_criticality(session, criticality_id, damaged, tables),
            *await watch_vigilance(session, vigilance_id, damaged, tables),
        ]


def run_details() -> str:
    """Return a link to the run of the workflow, when the watch runs in one."""
    server, repository, run = (
        os.environ.get(name)
        for name in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")
    )
    if server and repository and run:
        return f"\n\nFound by the [watch]({server}/{repository}/actions/runs/{run})."
    return "\n\nFound by `python data/watch.py`."


def gh(*arguments: str) -> str:
    """Run the GitHub CLI and return what it prints."""
    return subprocess.run(  # noqa: S603 - fixed arguments, no shell
        ["gh", *arguments],  # noqa: S607 - gh from the PATH of the runner
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def open_issues(problems: Sequence[Problem]) -> None:
    """Open an issue for each problem, unless an open issue has its title."""
    gh(
        "label",
        "create",
        LABEL,
        "--force",
        "--color",
        "D93F0B",
        "--description",
        "Found by the watch of the DPC bulletins",
    )
    open_titles = {
        issue["title"]
        for issue in json.loads(
            gh(
                "issue",
                "list",
                "--label",
                LABEL,
                "--state",
                "open",
                "--limit",
                "500",
                "--json",
                "title",
            )
        )
    }
    for problem in problems:
        if problem.title in open_titles:
            print(f"Already open: {problem.title}")
            continue
        url = gh(
            "issue",
            "create",
            "--label",
            LABEL,
            "--title",
            problem.title,
            "--body",
            problem.details + run_details(),
        )
        open_titles.add(problem.title)
        print(f"Opened {url.strip()}: {problem.title}")


def main() -> None:
    """Watch the latest bulletins, and report what aiodpc does not expect."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--issues", action="store_true", help="open a GitHub issue for each problem"
    )
    arguments = parser.parse_args()
    try:
        problems = asyncio.run(watch())
    except Exception as err:  # noqa: BLE001 - any failure of aiodpc is a problem to report
        problems = [
            problem_of(
                f"The watch failed: {type(err).__name__}",
                "```",
                traceback.format_exc().rstrip(),
                "```",
            )
        ]
    # The same text in several zones is one problem, with each place it was found
    merged: dict[str, list[str]] = {}
    for problem in problems:
        merged.setdefault(problem.title, []).append(problem.details)
    unique = []
    for title, details in merged.items():
        places = list(dict.fromkeys(details))
        more = len(places) - LISTED_PLACES
        unique.append(
            Problem(
                title,
                "\n\n".join(places[:LISTED_PLACES])
                + (f"\n\nAnd {more} more places." if more > 0 else ""),
            )
        )
    for problem in unique:
        print(f"\n{problem.title}\n{problem.details}")
    print(f"\n{len(unique)} problems." if unique else "\nNothing unexpected.")
    if arguments.issues:
        open_issues(unique)
    elif unique:
        sys.exit(1)


if __name__ == "__main__":
    main()
