# The bulletins as numeric codes

Every bulletin that the Italian Civil Protection Department (DPC) published in
a quarter, in the compact form of aiodpc: numeric codes for every zone and
day instead of GeoJSON, with the zones in tables of their own. It is the
proof of concept of the [study of the DPC data](../docs/study/en.md), to read
and to try. aiodpc and this data are not affiliated with DPC.

| Folder | Criticality bulletins | Vigilance bulletins | DPC files | Here |
|---|---:|---:|---:|---:|
| [`2026-Q3`](2026-Q3) | 97, from `20260701_1543` to `20260930_1423` | 92, from `20260701` to `20260930` | 746 files, 1.83 GB | 1.11 MB of bulletins and 8.2 MB of zones |

A quarter of bulletins takes 1,640 times fewer bytes than the files DPC
published, and 100 kB compressed with gzip. Most of what is left are the
shapes of the zones, written once: the 97 criticality bulletins of 2026-Q3
share one zone table, and so do the 92 vigilance bulletins.

## Files

```text
2026-Q3/
  criticality.jsonl     one criticality bulletin per line, in the order of their IDs
  vigilance.jsonl       one vigilance bulletin per line, with its phenomena
  zones/
    68bcac32826e.json     the zone table of the criticality bulletins
    68bcac32826e.geojson  the shapes of those zones
    d124f4a6cd97.json     the zone table of the vigilance bulletins
    d124f4a6cd97.geojson  the shapes of those zones
```

Each line of a `.jsonl` file is the document of
`CompactCriticality.to_json()` or `CompactVigilance.to_json()`: what a reader
of the bulletins would download each day. A criticality bulletin of the
quarter is 7.5 kB on average and a vigilance bulletin 4.3 kB.

```json
{"schema":1,"kind":1,"bulletin":"20260701_1543","zone_set":"68bcac32826e",
 "columns":["day","zone","level","criticality","mapped_risk","hydraulic","thunderstorms","hydrogeological"],
 "rows":[[0,28,2,2,2,1,2,2],[0,39,2,2,2,1,2,2],...]}
```

| Field | What it is |
|---|---|
| `schema` | Version of the layout of the document: it changes with a column |
| `kind` | `BulletinKind` code: 1 criticality, 2 vigilance |
| `bulletin` | ID of the bulletin, as DPC names its files |
| `zone_set` | Fingerprint of the zone table: the file `zones/ZONE_SET.json` |
| `columns`, `rows` | One row per zone and day, the values in the order of `columns` |
| `phenomena` | Vigilance only: `columns` and `rows` of the weather phenomena |

The columns of the rows:

| Bulletin | Column | Code |
|---|---|---|
| Both | `day` | Days after the day of publication: 0 and 1 for criticality, 0 to 2 for vigilance |
| Both | `zone` | Code of the zone in its zone table |
| Criticality | `level` | `AlertLevel`: 1 green, 2 yellow, 3 orange, 4 red (0 unknown) |
| Criticality | `criticality` | `Criticality` of the summary of the zone |
| Criticality | `mapped_risk` | `RiskType` the summary names; 0 when none |
| Criticality | `hydraulic`, `thunderstorms`, `hydrogeological` | `AlertLevel` of each risk |
| Vigilance | `precipitation` | `Precipitation`: the DPC `id_classificazione` |
| Phenomena | `day`, `code` | Day, and `PhenomenonType`: the DPC `id_fenomeno` |
| Phenomena | `latitude`, `longitude` | Position, 5 decimals (about 1 m) |

Every code is in the [data dictionary](../docs/data-dictionary.xlsx) and in
the enums of aiodpc (`AlertLevel.from_code(3)`); `aiodpc.Translator` tells it
in 13 languages.

A zone table (`zones/ZONE_SET.json`) gives each zone a code, its position in
name order, and lists its municipalities as DPC writes them, sorted and each
once. The codes hold for the zone set only: DPC publishes no codes of zones,
and a bulletin with other zones names another zone set. The `.geojson` file
of the same name has the shape of each zone, with its `code` and `name`.

## Reading it with pandas

The zones with the most days of orange or red alert, on the day of
publication:

```python
import json

import pandas as pd
from aiodpc import AlertLevel, Translator

folder = "data/2026-Q3"
english = Translator("en")

# One row per bulletin, then one row per zone and day
bulletins = pd.read_json(f"{folder}/criticality.jsonl", lines=True, dtype=False)
rows = bulletins.explode("rows", ignore_index=True)
alerts = pd.DataFrame(rows["rows"].tolist(), columns=bulletins["columns"][0])
alerts[["bulletin", "zone_set"]] = rows[["bulletin", "zone_set"]]

# The names of the zones, from the zone table each bulletin names
zones = []
for zone_set in alerts["zone_set"].unique():
    with open(f"{folder}/zones/{zone_set}.json", encoding="utf-8") as file:
        table = json.load(file)
    zones += [(zone_set, code, name) for code, name, _ in table["rows"]]
zones = pd.DataFrame(zones, columns=["zone_set", "zone", "zone_name"])
alerts = alerts.merge(zones, on=["zone_set", "zone"])
alerts["level_name"] = [english(AlertLevel.from_code(code)) for code in alerts["level"]]

# Days with an orange or red alert, on the day of publication
severe = alerts[(alerts["day"] == 0) & (alerts["level"] >= AlertLevel.ORANGE.code)]
days = severe.groupby("zone_name")["bulletin"].agg(lambda ids: ids.str[:8].nunique())
print(days.sort_values(ascending=False, kind="stable").head(5).to_string())
print(alerts[["bulletin", "day", "zone_name", "level_name"]].head(3).to_string())
```

```text
zone_name
Lario e Prealpi occidentali                                          6
Orobie bergamasche                                                   6
Alta pianura orientale                                               5
Bassa collina e pianura romagnola                                    5
Colli Euganei e Colli Berici - Bacini Bacchiglione Fratta-Gorzone    5
        bulletin  day              zone_name    level_name
0  20260701_1543    0  Bacini Tordino Vomano  Yellow alert
1  20260701_1543    0     Bacino dell'Aterno  Yellow alert
2  20260701_1543    0     Bacino del Pescara  Yellow alert
```

`dtype=False` keeps the IDs of the bulletins as text: otherwise pandas may
read `20260701` as a number.

## Reading it with DuckDB

The same question in SQL. DuckDB reads the rows as lists, numbered from 1 in
the order of `columns`: `r[1]` is `day`, `r[2]` `zone` and `r[3]` `level`.

```sql
WITH zones AS (
  SELECT zone_set, z[1]::INTEGER AS zone, z[2] ->> '$' AS zone_name
  FROM (
    SELECT zone_set, unnest(rows) AS z
    FROM read_json('data/2026-Q3/zones/*.json')
  )
),
alerts AS (
  SELECT bulletin, zone_set, unnest(rows) AS r
  FROM read_json('data/2026-Q3/criticality.jsonl')
)
SELECT zone_name, count(DISTINCT left(bulletin, 8)) AS days
FROM alerts
JOIN zones ON zones.zone_set = alerts.zone_set AND zones.zone = r[2]
WHERE r[1] = 0 AND r[3] >= 3
GROUP BY zone_name
ORDER BY days DESC, zone_name
LIMIT 5;
```

```text
┌───────────────────────────────────────────────────────────────────┬───────┐
│                             zone_name                             │ days  │
│                              varchar                              │ int64 │
├───────────────────────────────────────────────────────────────────┼───────┤
│ Lario e Prealpi occidentali                                       │     6 │
│ Orobie bergamasche                                                │     6 │
│ Alta pianura orientale                                            │     5 │
│ Bassa collina e pianura romagnola                                 │     5 │
│ Colli Euganei e Colli Berici - Bacini Bacchiglione Fratta-Gorzone │     5 │
└───────────────────────────────────────────────────────────────────┴───────┘
```

The zone tables mix numbers, names and lists in each row, so DuckDB reads
them as JSON: `->> '$'` takes the name as text.

## Writing a quarter again

```bash
pip install --editable .
python data/build.py 2026-Q3
```

[`build.py`](build.py) reads every bulletin DPC published in the quarter from
its GitHub repositories (about 2 minutes and 1.8 GB for 2026-Q3) and keeps
nothing else. A past quarter is fixed: running it again writes the same
files, byte for byte.

## License and attribution

The data is © Dipartimento della Protezione Civile – Presidenza del
Consiglio dei Ministri, under the
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) license, from
[DPC-Bollettini-Criticita-Idrogeologica-Idraulica](https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica)
and
[DPC-Bollettini-Vigilanza-Meteorologica](https://github.com/pcm-dpc/DPC-Bollettini-Vigilanza-Meteorologica).

Changes made by aiodpc: only the values described above are kept, each
replaced by its numeric code; the zones are moved to zone tables, with codes
of their own; the municipalities of each zone are sorted, each once; the
positions of the phenomena are rounded to 5 decimals. This data is shared
under the same license.
