# Foresight in EU Impact Assessments: harvesting and screening pipeline

Tooling built to support research on the use of strategic foresight in
EU-level impact assessments (De Vito et al., UWE Bristol).

It deterministically:

1. harvests every Commission impact assessment listed in the
   [Register of Commission Documents](https://ec.europa.eu/transparency/documents-register/)
   from 31 January 2022 onwards (all PDF parts, politely rate-limited);
2. extracts page-marked text and converts each part to Markdown and docx;
3. locates every occurrence of "foresight" (plus a configurable list of
   related method terms) with page-level provenance;
4. emits a spreadsheet dataset and a self-contained HTML review page whose
   links open the local PDF at the exact page of each mention.

Classification of mentions (embedded use vs contextual citation) is done by
the research team; the pipeline's job is to make that judgement fast and
fully evidenced. An optional AI-assist step using a documented prompt
([prompts/classification-prompt.md](prompts/classification-prompt.md)) can
pre-fill clearly-marked draft columns; see
[docs/adr/0001](docs/adr/0001-human-owned-classification.md) for why drafts
are never the final answer. The delivered drafts were produced by Claude
Fable 5 on 31 July 2026 (recorded as `AI_DRAFT_PROVENANCE` in
`pipeline/config.py` and under `provenance` in the bundle's
`ai_drafts.json`).

## Usage

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python pipeline/run_all.py
```

Artefacts land in `data/` (gitignored). Re-running is incremental: already
downloaded documents are skipped and newly published impact assessments are
appended.

Requires `pandoc` on PATH for the docx conversion step (`brew install
pandoc` on macOS); all other steps run without it.

## Design documentation

- [SPEC.md](SPEC.md): the full implementation contract (API endpoints, data
  schemas, output formats).
- [CONTEXT.md](CONTEXT.md): the project glossary.
- [docs/adr/](docs/adr/): architecture decision records.

## Citation

If you use this tooling, please cite it (see [CITATION.cff](CITATION.cff)).

## License

MIT. The harvested documents themselves are public EU Commission documents;
their reuse is governed by the Commission's
[reuse policy](https://commission.europa.eu/legal-notice_en), not this
license.
