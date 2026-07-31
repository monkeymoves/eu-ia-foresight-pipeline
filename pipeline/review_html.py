"""manifest.json + mentions.json -> data/out/review.html

A single self-contained, dependency-free HTML file for human review. See
SPEC.md ("data/out/review.html") for the contract. No CDN assets, no
network calls: everything (CSS, JS) is inlined so the file works when
opened directly from the local filesystem (file://).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config

_FORESIGHT_RE = re.compile(re.escape(config.PRIMARY_TERM), re.IGNORECASE)


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def highlight(text: str) -> str:
    """HTML-escape then wrap every case-insensitive 'foresight' in <mark>."""
    escaped = html.escape(text)
    return _FORESIGHT_RE.sub(lambda m: f"<mark>{m.group(0)}</mark>", escaped)


def esc(text) -> str:
    return html.escape(str(text)) if text is not None else ""


def verdict_chip(verdict: str) -> str:
    if verdict not in ("embedded", "contextual"):
        return ""
    return f'<span class="chip chip-{verdict}">AI draft: {verdict}</span>'


def mention_card(reference: str, ref_safe: str, mention: dict, draft_verdicts: dict) -> str:
    part = mention.get("part")
    page = mention.get("page")
    page_label = mention.get("page_label")
    in_ref = mention.get("in_reference_section", False)
    pdf_href = f"../pdfs/{ref_safe}/part{part}.pdf#page={page}"
    dv = draft_verdicts.get(mention.get("id"), {})
    draft_bit = ""
    if dv.get("verdict"):
        why = esc(dv.get("justification", ""))
        quote = esc(dv.get("evidence_quote", ""))
        draft_bit = (
            f'<p class="draft-line">{verdict_chip(dv["verdict"])} '
            f'<em>&ldquo;{quote}&rdquo;</em> {why}</p>'
        )
    label_bit = f' (label "{esc(page_label)}")' if page_label else ""
    ref_bit = ' <span class="ref-tag">in reference section</span>' if in_ref else ""
    return f"""
      <article class="mention">
        <p class="excerpt">{highlight(mention.get("excerpt", ""))}</p>
        <p class="mention-meta">
          Part {esc(part)}, page {esc(page)}{label_bit} &middot;
          <a href="{esc(pdf_href)}">open PDF at this page</a>{ref_bit}
        </p>{draft_bit}
      </article>"""


def ia_section(reference: str, ia: dict, ia_mentions: dict, draft: dict, topic: str) -> str:
    draft_verdicts = draft.get("mention_verdicts", {})
    ref_safe = ia.get("ref_safe", config.ref_safe(reference))
    mentions = ia_mentions.get("mentions", [])
    n = len(mentions)
    has = "true" if n else "false"
    flags = ia.get("flags", [])
    flags_bit = (
        f'<span class="flags">flags: {esc(", ".join(flags))}</span>' if flags else ""
    )
    cards = "\n".join(mention_card(reference, ref_safe, m, draft_verdicts) for m in mentions) or (
        '<p class="no-mentions">No foresight mentions found.</p>'
    )
    return f"""
    <section class="ia" data-has-mentions="{has}">
      <h2>{esc(reference)}</h2>
      <p class="title">{esc(ia.get("title", ""))}</p>
      <p class="ia-meta">
        {esc(ia.get("date", ""))} &middot; {esc(ia.get("responsible_department", ""))}
        &middot; {n} mention{"s" if n != 1 else ""} &middot;
        <a href="{esc(ia.get("detail_url", "#"))}">register detail</a> &middot;
        <a href="../pdfs/{esc(ref_safe)}/">PDFs</a> &middot;
        <a href="../md/{esc(ref_safe)}/">markdown</a> &middot;
        <a href="../docx/{esc(ref_safe)}/">docx</a>
        {flags_bit}
      </p>
      {ia_draft_block(draft, topic)}
      <div class="mentions">{cards}
      </div>
    </section>"""


def ia_draft_block(draft: dict, topic: str) -> str:
    bits = []
    if topic:
        bits.append(f'<span class="chip chip-topic">AI draft topic: {esc(topic)}</span>')
    if draft.get("kind"):
        bits.append(verdict_chip(draft["kind"]))
    if draft.get("methods"):
        bits.append(f"<strong>Methods:</strong> {esc('; '.join(draft['methods']))}")
    if draft.get("material_influence"):
        bits.append(f"<strong>Material influence:</strong> {esc(draft['material_influence'])}")
    if draft.get("influence_how"):
        bits.append(esc(draft["influence_how"]))
    if draft.get("notes"):
        bits.append(f"<strong>Notes:</strong> {esc(draft['notes'])}")
    if not bits:
        return ""
    inner = " &middot; ".join(bits)
    return (
        '<p class="ia-draft">' + inner +
        ' <span class="draft-caveat">(AI draft; requires human review)</span></p>'
    )


CSS = """
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --fg: #1b1b1b;
  --muted: #5f5f5f;
  --border: #dcdcdc;
  --card-bg: #fafafa;
  --mark-bg: #ffe58a;
  --mark-fg: #1b1b1b;
  --link: #0b5fa5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14161a;
    --fg: #e7e7e7;
    --muted: #a0a0a0;
    --border: #383b40;
    --card-bg: #1c1f24;
    --mark-bg: #7a5b00;
    --mark-fg: #fff3d6;
    --link: #6cb2f2;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 1.5rem;
  max-width: 66rem;
  margin-inline: auto;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.45;
}
header { margin-bottom: 1.5rem; }
h1 { font-size: 1.4rem; margin: 0 0 0.25rem; }
.meta { color: var(--muted); font-size: 0.9rem; margin: 0 0 1rem; }
.filters { display: flex; gap: 1.25rem; font-size: 0.9rem; }
.filters label { cursor: pointer; }
a { color: var(--link); }
section.ia {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
section.ia h2 { margin: 0 0 0.15rem; font-size: 1.05rem; }
.title { margin: 0 0 0.4rem; color: var(--muted); font-size: 0.92rem; }
.ia-meta { margin: 0 0 0.75rem; font-size: 0.85rem; color: var(--muted); }
.flags { color: #b45309; font-weight: 600; }
.mentions { display: flex; flex-direction: column; gap: 0.6rem; }
article.mention {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
}
.excerpt { margin: 0 0 0.4rem; font-size: 0.92rem; white-space: pre-wrap; }
.mention-meta { margin: 0; font-size: 0.8rem; color: var(--muted); }
.ref-tag {
  background: var(--border);
  border-radius: 4px;
  padding: 0.05rem 0.4rem;
  font-size: 0.75rem;
}
.no-mentions { color: var(--muted); font-style: italic; margin: 0; }
mark { background: var(--mark-bg); color: var(--mark-fg); border-radius: 2px; padding: 0 0.1rem; }
.chip {
  display: inline-block;
  border-radius: 4px;
  padding: 0.05rem 0.45rem;
  font-size: 0.78rem;
  font-weight: 600;
}
.chip-embedded { background: #14532d; color: #dcfce7; }
.chip-contextual { background: #57534e; color: #f5f5f4; }
.chip-topic { background: var(--border); color: var(--fg); }
@media (prefers-color-scheme: light) {
  .chip-embedded { background: #bbf7d0; color: #14532d; }
  .chip-contextual { background: #e7e5e4; color: #44403c; }
}
.draft-line { margin: 0.35rem 0 0; font-size: 0.82rem; color: var(--muted); }
.ia-draft { margin: 0 0 0.6rem; font-size: 0.85rem; }
.draft-caveat { color: var(--muted); font-style: italic; font-size: 0.78rem; }
details.zero-group { margin-top: 1.5rem; }
details.zero-group summary {
  cursor: pointer;
  font-weight: 600;
  padding: 0.5rem 0;
  color: var(--muted);
}
"""

JS = """
(function () {
  var radios = document.querySelectorAll('input[name="filter"]');
  var mainList = document.getElementById('main-list');
  var zeroGroup = document.getElementById('zero-group');
  function apply(mode) {
    mainList.style.display = mode === 'without' ? 'none' : '';
    if (mode === 'with') {
      zeroGroup.style.display = 'none';
    } else {
      zeroGroup.style.display = '';
    }
    if (mode === 'without') {
      zeroGroup.open = true;
    }
  }
  radios.forEach(function (r) {
    r.addEventListener('change', function () { apply(r.value); });
  });
  apply('all');
})();
"""


def build_html(manifest: dict, mentions: dict, drafts: dict | None = None) -> str:
    drafts = drafts or {}
    draft_ias = drafts.get("ias", {})
    draft_topics = drafts.get("topics", {})
    ias = manifest.get("ias", {})
    mention_ias = mentions.get("ias", {})
    ordered_refs = sorted(ias.keys(), key=lambda r: ias[r].get("date", ""), reverse=True)

    with_mentions = []
    without_mentions = []
    total_mentions = 0
    for reference in ordered_refs:
        ia = ias[reference]
        ia_m = mention_ias.get(reference, {})
        n = len(ia_m.get("mentions", []))
        total_mentions += n
        section = ia_section(reference, ia, ia_m, draft_ias.get(reference, {}), draft_topics.get(reference, ""))
        if n:
            with_mentions.append(section)
        else:
            without_mentions.append(section)

    generated_at = esc(mentions.get("generated_at", ""))
    primary_term = esc(mentions.get("primary_term", config.PRIMARY_TERM))
    n_ias = len(ordered_refs)

    main_html = "\n".join(with_mentions) or '<p class="no-mentions">No IAs with mentions.</p>'
    zero_html = "\n".join(without_mentions) or '<p class="no-mentions">None.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foresight in EU Impact Assessments &ndash; review</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Foresight in EU Impact Assessments &ndash; review</h1>
  <p class="meta">
    Generated {generated_at} &middot; primary term &quot;{primary_term}&quot; &middot;
    {n_ias} IAs &middot; {total_mentions} mention{"s" if total_mentions != 1 else ""}
  </p>
  <div class="filters" role="group" aria-label="Filter IAs">
    <label><input type="radio" name="filter" value="all" checked> All</label>
    <label><input type="radio" name="filter" value="with"> With mentions</label>
    <label><input type="radio" name="filter" value="without"> Without mentions</label>
  </div>
</header>
<main>
  <div id="main-list">{main_html}
  </div>
  <details class="zero-group" id="zero-group">
    <summary>IAs with no foresight mentions ({len(without_mentions)})</summary>
    {zero_html}
  </details>
</main>
<script>{JS}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=config.MANIFEST_PATH)
    parser.add_argument("--mentions", type=Path, default=config.MENTIONS_PATH)
    parser.add_argument("--out", type=Path, default=config.OUT_DIR / "review.html")
    parser.add_argument("--drafts", type=Path, default=config.DATA_DIR / "ai_drafts.json")
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    if not args.mentions.exists():
        print(f"error: mentions not found: {args.mentions}", file=sys.stderr)
        return 1

    manifest = load_json(args.manifest)
    mentions = load_json(args.mentions)

    drafts = load_json(args.drafts) if args.drafts.exists() else None
    if drafts:
        print(f"including AI drafts from {args.drafts}")
    out_html = build_html(manifest, mentions, drafts)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_html, encoding="utf-8")

    print(f"wrote {args.out} ({len(out_html)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
