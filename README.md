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

Given a location (coordinates, optionally a municipality), aiodpc finds its
zone and returns typed results. It is built on `asyncio` and `aiohttp`, has no
Home Assistant dependency and is fully typed.

## Installation

```bash
pip install aiodpc
```

Python 3.13 or later is required.

## Usage

```python
import asyncio

from aiodpc import AlertLevel, DpcClient, DpcError, Risk


async def main() -> None:
    async with DpcClient() as client:
        try:
            criticality = await client.get_criticality(41.9, 12.5)
            vigilance = await client.get_vigilance(
                41.9, 12.5, phenomena_radius_km=50
            )
        except DpcError as err:
            print(f"DPC data unavailable: {err}")
            return

    print(f"Criticality bulletin {criticality.id}")
    for day in criticality.days:
        print(f"{day.date} {day.zone_name}: {day.summary.alert}")
        for risk, assessment in day.risks.items():
            print(f"  {risk.name.lower()}: {assessment.level.name}")

    if (today := criticality.today()) and today.max_level >= AlertLevel.YELLOW:
        print("Alert today:", today.risks[Risk.HYDROGEOLOGICAL].info)

    for day in vigilance.days:
        print(f"{day.date} {day.zone_name}: {day.precipitation}")
        for phenomenon in day.phenomena:
            print(
                f"  {phenomenon.category} {phenomenon.description}"
                f" {phenomenon.distance_km} km {phenomenon.direction}"
            )


asyncio.run(main())
```

Pass your own session with `DpcClient(session)`; the client never closes a
session it did not create.

### Days and expiry

Each day of a bulletin carries its calendar `date` and its `expires` time (the
midnight, Europe/Rome, that ends the day). Look days up by date instead of by
position: `bulletin.day_for(date)`, `bulletin.today()` and
`bulletin.tomorrow()`. After midnight the bulletin published the day before
still answers `today()` with its second day until DPC publishes a new one.

By default, days that are already over are not downloaded
(`skip_expired=False` to get them all, e.g. for a past `bulletin_id`).

### Polling

The bulletin files are large (several MB per day). To poll, check the latest
ID and fetch the bulletin only when it changed:

```python
from aiodpc import BulletinKind

latest = await client.latest_bulletin_id(BulletinKind.CRITICALITY)
if latest != criticality.id:
    criticality = await client.get_criticality(41.9, 12.5, bulletin_id=latest)
```

The criticality bulletin is published every day by 16:00 (Europe/Rome) and may
be re-issued later the same day ("Aggiornamento"); the vigilance bulletin by
15:00.

### Municipality

With `municipality="Roma"`, the zones that list the municipality are
considered and the one with the highest level is used; `zone_name` is the zone
containing the coordinates. Large municipalities span several zones.

### Coverage check

`await client.is_location_covered(lat, lon)` returns whether the coordinates
are inside a DPC alert zone, for example to validate a configuration.

### Errors

All errors derive from `DpcError`:

- `DpcConnectionError`: network error, HTTP error status or timeout.
- `DpcParseError`: invalid JSON or unexpected data format.
- `DpcLocationError`: the location is not inside any zone of the bulletin.

Invalid arguments (coordinates, bulletin IDs) raise `ValueError`.

### Translations and codes

The texts written by DPC are kept in Italian (`Assessment.info`,
`Assessment.alert`, `VigilanceDay.precipitation`,
`Phenomenon.description`). Codes are exposed for translation and icons:
`AlertLevel`, `Risk` (value: the DPC code, e.g. `idraulico`),
`PhenomenonCategory` (e.g. `PRECIPITAZIONI`) and `Phenomenon.code` (the DPC
`id_fenomeno`).

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

## Credits

aiodpc derives from the [DPC Alert](https://github.com/caiosweet/Home-Assistant-custom-components-DPC-Alert)
Home Assistant integration by caiosweet (MIT license).

## License

MIT, see [LICENSE](LICENSE).
