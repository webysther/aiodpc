# AGENTS.md: aiodpc

Guidance for AI coding agents and contributors working on this repository.
`CLAUDE.md` imports this file.

aiodpc is an async Python client (asyncio, aiohttp) for the open data of the
Italian Civil Protection Department (DPC): the criticality bulletin (alert
levels for hydraulic, hydrogeological and thunderstorm risk) and the weather
vigilance bulletin (precipitation and phenomena). It is fully typed, has no
Home Assistant dependency and is published to PyPI.

Its main user is the Home Assistant integration
[DPC Alert](https://github.com/caiosweet/Home-Assistant-custom-components-DPC-Alert),
which pins an exact version. DPC parsing and HTTP fixes belong here;
Home Assistant code belongs in the integration.

## Ground rules

- **Do not commit, amend, push, tag, publish or move branches** (`reset`,
  `branch -f`, `rebase`). Leave every change uncommitted in the working tree;
  the maintainer reviews and commits it. Read-only git commands are fine.
- Ask before anything that leaves the machine: releases, PRs, issues,
  comments.
- Reply in the language the person writes in. Code, comments, docstrings,
  docs, the changelog and commit messages are in English.
- Check instead of guessing: answer data questions by measuring the live DPC
  data with a throwaway script outside the repository, and write the
  measurement in the docstring of the constant it sets.

## Layout: a layered API

From the simplest to the rawest. Keep the lower levels and add higher-level
methods that answer the caller's real question ("is there a risk here?",
"which one?"), rather than making callers combine low-level calls.

```text
src/aiodpc/
  monitor.py         MonitoredLocation, from DpcClient.location(): has_risk(), risk()
  client.py          DpcClient: bulletins of a location, maps, get_alert_zone(),
                     is_location_covered(), raw files
  maps.py            CriticalityMap, VigilanceMap: one download, .at(location)
                     for any number of places, without I/O; .compact()
  compact.py         a whole bulletin as numeric codes and a zone table
  parsers.py         pure parsing of the decoded GeoJSON, without I/O
  models.py          frozen dataclasses and enums; exceptions.py
  discovery.py       the latest bulletin ID, from the DPC map pages
  urls.py, geo.py, const.py
  municipalities.py  other names of municipalities (South Tyrol)
  schema.py          optional strict DTOs of the raw files (extra "schema", msgspec)
  i18n/              a text for every value of the models in each Language:
                     translation.py (Language, Translation), one module per
                     language, Translator in __init__.py
tests/               pytest; tests/server.py is a local HTTPS server standing in for DPC
examples/            tutorial.ipynb, the README tutorial with maps, saved with its
                     outputs; it writes alert-map.png, the map of the README
docs/                data_dictionary.py writes data-dictionary.xlsx, the DPC data
                     model with numeric codes, from the tables of aiodpc
docs/study/          the study of the DPC data (en.md, it.md) and measure.py,
                     which makes every number it cites (results.json, figures)
docs/paper/          the study as a research article (LaTeX, elsarticle) for
                     Government Information Quarterly: manuscript.tex
                     (anonymized), title-page.tex, highlights.txt, references.bib,
                     CHANGELOG.md (its revisions); built by .github/workflows/paper.yml
CITATION.cff         how to cite aiodpc and the study (author: Webysther Sperandio)
```

The public API is what `aiodpc/__init__.py` exports in `__all__`, plus the
documented modules: `parsers`, `urls`, `geo`, `municipalities`, `discovery`,
`schema`, `i18n`, `compact`.

## Checks

```bash
python -m venv .venv && . .venv/bin/activate
pip install --editable . --group dev   # pip >= 25.1
ruff format --check . && ruff check .  # every rule ("ALL"), see pyproject.toml
mypy                                   # strict, src and tests
pytest --cov
```

CI runs the same on Python 3.13 and 3.14. Warnings are errors in pytest.
The coverage gate is 95% with branches; keep it at 100%.

## Tests

- Never reach DPC: `tests/server.py` answers for the DPC hosts over HTTPS
  (certificates from trustme), serving `tests/fixtures`.
- `tests/fixtures/real` holds unmodified excerpts of real bulletins that guard
  the data format: never edit them. The other fixtures are small and
  hand-made: their zones are coarse rectangles, so pick test locations that
  are realistic against those rectangles.
- Never depend on the current date: pass `now=` or use fixed dates.
  `.today` in a test breaks the day after the fixture's date.

## Documentation

- The README is also the PyPI page: link the repository files with absolute
  GitHub URLs.
- Every Python example of the README is a complete script (imports,
  `async def main()`, `asyncio.run(main())`) that works when copied and
  pasted. Run each one against the live DPC data before changing it, and
  show its real output. Secondary examples go in `<details>`.
- The study (`docs/study/en.md`, `it.md`) says the same in both languages.
  Every number it cites comes from `results.json`, written by `measure.py`;
  every claim of method cites its source in the References.
- The paper (`docs/paper/`) follows the study: a number changed in the study
  changes in `manuscript.tex` too. The manuscript stays anonymized (no author
  name, no link to this repository) while `\anonymoustrue`; every DOI of
  `references.bib` is checked against Crossref.
- The paper has revisions, listed in `docs/paper/CHANGELOG.md` (`## rN -
  DATE`, newest first). A change to its content (`manuscript.tex`,
  `title-page.tex`, `highlights.txt`, `references.bib`, or the figures and
  numbers of `docs/study` it uses) after the latest revision was committed
  opens a new revision, with what changed; further changes before the next
  commit stay in that revision. The build, the README and the changelog of the
  paper are not its content.
  `.github/workflows/paper.yml` builds the PDFs, and `./publish.sh paper`
  downloads them to `paper-rN.pdf` (ignored by git).
- The tutorial grows from one question about one place to the whole country;
  `examples/tutorial.ipynb` tells the same story with maps. Keep them in step.

## Translations

- Every value of the models is an enum, and every enum has a text in every
  `Language`: `tests/test_i18n.py` fails on a missing one. A new enum or member
  needs its text in every language, and its table in `Translation`.
- The Italian texts are those DPC writes (its legends, `"Ordinaria"`,
  `"Deboli"`). DPC Alert takes its texts from here, so that the library and
  the integration say the same.
- A template whose language declines nouns after a preposition joins the
  level and the risk with a dash ("Жовте попередження — гідрогеологічний
  ризик"), since the risk types are in the nominative.
- Risk types are written as within a sentence ("hydrogeological risk");
  every other text as a label. The templates hold the grammar of a language.
- A DPC text aiodpc does not recognise is returned as it is, never dropped.
- To add a language: a member of `Language`, a module in `i18n/`, its entry in
  `TRANSLATIONS`; the tests list what is missing.
- After changing a table, write the data dictionary again
  (`python docs/data_dictionary.py`).
- Every value has a numeric `code` and `from_code()`. A released code never
  changes and is never reused: a new value gets a new code. The codes DPC
  publishes (`id_fenomeno`, `id_classificazione`) are kept as they are.
- The columns of the compact records are a format: a change of column needs
  a new `compact.SCHEMA_VERSION`.

## DPC data

Facts that are easy to get wrong:

- The criticality and vigilance files spell properties differently:
  `"Nome zona"`/`"Comuni"` and `"Nome_Zona"`/`"comuni"`.
- Days are Italian days (Europe/Rome). The assessment of a day is valid until
  the midnight that ends it.
- Zones list municipalities by name only, without province or region.
  - South Tyrol is written `"Bolzano/Bozen"` in the criticality bulletin,
    `"Bolzano"` in the vigilance bulletin, and a few names differently
    (`"Rasun Anterselva"`, old names like `"Salorno"`).
    `municipalities.municipality_names()` groups the names of each
    municipality. It leaves out German names that are also another
    municipality: "Corvara" is also a municipality of Abruzzo.
  - A few names belong to two municipalities far apart: Peglio, Livo,
    Samone, Castro, San Teodoro, Calliano, Valverde. A municipality only
    matches the zones within `MUNICIPALITY_RADIUS_KM` (60 km) of the
    location. Measured: every point of Rome is within 47 km of its zones,
    while the nearest homonyms are about 90 km from each other's zones.
  - Large municipalities span several zones (Rome: five). The highest
    level wins, and the zone is named after the one containing the
    coordinates.
- A bulletin is about 18 MB: check its features once (`GeoJsonFeatures`) and
  read it at every place.

## Versioning and releases

- Semantic Versioning: before 1.0 a minor version may change the API; a patch
  fixes behaviour, and may add a helper the fix needs.
- To prepare a release, add a `## [X.Y.Z] - Unreleased` section to
  `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
  Added, Changed, Fixed, Removed), written for the users of the library, with
  its compare link at the end of the file.
- In the same change that opens that section, set `__version__` in
  `src/aiodpc/__init__.py` to `X.Y.Z`. It is the version of the package
  (`pyproject.toml` reads it), and `publish.sh` stops with
  `src/aiodpc/__init__.py has version A, not X.Y.Z` when it does not match.
- The maintainer commits and runs `./publish.sh X.Y.Z [--dry-run]`. It dates
  the section, creates the GitHub release with its notes, and the release
  workflow tests, builds and publishes to PyPI.
- DPC Alert then pins the new version, once it is on PyPI.

## Code style

- Readable, descriptive code over clever code: descriptive names, typed models
  and enums instead of raw dicts, small focused helpers, docstrings that say
  what and why.
- No magic numbers: a `Final` constant whose docstring says where its value
  comes from (see `MUNICIPALITY_RADIUS_KM`).
- Parsing stays pure and I/O stays in the client: no network in `parsers`,
  `maps`, `geo` or `municipalities`.
- mypy strict, ruff with every rule. A `# noqa` or `# type: ignore[code]`
  needs a reason.
- Comments explain why, not what.
