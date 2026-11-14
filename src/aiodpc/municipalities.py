"""Other names of the municipalities, as DPC writes them.

The criticality bulletin writes the municipalities of South Tyrol with their
Italian and German name ("Bolzano/Bozen"), the vigilance bulletin with their
Italian name only ("Bolzano"), and a few of them differently: "Rasun
Anterselva", or the name before their renaming ("Salorno"). Each group holds
the names DPC uses for one municipality, so that it is found by any of them
in both bulletins.

The groups come from the bulletins of 2026-11-14. A German name that is also
the name of another municipality is left out: "Corvara" (Corvara in Badia) is
also a municipality of Abruzzo.
"""

from __future__ import annotations

import functools
from typing import Final

MUNICIPALITY_NAMES: Final[tuple[tuple[str, ...], ...]] = (
    ("Aldino", "Aldein"),
    ("Andriano", "Andrian"),
    ("Anterivo", "Altrei"),
    ("Appiano sulla strada del vino", "Eppan an der Weinstrasse"),
    ("Avelengo", "Hafling"),
    ("Badia", "Abtei"),
    ("Barbiano", "Barbian"),
    ("Bolzano", "Bozen"),
    ("Braies", "Prags"),
    ("Brennero", "Brenner"),
    ("Bressanone", "Brixen"),
    ("Bronzolo", "Branzoll"),
    ("Brunico", "Bruneck"),
    ("Caines", "Kuens"),
    ("Caldaro sulla strada del vino", "Kaltern an der Weinstrasse"),
    ("Campo Tures", "Sand in Taufers"),
    ("Campo di Trens", "Freienfeld"),
    ("Castelbello-Ciardes", "Kastelbell-Tschars"),
    ("Castelrotto", "Kastelruth"),
    ("Cermes", "Tscherms"),
    ("Chienes", "Kiens"),
    ("Chiusa", "Klausen"),
    ("Cornedo all'Isarco", "Karneid"),
    ("Cortaccia sulla strada del vino", "Kurtatsch an der Weinstrasse"),
    ("Cortina sulla strada del vino", "Kurtinig an der Weinstrasse"),
    ("Curon Venosta", "Graun im Vinschgau"),
    ("Dobbiaco", "Toblach"),
    ("Egna", "Neumarkt"),
    ("Falzes", "Pfalzen"),
    ("Fiè allo Sciliar", "Völs am Schlern", "Fi allo Sciliar"),
    ("Fortezza", "Franzensfeste"),
    ("Funes", "Villnöss"),
    ("Gargazzone", "Gargazon"),
    ("Glorenza", "Glurns"),
    ("La Valle", "Wengen"),
    ("Laces", "Latsch"),
    ("Lagundo", "Algund"),
    ("Laion", "Lajen"),
    ("Laives", "Leifers"),
    ("Lasa", "Laas"),
    ("Lauregno", "Laurein"),
    ("Luson", "Lüsen"),
    (
        "Magrè sulla strada del vino",
        "Margreid an der Weinstrasse",
        "Magr sulla strada del vino",
    ),
    ("Malles Venosta", "Mals"),
    ("Marebbe", "Enneberg"),
    ("Marlengo", "Marling"),
    ("Martello", "Martell"),
    ("Meltina", "Mölten"),
    ("Merano", "Meran"),
    ("Monguelfo-Tesido", "Welsberg-Taisten"),
    ("Montagna sulla strada del vino", "Montan an der Weinstrasse", "Montagna"),
    ("Moso in Passiria", "Moos in Passeier"),
    ("Nalles", "Nals"),
    ("Naturno", "Naturns"),
    ("Naz-Sciaves", "Natz-Schabs"),
    ("Nova Levante", "Welschnofen"),
    ("Nova Ponente", "Deutschnofen"),
    ("Ora", "Auer"),
    ("Ortisei", "St. Ulrich"),
    ("Parcines", "Partschins"),
    ("Perca", "Percha"),
    ("Ponte Gardena", "Waidbruck"),
    ("Postal", "Burgstall"),
    ("Prato allo Stelvio", "Prad am Stilfserjoch"),
    ("Predoi", "Prettau"),
    ("Proves", "Proveis"),
    ("Racines", "Ratschings"),
    ("Rasun-Anterselva", "Rasen-Antholz", "Rasun Anterselva"),
    ("Renon", "Ritten"),
    ("Rifiano", "Riffian"),
    ("Rio di Pusteria", "Mühlbach"),
    ("Rodengo", "Rodeneck"),
    ("Salorno sulla strada del vino", "Salurn an der Weinstrasse", "Salorno"),
    ("San Candido", "Innichen"),
    ("San Genesio Atesino", "Jenesien"),
    ("San Leonardo in Passiria", "St. Leonhard in Passeier"),
    ("San Lorenzo di Sebato", "St. Lorenzen"),
    ("San Martino in Badia", "St. Martin in Thurn"),
    ("San Martino in Passiria", "St. Martin in Passeier"),
    ("San Pancrazio", "St. Pankraz"),
    ("Santa Cristina Valgardena", "St. Christina in Gröden"),
    ("Sarentino", "Sarntal"),
    ("Scena", "Schenna"),
    ("Selva dei Molini", "Mühlwald"),
    ("Selva di Val Gardena", "Wolkenstein in Gröden"),
    ("Senale-San Felice", "Unsere Liebe Frau im Walde-St. Felix"),
    ("Senales", "Schnals"),
    ("Sesto", "Sexten"),
    ("Silandro", "Schlanders"),
    ("Sluderno", "Schluderns"),
    ("Stelvio", "Stilfs"),
    ("Terento", "Terenten"),
    ("Terlano", "Terlan"),
    ("Termeno sulla strada del vino", "Tramin an der Weinstrasse"),
    ("Tesimo", "Tisens"),
    ("Tires", "Tiers"),
    ("Tirolo", "Tirol"),
    ("Trodena nel parco naturale", "Truden im Naturpark"),
    ("Tubre", "Taufers im Münstertal"),
    ("Ultimo", "Ulten"),
    ("Vadena", "Pfatten"),
    ("Val di Vizze", "Pfitsch"),
    ("Valdaora", "Olang"),
    ("Valle Aurina", "Ahrntal"),
    ("Valle di Casies", "Gsies"),
    ("Vandoies", "Vintl"),
    ("Varna", "Vahrn"),
    ("Velturno", "Feldthurns"),
    ("Verano", "Vöran"),
    ("Villabassa", "Niederdorf"),
    ("Villandro", "Villanders"),
    ("Vipiteno", "Sterzing"),
)
"""The names of each municipality that DPC writes in more than one way."""


def normalize(name: str) -> str:
    """Return a name for comparisons: case and spacing do not matter."""
    return " ".join(name.split()).casefold()


_OTHER_NAMES: Final[dict[str, frozenset[str]]] = {
    normalize(name): frozenset(normalize(other) for other in group)
    for group in MUNICIPALITY_NAMES
    for name in group
}


@functools.cache
def municipality_names(name: str) -> frozenset[str]:
    """Return every name of a municipality, normalized.

    ``name`` may hold several names separated by "/", as in "Bolzano/Bozen".
    """
    names = (normalize(part) for part in name.split("/") if part.strip())
    return frozenset().union(*(_OTHER_NAMES.get(part, {part}) for part in names))
