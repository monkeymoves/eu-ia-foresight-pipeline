# SPEC: Foresight in EU Impact Assessments pipeline

Handover spec for implementation. Decisions behind this spec: [CONTEXT.md](CONTEXT.md)
and [docs/adr/0001](docs/adr/0001-human-owned-classification.md). Do not
re-litigate decisions here; build to this contract.

## Purpose

Harvest all EU Commission impact assessments (register search, type
IMPACT_ASSESS, dateFrom 2022-01-31), locate every occurrence of "foresight"
with page-level provenance, and produce: an xlsx dataset, a self-contained
review.html, per-IA markdown text, and docx conversions. Classification of
mentions is done by humans, optionally seeded with AI drafts (out of scope
for this pipeline; see prompts/).

## Repository layout

```
pipeline/
  config.py         shared constants (paths, terms, delays)  [core]
  harvest.py        register API -> manifest.json + PDFs      [core]
  extract.py        PDFs -> per-part markdown with page markers [core]
  detect.py         markdown -> mentions.json                 [core]
  outputs_xlsx.py   manifest+mentions -> dataset.xlsx         [outputs]
  review_html.py    manifest+mentions -> review.html          [outputs]
  convert_docx.py   markdown -> docx via pandoc               [outputs]
  run_all.py        orchestrates the above in order           [outputs]
prompts/
  classification-prompt.md   documented AI-draft prompt       [outputs]
data/               gitignored; all artefacts live here
  manifest.json
  pdfs/<ref-safe>/part<N>.pdf
  md/<ref-safe>/part<N>.md
  docx/<ref-safe>/part<N>.docx
  mentions.json
  out/dataset.xlsx
  out/review.html
  out/README.md     instructions for the research team
```

`<ref-safe>` = reference with `(` `)` `/` replaced: `SWD(2026)616` ->
`SWD_2026_616`. Store the mapping in the manifest; never parse it back.

Python 3.11+, dependencies pinned in requirements.txt (expected: requests,
pymupdf, openpyxl). Scripts are idempotent: safe to re-run, skip work
already done, only append new register entries.

## EU register API (verified 2026-07-31)

Search (paged, 20 per page, pages are 1-based; iterate until totalResults
exhausted). `categories` and `departments` must be present as empty arrays
or the endpoint returns 503:

```
POST https://ec.europa.eu/transparency/documents-register/api/groupSearch?size=20&page=N
Content-Type: application/json
{"types":["IMPACT_ASSESS"],"categories":[],"departments":[],"language":"en",
 "keywordsSearchType":"AT_LEAST_ONE","target":"TITLE_AND_CONTENT",
 "sortBy":"DOCUMENT_DATE_DESC","isRegular":true,"keywords":"",
 "reference":"","page":N,"dateFrom":"2022-01-31T00:00:00.000Z"}
```

Response: `totalResults`, `documents[]` each with `reference` (e.g.
`SWD(2026)616`), `date`, `responsibleDepartment` (e.g. `CLIMA`), `url`
(detail page), `attachments[]`. `documents[].title` is always null; the
title lives in `attachments[].linguisticVersions.en.title`, so take the IA
title from the main/part-1 English version. Each attachment has `part`
(1..N) and `linguisticVersions` keyed by language; use `en` and take its
`ersId`, `id`, and `title`. If an attachment has no `en` version, record the IA in
manifest `flags` as `no_english_version` with available languages, and skip
that part's download (do not fail the run). Some attachments repeat the
same `number` across parts; the (reference, part) pair is the identity.

Download (verified: returns the PDF with Content-Disposition):

```
GET https://ec.europa.eu/transparency/documents-register/api/files/{reference}?ersIds={ersId}
```

Politeness: sequential, minimum 1.5 s between requests, exponential backoff
retries (3 attempts) on 429/5xx/timeouts, User-Agent
`eu-ia-foresight-pipeline (academic research; +<repo URL>)`. Never
parallelise requests to the register.

## Data contracts

### data/manifest.json

```json
{
  "search": {"date_from": "2022-01-31", "last_run": "<iso8601>"},
  "ias": {
    "SWD(2026)616": {
      "ref_safe": "SWD_2026_616",
      "title": "COMMISSION STAFF WORKING DOCUMENT ...",
      "date": "2026-07-17",
      "responsible_department": "CLIMA",
      "detail_url": "https://ec.europa.eu/transparency/documents-register/detail?ref=SWD(2026)616",
      "first_seen": "<iso8601>",
      "flags": [],
      "parts": [
        {"part": 1, "ers_id": "090166e530b8b278", "attachment_id": 3161071,
         "pdf": "pdfs/SWD_2026_616/part1.pdf", "sha256": "...",
         "downloaded_at": "<iso8601>", "pages": 143}
      ]
    }
  }
}
```

### Page-marked markdown (extract.py)

One .md per part via PyMuPDF. Before each PDF page's text, emit a marker
line on its own line: `<!-- page:N -->` where N is the 1-based PDF page
number (not the printed page label; record both if the label is available:
`<!-- page:N label:"37" -->`). Preserve reading order per page; do not
attempt layout reconstruction. These markers are the provenance backbone:
detect.py, review_html.py and the human workflow all depend on them.

### data/mentions.json

```json
{
  "generated_at": "<iso8601>",
  "primary_term": "foresight",
  "related_terms": ["horizon scanning", "megatrend", "scenario planning",
                     "delphi", "backcasting", "futures literacy"],
  "ias": {
    "SWD(2026)616": {
      "foresight_mention": true,
      "mentions": [
        {"id": "SWD(2026)616#p2-14-1", "part": 2, "page": 14,
         "page_label": "12",
         "excerpt": "... circa 400 words centred on the hit ...",
         "match_text": "Foresight",
         "in_reference_section": false}
      ],
      "related_term_counts": {"horizon scanning": 2, "megatrend": 0, ...},
      "related_term_locations": [{"term": "horizon scanning", "part": 1, "page": 44}]
    }
  }
}
```

Matching: case-insensitive substring `foresight` (catches Foresight,
foresight-based etc.). Related terms: case-insensitive, `megatrend` matches
megatrends. `in_reference_section` is a heuristic (mention appears after a
heading matching /^(references|bibliography|endnotes)/i in that part);
best-effort, default false. Excerpt: about 400 words centred on the match,
trimmed to sentence boundaries where cheap, newlines collapsed.

### data/out/dataset.xlsx (openpyxl)

Sheet "IAs", one row per IA, ordered by date descending:

| column | source |
|---|---|
| Reference | manifest |
| Title | manifest |
| Date | manifest |
| Responsible service | manifest (department code) |
| Topic | blank (filled later; controlled vocabulary) |
| Scope | derived from title, enum: new regulation, amending regulation, new directive, amending directive, council directive, decision, multiple acts, other. Regex over the title's act phrases; multiple distinct acts -> multiple acts |
| Foresight mention | YES / no |
| Mention count | count |
| Kind of foresight (final) | blank, human-owned; validation list embedded, contextual |
| AI draft: kind | blank (filled by AI step) |
| AI draft: methods | blank |
| AI draft: material influence | blank; validation yes, no, unclear |
| AI draft: how | blank |
| Other / notes | blank |
| Related: <term> | one count column per related term |
| Parts | number of parts |
| PDF folder | relative path pdfs/<ref-safe>/ |
| Markdown folder | relative path md/<ref-safe>/ |
| Docx folder | relative path docx/<ref-safe>/ |
| Flags | comma-joined manifest flags |

Sheet "Mentions", one row per mention: Reference, Part, Page, Page label,
Open PDF at page (hyperlink, see below), Excerpt, In reference section,
AI draft verdict, AI draft justification, Human verdict (validation list),
Human notes. Freeze header rows, sensible column widths, wrap text on
excerpt. On the IAs sheet, Reference links to the register detail page and
PDF folder links to the relative folder.

Because spreadsheet applications strip URL fragments from file hyperlinks
(a direct link to part1.pdf#page=14 opens at page 1), each mention's
hyperlink targets a tiny generated redirect page in data/links/ that
forwards the browser to ../pdfs/<ref-safe>/part<N>.pdf#page=<page> with the
fragment intact. outputs_xlsx.py generates one stub per mention.

### data/out/review.html (review_html.py)

Single self-contained file (inline CSS/JS, no CDN). For each IA (date
descending): header with reference, title, date, department, mention count,
links to detail page and local folders. Under it, each mention as a card:
excerpt with every case-insensitive `foresight` wrapped in `<mark>`, page
info, and a link `../pdfs/<ref-safe>/part<N>.pdf#page=<page>` (relative
path; review.html sits in data/out/). IAs with zero mentions listed in a
collapsed section at the end. Filter controls: all / with mentions /
without. Keep it dependency-free and readable in any modern browser opened
from the local filesystem. Must render acceptably in light and dark mode.

### data/out/README.md

Written for the research team: what the bundle contains, download the whole
folder before opening review.html, how the columns work (final columns are
theirs; AI draft columns are suggestions), and how to rerun the AI step
with prompts/classification-prompt.md on their own Claude subscription.

### prompts/classification-prompt.md

The documented prompt for the AI draft step: given a mention excerpt (plus
neighbouring context), return verdict embedded or contextual, a direct
quote as evidence, one-line justification; and per IA the synthesis fields
(methods, material influence yes/no/unclear, how). States the definitions:
embedded = foresight outputs or methods actually used in the assessment;
contextual = passing or bibliographic citation. Bibliography-only mentions
default to contextual.

## Non-goals

- No paid API calls anywhere in this pipeline.
- No Word-native pipeline logic: docx files are generated conveniences.
- No topic assignment in code (done in the AI/human layer against the
  controlled vocabulary).
- No scraping of pages other than the two documented endpoints.

## Definition of done

`python pipeline/run_all.py` on a clean checkout produces manifest, PDFs,
markdown, docx, mentions.json, dataset.xlsx, review.html and out/README.md
for the full corpus, and a second run performs no redundant downloads.
