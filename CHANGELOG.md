# Changelog

All notable changes to aiodpc. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/): before 1.0, a minor version may
change the API.

## [0.4.0] - Unreleased

### Added

- `DpcClient.get_alert_zone(location)` returns the `AlertZone` of a location:
  its name and its municipalities, for example to let a user pick a
  municipality. It raises `DpcLocationError` when the location is in no zone.
- `aiodpc.parsers.parse_alert_zone()`.

## [0.3.0] - 2026-11-14

Several places now cost a single download: get the bulletin of the whole of
Italy once, then read it at each place.

```python
criticality = await dpc.get_criticality_map()
vigilance = await dpc.get_vigilance_map()

for place in (home, office):
    print(criticality.at(place).today)
    print(vigilance.at(place, phenomena_within_km=20).today)
```

### Added

- `DpcClient.get_criticality_map()` and `DpcClient.get_vigilance_map()` return
  a `CriticalityMap` or a `VigilanceMap`: the files of a bulletin, downloaded
  once. Their `at(location)` returns the bulletin of a location without any
  request; on the vigilance map, each reading takes its own
  `phenomena_within_km`. A location outside every zone raises
  `DpcLocationError` for that location only.
- `aiodpc.parsers.GeoJsonFeatures`: a DPC GeoJSON file checked once. The parse
  functions accept it in place of the decoded GeoJSON.
- `aiodpc.parsers.check_phenomena_distance()`.

### Changed

- `get_criticality()` and `get_vigilance()` read a map, with the same results.
- The JSON files are decoded in a worker thread: they are several MB each, and
  decoding them blocked the event loop.

## [0.2.1] - 2026-11-14

### Fixed

- The municipalities of South Tyrol are found by their Italian or German name
  (`"Bolzano"` or `"Bozen"`) in both bulletins. DPC writes them as
  `"Bolzano/Bozen"` in the criticality bulletin and as `"Bolzano"` in the
  vigilance bulletin, and a few of them differently (`"Rasun Anterselva"`, or
  `"Salorno"` before its renaming), so they were not found and the coordinates
  were used instead. `aiodpc.municipalities` holds these other names.
- A municipality is first looked up as written; its other names are tried only
  when no zone lists it, so `"Corvara"` (Abruzzo) is never taken for
  `"Corvara in Badia/Corvara"`.

## [0.2.0] - 2026-11-14

The API now has three levels: ask whether a place has a risk, read the
bulletins day by day, or get the raw DPC files.

```python
async with DpcClient() as dpc:
    home = dpc.location(41.9, 12.5)

    if await home.has_risk(Day.TOMORROW):
        print(await home.risk(Day.TOMORROW))  # yellow (hydrogeological)
```

### Added

- `DpcClient.location()` returns a `MonitoredLocation` that answers
  `has_risk()` and `risk()` for today, tomorrow (`Day.TOMORROW`) or a date.
  It keeps the bulletin and downloads it again only when DPC publishes a new
  one, so it can be polled freely.
- `Risk`: the alert level, the risk types at that level, the DPC description,
  the end of validity and the complete day.
- `Location`: coordinates and optional municipality, validated once.
- `Precipitation`: the expected precipitation of the vigilance bulletin, from
  `none` to `very_heavy`.
- Optional strict DTOs of the raw DPC files (`pip install "aiodpc[schema]"`):
  `get_criticality_file()`, `get_vigilance_file()`, `get_phenomena_file()` and
  the `aiodpc.schema` decoders. They raise `DpcParseError` naming the field
  when DPC changes its format.
- `DpcNoDataError`: no published bulletin covers the requested day.
- Bulletins are iterable and have `today`, `tomorrow` and `on(date)`.
- Criticality days have each risk as an attribute (`day.hydrogeological`),
  `is_alert` and `assessment(risk_type)`.
- Levels print as their name (`str(AlertLevel.ORANGE) == "orange"`) and
  phenomena as a readable sentence (`wind: forti, 30.4 km WSW`).

### Changed

These changes break code written for 0.1.0:

| 0.1.0 | 0.2.0 |
| --- | --- |
| `get_criticality(lat, lon, municipality=...)` | `get_criticality(Location(lat, lon, municipality=...))` |
| `get_vigilance(lat, lon, phenomena_radius_km=...)` | `get_vigilance(location, phenomena_within_km=...)` |
| `is_location_covered(lat, lon)` | `is_location_covered(location)` |
| `Risk` (enum, Italian values) | `RiskType` (English values: `hydraulic`, ...) |
| `AlertLevel.NONE` | `AlertLevel.GREEN` |
| `day.zone_name` | `day.zone` |
| `day.expires` | `day.valid_until` |
| `day.summary`, `day.max_level` | `day.description`, `day.level` |
| `day.risks[Risk.HYDRAULIC]` | `day.hydraulic` (`day.risks` is now a tuple) |
| `Assessment(info, alert, level)` | `RiskAssessment(type, level, description)` |
| `VigilanceDay.level` (int) and `.precipitation` (text) | `VigilanceDay.precipitation` (`Precipitation`) |
| `PhenomenonCategory` Italian values (`PRECIPITAZIONI`) | English values (`precipitation`) |
| `bulletin.today(now)`, `tomorrow(now)`, `day_for(date)` | `bulletin.today`, `tomorrow` (properties), `on(date)` |
| `aiodpc.parsers.day_expires` | `aiodpc.parsers.end_of_day` |

The functions of `aiodpc.parsers` take a `Location`, and `parse_assessment`
returns the level and the description.

## [0.1.0] - 2026-11-14

First release.

- Async client of the DPC criticality bulletin (alert level of each risk for
  today and tomorrow) and weather vigilance bulletin (expected precipitation
  and significant phenomena for three days).
- Zone lookup by coordinates, optionally by municipality.
- Discovery of the latest bulletin from the DPC map pages, replaceable with
  another `BulletinIdSource`.
- Typed, immutable models; errors `DpcConnectionError`, `DpcParseError` and
  `DpcLocationError`.
- Pure parsing functions, no Home Assistant dependency, fully typed.

[0.4.0]: https://github.com/webysther/aiodpc/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/webysther/aiodpc/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/webysther/aiodpc/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/webysther/aiodpc/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/webysther/aiodpc/releases/tag/v0.1.0
