"""Writes data/out/README.md - instructions for the research team.

Single owner of data/out/README.md (see the outputs-layer task notes: this
script owns it rather than outputs_xlsx.py or run_all.py generating it
inline). Reads manifest.json + mentions.json only to report live counts;
the prose itself is static. See SPEC.md "data/out/README.md".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def counts(manifest: dict, mentions: dict) -> tuple[int, int]:
    n_ias = len(manifest.get("ias", {}))
    n_mentions = sum(
        len(v.get("mentions", [])) for v in mentions.get("ias", {}).values()
    )
    return n_ias, n_mentions


def build_readme(manifest: dict, mentions: dict) -> str:
    n_ias, n_mentions = counts(manifest, mentions)
    kind_values = ", ".join(config.KIND_VALUES)
    influence_values = ", ".join(config.INFLUENCE_VALUES)
    return f"""# Foresight in EU Impact Assessments - data bundle

This folder is a self-contained snapshot: {n_ias} impact assessments,
{n_mentions} located "foresight" mentions. It was produced by
`pipeline/run_all.py` - see the repository's SPEC.md for the full method.

## Before you start

**Download the whole `data/` folder to your own machine before opening
anything.** `review.html` and `dataset.xlsx` link to the PDFs, markdown and
docx files using relative paths (`../pdfs/...`, `../md/...`, `../docx/...`).
Those links only resolve if the folder structure below is kept intact and
everything sits together locally - they will not work from a partial
download or if `out/` is moved out of `data/`.

```
data/
  manifest.json       one register entry per impact assessment (IA)
  mentions.json       every located "foresight" mention, with page refs
  pdfs/<ref>/partN.pdf
  md/<ref>/partN.md   page-marked plain text of each PDF
  docx/<ref>/partN.docx   Word versions of the markdown, for easier reading
  out/
    dataset.xlsx      the spreadsheet - see below
    review.html       open this first; double-click to open in a browser
    README.md         this file
```

## Start here: review.html

Open `data/out/review.html` in any modern browser (double-click it, no
server needed). Each impact assessment is listed newest-first with every
"foresight" mention shown as an excerpt (the word is highlighted), a link
to the register entry, and a link that jumps straight to the right page of
the source PDF. IAs with no mentions are collapsed at the bottom. Use the
"all / with mentions / without mentions" control at the top to filter.

## The spreadsheet: dataset.xlsx

Two sheets:

- **IAs** - one row per impact assessment.
- **Mentions** - one row per individual "foresight" mention, with its
  excerpt and page reference, for detailed classification.

### Which columns are yours vs. AI-drafted

- Columns named **"AI draft: ..."** (and **"AI draft verdict"** /
  **"AI draft justification"** on the Mentions sheet) are optional,
  machine-generated suggestions. They are a head start, not a result -
  see `docs/adr/0001-human-owned-classification.md` for why.
- Columns without "AI draft" in the name - **Kind of foresight (final)**,
  **Human verdict**, **Human notes**, **Topic**, **Other / notes** - are
  yours. These are what actually gets used in the published research.
  Confirm or override every AI draft; blank AI draft columns are simply
  ones nobody has run yet, not a judgement of "contextual" by default.
- **Scope** is filled in automatically from the title (a best-effort
  regex heuristic - please sanity-check it, it has not been reviewed by
  the team yet).
- Dropdown lists are embedded on the verdict/kind/influence columns
  (kind: {kind_values}; influence: {influence_values}) so you can pick
  from a fixed list rather than typing free text.

## Re-running the AI draft step yourself

The AI draft columns are produced by pasting mention excerpts into a
Claude session (claude.ai or Claude Code) under your own subscription -
**no paid API calls are used anywhere in this pipeline**. The prompt is
versioned at `prompts/classification-prompt.md` in the repository. To
redo or extend the drafts:

1. Open `prompts/classification-prompt.md` and copy its contents into a
   new claude.ai chat (or `claude` in a terminal).
2. Paste in the excerpt(s) from the Mentions sheet (and the IA's title/
   department for context) in the format the prompt asks for.
3. Copy Claude's output back into the matching "AI draft" columns.
4. Review each one against the excerpt before treating it as final -
   that review is the point of this workflow, not a formality.

## Questions

See CONTEXT.md and SPEC.md in the repository for the glossary and full
data contracts, and docs/adr/0001 for why classification is human-owned.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=config.MANIFEST_PATH)
    parser.add_argument("--mentions", type=Path, default=config.MENTIONS_PATH)
    parser.add_argument("--out", type=Path, default=config.OUT_DIR / "README.md")
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    if not args.mentions.exists():
        print(f"error: mentions not found: {args.mentions}", file=sys.stderr)
        return 1

    manifest = load_json(args.manifest)
    mentions = load_json(args.mentions)

    readme = build_readme(manifest, mentions)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(readme, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
