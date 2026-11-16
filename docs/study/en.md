# The DPC alert bulletins as open data: a lighter model

*A study of the open data of the national bulletins of the Italian Civil
Protection Department (Dipartimento della Protezione Civile, DPC), with a
proposal. [Versione italiana](it.md).*

Every number below is measured by [`measure.py`](measure.py), which anyone can
run again; its output is [`results.json`](results.json). The measurements use
the bulletins published up to 15 November 2026.

## Summary

Every afternoon DPC publishes two bulletins for the whole of Italy: the
**criticality bulletin** (the alert level of each alert zone for the
hydraulic, thunderstorm and hydrogeological risks, for today and tomorrow) and
the **weather vigilance bulletin** (the expected precipitation of each
vigilance zone and the significant weather phenomena, for three days). They
are published as open data, under CC BY 4.0, in GeoJSON and other formats.

- One day of both bulletins is **19.3 MB** of GeoJSON. The alerts themselves
  are a few kilobytes of it: **96%** of a criticality file is the shape of the
  zones, which is the same every day.
- The same information as numeric codes is **13.4 kB**, **1,438 times
  smaller** (3.8 kB compressed, 2,012 times smaller than the compressed
  GeoJSON). The shapes and the municipalities go in a reference published only
  when they change: five times in the six years measured.
- Every value of the bulletins belongs to a small closed set. Over 2,572
  bulletins since 2020, the Italian texts are four criticalities and three
  risks, each criticality always with the same alert level. They can be
  numeric codes, which any application can tell in any language.
- The files have defects that a model with codes avoids: characters lost by an
  encoding error in every file, a zone name cut at 150 bytes, municipality
  lists repeating names up to 62 times (2020 to 2024), two spellings of the
  same fields, and zones renamed without an identifier that stays.

The proposal: keep the current files, and publish next to them a versioned
reference of the zones (with stable codes and the ISTAT codes of the
municipalities) and three small daily files of numeric codes, following the
[data dictionary](../data-dictionary.xlsx).

## 1. What DPC publishes

The bulletins are published on
[mappe.protezionecivile.gov.it](https://mappe.protezionecivile.gov.it/) and in
two GitHub repositories,
[DPC-Bollettini-Criticita-Idrogeologica-Idraulica](https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica)
and
[DPC-Bollettini-Vigilanza-Meteorologica](https://github.com/pcm-dpc/DPC-Bollettini-Vigilanza-Meteorologica).

| Bulletin | Files a day (GeoJSON) | Size | Features |
|---|---|---|---|
| Criticality | today, tomorrow | 2 × 5.53 MB | 187 alert zones |
| Vigilance, zones | today, tomorrow, the day after | 3 × 2.72 MB | 71 vigilance zones |
| Vigilance, phenomena | today, tomorrow, the day after | 0.02 to 0.03 MB | 63 to 91 points |
| **One day** | **8 files** | **19.3 MB** (7.6 MB compressed) | |

Measured on the bulletins of 15 November 2026 (criticality `20261115_1421`,
vigilance `20261115`). The criticality repository counts 2,572 bulletins
from 1 January 2020 to 15 November 2026, on 2,511 days: on 58 days DPC
published an update. The repositories hold every day since, in several
formats (GeoJSON, TopoJSON, shapefile, XML, PDF and images): they weigh
6.6 GB and 12.9 GB (GitHub, 16 November 2026).

Each zone of a criticality file carries its name (`Nome zona`), its
municipalities by name (`Comuni`), its shape, and four texts:

```json
"Rappresentata nella mappa": "Ordinaria per rischio idrogeologico / ALLERTA GIALLA",
"Per rischio idraulico": "Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA",
"Per rischio temporali": "Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA",
"Per rischio idrogeologico": "Ordinaria / ALLERTA GIALLA"
```

A vigilance zone carries its name (`Nome_Zona`), its municipalities
(`comuni`), its shape, the class of the expected precipitation
(`id_classificazione`, a number) and its text (`Quantitativi_previsti`). A
phenomenon is a point with a code (`id_fenomeno`, a number).

## 2. What the files are made of

![What a criticality file is made of](figures/en-composition.png)

| File | Zone shapes | Municipality lists | Names and alerts |
|---|---|---|---|
| Criticality | 96.3% | 2.1% | 1.4% |
| Vigilance, zones | 93.8% | 5.6% | 0.3% |

The bulletin itself, what changes from one day to the next, is between 0.3%
and 1.4% of a zone file. The phenomena files are small already (20 to 29 kB).

## 3. The zones rarely change

A sample of 73 criticality files from July 2020 to September 2026, drawn among
the days with red alerts, orange alerts and several risks (12,250 zone-days),
gives the history of the zones:

![Alert zones in the sampled bulletins](figures/en-zones.png)

- **The shapes are the same from one bulletin to the next.** Comparing each
  zone with the same zone in the previous sampled file, the shape is
  byte-identical in 11,684 of 12,041 comparisons (97.0%). The 357 others
  happen at five moments: in 2021-04 (14 zones), 2021-07 (13), 2023-05 (166
  of 170 zones), 2026-01 (16) and 2026-08 (148 of 187). Each is dated by the
  first sampled file that shows it: the 2026-01 change happened between
  9 November 2025 and 18 January 2026.
- **The set of zones changed four times:** from 158 zones to 168 in 2021-04
  (18 added, 8 removed), to 170 in 2021-07, four zones renamed in 2023-05, and
  187 zones in 2026-08 (26 added, 9 removed).
- **Zones are renamed without an identifier that stays.** "Nodo idraulico di
  Milano" became "Nodo Idraulico di Milano" (a capital letter) in 2021-07;
  "Pianura bolognese di Reno e suoi affluenti" became "Pianura bolognese" in
  2023-05. Matching zones by name across bulletins breaks at each change.

Publishing the shapes every day sends the same 5.3 MB of criticality shapes
and 2.6 MB of vigilance shapes again and again: 18.3 of the 19.3 MB of a
day.

## 4. Every value belongs to a closed set

The HTML summaries of all the 2,572 bulletins, and every zone of the sample,
use only these texts:

| Criticality | Alert | Risks |
|---|---|---|
| Assenza di fenomeni significativi prevedibili | NESSUNA ALLERTA (green) | none |
| Ordinaria | ALLERTA GIALLA (yellow) | idraulico, temporali, idrogeologico |
| Moderata | ALLERTA ARANCIONE (orange) | idraulico, temporali, idrogeologico |
| Elevata | ALLERTA ROSSA (red) | idraulico, idrogeologico |

- Each criticality always goes with the same alert level: the four pairs
  above are the only ones in 12,250 zone-days.
- The summary of a zone (`Rappresentata nella mappa`) names one risk, the one
  its map shows, even when other risks have the same level.
- DPC never published a red alert for thunderstorms in the period.
- The precipitation of the vigilance bulletin is already a class (1 to 5), and
  the phenomena already have codes (24 in the DPC legend).

A text that is always one of a few values is a code written in words, and in
one language. As numbers, each value is a code; a list of codes gives its
label in Italian, and in any language. aiodpc does it in six languages today.

## 5. Defects that codes avoid

| Defect | Measured |
|---|---|
| Characters lost by an encoding error | "Valle d?Aosta" (Valle d’Aosta) in every one of the 73 sampled files; "Savogna d'Isonzo-Sovodnje ob So?i" (Soči) in 19 |
| A zone name cut short | Since 2026-08, "…Valle di Champorcher e Valle di Gressoney" is "…Valle di Gresso": 146 characters, exactly 150 bytes with its two typographic apostrophes, which suggests a 150-byte field |
| Municipalities repeated | 21 of the 73 sampled files, from 2020 to February 2024, repeat names up to 62 times: 4,671,290 entries for 598,107 municipalities. A 2020 file lists 205,375 names for 8,215 municipalities. The files of 2026 have no repeats |
| Two spellings of the same field | `Nome zona` and `Comuni` in the criticality files, `Nome_Zona` and `comuni` in the vigilance files |
| Two languages in the file names | `_today`, `_tomorrow` for the criticality files; `_oggi`, `_domani`, `_dopodomani` for the vigilance files and the preview images of both |
| Municipalities by name only | Seven names (Peglio, Livo, Samone, Castro, San Teodoro, Calliano, Valverde) each belong to two municipalities far apart; "Bolzano/Bozen" in one bulletin is "Bolzano" in the other |
| Fields of the phenomena | `id` is empty in every phenomenon of the files of 15 November 2026; `data_bollettino` is a date with a time zone ("2026-11-15Z") |

## 6. The proposal

Keep the current files, so that no application breaks, and publish next to
them:

1. **A reference of the zones, versioned.** One file of the alert zones and one
   of the vigilance zones, each with a stable code per zone, its name, its
   shape and the ISTAT codes of its municipalities, each once. A new version
   only when the zones change, with the date it applies from; the previous
   versions stay.
2. **Three small daily files of codes**, which name the version of the zones
   they use:
   - criticality: day, zone code, alert level of the zone, risk shown on the
     map, alert level of each of the three risks;
   - vigilance: day, zone code, precipitation class;
   - phenomena: day, phenomenon code, latitude, longitude.
3. **The lists of codes**, with their labels in Italian: the
   [data dictionary](../data-dictionary.xlsx) proposes one, which keeps the
   codes DPC already publishes (`id_classificazione`, `id_fenomeno`).

Some fixes are worth making in the current files too: UTF-8 throughout, no
limit that cuts names, the same spelling of the fields in both bulletins, and
dates in ISO 8601 (`2026-11-15`).

The criticality does not need a column of its own: in every bulletin
measured it follows from the alert level. It can be kept for clarity.

## 7. What it saves

![Bytes of one day of both bulletins](figures/en-sizes.png)

| | GeoJSON today | Codes | Ratio |
|---|---|---|---|
| One day | 19.3 MB | 13.4 kB | 1,438× |
| One day, compressed (gzip) | 7.6 MB | 3.8 kB | 2,012× |
| One year (365 days) | 7.0 GB | 4.9 MB | |
| Reading one day (JSON or CSV, in Python) | about 0.4 s | 0.3 ms | over 1,000× |

The reference of the zones weighs 5.3 MB (alert zones) and 2.6 MB
(vigilance zones) as GeoJSON, and 124 kB and 155 kB as tables of names and
municipalities; it is downloaded once per version. The reading times were
measured on one machine and only show the order of magnitude.

Beyond the bytes:

- **Any language.** A code is told in any language from a list of labels;
  DPC's own Italian texts become one of those lists.
- **Fewer errors.** Applications compare numbers instead of parsing Italian
  sentences, whose wording (case, apostrophes, "criticità" or not) varies
  between the files and the summaries.
- **History.** A year of both bulletins fits in about 5 MB: the history of the
  alerts of a zone, or of the whole country, becomes simple to study.
- **Small devices.** A sensor, a phone on a weak connection, or a home
  automation system can follow the alerts without downloading megabytes a
  day.

## 8. Proof of concept

[aiodpc](https://github.com/webysther/aiodpc), an open source Python client of
the DPC bulletins, makes these files from the current ones. The same codes are
in its data dictionary.

```python
import asyncio

from aiodpc import DpcClient


async def main() -> None:
    async with DpcClient() as dpc:
        criticality = await dpc.get_criticality_map(
            bulletin_id="20261115_1421", skip_expired=False
        )
        vigilance = await dpc.get_vigilance_map(
            bulletin_id="20261115", skip_expired=False
        )
    compact = criticality.compact()
    weather = vigilance.compact()

    for text in (compact.to_csv(), weather.phenomena_csv(), compact.zones.to_csv()):
        for line in text.splitlines()[:3]:
            print(line[:78])
    print("zone set", compact.zones.fingerprint)


asyncio.run(main())
```

```text
day,zone,level,criticality,mapped_risk,hydraulic,thunderstorms,hydrogeological
0,28,1,1,0,1,1,1
0,39,1,1,0,1,1,1
day,code,latitude,longitude
0,5,45.82818,7.08536
0,5,44.98053,6.76341
code,name,municipalities
1,Alpago Cansiglio - Bacino Piave,Alpago|Chies d'Alpago|Tambre
2,Alta Irpinia e Sannio,Altavilla Irpina|Andretta|Apice|Apollosa|Aquilonia|Ari
zone set 68bcac32826e
```

Since DPC publishes no zone codes, aiodpc numbers the zones by their names in
alphabetical order, and marks the set of zones with a fingerprint: the codes
hold until the zones change. Stable codes from DPC would hold across changes.

## 9. Method and limits

- **History**: the summary file (`files/YYYYMMDD_HHMM.json`) of every
  criticality bulletin published from 1 January 2020 to 15 November 2026,
  2,572 in all. Their HTML summaries name the criticality, risk and alert of
  each group of zones.
- **Sample**: 73 criticality GeoJSON files, 25 drawn (seed 7) from each group
  of bulletin days: with a red alert (206 days), with an orange alert (1,052)
  and with several risks at the same level (2,854); some days are in two
  groups. The sample favours the days with alerts, where the texts vary most;
  the dates of the changes of the zones are those of the first sampled file
  that shows them.
- **One day in full**: the eight files of 15 November 2026.
- **Not measured**: the TopoJSON, shapefile, XML and PDF files, and the
  vigilance history before November 2026.

The data is © Dipartimento della Protezione Civile – Presidenza del Consiglio
dei Ministri, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
This study is not affiliated with DPC; it was written with aiodpc, whose
authors welcome corrections.
