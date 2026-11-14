# aiodpc

Async Python client for the open data of the Italian Civil Protection
Department (Dipartimento della Protezione Civile, DPC): the national alert
bulletins.

- **Bollettino di criticità idrogeologica e idraulica**: the alert level
  (green, yellow, orange, red) of each alert zone for today and tomorrow, for
  the hydraulic, thunderstorm and hydrogeological risks.
- **Bollettino di vigilanza meteorologica**: the expected precipitation of each
  vigilance zone for today, tomorrow and the day after, and the significant
  weather phenomena (heavy rain, wind, sea storms, frost, fog, temperatures).

Given a location (coordinates, optionally a municipality), aiodpc tells
whether it has a risk and which one, or returns the bulletins of its zone, day
by day. It is built on `asyncio` and `aiohttp`, has no Home Assistant
dependency and is fully typed.

## Installation

```bash
pip install aiodpc
```

Python 3.13 or later is required.

## Usage

aiodpc has three levels, from the simplest to the rawest: ask whether a place
has a risk, read the bulletins day by day, or get the DPC files as they are.

### Is there a risk here?

```python
import asyncio

from aiodpc import Day, DpcClient


async def main() -> None:
    async with DpcClient() as dpc:
        home = dpc.location(41.9, 12.5)

        if await home.has_risk():
            risk = await home.risk()
            print(f"Alert today: {risk}")  # Alert today: orange (hydrogeological)
            print(risk.description)  # Moderata per rischio idrogeologico
            print(f"Valid until {risk.valid_until}")

        if await home.has_risk(Day.TOMORROW):
            print(f"Alert tomorrow: {await home.risk(Day.TOMORROW)}")


asyncio.run(main())
```

A risk has:

- `level`: an `AlertLevel`, `green`, `yellow`, `orange` or `red`. Levels are
  ordered (`risk.level >= AlertLevel.ORANGE`); yellow and higher are alerts.
- `types`: the `RiskType`s at that level: `HYDRAULIC`, `THUNDERSTORMS`,
  `HYDROGEOLOGICAL`.
- `description`: the DPC summary, in Italian; `valid_until`: the midnight
  (Europe/Rome) that ends the day; `day`: the complete assessment of the day.

The location keeps its bulletin: it checks for a new one at most once a
minute and downloads it only when DPC publishes one, so `has_risk()` and
`risk()` can be called as often as needed (for example at every update of a
Home Assistant coordinator).

### Bulletins, day by day

```python
from aiodpc import DpcClient, Location

ROME = Location(41.9, 12.5)

async with DpcClient() as dpc:
    alerts = await dpc.get_criticality(ROME)
    weather = await dpc.get_vigilance(ROME, phenomena_within_km=50)

for day in alerts:
    print(f"{day.date} {day.zone}: {day.level}")  # 2026-11-15 Bacini di Roma: orange
    for risk in day.risks:
        print(f"  {risk}")  # hydrogeological: orange

for day in weather:
    print(f"{day.date} {day.zone}: {day.precipitation}")  # ... Comune di Roma: moderate
    for phenomenon in day.phenomena:
        print(f"  {phenomenon}")  # wind: forti, 30.4 km WSW
```

A criticality day has the `level` of its zone and the assessment of each risk
type: `day.hydraulic`, `day.thunderstorms`, `day.hydrogeological` (all of them
in `day.risks`). A vigilance day has the expected `precipitation` (a
`Precipitation`, from `none` to `very_heavy`) and the significant `phenomena`
near the location.

Pass your own session with `DpcClient(session)`; the client never closes a
session it did not create.

#### Days and validity

Each day carries its calendar `date` and `valid_until`, the midnight
(Europe/Rome) that ends it. Look days up by date rather than by position:
`bulletin.today`, `bulletin.tomorrow` or `bulletin.on(date)`. After midnight
the bulletin published the day before still answers `today` with its second
day until DPC publishes a new one.

By default, days that are already over are not downloaded
(`skip_expired=False` to get them all, e.g. for a past `bulletin_id`).

#### Polling

The bulletin files are large (several MB per day). `dpc.location()` polls
efficiently for you; with the bulletins, check the latest ID and fetch the
bulletin only when it changed:

```python
from aiodpc import BulletinKind

latest = await dpc.latest_bulletin_id(BulletinKind.CRITICALITY)
if latest != alerts.id:
    alerts = await dpc.get_criticality(ROME, bulletin_id=latest)
```

The criticality bulletin is published every day by 16:00 (Europe/Rome) and may
be re-issued later the same day ("Aggiornamento"); the vigilance bulletin by
15:00.

#### Several places

Each bulletin is the same file for the whole of Italy (about 18 MB a day for
both). For several places, download it once with `get_criticality_map()` or
`get_vigilance_map()` and read it at each place with `at()`, which makes no
request:

```python
criticality = await dpc.get_criticality_map()
vigilance = await dpc.get_vigilance_map()

for place in (home, office):
    print(criticality.at(place).today)
    print(vigilance.at(place, phenomena_within_km=20).today)
```

`at()` raises `DpcLocationError` for a place outside every zone without
affecting the others. A map holds the decoded files (tens of MB): keep it only
while reading it. `at()` does no I/O, so it can also run in an executor.

### Raw DPC files (optional)

```bash
pip install "aiodpc[schema]"
```

The DPC files are also available as typed DTOs, with clean names for the
DPC fields (`zone_name` for `"Nome zona"`):

```python
file = await dpc.get_criticality_file()  # latest bulletin, publication day
for zone in file.features:
    print(zone.properties.zone_name, zone.properties.summary)
```

The DTOs are strict, which is their purpose: when DPC changes its format they
raise `DpcParseError` saying where, e.g. ``Object missing required field `Nome
zona` - at `$.features[1].properties` ``. New fields are ignored. The rest of
aiodpc does not use them and keeps working when the data is incomplete.
`get_vigilance_file()` and `get_phenomena_file()` cover the vigilance bulletin;
`aiodpc.schema` decodes files fetched by other means.

### Municipality

With `dpc.location(41.9, 12.5, municipality="Roma")` or
`Location(41.9, 12.5, municipality="Roma")`, the zones that list the
municipality are considered and the one with the highest level is used; `zone`
is the zone containing the coordinates. Large municipalities span several
zones.

In South Tyrol either the Italian or the German name works (`"Bolzano"` or
`"Bozen"`), although DPC writes them as `"Bolzano/Bozen"` in the criticality
bulletin and as `"Bolzano"` in the vigilance bulletin.

### Coverage check

`await dpc.is_location_covered(Location(lat, lon))` returns whether the
coordinates are inside a DPC alert zone, for example to validate a
configuration.

`await dpc.get_alert_zone(Location(lat, lon))` returns the alert zone of the
coordinates with its municipalities (`zone.name`, `zone.municipalities`), for
example to let a user pick a municipality, and raises `DpcLocationError` when
the coordinates are in no zone.

### Errors

All errors derive from `DpcError`:

- `DpcConnectionError`: network error, HTTP error status or timeout.
- `DpcParseError`: invalid JSON or unexpected data format.
- `DpcLocationError`: the location is not inside any zone of the bulletin.
- `DpcNoDataError`: no published bulletin covers the requested day.

Invalid arguments (coordinates, bulletin IDs) raise `ValueError`.

### Translations and codes

`AlertLevel`, `Precipitation`, `RiskType` and `PhenomenonCategory` print as
English codes (`orange`, `very_heavy`, `hydrogeological`, `wave_motion`),
ready to be used as translation keys; `Phenomenon.code` is the DPC
`id_fenomeno`. The texts written by DPC are kept in Italian (`description`).

### Low-level API

- `aiodpc.parsers`: pure parsing functions taking the decoded GeoJSON, to parse
  one download for several locations or to test without network.
- `aiodpc.urls`: URLs of the bulletin files.
- `aiodpc.discovery`: the latest bulletin ID is read from the DPC map pages by
  default (`MapPageIdSource`); implement `BulletinIdSource` to use another
  source.

## Data source and attribution

The data is published by the Dipartimento della Protezione Civile on
[mappe.protezionecivile.gov.it](https://mappe.protezionecivile.gov.it/) and
GitHub
([pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica](https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica),
[pcm-dpc/DPC-Bollettini-Vigilanza-Meteorologica](https://github.com/pcm-dpc/DPC-Bollettini-Vigilanza-Meteorologica))
under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
license. Applications showing the data must credit:

> Dipartimento della Protezione Civile – Presidenza del Consiglio dei Ministri

The text is available as `aiodpc.ATTRIBUTION`.

This project is not affiliated with or endorsed by DPC. The bulletins are
official, but this library is not: for safety decisions, always refer to
the official DPC and regional channels.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install --editable . --group dev   # pip >= 25.1
ruff format --check . && ruff check .
mypy
pytest --cov
```

The tests never reach DPC: a local HTTPS server answers for the DPC hosts.
`tests/fixtures/real` holds unmodified excerpts of real bulletins to guard the
data format.

To release, set `__version__` in `src/aiodpc/__init__.py`, describe the
changes in a `## [X.Y.Z] - Unreleased` section of [CHANGELOG.md](CHANGELOG.md),
commit, then run `./publish.sh X.Y.Z` (`--dry-run` first to preview). It
creates the GitHub release with the changelog notes, and the release workflow
publishes to PyPI.

## Credits

aiodpc derives from the [DPC Alert](https://github.com/caiosweet/Home-Assistant-custom-components-DPC-Alert)
Home Assistant integration by caiosweet (MIT license).

## License

MIT, see [LICENSE](LICENSE).
