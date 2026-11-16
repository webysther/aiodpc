# Revisions of the paper

Each revision is a state of the content of the paper: `manuscript.tex`,
`title-page.tex`, `highlights.txt`, `references.bib`, and the figures and
numbers of [`docs/study`](../study) that it uses. A change to any of them after
the latest revision was committed starts a new revision, at the top of this
file, with what changed.
`./publish.sh paper` names the PDFs after the latest revision
(`paper-r2.pdf`).

## r2 - 2026-11-16

- The coded model publishes one JSON document per bulletin instead of three
  CSV tables; the documents of a period form a JSON Lines file. One day is
  15.3 kB (1,259 times less) instead of 13.4 kB, 4.0 kB compressed; the
  abstract, the design, the evaluation table, the figure of the sizes, the
  conclusion and a highlight change with it.
- A quarter of bulletins (2026 Q3, 189 bulletins) as JSON Lines: 1.1 MB
  against 1.83 GB, in the demonstration, the evaluation table and the data
  availability statement.
- JSON (RFC 8259) and JSON Schema (Pezoa et al., 2016) are cited in place of
  CSV on the Web.
- The implementation renders the codes in 13 languages, not six.

## r1 - 2026-11-16

- First version, for Government Information Quarterly: the census of the
  zones of 2,571 bulletins, the coded data model and its evaluation.
