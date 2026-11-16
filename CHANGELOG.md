# Changelog

All notable changes to aiodpc. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/): before 1.0, a minor version may
change the API.

## [0.9.0] - 2026-11-16

The compact bulletins are JSON only: one document per bulletin, on a single
line, so the bulletins of a period are a JSON Lines file. The JSON document
keeps both bulletins in one file each, with their header, and its numbers
stay numbers; compressed, it is about the size of the CSV it replaces.

### Removed

- **Breaking:** `CompactCriticality.to_csv()`, `CompactVigilance.to_csv()`,
  `CompactVigilance.phenomena_csv()`, `ZoneTable.to_csv()` and
  `aiodpc.compact.MUNICIPALITY_SEPARATOR`. Use `to_json()`: the same rows
  under `"rows"`, in the order of `"columns"`, and the phenomena under
  `"phenomena"`. For a table, `pandas.DataFrame(document["rows"],
  columns=document["columns"])`.

### Added

- `DpcClient.get_preview()`: the preview image of the map of a day, or `None`
  while DPC publishes it blank, and `aiodpc.previews.is_blank_preview()` for a
  preview downloaded by other means, without an imaging library. From August
  to November 2026, DPC published 40% of the criticality previews and 5% of
  the vigilance previews blank, and replaced only some of them later, at the
  same address: ask again later rather than keep a blank one.
- A watch of the live data in the repository (`data/watch.py`, run by a
  workflow four times a day): it reads every day of the latest bulletins and
  opens an issue for what aiodpc does not expect, such as a new text, a format
  change, an encoding error or zones the census has not seen, so that a
  change of DPC is handled before it reaches the users.
- `data/2026-Q3` in the repository: every bulletin of the third quarter of
  2026 as JSON Lines, 1.1 MB for the 1.8 GB of GeoJSON that DPC published,
  with examples in pandas and DuckDB. `data/build.py` writes any quarter.

## [0.8.0] - 2026-11-16

### Added

- Seven languages: Simplified Chinese (`zh-Hans`), Romanian, Arabic,
  Ukrainian, Albanian, Bengali and Hindi, with a text for every value of the
  models, as the other six. `Language.of` finds them by their tags, such as
  `"zh-CN"`, `"uk_UA"` or `"hi-IN"`; Chinese in any script or region gets the
  simplified texts.

## [0.7.0] - 2026-11-16

### Added

- `aiodpc.i18n`: a text for every value of the models in English, Italian,
  Brazilian Portuguese, French, German and Spanish, checked by the tests so
  that none is missing. `Translator("pt-BR")` tells any value as a label
  (`tell(AlertLevel.YELLOW)`, "Alerta amarelo"), a risk with its risk types
  (`tell.risk(risk)`), the DPC description of a risk, day or assessment
  (`tell.description(risk)`, "Criticidade ordinária para risco
  hidrogeológico") and a phenomenon with its distance and direction
  (`tell.phenomenon(phenomenon)`). In Italian the texts are those DPC writes;
  a DPC text aiodpc does not recognise is returned as it is.
- `Criticality` and the `criticality` of `RiskAssessment`, `CriticalityDay`
  and `Risk`: the DPC description read into an enum (`"Ordinaria"` is
  `Criticality.ORDINARY`). Every DPC text since 2020 is one of four
  criticalities, each always with the same alert level.
- `mapped_risk` of `CriticalityDay` and `Risk`: the one risk the DPC summary
  of a zone names, the one its map shows, even when other risks have the same
  level (`Risk.types` has all of them).
- `CompassPoint`: the 16 compass points, translated like the other values.
- `Language.of(tag)`: the language of a tag such as `"pt_BR"` or `"it-IT"`.
- A tutorial in the README and in `examples/tutorial.ipynb`, from one question
  about one place to the map of Italy and the same notice in six languages.
- `code` and `from_code()` on every value: `AlertLevel.YELLOW.code` is 2,
  `RiskType.from_code(3)` is `RiskType.HYDROGEOLOGICAL`. The codes DPC
  publishes are kept (`id_fenomeno`, `id_classificazione`); the others are
  listed in the data dictionary and never change once released.
- `CriticalityMap.compact()` and `VigilanceMap.compact()`
  (`aiodpc.compact`): a whole bulletin as records of numeric codes, with the
  zones in a `ZoneTable` whose `fingerprint` changes only when the zones do.
  A day of both bulletins is about 13 kB of CSV instead of 19 MB of GeoJSON.
- `docs/data-dictionary.xlsx`: every field of the DPC files and every value
  they take, with a numeric code, the text DPC writes and its translations.
- `docs/study/`: a study of the DPC data, in English and Italian, with the
  measurements and a proposal of a lighter data model, and `CITATION.cff` to
  cite aiodpc and the study.

### Changed

- `Phenomenon.direction` is a `CompassPoint` instead of a `str`. It is still
  equal to its abbreviation (`direction == "WNW"`); type checkers ask for
  `CompassPoint.WNW` where code builds a `Phenomenon`.

## [0.6.0] - 2026-11-15

### Added

- `PhenomenonType` and `Phenomenon.type`: the type of a weather phenomenon,
  one per code of the DPC legend, named in English (`light_snow`,
  `moderate_sea`, `rising_waves`...), for applications that show it in their
  own language. `Phenomenon.description` keeps the legend as DPC writes it,
  in Italian. `PhenomenonType.of(code)` and
  `aiodpc.models.PHENOMENON_TYPE_CODES` map the codes to the types.

## [0.5.0] - 2026-11-15

### Added

- `Day.AFTER_TOMORROW` and `VigilanceBulletin.after_tomorrow`: the third day
  of the vigilance bulletin, looked up by date like `today` and `tomorrow`.
  The criticality bulletin covers only today and tomorrow.
- `Phenomenon.key`: what identifies a phenomenon among those of its day, its
  code and position (e.g. `"5@41.57313417,12.67477485"`). A later bulletin
  with the same phenomenon at the same place, for the same day, gives the
  same key, whatever location it is read at.

### Changed

- `Day` has a third member, `AFTER_TOMORROW`. Code that iterates over `Day`
  for the days of the criticality bulletin gets it too: list them instead,
  `(Day.TODAY, Day.TOMORROW)`.

## [0.4.1] - 2026-11-15

### Fixed

- A municipality is looked up only in the zones near its location, within
  60 km. DPC lists the municipalities by name, and a few names belong to two
  municipalities far apart: Peglio, in Lombardy and in the Marche, got the
  highest alert of both. So did Livo, Samone, Castro, San Teodoro, Calliano
  and Valverde. Each now gets its own zone. A municipality listed only far
  from the location is ignored, with a warning, and the coordinates are used.
- "Corvara in Badia/Corvara", as the criticality bulletin lists it, no longer
  matches the Corvara of Abruzzo in the vigilance bulletin.

### Added

- `aiodpc.geo.distance_to_area_km()`: the distance from a point to a Polygon
  or MultiPolygon, 0 inside it.
- `aiodpc.parsers.MUNICIPALITY_RADIUS_KM`, the 60 km above.

## [0.4.0] - 2026-11-14

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

[0.9.0]: https://github.com/webysther/aiodpc/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/webysther/aiodpc/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/webysther/aiodpc/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/webysther/aiodpc/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/webysther/aiodpc/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/webysther/aiodpc/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/webysther/aiodpc/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/webysther/aiodpc/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/webysther/aiodpc/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/webysther/aiodpc/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/webysther/aiodpc/releases/tag/v0.1.0
