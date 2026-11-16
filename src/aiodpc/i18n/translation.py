"""What a translation of aiodpc is made of, and the languages it speaks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from aiodpc.models import (
    AlertLevel,
    BulletinKind,
    CompassPoint,
    Criticality,
    Day,
    PhenomenonCategory,
    PhenomenonType,
    Precipitation,
    RiskType,
)


class Language(StrEnum):
    """A language aiodpc speaks, as its BCP 47 tag."""

    ENGLISH = "en"
    ITALIAN = "it"
    BRAZILIAN_PORTUGUESE = "pt-BR"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    SIMPLIFIED_CHINESE = "zh-Hans"
    ROMANIAN = "ro"
    ARABIC = "ar"
    UKRAINIAN = "uk"
    ALBANIAN = "sq"
    BENGALI = "bn"
    HINDI = "hi"

    @classmethod
    def of(cls, tag: str) -> Language | None:
        """Return the language of a tag such as "pt-BR", "pt_BR", "it-IT" or "de".

        The tag is matched whole, ignoring case and with ``_`` for ``-``, then
        by its primary language: "it-CH" is Italian and "pt-PT" Brazilian
        Portuguese. None when aiodpc does not speak the language.
        """
        normalized = tag.strip().replace("_", "-").casefold()
        primary = normalized.partition("-")[0]
        whole = next(
            (language for language in cls if language.casefold() == normalized), None
        )
        return whole or next(
            (
                language
                for language in cls
                if language.casefold().partition("-")[0] == primary
            ),
            None,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Translation:
    """Every text of aiodpc in one language.

    Each table has a text for every member of its enum. The labels start with
    a capital letter, except the risk types, which are written as within a
    sentence. The templates are :meth:`str.format` strings with the named
    fields their docstrings list.
    """

    language: Language
    alert_levels: Mapping[AlertLevel, str]
    """The alert of each level, e.g. "Yellow alert"."""
    criticalities: Mapping[Criticality, str]
    """Each criticality, e.g. "Ordinary criticality"; in Italian as DPC
    writes it ("Ordinaria")."""
    risk_types: Mapping[RiskType, str]
    """Each risk as within a sentence, e.g. "hydrogeological risk"."""
    precipitation: Mapping[Precipitation, str]
    """The expected precipitation, e.g. "Light"."""
    phenomenon_categories: Mapping[PhenomenonCategory, str]
    """Each category of weather phenomena, e.g. "Wind"."""
    phenomenon_types: Mapping[PhenomenonType, str]
    """Each weather phenomenon, e.g. "Scattered or intermittent rain"."""
    compass_points: Mapping[CompassPoint, str]
    """The abbreviation of each compass point, e.g. "WNW"."""
    days: Mapping[Day, str]
    """Each day relative to today, e.g. "Tomorrow"."""
    bulletin_kinds: Mapping[BulletinKind, str]
    """The name of each bulletin, e.g. "Weather vigilance bulletin"."""
    criticality_for_risk: str
    """The criticality of a risk: ``{criticality}`` and ``{risk}``."""
    alert_for_risks: str
    """An alert and its risks: ``{level}`` and ``{risks}``."""
    phenomenon: str
    """A phenomenon near a place: ``{phenomenon}``, ``{distance}`` (km) and
    ``{direction}``."""
    unknown_phenomenon: str
    """A phenomenon whose code aiodpc does not know: ``{code}``."""
    conjunction: str
    """The word joining the last two items of a list, e.g. "and"."""
    decimal_separator: str
    """The separator of the decimals of a number, e.g. "." or ","."""
