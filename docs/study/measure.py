"""Measure the DPC bulletin data: every number of the study (en.md, it.md).

    pip install --editable . --group docs
    python docs/study/measure.py CACHE_DIR

Downloads into CACHE_DIR, and keeps between runs (about 450 MB): the summary
of every criticality bulletin published up to :data:`UNTIL`, a seeded sample
of their GeoJSON files, and the files of one day of both bulletins. Writes
``results.json`` and the figures next to this script. The bulletins are fixed,
so a later run gives the same numbers, except the sizes of the repositories.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import gzip
import hashlib
import html
import io
import json
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import aiohttp
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

from aiodpc import Criticality, CriticalityMap, RiskType, VigilanceMap
from aiodpc.parsers import parse_assessment

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

HERE: Final = Path(__file__).parent
RESULTS: Final = HERE / "results.json"
FIGURES: Final = HERE / "figures"

UNTIL: Final = "20261115"
"""Last publication day of the bulletins measured."""
DAY_CRITICALITY: Final = "20261115_1421"
"""The criticality bulletin of the day measured in full."""
DAY_VIGILANCE: Final = "20261115"
"""The vigilance bulletin of the day measured in full."""

SAMPLE_PER_GROUP: Final = 25
"""GeoJSON files drawn from each group: red, orange and several-risk days."""
SAMPLE_SEED: Final = 7

CRITICALITY_REPO: Final = "pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica"
VIGILANCE_REPO: Final = "pcm-dpc/DPC-Bollettini-Vigilanza-Meteorologica"
API: Final = "https://api.github.com/repos"
RAW: Final = "https://raw.githubusercontent.com/{repo}/master/files/{path}"

DOWNLOADS: Final = 12
"""Downloads at the same time."""
TIMINGS: Final = 5
"""Runs of each timing; the fastest is kept."""
DAYS_PER_YEAR: Final = 365
RFC7946_DECIMALS: Final = 6
"""Decimals of a coordinate RFC 7946 (GeoJSON, section 11.2) finds enough:
about 10 cm."""
MEGABYTE: Final = 1e6
INSIDE_LABEL: Final = 0.2
"""Smallest share of a bar whose label fits inside it."""

COLOR: Final = "#2a78d6"
INK: Final = "#52514e"

APOSTROPHE: Final = "\u2019"
"""The typographic apostrophe, three bytes in UTF-8: the character the zone
names of the Aosta Valley lost ("Valle d?Aosta")."""

LOST_CHARACTER: Final = re.compile(r"\w\?\w")
"""A character lost by an encoding error: "Valle d?Aosta"."""


async def fetch(session: aiohttp.ClientSession, url: str, path: Path) -> bytes:
    """Return a file, downloaded once into the cache."""
    if path.exists():
        return path.read_bytes()
    async with session.get(url) as response:
        response.raise_for_status()
        data = await response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


async def fetch_all(
    session: aiohttp.ClientSession, items: Iterable[tuple[str, Path]]
) -> None:
    """Download files into the cache, a few at a time."""
    limit = asyncio.Semaphore(DOWNLOADS)

    async def one(url: str, path: Path) -> None:
        async with limit:
            await fetch(session, url, path)

    await asyncio.gather(*(one(url, path) for url, path in items))


async def api(session: aiohttp.ClientSession, path: str) -> Any:  # noqa: ANN401 - JSON
    """Return a document of the GitHub API."""
    async with session.get(f"{API}/{path}") as response:
        response.raise_for_status()
        return await response.json()


async def bulletin_ids(session: aiohttp.ClientSession) -> list[str]:
    """Return the IDs of the criticality bulletins published up to UNTIL."""
    contents = await api(session, f"{CRITICALITY_REPO}/contents/")
    files = next(item["sha"] for item in contents if item["name"] == "files")
    tree = await api(session, f"{CRITICALITY_REPO}/git/trees/{files}")
    names = (item["path"] for item in tree["tree"] if item["type"] == "blob")
    return sorted(
        name.removesuffix(".json")
        for name in names
        if re.fullmatch(r"\d{8}_\d{4}\.json", name) and name[:8] <= UNTIL
    )


def headings(summary: dict[str, Any], day: str) -> list[str]:
    """Return the bold headings of the HTML summary of a bulletin day."""
    text = html.unescape(summary[day].get("html_descrition") or "")
    return [
        heading.strip().rstrip(":")
        for heading in re.findall(r"<b>([A-Z][^<]*?)</b>", text)
        if "ALLERTA" in heading
    ]


def history(cache: Path, ids: Sequence[str]) -> tuple[dict[str, Any], list[str]]:
    """Measure the summaries of every bulletin; return the sampled file names."""
    texts: Counter[str] = Counter()
    groups: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for bulletin_id in ids:
        summary = json.loads((cache / "meta" / f"{bulletin_id}.json").read_bytes())
        for day in ("today", "tomorrow"):
            found = headings(summary, day)
            texts.update(found)
            if any("ELEVATA" in heading for heading in found):
                groups["red"].add((bulletin_id, day))
            if any("MODERATA" in heading for heading in found):
                groups["orange"].add((bulletin_id, day))
            levels = [heading.split()[0] for heading in found if "CRITICIT" in heading]
            if len(levels) != len(set(levels)):
                groups["several risks"].add((bulletin_id, day))
    random.seed(SAMPLE_SEED)
    sample: set[tuple[str, str]] = set()
    for group in ("red", "orange", "several risks"):
        candidates = sorted(groups[group])
        size = min(SAMPLE_PER_GROUP, len(candidates))
        sample |= set(random.sample(candidates, size))
    days_published = Counter(bulletin_id[:8] for bulletin_id in ids)
    results = {
        "bulletins": len(ids),
        "first": ids[0],
        "last": ids[-1],
        "days": len(days_published),
        "days_with_update": sum(count > 1 for count in days_published.values()),
        "texts": dict(texts.most_common()),
        "groups": {group: len(items) for group, items in groups.items()},
    }
    return results, [f"{bulletin_id}_{day}.json" for bulletin_id, day in sorted(sample)]


def zones_of(geojson: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the features of a criticality file by zone name."""
    return {
        feature["properties"]["Nome zona"]: feature for feature in geojson["features"]
    }


def digest(value: object) -> str:
    """Return a digest of a JSON value."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def sample_texts(files: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Measure the criticality texts of every zone of the sample."""
    summaries: Counter[str] = Counter()
    risks: Counter[str] = Counter()
    pairs: set[tuple[str, str]] = set()
    for geojson in files:
        for feature in geojson["features"]:
            properties = feature["properties"]
            summaries[properties["Rappresentata nella mappa"]] += 1
            for name in (
                "Per rischio idraulico",
                "Per rischio temporali",
                "Per rischio idrogeologico",
            ):
                risks[properties[name]] += 1
            for text in [properties["Rappresentata nella mappa"]] + [
                properties[name]
                for name in (
                    "Per rischio idraulico",
                    "Per rischio temporali",
                    "Per rischio idrogeologico",
                )
            ]:
                assessment = parse_assessment(text)
                pairs.add(
                    (str(Criticality.of(assessment.description)), str(assessment.level))
                )
    return {
        "zone_days": sum(len(geojson["features"]) for geojson in files),
        "summary_texts": dict(sorted(summaries.items())),
        "risk_texts": dict(sorted(risks.items())),
        "criticality_level_pairs": sorted(pairs),
        "summaries_name_one_risk": all(
            RiskType.named_in(text) is not None or text.startswith("Assenza")
            for text in summaries
        ),
    }


def zone_set_changes(
    names: Sequence[str], files: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the files where the set of zone names changes, and how."""
    changes: list[dict[str, Any]] = []
    previous: dict[str, dict[str, Any]] | None = None
    for name, geojson in zip(names, files, strict=True):
        zones = zones_of(geojson)
        if previous is None or set(zones) != set(previous):
            changes.append(
                {
                    "file": name,
                    "zones": len(zones),
                    "added": sorted(set(zones) - set(previous or {})),
                    "removed": sorted(set(previous or {}) - set(zones))
                    if previous
                    else [],
                }
            )
        previous = zones
    changes[0]["added"] = []
    return changes


def shape_changes(
    names: Sequence[str], files: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Compare each zone with the same zone in the previous file of the sample."""
    compared = same = 0
    changes = []
    previous: dict[str, dict[str, Any]] = {}
    previous_name = ""
    for name, geojson in zip(names, files, strict=True):
        zones = zones_of(geojson)
        common = set(zones) & set(previous)
        changed = sorted(
            zone
            for zone in common
            if digest(zones[zone]["geometry"]) != digest(previous[zone]["geometry"])
        )
        compared += len(common)
        same += len(common) - len(changed)
        if changed:
            changes.append(
                {"previous": previous_name, "file": name, "zones": len(changed)}
            )
        previous, previous_name = zones, name
    return {"compared": compared, "same": same, "changes": changes}


def municipality_lists(
    names: Sequence[str], files: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Measure the municipality lists: repeated names and their order."""
    repeated = []
    entries = unique = compared = same_set = same_order = 0
    most = 0
    previous: dict[str, dict[str, Any]] = {}
    for name, geojson in zip(names, files, strict=True):
        zones = zones_of(geojson)
        file_entries = sum(
            len(feature["properties"]["Comuni"]) for feature in zones.values()
        )
        file_unique = sum(
            len(set(feature["properties"]["Comuni"])) for feature in zones.values()
        )
        entries += file_entries
        unique += file_unique
        if file_entries > file_unique:
            repeated.append(
                {"file": name, "entries": file_entries, "unique": file_unique}
            )
        for feature in zones.values():
            counts = Counter(feature["properties"]["Comuni"])
            most = max(most, *counts.values(), 0)
        for zone in set(zones) & set(previous):
            listed = zones[zone]["properties"]["Comuni"]
            before = previous[zone]["properties"]["Comuni"]
            compared += 1
            same_set += set(listed) == set(before)
            same_order += list(dict.fromkeys(listed)) == list(dict.fromkeys(before))
        previous = zones
    return {
        "entries": entries,
        "unique": unique,
        "files_with_repeats": repeated,
        "most_repeats_of_a_name": most,
        "compared": compared,
        "same_set": same_set,
        "same_order": same_order,
    }


def damaged_names(
    files: Sequence[dict[str, Any]], changes: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Return the names with lost characters, and the names cut short."""
    lost = Counter(
        text
        for geojson in files
        for feature in geojson["features"]
        for text in [
            feature["properties"]["Nome zona"],
            *feature["properties"]["Comuni"],
        ]
        if LOST_CHARACTER.search(text)
    )
    cut = [
        {
            "before": old,
            "after": new,
            "characters": len(new),
            "bytes_with_apostrophes": len(new.replace("?", APOSTROPHE).encode()),
        }
        for change in changes
        for old in change["removed"]
        for new in change["added"]
        # Cut in the middle of a word, unlike a zone renamed to a shorter name
        if old.startswith(new) and old != new and old[len(new)].isalpha()
    ]
    return {
        "lost_characters": dict(lost.most_common()),
        "files_with_lost_characters": sum(
            any(
                LOST_CHARACTER.search(text)
                for feature in geojson["features"]
                for text in [
                    feature["properties"]["Nome zona"],
                    *feature["properties"]["Comuni"],
                ]
            )
            for geojson in files
        ),
        "names_cut_mid_word": cut,
    }


def sample_zones(
    names: Sequence[str], files: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Measure how the zones change: their set, shapes, municipalities and names."""
    changes = zone_set_changes(names, files)
    return {
        "zone_set_changes": changes,
        "shapes": shape_changes(names, files),
        "municipalities": municipality_lists(names, files),
        **damaged_names(files, changes),
    }


def rounded(value: Any, decimals: int) -> Any:  # noqa: ANN401 - JSON
    """Return GeoJSON coordinates with their numbers rounded."""
    if isinstance(value, float):
        return round(value, decimals)
    if isinstance(value, list):
        return [rounded(item, decimals) for item in value]
    return value


def decimals_of(geometry: dict[str, Any] | None) -> int:
    """Return the most decimals of the coordinates of a geometry."""
    text = json.dumps(geometry["coordinates"]) if geometry else ""
    return max((len(digits) for digits in re.findall(r"\.(\d+)", text)), default=0)


def composition(data: bytes) -> dict[str, Any]:
    """Return the size of a GeoJSON file and what it is made of."""
    geojson = json.loads(data)
    features = geojson["features"]

    def size(value: object) -> int:
        return len(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        )

    municipalities = sum(
        size(value)
        for feature in features
        for key, value in feature["properties"].items()
        if key in {"Comuni", "comuni"}
    )
    properties = sum(size(feature["properties"]) for feature in features)
    return {
        "bytes": len(data),
        "gzip": len(gzip.compress(data)),
        "features": len(features),
        "geometry": sum(size(feature["geometry"]) for feature in features),
        "geometry_rfc7946_precision": sum(
            size(
                {
                    **feature["geometry"],
                    "coordinates": rounded(
                        feature["geometry"]["coordinates"], RFC7946_DECIMALS
                    ),
                }
            )
            for feature in features
            if feature["geometry"]
        ),
        "most_decimals": max(decimals_of(feature["geometry"]) for feature in features),
        "municipalities": municipalities,
        "other_properties": properties - municipalities,
    }


def fastest(work: Any) -> float:  # noqa: ANN401 - any callable
    """Return the fastest of a few runs of some work, in seconds."""
    times = []
    for _run in range(TIMINGS):
        start = time.perf_counter()
        work()
        times.append(time.perf_counter() - start)
    return min(times)


def one_day(day: dict[str, bytes]) -> dict[str, Any]:
    """Measure one day of both bulletins, as DPC publishes it and compact."""
    criticality = [json.loads(day[f"criticality_{offset}"]) for offset in (0, 1)]
    vigilance = [
        (
            offset,
            json.loads(day[f"vigilance_{offset}"]),
            json.loads(day[f"phenomena_{offset}"]),
        )
        for offset in (0, 1, 2)
    ]
    compact_criticality = CriticalityMap(
        DAY_CRITICALITY, enumerate(criticality)
    ).compact()
    compact_vigilance = VigilanceMap(DAY_VIGILANCE, vigilance).compact()
    documents = {
        "criticality.csv": compact_criticality.to_csv(),
        "vigilance.csv": compact_vigilance.to_csv(),
        "phenomena.csv": compact_vigilance.phenomena_csv(),
    }
    compact = "".join(documents.values()).encode()
    references = {
        "criticality_zones.json": compact_criticality.zones.to_json(),
        "vigilance_zones.json": compact_vigilance.zones.to_json(),
        "criticality_zones.geojson": json.dumps(
            compact_criticality.zones.to_geojson(), separators=(",", ":")
        ),
        "vigilance_zones.geojson": json.dumps(
            compact_vigilance.zones.to_geojson(), separators=(",", ":")
        ),
    }
    dpc_bytes = sum(len(data) for data in day.values())
    dpc_gzip = sum(len(gzip.compress(data)) for data in day.values())
    return {
        "files": {name: composition(data) for name, data in day.items()},
        "dpc_bytes": dpc_bytes,
        "dpc_gzip": dpc_gzip,
        "compact": {name: len(text.encode()) for name, text in documents.items()},
        "compact_bytes": len(compact),
        "compact_gzip": len(gzip.compress(compact)),
        "references": {name: len(text.encode()) for name, text in references.items()},
        "ratio": dpc_bytes / len(compact),
        "ratio_gzip": dpc_gzip / len(gzip.compress(compact)),
        "zone_sets": [
            compact_criticality.zones.fingerprint,
            compact_vigilance.zones.fingerprint,
        ],
        "decode_dpc_seconds": fastest(
            lambda: [json.loads(data) for data in day.values()]
        ),
        "decode_compact_seconds": fastest(
            lambda: [list(csv.reader(io.StringIO(text))) for text in documents.values()]
        ),
        "year_dpc_bytes": dpc_bytes * DAYS_PER_YEAR,
        "year_compact_bytes": len(compact) * DAYS_PER_YEAR,
    }


FIGURE_TEXTS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "sizes": "Bytes of one day of both bulletins (log scale)",
        "dpc": "DPC GeoJSON",
        "dpc_gzip": "DPC GeoJSON, gzip",
        "compact": "Compact CSV",
        "compact_gzip": "Compact CSV, gzip",
        "composition": "What a criticality file is made of (share of its bytes)",
        "geometry": "Zone shapes",
        "municipalities": "Municipality lists",
        "other": "Names and alerts",
        "zones": "Alert zones in the sampled bulletins, and when shapes changed",
        "zones_axis": "Zones",
        "shapes": "{date}: {count} shapes",
        "decimal": ".",
    },
    "it": {
        "sizes": "Byte di un giorno dei due bollettini (scala logaritmica)",
        "dpc": "GeoJSON DPC",
        "dpc_gzip": "GeoJSON DPC, gzip",
        "compact": "CSV compatto",
        "compact_gzip": "CSV compatto, gzip",
        "composition": "Di cosa è fatto un file di criticità (quota dei byte)",
        "geometry": "Forme delle zone",
        "municipalities": "Elenchi dei comuni",
        "other": "Nomi e allerte",
        "zones": "Zone di allerta nel campione, e quando sono cambiate le forme",
        "zones_axis": "Zone",
        "shapes": "{date}: {count} forme",
        "decimal": ",",
    },
}
"""The texts of the figures, in the languages of the study."""


def number(value: float, texts: dict[str, str], spec: str = ".1f") -> str:
    """Return a number with the decimal separator of a language."""
    return format(value, spec).replace(".", texts["decimal"])


def figure_sizes(day: dict[str, Any], language: str) -> None:
    """Draw the bytes of one day: as DPC publishes it and compact."""
    texts = FIGURE_TEXTS[language]
    bars = [
        (texts["dpc"], day["dpc_bytes"]),
        (texts["dpc_gzip"], day["dpc_gzip"]),
        (texts["compact"], day["compact_bytes"]),
        (texts["compact_gzip"], day["compact_gzip"]),
    ]
    figure, axes = plt.subplots(figsize=(7, 2.6), facecolor="white")
    labels = [label for label, _value in bars][::-1]
    values = [value for _label, value in bars][::-1]
    axes.barh(labels, values, color=COLOR, height=0.5)
    axes.set_xscale("log")
    for position, value in enumerate(values):
        text = (
            f"{number(value / MEGABYTE, texts)} MB"
            if value >= MEGABYTE
            else f"{number(value / 1e3, texts)} kB"
        )
        axes.text(value * 1.15, position, text, va="center", fontsize=9, color=INK)
    axes.set_xlim(1e3, 2e8)
    axes.spines[["top", "right"]].set_visible(False)
    axes.tick_params(colors=INK, labelsize=9)
    axes.set_title(texts["sizes"], loc="left", fontsize=11)
    figure.tight_layout()
    figure.savefig(FIGURES / f"{language}-sizes.png", dpi=150)
    plt.close(figure)


def figure_composition(day: dict[str, Any], language: str) -> None:
    """Draw what a criticality file is made of."""
    texts = FIGURE_TEXTS[language]
    parts = day["files"]["criticality_0"]
    shares = [
        (texts["geometry"], parts["geometry"]),
        (texts["municipalities"], parts["municipalities"]),
        (texts["other"], parts["other_properties"]),
    ]
    total = parts["bytes"]
    figure, axes = plt.subplots(figsize=(7, 2.2), facecolor="white")
    labels = [label for label, _value in shares][::-1]
    values = [value / total for _label, value in shares][::-1]
    axes.barh(labels, values, color=COLOR, height=0.5)
    for position, value in enumerate(values):
        axes.text(
            value + 0.01,
            position,
            f"{number(value * 100, texts)}%",
            va="center",
            fontsize=9,
            color=INK,
        )
    axes.set_xlim(0, 1.1)
    axes.xaxis.set_visible(False)
    axes.spines[["top", "right", "bottom"]].set_visible(False)
    axes.tick_params(colors=INK, labelsize=9)
    axes.set_title(texts["composition"], loc="left", fontsize=11)
    figure.tight_layout()
    figure.savefig(FIGURES / f"{language}-composition.png", dpi=150)
    plt.close(figure)


def file_date(name: str) -> dt.date:
    """Return the publication day of a sampled file."""
    return dt.date(int(name[:4]), int(name[4:6]), int(name[6:8]))


def figure_zones(
    names: Sequence[str],
    files: Sequence[dict[str, Any]],
    shapes: dict[str, Any],
    language: str,
) -> None:
    """Draw the number of zones over time, and when their shapes changed."""
    texts = FIGURE_TEXTS[language]
    dates = [file_date(name) for name in names]
    counts = [len(geojson["features"]) for geojson in files]
    figure, axes = plt.subplots(figsize=(7, 2.8), facecolor="white")
    axes.step(dates, counts, where="post", color=COLOR, linewidth=2)
    for index, change in enumerate(shapes["changes"]):
        when = file_date(change["file"])
        count = counts[list(names).index(change["file"])]
        axes.plot(
            [when],
            [count],
            "o",
            color=COLOR,
            markersize=6,
            markeredgecolor="white",
            markeredgewidth=1.5,
        )
        above = index % 2 == 0
        axes.annotate(
            texts["shapes"].format(date=f"{when:%Y-%m}", count=change["zones"]),
            (when, count),
            textcoords="offset points",
            xytext=(0, 9 if above else -15),
            ha="center",
            fontsize=8,
            color=INK,
        )
    axes.set_ylim(min(counts) - 20, max(counts) + 20)
    axes.set_ylabel(texts["zones_axis"], fontsize=9, color=INK)
    axes.spines[["top", "right"]].set_visible(False)
    axes.tick_params(colors=INK, labelsize=8)
    axes.set_title(texts["zones"], loc="left", fontsize=11)
    figure.tight_layout()
    figure.savefig(FIGURES / f"{language}-zones.png", dpi=150)
    plt.close(figure)


async def main() -> None:
    """Download what is missing, measure and write the results and figures."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cache", type=Path, help="directory of the downloads")
    cache = parser.parse_args().cache
    async with aiohttp.ClientSession() as session:
        ids = await bulletin_ids(session)
        await fetch_all(
            session,
            (
                (
                    RAW.format(repo=CRITICALITY_REPO, path=f"{bulletin_id}.json"),
                    cache / "meta" / f"{bulletin_id}.json",
                )
                for bulletin_id in ids
            ),
        )
        summaries, names = history(cache, ids)
        await fetch_all(
            session,
            (
                (
                    RAW.format(repo=CRITICALITY_REPO, path=f"geojson/{name}"),
                    cache / "geo" / name,
                )
                for name in names
            ),
        )
        day_files = {
            **{
                f"criticality_{offset}": (
                    CRITICALITY_REPO,
                    f"geojson/{DAY_CRITICALITY}_{name}.json",
                )
                for offset, name in enumerate(("today", "tomorrow"))
            },
            **{
                f"vigilance_{offset}": (
                    VIGILANCE_REPO,
                    f"geojson/{DAY_VIGILANCE}_{name}.json",
                )
                for offset, name in enumerate(("oggi", "domani", "dopodomani"))
            },
            **{
                f"phenomena_{offset}": (
                    VIGILANCE_REPO,
                    f"geojson/{DAY_VIGILANCE}_fenomeni_{name}.json",
                )
                for offset, name in enumerate(("oggi", "domani", "dopodomani"))
            },
        }
        day = {
            key: await fetch(
                session,
                RAW.format(repo=repo, path=path),
                cache / "day" / path.replace("/", "_"),
            )
            for key, (repo, path) in day_files.items()
        }
        repositories = {
            repo: (await api(session, repo))["size"]
            for repo in (CRITICALITY_REPO, VIGILANCE_REPO)
        }
    files = [json.loads((cache / "geo" / name).read_bytes()) for name in names]
    zones = sample_zones(names, files)
    day_results = one_day(day)
    results = {
        "until": UNTIL,
        "measured_on": time.strftime("%Y-%m-%d"),
        "history": summaries,
        "sample": {"files": len(names), **sample_texts(files), **zones},
        "day": {
            "criticality": DAY_CRITICALITY,
            "vigilance": DAY_VIGILANCE,
            **day_results,
        },
        "repository_kilobytes": repositories,
    }
    RESULTS.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    FIGURES.mkdir(exist_ok=True)
    for language in FIGURE_TEXTS:
        figure_sizes(day_results, language)
        figure_composition(day_results, language)
        figure_zones(names, files, zones["shapes"], language)


if __name__ == "__main__":
    asyncio.run(main())
