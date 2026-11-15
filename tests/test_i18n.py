"""Tests of the translations: every value of the models in every language."""

from __future__ import annotations

import dataclasses
import datetime as dt
import string
from typing import TYPE_CHECKING

import pytest

from aiodpc import (
    AlertLevel,
    BulletinKind,
    CompassPoint,
    Criticality,
    Day,
    Language,
    Phenomenon,
    PhenomenonCategory,
    PhenomenonType,
    Precipitation,
    Risk,
    RiskAssessment,
    RiskType,
    Translation,
    Translator,
)
from aiodpc.i18n import TRANSLATIONS
from aiodpc.models import CRITICALITY_TEXTS, RISK_TYPE_NAMES
from aiodpc.parsers import (
    ALERT_LEVELS,
    PHENOMENON_TYPES,
    PRECIPITATION_TEXTS,
    parse_assessment,
)

from .test_models import criticality_day

if TYPE_CHECKING:
    from enum import Enum

# Every criticality text of the DPC files, measured on every zone of 73
# bulletins from 2020 to 2026 chosen for their red and orange alerts and their
# days with several risks: each risk ("Per rischio idrogeologico")...
DPC_RISK_TEXTS = (
    "Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA",
    "Ordinaria / ALLERTA GIALLA",
    "Moderata / ALLERTA ARANCIONE",
    "Elevata / ALLERTA ROSSA",
)
# ... and the summary of the zone ("Rappresentata nella mappa")
DPC_SUMMARY_TEXTS = (
    "Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA",
    "Ordinaria per rischio idraulico / ALLERTA GIALLA",
    "Ordinaria per rischio temporali / ALLERTA GIALLA",
    "Ordinaria per rischio idrogeologico / ALLERTA GIALLA",
    "Moderata per rischio idraulico / ALLERTA ARANCIONE",
    "Moderata per rischio temporali / ALLERTA ARANCIONE",
    "Moderata per rischio idrogeologico / ALLERTA ARANCIONE",
    "Elevata per rischio idraulico / ALLERTA ROSSA",
    "Elevata per rischio idrogeologico / ALLERTA ROSSA",
)

TABLES: tuple[tuple[str, type[Enum]], ...] = (
    ("alert_levels", AlertLevel),
    ("criticalities", Criticality),
    ("risk_types", RiskType),
    ("precipitation", Precipitation),
    ("phenomenon_categories", PhenomenonCategory),
    ("phenomenon_types", PhenomenonType),
    ("compass_points", CompassPoint),
    ("days", Day),
    ("bulletin_kinds", BulletinKind),
)
TEMPLATES = {
    "criticality_for_risk": {"criticality", "risk"},
    "alert_for_risks": {"level", "risks"},
    "phenomenon": {"phenomenon", "distance", "direction"},
    "unknown_phenomenon": {"code"},
}

TODAY = dt.date(2026, 11, 15)


@dataclasses.dataclass(frozen=True)
class Text:
    """A DPC text, described like the models."""

    description: str


def phenomenon(code: int, distance_km: float, direction: CompassPoint) -> Phenomenon:
    """Return a phenomenon near the place."""
    return Phenomenon(
        code=code,
        category=None,
        description=None,
        latitude=41.8,
        longitude=12.3,
        distance_km=distance_km,
        direction=direction,
        degrees=0,
        bulletin_id=None,
        bulletin_date=None,
    )


def risk_of(levels: dict[RiskType, AlertLevel], description: str = "") -> Risk:
    """Return the risk of a day with these levels."""
    day = criticality_day(TODAY, levels=levels)
    return Risk.of(dataclasses.replace(day, description=description))


def test_every_language_has_a_translation() -> None:
    """Every language has a translation, which is in that language."""
    assert set(TRANSLATIONS) == set(Language)
    for language, translation in TRANSLATIONS.items():
        assert translation.language is language


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize(("table", "enum"), TABLES)
def test_every_value_has_a_text(
    language: Language, table: str, enum: type[Enum]
) -> None:
    """Every member of every enum has a text in every language, and no more."""
    texts = getattr(TRANSLATIONS[language], table)
    assert set(texts) == set(enum)
    for text in texts.values():
        assert isinstance(text, str)
        assert text
        assert text == text.strip()


def test_every_value_of_the_models_is_translated() -> None:
    """The translations cover every field of :class:`Translation`."""
    fields = {field.name for field in dataclasses.fields(Translation)}
    others = {"language", "conjunction", "decimal_separator"}
    assert fields == {table for table, _enum in TABLES} | set(TEMPLATES) | others


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize(("template", "names"), TEMPLATES.items())
def test_templates_have_their_fields(
    language: Language, template: str, names: set[str]
) -> None:
    """Each template uses exactly the fields its docstring lists."""
    text = getattr(TRANSLATIONS[language], template)
    fields = {name for _text, name, _spec, _conv in string.Formatter().parse(text)}
    assert fields - {None} == names


@pytest.mark.parametrize("language", list(Language))
def test_compass_points_are_distinct(language: Language) -> None:
    """Each language tells the 16 compass points apart."""
    points = TRANSLATIONS[language].compass_points
    assert len(set(points.values())) == len(CompassPoint)


def test_italian_says_what_dpc_writes() -> None:
    """The Italian texts are those of the DPC files and legends."""
    italian = TRANSLATIONS[Language.ITALIAN]
    for text, level in ALERT_LEVELS.items():
        assert italian.alert_levels[level].casefold() == text.casefold()
    for text, precipitation in PRECIPITATION_TEXTS.items():
        assert italian.precipitation[precipitation].casefold() == text.casefold()
    for text, criticality in CRITICALITY_TEXTS.items():
        assert italian.criticalities[criticality].casefold() == text
    for name, risk_type in RISK_TYPE_NAMES.items():
        assert italian.risk_types[risk_type] == f"rischio {name}"
    for code, (_category, legend) in PHENOMENON_TYPES.items():
        phenomenon_type = PhenomenonType.of(code)
        assert phenomenon_type is not None
        assert legend in italian.phenomenon_types[phenomenon_type].casefold()


@pytest.mark.parametrize("text", DPC_RISK_TEXTS + DPC_SUMMARY_TEXTS)
def test_italian_description_is_dpc_text(text: str) -> None:
    """Every DPC criticality text is translated back to itself in Italian."""
    assessment = parse_assessment(text)
    assert Translator(Language.ITALIAN).description(assessment) == (
        assessment.description
    )


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("text", DPC_RISK_TEXTS + DPC_SUMMARY_TEXTS)
def test_every_dpc_text_is_translated(language: Language, text: str) -> None:
    """Every DPC criticality text is recognised, so translated in every language."""
    assessment = parse_assessment(text)
    assert Criticality.of(assessment.description) is not Criticality.UNKNOWN
    translated = Translator(language).description(assessment)
    assert translated
    if language is not Language.ITALIAN:
        assert translated != assessment.description


@pytest.mark.parametrize(
    ("text", "criticality"),
    [
        ("Assenza di fenomeni significativi prevedibili", Criticality.ABSENT),
        ("Ordinaria", Criticality.ORDINARY),
        ("Moderata per rischio temporali", Criticality.MODERATE),
        ("  Elevata   per rischio idraulico ", Criticality.HIGH),
        # As in the HTML summaries of the DPC bulletins
        ("ORDINARIA CRITICITA' PER RISCHIO IDRAULICO", Criticality.ORDINARY),
        ("Ordinariamente", Criticality.UNKNOWN),
        ("Sintesi", Criticality.UNKNOWN),
        ("", Criticality.UNKNOWN),
    ],
)
def test_criticality_of_text(text: str, criticality: Criticality) -> None:
    """A criticality is read from the start of a DPC text."""
    assert Criticality.of(text) is criticality


@pytest.mark.parametrize(
    ("text", "risk_type"),
    [
        ("Ordinaria per rischio idraulico", RiskType.HYDRAULIC),
        ("Ordinaria per rischio temporali", RiskType.THUNDERSTORMS),
        ("ELEVATA CRITICITA' PER RISCHIO IDROGEOLOGICO", RiskType.HYDROGEOLOGICAL),
        ("Ordinaria", None),
        ("Ordinaria per rischio", None),
        ("Ordinaria per rischio neve", None),
    ],
)
def test_risk_named_in_text(text: str, risk_type: RiskType | None) -> None:
    """The risk a DPC text names is the word after "per rischio"."""
    assert RiskType.named_in(text) is risk_type


def test_models_have_their_criticality() -> None:
    """The assessments, days and risks expose their criticality and mapped risk."""
    assessment = RiskAssessment(RiskType.HYDRAULIC, AlertLevel.ORANGE, "Moderata")
    assert assessment.criticality is Criticality.MODERATE
    day = dataclasses.replace(
        criticality_day(TODAY, levels={RiskType.THUNDERSTORMS: AlertLevel.YELLOW}),
        description="Ordinaria per rischio temporali",
    )
    assert day.criticality is Criticality.ORDINARY
    assert day.mapped_risk is RiskType.THUNDERSTORMS
    risk = Risk.of(day)
    assert risk.criticality is Criticality.ORDINARY
    assert risk.mapped_risk is RiskType.THUNDERSTORMS
    green = criticality_day(TODAY)
    assert dataclasses.replace(green, description=DPC_RISK_TEXTS[0]).mapped_risk is None


@pytest.mark.parametrize(
    ("tag", "language"),
    [
        ("en", Language.ENGLISH),
        ("en-GB", Language.ENGLISH),
        ("it_IT", Language.ITALIAN),
        ("pt-BR", Language.BRAZILIAN_PORTUGUESE),
        ("pt_br", Language.BRAZILIAN_PORTUGUESE),
        ("pt", Language.BRAZILIAN_PORTUGUESE),
        ("pt-PT", Language.BRAZILIAN_PORTUGUESE),
        ("FR-ch", Language.FRENCH),
        (" de ", Language.GERMAN),
        ("es-419", Language.SPANISH),
        ("ja", None),
        ("", None),
    ],
)
def test_language_of_tag(tag: str, language: Language | None) -> None:
    """A tag is matched whole, then by its primary language."""
    assert Language.of(tag) is language


def test_translator_language() -> None:
    """A translator is made from a language or a tag."""
    assert Translator(Language.GERMAN).language is Language.GERMAN
    assert Translator("pt_BR").language is Language.BRAZILIAN_PORTUGUESE
    assert repr(Translator("it-IT")) == "Translator('it')"
    with pytest.raises(ValueError, match="Unsupported language: 'ja'"):
        Translator("ja")


@pytest.mark.parametrize("language", list(Language))
def test_every_value_is_a_label(language: Language) -> None:
    """Every value of the models is told as a label, starting with a capital."""
    translator = Translator(language)
    for _table, enum in TABLES:
        for value in enum:
            label = translator(value)  # type: ignore[arg-type] # Enum of TABLES
            assert label[:1] == label[:1].upper()


@pytest.mark.parametrize(
    ("language", "value", "label"),
    [
        (Language.ENGLISH, RiskType.THUNDERSTORMS, "Thunderstorm risk"),
        (Language.ITALIAN, RiskType.HYDROGEOLOGICAL, "Rischio idrogeologico"),
        (Language.GERMAN, RiskType.HYDROGEOLOGICAL, "Hydrogeologisches Risiko"),
        (Language.BRAZILIAN_PORTUGUESE, AlertLevel.YELLOW, "Alerta amarelo"),
        (Language.SPANISH, Precipitation.HEAVY, "Fuerte"),
        (Language.FRENCH, Day.AFTER_TOMORROW, "Après-demain"),
        (Language.GERMAN, CompassPoint.ENE, "ONO"),
        (Language.ITALIAN, PhenomenonType.STRONG_WIND, "Venti forti"),
    ],
)
def test_label(
    language: Language, value: AlertLevel | RiskType | Precipitation, label: str
) -> None:
    """A value is told as its label."""
    assert Translator(language)(value) == label


@pytest.mark.parametrize(
    ("language", "levels", "text"),
    [
        (Language.ENGLISH, {}, "No alert"),
        (
            Language.ENGLISH,
            {RiskType.HYDROGEOLOGICAL: AlertLevel.YELLOW},
            "Yellow alert for hydrogeological risk",
        ),
        (
            Language.BRAZILIAN_PORTUGUESE,
            {
                RiskType.THUNDERSTORMS: AlertLevel.ORANGE,
                RiskType.HYDROGEOLOGICAL: AlertLevel.ORANGE,
            },
            "Alerta laranja para risco de tempestades e risco hidrogeológico",
        ),
        (
            Language.GERMAN,
            dict.fromkeys(RiskType, AlertLevel.RED),
            "Rote Warnung für Hochwasserrisiko, Gewitterrisiko und "
            "hydrogeologisches Risiko",
        ),
        (
            Language.ITALIAN,
            {RiskType.HYDRAULIC: AlertLevel.YELLOW},
            "Allerta gialla per rischio idraulico",
        ),
    ],
)
def test_risk(
    language: Language, levels: dict[RiskType, AlertLevel], text: str
) -> None:
    """A risk is told as its alert and its risk types."""
    assert Translator(language).risk(risk_of(levels)) == text


@pytest.mark.parametrize(
    ("language", "description", "text"),
    [
        (
            Language.ENGLISH,
            "Ordinaria per rischio idrogeologico",
            "Ordinary criticality for hydrogeological risk",
        ),
        (
            Language.BRAZILIAN_PORTUGUESE,
            "Elevata per rischio idraulico",
            "Criticidade elevada para risco hidráulico",
        ),
        (
            Language.SPANISH,
            "Assenza di fenomeni significativi prevedibili",
            "Ausencia de fenómenos significativos previsibles",
        ),
        (Language.FRENCH, "Moderata", "Criticité modérée"),
        # What aiodpc does not recognise stays as DPC wrote it
        (Language.ENGLISH, "Sintesi", "Sintesi"),
        (Language.ENGLISH, "Ordinaria per rischio neve", "Ordinaria per rischio neve"),
    ],
)
def test_description(language: Language, description: str, text: str) -> None:
    """The DPC criticality text of a risk, day or assessment is translated."""
    translator = Translator(language)
    assert translator.description(Text(description)) == text
    risk = risk_of({}, description)
    assert translator.description(risk) == text
    assert translator.description(risk.day) == text


@pytest.mark.parametrize(
    ("language", "item", "text"),
    [
        (
            Language.ENGLISH,
            phenomenon(1, 20.2, CompassPoint.WNW),
            "Scattered or intermittent rain, 20.2 km WNW",
        ),
        (
            Language.BRAZILIAN_PORTUGUESE,
            phenomenon(1, 20.2, CompassPoint.WNW),
            "Chuvas esparsas ou intermitentes, 20,2 km ONO",
        ),
        (
            Language.GERMAN,
            phenomenon(11, 7.0, CompassPoint.E),
            "Stürmischer Wind, 7,0 km O",
        ),
        (
            Language.ITALIAN,
            phenomenon(99, 3.5, CompassPoint.N),
            "Fenomeno 99, 3,5 km N",
        ),
    ],
)
def test_phenomenon(language: Language, item: Phenomenon, text: str) -> None:
    """A phenomenon is told with its distance and direction."""
    assert Translator(language).phenomenon(item) == text
