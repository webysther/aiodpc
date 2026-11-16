# The study as a research article

The study of [`docs/study`](../study/en.md), written as a research article for
**Government Information Quarterly** (Elsevier). The manuscript is anonymized
for double anonymized review.

| File | What it is |
|---|---|
| `manuscript.tex` | The article, without anything that identifies the author |
| `title-page.tex` | Author, affiliation, CRediT roles, declarations |
| `highlights.txt` | Five highlights, at most 85 characters each |
| `references.bib` | The references; every DOI checked against Crossref |
| `CHANGELOG.md` | The revisions of the paper |

The figures are the PDFs that [`measure.py`](../study/measure.py) draws in
`docs/study/figures`; every number comes from
[`results.json`](../study/results.json).

## Build

GitHub Actions builds both PDFs ([`paper.yml`](../../.github/workflows/paper.yml))
whenever the paper changes on `main`. To download them, after pushing:

```bash
./publish.sh paper      # paper-rN.pdf and paper-rN-title-page.pdf, ignored by git
```

`rN` is the latest revision in [`CHANGELOG.md`](CHANGELOG.md). Locally, with
TeX Live (`elsarticle` is part of it):

```bash
cd docs/paper
latexmk -pdf manuscript.tex
latexmk -pdf title-page.tex
```

On Overleaf, upload the `.tex` and `.bib` files and the three `en-*.pdf` figures,
and change `\graphicspath` in `manuscript.tex` to the folder of the figures.

For the preprint or the accepted version, set `\anonymousfalse`: the
manuscript then names `aiodpc` and links this repository.

## Why this journal

| Journal | Fit | Notes |
|---|---|---|
| **Government Information Quarterly** (Elsevier) | Open government data and its quality; three of the works the study builds on were published there (Vetrò et al., 2016; Kubler et al., 2018; Attard et al., 2015) | Double anonymized review; LaTeX with `elsarticle`; free to publish, open access optional |
| ACM Journal of Data and Information Quality | Data quality methods; Neumaier et al. (2016) | `acmart` (`acmsmall`); a narrower audience for the policy side |
| International Journal of Disaster Risk Reduction (Elsevier) | Early warning | Would need more on the warning chain and its users than the study measures |
| Natural Hazards and Earth System Sciences (Copernicus) | Hazards | Open access with a charge per page; the study is about data, not hazards |

The CAPES Qualis Periódicos ranking is not used in the 2025–2028 evaluation
cycle, which rates each article instead of the journal it appears in.
"Rated A" therefore means a journal in the first quartile of Scopus or
JCR in its field. Government Information Quarterly is in that group.

Moving to JDIQ means changing the class (`acmart`, `acmsmall`) and adding the
CCS concepts; the text needs no change.
