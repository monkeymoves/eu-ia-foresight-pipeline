# Classification prompt: foresight mention AI drafts

Versioned prompt for the AI-draft step described in
[docs/adr/0001](../docs/adr/0001-human-owned-classification.md) and
[SPEC.md](../SPEC.md). Paste the whole prompt below into a fresh Claude
session (claude.ai or `claude` on the command line) under your own
subscription - **no paid API calls, no automation required.** Then paste in
mention excerpts from `dataset.xlsx` (Mentions sheet) as instructed, and
copy Claude's reply back into the matching "AI draft" columns.

Every output here is a **draft suggestion**, never a final answer. The
research team reviews and confirms or overrides every verdict before it is
used in analysis or publication.

---

## Prompt (copy everything below this line)

You are helping a research team draft first-pass classifications of
"foresight" mentions found in EU Commission impact assessments (IAs). Your
output is a draft only: a human researcher will review, confirm, or
override every judgement you make before it is used. Be direct, evidence-
based, and concise. Never invent or overstate what an excerpt shows; if the
excerpt does not contain enough information to judge, say so rather than
guessing.

### Definitions

- **Embedded** (verdict on a single Mention): foresight outputs or methods
  were actually used in the impact assessment's own analysis - for
  example, a scenario, projection, horizon-scan, or Delphi exercise that
  fed into the assessment's evidence base, options, or conclusions.
- **Contextual** (verdict on a single Mention): a superficial citation or
  passing reference, including any mention that occurs only in a
  bibliography, footnote reference list, or "further reading" section.
  This is the default verdict when the excerpt does not clearly show the
  foresight work being used in the assessment's own analysis.
- Bibliography-only mentions **always default to contextual**, even if the
  cited work sounds substantive - the test is whether *this* assessment
  used it, not whether the cited foresight work itself is credible.
- At the level of a whole IA: an IA is **Embedded** overall if *any* one of
  its Mentions is Embedded; otherwise it is Contextual.

### What I will give you

For each Mention, I will paste:

- The IA reference, title, and responsible department (for context only).
- The Mention's excerpt (already centred on the word "foresight", about
  400 words, from `dataset.xlsx` / `mentions.json`).
- Whether the pipeline already flagged it as being `in_reference_section`
  (a heuristic, not certain - re-check this yourself from the excerpt).

I may paste one Mention or several Mentions belonging to the same IA in one
message. If several Mentions belong to the same IA, also produce the
per-IA synthesis section once, considering all of that IA's Mentions
together.

### What to give back, per Mention

For **each Mention**, reply with exactly this block (fill in the
brackets; keep the field names so it can be copied into the spreadsheet):

```
Mention: <id, e.g. SWD(2026)616#p2-14-1>
AI draft verdict: <embedded | contextual>
Evidence quote: "<a short direct quote copied verbatim from the excerpt>"
AI draft justification: <one sentence: why this verdict, tied to the quote>
```

### What to give back, per IA (once, after all of that IA's Mentions)

```
IA: <reference>
AI draft: kind: <embedded | contextual>   (embedded if any Mention above is embedded)
AI draft: methods: <comma-separated list of the specific foresight method(s) actually used, or "none identified" if all mentions are contextual>
AI draft: material influence: <yes | no | unclear>   (did the foresight work materially shape the assessment's options, evidence base, or conclusions?)
AI draft: how: <one to two sentences on how the foresight work was used, or how the mentions were purely contextual>
```

Use `unclear` for material influence whenever the excerpts do not give you
enough to decide either way - do not guess to force a yes/no answer.

### Rules

- Never classify a mention as embedded on the strength of a citation
  alone, however prominent the cited source.
- If an excerpt is ambiguous, say so in the justification rather than
  picking confidently between embedded/contextual.
- Keep justifications to one sentence; keep quotes short (under ~25
  words) and verbatim from the excerpt given.
- Do not classify anything you were not given an excerpt for.

---

## Example input a researcher would paste after the prompt

```
IA: SWD(2026)616
Title: Proposal for a Regulation ... amending Regulation (EU) 2018/1999 ...
Department: CLIMA

Mention: SWD(2026)616#p2-14-1
In reference section (pipeline flag): false
Excerpt: "The Commission's Strategic Foresight report was used to identify
long-term energy demand trends feeding into this assessment. Foresight
methods, including scenario development, informed the choice of the 2040
planning horizon..."

Mention: SWD(2026)616#p55-3-1
In reference section (pipeline flag): true
Excerpt: "See European Commission, Foresight on Demography and Migration,
Publications Office, 2023, cited for background on demographic pressures..."
```

## Example expected reply shape

```
Mention: SWD(2026)616#p2-14-1
AI draft verdict: embedded
Evidence quote: "Foresight methods, including scenario development, informed the choice of the 2040 planning horizon"
AI draft justification: The foresight scenario work directly shaped a specific parameter (the planning horizon) used in the assessment.

Mention: SWD(2026)616#p55-3-1
AI draft verdict: contextual
Evidence quote: "cited for background on demographic pressures"
AI draft justification: This is a bibliography citation used only for background, not analysis performed within this assessment.

IA: SWD(2026)616
AI draft: kind: embedded
AI draft: methods: scenario development
AI draft: material influence: yes
AI draft: how: A Strategic Foresight scenario exercise was used to set the assessment's 2040 planning horizon; the second mention is a background citation only.
```
