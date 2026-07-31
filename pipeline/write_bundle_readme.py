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
    base_url = config.PUBLIC_BASE_URL
    kind_values = ", ".join(config.KIND_VALUES)
    influence_values = ", ".join(config.INFLUENCE_VALUES)
    return f"""# Foresight in EU Impact Assessments - data bundle

{n_ias} impact assessments, {n_mentions} located "foresight" mentions.
Produced by `pipeline/run_all.py`; method and schemas in the repository's
SPEC.md (https://github.com/monkeymoves/eu-ia-foresight-pipeline).

## The two working surfaces

1. **The review page** - browse the evidence.
   Hosted at {base_url}/out/review.html (also in this bundle at
   `out/review.html`, which works offline). Search and filters at the top,
   an index of mention-bearing IAs on the left, every mention as a
   highlighted excerpt with a link that opens the source PDF at the exact
   page. Tick mentions as you review them; ticks are stored in your own
   browser only (a personal aid, not shared data).

2. **The spreadsheet** - record the judgements.
   `out/dataset.xlsx`: a single sheet, one row per impact assessment.
   Read the evidence for an IA on the review page (the "Review page" link
   in its row takes you straight there), then record your call in that row.

## Which columns are yours vs AI-drafted

- Yours (the actual dataset): **Topic**, **Kind of foresight (final)**,
  **Other / notes**. Dropdowns are embedded where a fixed list applies
  (kind: embedded, contextual).
- Machine suggestions, clearly named **"AI draft: ..."**: topic, kind,
  methods, material influence, how, notes. Every draft verdict traces to a
  verbatim quote visible on the review page. Confirm or override; never
  treat a draft as a result (see docs/adr/0001 in the repository).
- Deterministic (no AI, but heuristics worth sanity-checking): **Scope**
  (parsed from the title), **Mention pages**, **Related: ...** term counts,
  **Flags** (e.g. register-side download failures).

The "Reference" column links to the official register entry; "Review page"
links to that IA's section of the hosted review page. Both are ordinary
web links, so they work from Excel, Google Sheets, or anywhere else.

## Working in Google Sheets

Upload `dataset.xlsx` to Google Drive and open it with Google Sheets (or
File > Import in an empty Sheet). Links and dropdowns survive the
conversion, and the whole team can then work in one shared Sheet.

## Folder contents

```
manifest.json       one register entry per impact assessment (IA)
mentions.json       every located "foresight" mention, with page refs
ai_drafts.json      the combined AI draft classifications (with evidence)
pdfs/<ref>/partN.pdf
md/<ref>/partN.md   page-marked plain text of each PDF
docx/<ref>/partN.docx   Word versions, for easier reading
out/
  dataset.xlsx      the spreadsheet (web links - for Google Sheets)
  dataset-offline.xlsx  same sheet with local links, for offline use
  links/            per-IA redirect stubs used by the offline spreadsheet
  review.html       the review page (self-contained, works offline)
  README.md         this file
```

## Re-running the AI draft step yourself

The AI drafts were produced in Claude sessions (claude.ai / Claude Code)
using the versioned prompt at `prompts/classification-prompt.md` in the
repository - no paid API calls anywhere. To redo or extend them, paste the
prompt plus the relevant excerpts into your own Claude session and copy
the output back into the "AI draft" columns, then review as usual.
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
