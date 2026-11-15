"""The alerts, risks and weather of the DPC bulletins in other languages.

DPC writes its bulletins in Italian. Every value of the models of aiodpc has
a text in each :class:`Language`, so an alert can be told in any of them::

    pt = Translator("pt-BR")
    pt(AlertLevel.YELLOW)  # "Alerta amarelo"
    pt.risk(risk)  # "Alerta amarelo para risco hidrogeológico"
    pt.description(risk)  # "Criticidade ordinária para risco hidrogeológico"
    pt.phenomenon(phenomenon)  # "Chuvas esparsas ou intermitentes, 20,2 km ONO"

The names of the zones and municipalities are proper names and stay as DPC
writes them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Protocol

from aiodpc.models import (
    RISK_NAME_PREFIX,
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

from . import de, en, es, fr, it, pt_br
from .translation import Language, Translation

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from aiodpc.models import Phenomenon, Risk

__all__ = [
    "TRANSLATIONS",
    "Described",
    "Language",
    "Translatable",
    "Translation",
    "Translator",
]

TRANSLATIONS: Final[Mapping[Language, Translation]] = {
    translation.language: translation
    for translation in (
        en.TRANSLATION,
        it.TRANSLATION,
        pt_br.TRANSLATION,
        fr.TRANSLATION,
        de.TRANSLATION,
        es.TRANSLATION,
    )
}
"""The translation of each language."""

type Translatable = (
    AlertLevel
    | BulletinKind
    | CompassPoint
    | Criticality
    | Day
    | PhenomenonCategory
    | PhenomenonType
    | Precipitation
    | RiskType
)
"""A value of the models that has a text in every language."""


class Described(Protocol):
    """A model with a DPC criticality text: a risk, a day or an assessment."""

    @property
    def description(self) -> str:
        """Return the text as DPC writes it, in Italian."""
        ...


class Translator:
    """Tells the values and models of aiodpc in one language.

    ``language`` is a :class:`Language` or a tag such as ``"pt-BR"`` or
    ``"it-IT"`` (see :meth:`Language.of`). Raises ``ValueError`` for a
    language aiodpc does not speak.
    """

    __slots__ = ("_tables", "translation")

    def __init__(self, language: Language | str) -> None:
        """Initialize the translator of a language."""
        found = Language.of(language)
        if found is None:
            supported = ", ".join(Language)
            msg = f"Unsupported language: {language!r}; supported: {supported}"
            raise ValueError(msg)
        self.translation: Translation = TRANSLATIONS[found]
        """The texts of the language."""
        translation = self.translation
        self._tables: Mapping[type, Mapping[Any, str]] = {
            AlertLevel: translation.alert_levels,
            BulletinKind: translation.bulletin_kinds,
            CompassPoint: translation.compass_points,
            Criticality: translation.criticalities,
            Day: translation.days,
            PhenomenonCategory: translation.phenomenon_categories,
            PhenomenonType: translation.phenomenon_types,
            Precipitation: translation.precipitation,
            RiskType: translation.risk_types,
        }

    @property
    def language(self) -> Language:
        """Return the language of the translator."""
        return self.translation.language

    def __call__(self, value: Translatable) -> str:
        """Return the text of a value, as a label: "Hydrogeological risk"."""
        return _capitalized(self._tables[type(value)][value])

    def risk(self, risk: Risk) -> str:
        """Return the alert of a risk and its risk types.

        E.g. "Yellow alert for thunderstorm risk and hydrogeological risk", or
        "No alert".
        """
        translation = self.translation
        level = translation.alert_levels[risk.level]
        if not risk.types:
            return level
        risks = self._listed(translation.risk_types[item] for item in risk.types)
        return translation.alert_for_risks.format(level=level, risks=risks)

    def description(self, described: Described) -> str:
        """Return the DPC criticality text of a risk, day or assessment.

        E.g. "Ordinaria per rischio idrogeologico" is "Ordinary criticality for
        hydrogeological risk". A text aiodpc does not recognise is returned as
        DPC wrote it, in Italian, rather than lost.
        """
        text = described.description
        criticality = Criticality.of(text)
        risk_type = RiskType.named_in(text)
        names_a_risk = RISK_NAME_PREFIX in " ".join(text.split()).casefold()
        if criticality is Criticality.UNKNOWN or (names_a_risk and risk_type is None):
            return text
        translation = self.translation
        name = translation.criticalities[criticality]
        if risk_type is None:
            return name
        return translation.criticality_for_risk.format(
            criticality=name, risk=translation.risk_types[risk_type]
        )

    def phenomenon(self, phenomenon: Phenomenon) -> str:
        """Return a phenomenon with its distance and direction.

        E.g. "Scattered or intermittent rain, 20.2 km WNW".
        """
        translation = self.translation
        phenomenon_type = phenomenon.type
        what = (
            translation.unknown_phenomenon.format(code=phenomenon.code)
            if phenomenon_type is None
            else translation.phenomenon_types[phenomenon_type]
        )
        distance = f"{phenomenon.distance_km:.1f}".replace(
            ".", translation.decimal_separator
        )
        return translation.phenomenon.format(
            phenomenon=what,
            distance=distance,
            direction=translation.compass_points[phenomenon.direction],
        )

    def _listed(self, items: Iterable[str]) -> str:
        """Return items as a list: "a, b and c"."""
        *first, last = items
        if not first:
            return last
        return f"{', '.join(first)} {self.translation.conjunction} {last}"

    def __repr__(self) -> str:
        """Return the representation of the translator."""
        return f"Translator({self.language.value!r})"


def _capitalized(text: str) -> str:
    """Return a text starting with a capital letter."""
    return text[:1].upper() + text[1:]
