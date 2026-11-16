"""Write docs/data-dictionary.xlsx: the data model of the DPC bulletins.

Every field of the DPC files, and every value of every domain with a numeric
code, the text DPC writes and its translations, from the tables of aiodpc so
that the document always says what the library does::

    pip install --editable . --group docs
    python docs/data_dictionary.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import aiodpc
from aiodpc import (
    AlertLevel,
    BulletinKind,
    CompassPoint,
    Criticality,
    Day,
    Language,
    PhenomenonCategory,
    PhenomenonType,
    Precipitation,
    RiskType,
    Translator,
)
from aiodpc.i18n import TRANSLATIONS
from aiodpc.parsers import ALERT_LEVELS, PHENOMENON_TYPES, RISK_PROPERTIES
from aiodpc.urls import CRITICALITY_DAYS, VIGILANCE_DAYS

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from enum import Enum

    from openpyxl.worksheet.worksheet import Worksheet

OUTPUT: Final = Path(__file__).with_name("data-dictionary.xlsx")

FONT: Final = "Arial"
HEADER_FILL: Final = PatternFill("solid", start_color="1F4E78")
GROUP_FILL: Final = PatternFill("solid", start_color="DDEBF7")

DPC: Final = "DPC"
"""Code status: the code DPC already publishes."""
AIODPC: Final = "aiodpc"
"""Code status: the code aiodpc uses."""
PROPOSED: Final = "proposed"
"""Code status: a code proposed by this document."""

COMPASS_STEP_DEGREES: Final = 360 / len(CompassPoint)
"""Degrees between two compass points: 22.5."""

UNKNOWN_NOTE: Final = (
    "Not published by DPC: what aiodpc gives a missing or unrecognised value."
)


def labels(value: Enum) -> list[str]:
    """Return the label of a value in every language."""
    return [Translator(language)(value) for language in Language]  # type: ignore[arg-type] # every Enum here is Translatable


def values() -> Iterable[list[object]]:
    """Return a row for every value of every domain."""
    italian = Translator(Language.ITALIAN)
    alert_texts = {level: text for text, level in ALERT_LEVELS.items()}
    for level in AlertLevel:
        note = (
            UNKNOWN_NOTE
            if level is AlertLevel.UNKNOWN
            else "Yellow and higher are alerts."
        )
        yield [
            "AlertLevel",
            level.code,
            AIODPC,
            str(level),
            alert_texts.get(level, ""),
            *labels(level),
            note,
        ]
    for criticality in Criticality:
        unknown = criticality is Criticality.UNKNOWN
        note = (
            UNKNOWN_NOTE
            if unknown
            else f"Always with the alert level of code {criticality.code}."
        )
        yield [
            "Criticality",
            criticality.code,
            AIODPC,
            str(criticality),
            "" if unknown else italian(criticality),
            *labels(criticality),
            note,
        ]
    for risk_type in RiskType:
        note = "No red alert since 2020." if risk_type is RiskType.THUNDERSTORMS else ""
        yield [
            "RiskType",
            risk_type.code,
            PROPOSED,
            str(risk_type),
            RISK_PROPERTIES[risk_type],
            *labels(risk_type),
            note,
        ]
    for precipitation in Precipitation:
        unknown = precipitation is Precipitation.UNKNOWN
        status, text = (AIODPC, "") if unknown else (DPC, italian(precipitation))
        note = UNKNOWN_NOTE if unknown else "The code is id_classificazione."
        yield [
            "Precipitation",
            precipitation.code,
            status,
            str(precipitation),
            text,
            *labels(precipitation),
            note,
        ]
    for category in PhenomenonCategory:
        note = "The tens of id_fenomeno (id_fenomeno // 10)."
        yield [
            "PhenomenonCategory",
            category.code,
            PROPOSED,
            str(category),
            "",
            *labels(category),
            note,
        ]
    for phenomenon_type in PhenomenonType:
        _category, legend = PHENOMENON_TYPES[phenomenon_type.code]
        yield [
            "PhenomenonType",
            phenomenon_type.code,
            DPC,
            str(phenomenon_type),
            legend,
            *labels(phenomenon_type),
            "The code is id_fenomeno; the text is the DPC legend.",
        ]
    for point in CompassPoint:
        degrees = f"{point.code * COMPASS_STEP_DEGREES:g}°"
        yield [
            "CompassPoint",
            point.code,
            PROPOSED,
            str(point),
            "",
            *labels(point),
            f"Computed by aiodpc; {degrees} clockwise from north.",
        ]
    for day in Day:
        files = [
            days[day.value]
            for days in (CRITICALITY_DAYS, VIGILANCE_DAYS)
            if day.value < len(days)
        ]
        yield [
            "Day",
            day.code,
            AIODPC,
            day.name.lower(),
            " / ".join(files),
            *labels(day),
            "Days after the publication day: the offset of the files.",
        ]
    for kind in BulletinKind:
        yield [
            "BulletinKind",
            kind.code,
            PROPOSED,
            str(kind),
            italian(kind),
            *labels(kind),
            "",
        ]


FIELDS: Final[Sequence[Sequence[str]]] = (
    (
        "Criticality bulletin: one GeoJSON a day (files/geojson/{id}_today.json and _tomorrow.json), one feature per alert zone",
    ),
    (
        "Nome zona",
        '"Bacini di Roma"',
        "Name of the alert zone.",
        "CriticalityDay.zone, AlertZone.name",
        "Proper name",
        "Add a stable code of the zone next to its name, so that a zone is followed from one bulletin to the next without matching names.",
    ),
    (
        "Comuni",
        '["Albano Laziale", "Anguillara Sabazia", ...]',
        "Municipalities of the zone, by name only.",
        "AlertZone.municipalities, Location.municipality",
        "Proper names",
        'Add the ISTAT code of each municipality: names are ambiguous (Peglio, Livo, Samone, Castro, San Teodoro, Calliano and Valverde each name two municipalities far apart) and spelled differently by the two bulletins ("Bolzano/Bozen" here, "Bolzano" in the vigilance files).',
    ),
    (
        "Rappresentata nella mappa",
        '"Ordinaria per rischio idrogeologico / ALLERTA GIALLA"',
        "Summary of the zone: its criticality, the one risk the map shows and the alert.",
        "CriticalityDay.description, .criticality, .mapped_risk, .level",
        "Criticality, RiskType, AlertLevel",
        "Three numeric fields instead of one Italian text: the criticality (Criticality), the risk the map shows (RiskType, empty when green) and the alert level (AlertLevel).",
    ),
    (
        "Per rischio idraulico",
        '"Ordinaria / ALLERTA GIALLA"',
        "Criticality and alert of the hydraulic risk.",
        "CriticalityDay.hydraulic: RiskAssessment.criticality, .level",
        "Criticality, AlertLevel",
        "One numeric alert level per risk (AlertLevel); the criticality always goes with it.",
    ),
    (
        "Per rischio temporali",
        '"Moderata / ALLERTA ARANCIONE"',
        "Criticality and alert of the thunderstorm risk.",
        "CriticalityDay.thunderstorms",
        "Criticality, AlertLevel",
        'As "Per rischio idraulico".',
    ),
    (
        "Per rischio idrogeologico",
        '"Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA"',
        "Criticality and alert of the hydrogeological risk.",
        "CriticalityDay.hydrogeological",
        "Criticality, AlertLevel",
        'As "Per rischio idraulico".',
    ),
    (
        "geometry",
        "Polygon or MultiPolygon",
        "Shape of the zone.",
        "Finds the zone of a place.",
        "GeoJSON",
        "Keep.",
    ),
    (
        "Weather vigilance bulletin: zones, one GeoJSON a day (files/geojson/{id}_oggi.json, _domani.json and _dopodomani.json)",
    ),
    (
        "Nome_Zona",
        '"Comune di Roma"',
        "Name of the vigilance zone.",
        "VigilanceDay.zone",
        "Proper name",
        'One spelling for both bulletins ("Nome zona" in the criticality files), and a stable zone code.',
    ),
    (
        "comuni",
        '["Albano Laziale", "Anguillara Sabazia", ...]',
        "Municipalities of the zone, by name only.",
        "Location.municipality",
        "Proper names",
        'ISTAT codes, and one spelling for both bulletins ("Comuni" in the criticality files).',
    ),
    (
        "id_classificazione",
        "2",
        "Class of the expected precipitation.",
        "VigilanceDay.precipitation",
        "Precipitation",
        "Already numeric: keep.",
    ),
    (
        "Quantitativi_previsti",
        '"Deboli"',
        "Italian text of the class.",
        "Read only when the class is missing.",
        "Precipitation",
        "The same as id_classificazione: a label that clients can translate from the code.",
    ),
    (
        "Weather vigilance bulletin: phenomena, one GeoJSON a day (files/geojson/{id}_fenomeni_oggi.json, ...), one Point per phenomenon",
    ),
    (
        "id",
        "null",
        "Always empty in the files measured.",
        "Not read.",
        "",
        "Fill it, or remove it.",
    ),
    (
        "id_bollettino",
        "202611151",
        "Publication date and day of the file (1 to 3).",
        "Phenomenon.bulletin_id",
        "",
        "Keep.",
    ),
    (
        "data_bollettino",
        '"2026-11-15Z"',
        "Publication date.",
        "Phenomenon.bulletin_date",
        "",
        'An ISO 8601 date without a time zone ("2026-11-15"): a "Z" on a date is not standard.',
    ),
    (
        "id_fenomeno",
        "5",
        "Code of the phenomenon, as in the DPC legend.",
        "Phenomenon.code, .type, .category",
        "PhenomenonType, PhenomenonCategory",
        "Already numeric: keep. Its tens give the category.",
    ),
    (
        "lat, lon",
        "41.57313417, 12.67477485",
        "Position of the phenomenon.",
        "Phenomenon.latitude, .longitude, .key",
        "",
        "The same as the Point geometry.",
    ),
    ("Both bulletins: names of the files",),
    (
        "Criticality bulletin ID",
        '"20261115_1421"',
        "Publication date and time (Europe/Rome).",
        "CriticalityBulletin.id, .published",
        "",
        "Keep.",
    ),
    (
        "Vigilance bulletin ID",
        '"20261115"',
        "Publication date.",
        "VigilanceBulletin.id, .date",
        "",
        "Keep.",
    ),
    (
        "Day of the file",
        '"today", "tomorrow" / "oggi", "domani", "dopodomani"',
        "Day after the publication day: English in the criticality files, Italian in the vigilance files and the preview images.",
        "CriticalityDay.offset, VigilanceDay.offset",
        "Day",
        "One spelling for both bulletins, or the number of the day (Day).",
    ),
    ("Computed by aiodpc for a place, not published by DPC",),
    (
        "distance, direction",
        "20.2 km WNW",
        "Distance and compass point from the place to a phenomenon.",
        "Phenomenon.distance_km, .direction, .degrees",
        "CompassPoint",
        "",
    ),
)
"""The fields of the DPC files; a row of one cell starts a group."""

ABOUT: Final = (
    "What this is",
    "Every field of the open data files of the national DPC bulletins (criticality and weather vigilance), and every value they take, with a numeric code and its text in six languages.",
    "Why",
    'DPC writes most values as Italian text, such as "Ordinaria per rischio idrogeologico / ALLERTA GIALLA". A numeric code for each value makes the files simpler to read by programs and to translate into any language. These are the codes aiodpc uses, offered as a proposal of data model.',
    "Sheets",
    "Fields: the fields of the DPC files, what aiodpc reads from them, and the proposal. Values: every value of every domain, its code, the text DPC writes and its translations. Templates: the sentences aiodpc makes from them.",
    "Code status",
    "DPC: DPC already publishes the code. aiodpc: aiodpc uses the code. proposed: this document proposes the code.",
    "Measured",
    "The summaries of the 2572 criticality bulletins published from January 2020 to 15 November 2026, and every zone of 73 of them (12,250 zone-days) chosen for their red and orange alerts and their days with several risks. The criticality texts are a closed set: four criticalities and three risks, each criticality always with the same alert level. DPC never published a red alert for thunderstorms.",
    "Source",
    f"Generated by docs/data_dictionary.py from aiodpc {aiodpc.__version__} (https://github.com/webysther/aiodpc): the codes are the .code of the values of aiodpc.models, the texts those of aiodpc.i18n.",
    "Data",
    f"{aiodpc.ATTRIBUTION}, CC BY 4.0. This document is not affiliated with DPC.",
)
"""The About sheet: a heading, then its text."""

TEMPLATES: Final = {
    "criticality_for_risk": "A criticality and the risk it concerns: {criticality}, {risk}.",
    "alert_for_risks": "An alert and its risks: {level}, {risks}.",
    "phenomenon": "A phenomenon near a place: {phenomenon}, {distance} (km), {direction}.",
    "unknown_phenomenon": "A phenomenon of a code aiodpc does not know: {code}.",
    "conjunction": "The word before the last item of a list.",
    "decimal_separator": "The separator of the decimals.",
}
"""The templates of a translation and what they are for."""


def write_table(
    sheet: Worksheet,
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    widths: Sequence[int],
) -> None:
    """Write a table with a frozen header row and filters."""
    sheet.append(list(headers))
    for cell in sheet[1]:
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    for row in rows:
        sheet.append(list(row))
        group = len(row) == 1
        for cell in sheet[sheet.max_row]:
            cell.font = Font(name=FONT, bold=group)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if group:
                cell.fill = GROUP_FILL
        if group:
            sheet.merge_cells(
                start_row=sheet.max_row,
                start_column=1,
                end_row=sheet.max_row,
                end_column=len(headers),
            )
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.freeze_panes = "B2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{sheet.max_row}"


def main() -> None:
    """Write the workbook."""
    workbook = Workbook()
    about = workbook.active
    assert about is not None  # noqa: S101 - a new workbook has a sheet
    about.title = "About"
    about.append(["DPC bulletins: data dictionary"])
    about["A1"].font = Font(name=FONT, bold=True, size=14)
    for heading, text in zip(ABOUT[::2], ABOUT[1::2], strict=True):
        about.append([])
        about.append([heading])
        about[f"A{about.max_row}"].font = Font(name=FONT, bold=True)
        about.append([text])
        about[f"A{about.max_row}"].font = Font(name=FONT)
        about[f"A{about.max_row}"].alignment = Alignment(wrap_text=True, vertical="top")
    about.column_dimensions["A"].width = 110

    languages = [language.value for language in Language]
    write_table(
        workbook.create_sheet("Fields"),
        [
            "DPC field",
            "Example, as published",
            "Meaning",
            "aiodpc",
            "Domain",
            "Proposal",
        ],
        FIELDS,
        [26, 34, 38, 34, 24, 60],
    )
    write_table(
        workbook.create_sheet("Values"),
        ["Domain", "Code", "Code status", "aiodpc key", "DPC text", *languages, "Note"],
        values(),
        [20, 7, 11, 24, 30, *[30] * len(languages), 40],
    )
    write_table(
        workbook.create_sheet("Templates"),
        ["Template", "Purpose and fields", *languages],
        (
            [
                name,
                purpose,
                *[getattr(TRANSLATIONS[language], name) for language in Language],
            ]
            for name, purpose in TEMPLATES.items()
        ),
        [22, 40, *[28] * len(languages)],
    )
    workbook.save(OUTPUT)


if __name__ == "__main__":
    main()
