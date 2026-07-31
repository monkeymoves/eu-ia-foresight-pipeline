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

TITLE_TRUNCATE_CHARS = 90


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def highlight(text: str) -> str:
    """HTML-escape then wrap every case-insensitive 'foresight' in <mark>."""
    escaped = html.escape(text)
    return _FORESIGHT_RE.sub(lambda m: f"<mark>{m.group(0)}</mark>", escaped)


def esc(text) -> str:
    return html.escape(str(text)) if text is not None else ""


def truncate(text: str, limit: int = TITLE_TRUNCATE_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def verdict_chip(verdict: str) -> str:
    if verdict not in ("embedded", "contextual"):
        return ""
    return f'<span class="chip chip-{verdict}">AI draft: {verdict}</span>'


def kind_chip_small(kind: str) -> str:
    """Compact chip used in collapsed summaries / sidebar (no 'AI draft:' prefix)."""
    if kind not in ("embedded", "contextual"):
        return ""
    return f'<span class="chip chip-{kind} chip-sm">{esc(kind)}</span>'


def mention_card(reference: str, ref_safe: str, mention: dict, draft_verdicts: dict) -> str:
    part = mention.get("part")
    page = mention.get("page")
    page_label = mention.get("page_label")
    in_ref = mention.get("in_reference_section", False)
    pdf_href = f"../pdfs/{ref_safe}/part{part}.pdf#page={page}"
    mention_id = mention.get("id", "")
    dv = draft_verdicts.get(mention_id, {})
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
      <article class="mention" data-mention-id="{esc(mention_id)}">
        <p class="excerpt">{highlight(mention.get("excerpt", ""))}</p>
        <p class="mention-meta">
          Part {esc(part)}, page {esc(page)}{label_bit} &middot;
          <a href="{esc(pdf_href)}">open PDF at this page</a>{ref_bit}
        </p>{draft_bit}
        <label class="reviewed-toggle">
          <input type="checkbox" class="reviewed-checkbox" data-mention-id="{esc(mention_id)}" data-ia="{esc(ref_safe)}">
          Reviewed
        </label>
      </article>"""


def build_search_blob(reference: str, title: str, department: str, topic: str) -> str:
    parts = [reference, title, department, topic]
    return esc(" ".join(p for p in parts if p).lower())


def ia_section(reference: str, ia: dict, ia_mentions: dict, draft: dict, topic: str) -> str:
    draft_verdicts = draft.get("mention_verdicts", {})
    ref_safe = ia.get("ref_safe", config.ref_safe(reference))
    mentions = ia_mentions.get("mentions", [])
    n = len(mentions)
    has = "true" if n else "false"
    kind = draft.get("kind") if draft.get("kind") in ("embedded", "contextual") else ""
    title = ia.get("title", "")
    date = ia.get("date", "")
    department = ia.get("responsible_department", "")
    flags = ia.get("flags", [])
    flags_bit = (
        f'<span class="flags">flags: {esc(", ".join(flags))}</span>' if flags else ""
    )
    cards = "\n".join(mention_card(reference, ref_safe, m, draft_verdicts) for m in mentions) or (
        '<p class="no-mentions">No foresight mentions found.</p>'
    )
    search_blob = build_search_blob(reference, title, department, topic)

    summary_bits = [
        f'<span class="ia-ref">{esc(reference)}</span>',
        f'<span class="ia-title-trunc">{esc(truncate(title))}</span>',
    ]
    if date:
        summary_bits.append(f'<span class="ia-date">{esc(date)}</span>')
    if department:
        summary_bits.append(f'<span class="ia-dept">{esc(department)}</span>')
    if topic:
        summary_bits.append(f'<span class="ia-topic">{esc(topic)}</span>')
    if kind:
        summary_bits.append(kind_chip_small(kind))
    summary_bits.append(f'<span class="ia-count">{n} mention{"s" if n != 1 else ""}</span>')
    if n:
        summary_bits.append(
            f'<span class="ia-progress" id="progress-{esc(ref_safe)}">0/{n} reviewed</span>'
        )
    summary_line = "\n          ".join(summary_bits)

    return f"""
    <details class="ia" id="ia-{esc(ref_safe)}" data-has-mentions="{has}" data-kind="{esc(kind)}" data-search="{search_blob}" data-ia="{esc(ref_safe)}" data-count="{n}">
      <summary class="ia-summary">
          {summary_line}
      </summary>
      <div class="ia-body">
        <p class="title">{esc(title)}</p>
        <p class="ia-meta">
          {esc(date)} &middot; {esc(department)}
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
      </div>
    </details>"""


def sidebar_item(reference: str, ia: dict, n: int, kind: str, topic: str) -> str:
    ref_safe = ia.get("ref_safe", config.ref_safe(reference))
    department = ia.get("responsible_department", "")
    title = ia.get("title", "")
    search_blob = build_search_blob(reference, title, department, topic)
    chip = kind_chip_small(kind) if kind else ""
    return f"""
      <li class="sidebar-item" data-ia="{esc(ref_safe)}" data-has-mentions="true" data-kind="{esc(kind)}" data-search="{search_blob}">
        <a class="sidebar-link" href="#ia-{esc(ref_safe)}" data-target="ia-{esc(ref_safe)}">
          <span class="sidebar-ref">{esc(reference)}</span>
          <span class="sidebar-count">{n}</span>
        </a>
        <div class="sidebar-sub">
          <span class="sidebar-dept">{esc(department)}</span>
          {chip}
        </div>
        <div class="sidebar-progress" id="sidebar-progress-{esc(ref_safe)}">0/{n} reviewed</div>
      </li>"""


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
  --header-bg: #ffffff;
  --mark-bg: #ffe58a;
  --mark-fg: #1b1b1b;
  --link: #0b5fa5;
  --accent: #0b5fa5;
  --done-bg: #eefaf0;
  --done-border: #b7e4c1;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14161a;
    --fg: #e7e7e7;
    --muted: #a0a0a0;
    --border: #383b40;
    --card-bg: #1c1f24;
    --header-bg: #14161a;
    --mark-bg: #7a5b00;
    --mark-fg: #fff3d6;
    --link: #6cb2f2;
    --accent: #6cb2f2;
    --done-bg: #10241a;
    --done-border: #2c5c3d;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.45;
}
a { color: var(--link); }
.wrap { max-width: 90rem; margin-inline: auto; padding: 0 1.5rem; }

/* ---- sticky header ---- */
header.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--header-bg);
  border-bottom: 1px solid var(--border);
  padding: 1rem 0;
}
.topbar-row1 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}
h1 { font-size: 1.3rem; margin: 0 0 0.2rem; }
.meta { color: var(--muted); font-size: 0.85rem; margin: 0 0 0.75rem; }
.sidebar-toggle {
  display: none;
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--fg);
  border-radius: 6px;
  padding: 0.35rem 0.7rem;
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.9rem 1.4rem;
  margin-bottom: 0.5rem;
}
#search-input {
  flex: 1 1 18rem;
  min-width: 12rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
  color: var(--fg);
  font-size: 0.9rem;
}
.filters { display: flex; gap: 1rem; font-size: 0.85rem; flex-wrap: wrap; }
.filters label { cursor: pointer; white-space: nowrap; }
.expand-controls { display: flex; gap: 0.5rem; }
.expand-controls button {
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--fg);
  border-radius: 6px;
  padding: 0.35rem 0.65rem;
  font-size: 0.82rem;
  cursor: pointer;
}
.expand-controls button:hover { border-color: var(--accent); }
.counts {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
  color: var(--muted);
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}
.counts strong { color: var(--fg); }
.review-note {
  margin: 0.35rem 0 0;
  font-size: 0.76rem;
  color: var(--muted);
  font-style: italic;
}

/* ---- layout: sidebar + main ---- */
.layout {
  display: flex;
  align-items: flex-start;
  gap: 1.5rem;
  padding: 1.25rem 0 2rem;
}
.sidebar {
  flex: 0 0 17rem;
  width: 17rem;
  position: sticky;
  top: 9.5rem;
  max-height: calc(100vh - 10rem);
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card-bg);
  padding: 0.5rem;
}
.sidebar h2 {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--muted);
  margin: 0.25rem 0.4rem 0.5rem;
}
#sidebar-list { list-style: none; margin: 0; padding: 0; }
.sidebar-item {
  border-bottom: 1px solid var(--border);
  padding: 0.45rem 0.4rem;
}
.sidebar-item:last-child { border-bottom: none; }
.sidebar-link {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  text-decoration: none;
}
.sidebar-link:hover { text-decoration: underline; }
.sidebar-count {
  color: var(--muted);
  font-weight: 400;
  font-variant-numeric: tabular-nums;
}
.sidebar-sub {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.15rem;
  font-size: 0.75rem;
  color: var(--muted);
  flex-wrap: wrap;
}
.sidebar-progress {
  margin-top: 0.15rem;
  font-size: 0.72rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

main { flex: 1; min-width: 0; }

/* ---- IA sections (details/summary) ---- */
details.ia {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0;
  margin-bottom: 0.6rem;
}
details.ia[hidden] { display: none; }
details.ia > summary.ia-summary {
  cursor: pointer;
  list-style: none;
  padding: 0.6rem 1rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0 0.6rem;
  font-size: 0.88rem;
}
details.ia > summary.ia-summary::-webkit-details-marker { display: none; }
details.ia > summary.ia-summary::before {
  content: "\\25B8";
  color: var(--muted);
  margin-right: 0.15rem;
  transition: transform 0.1s ease;
}
details.ia[open] > summary.ia-summary::before { transform: rotate(90deg); }
.ia-ref { font-weight: 700; }
.ia-title-trunc { color: var(--muted); flex: 1 1 16rem; min-width: 8rem; }
.ia-date, .ia-dept, .ia-topic, .ia-count, .ia-progress {
  font-size: 0.8rem;
  color: var(--muted);
  white-space: nowrap;
}
.ia-count { font-weight: 600; color: var(--fg); }
.ia-progress { font-variant-numeric: tabular-nums; }
.ia-body { padding: 0 1.25rem 1rem; }
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
article.mention.is-reviewed {
  background: var(--done-bg);
  border-color: var(--done-border);
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
.reviewed-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--muted);
  cursor: pointer;
  user-select: none;
}
.reviewed-toggle input { cursor: pointer; }
.chip {
  display: inline-block;
  border-radius: 4px;
  padding: 0.05rem 0.45rem;
  font-size: 0.78rem;
  font-weight: 600;
}
.chip-sm { font-size: 0.72rem; padding: 0.02rem 0.35rem; }
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
details.ia.deep-linked { outline: 2px solid var(--link); outline-offset: 2px; }
details.zero-group { margin-top: 1.5rem; border: none; }
details.zero-group > summary {
  cursor: pointer;
  list-style: none;
  font-weight: 600;
  padding: 0.5rem 0;
  color: var(--muted);
}
details.zero-group > summary::-webkit-details-marker { display: none; }
details.zero-group .ia { margin: 0.5rem 0 0; }

/* ---- narrow screens: sidebar becomes a slide-over drawer ---- */
@media (max-width: 900px) {
  .sidebar-toggle { display: inline-block; }
  .layout { flex-direction: column; }
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 82vw;
    max-width: 20rem;
    max-height: none;
    z-index: 100;
    border-radius: 0;
    transform: translateX(-100%);
    transition: transform 0.18s ease;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.25);
  }
  body.sidebar-open .sidebar { transform: translateX(0); }
  .sidebar-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 90;
  }
  body.sidebar-open .sidebar-backdrop { display: block; }
}
"""

JS = """
(function () {
  'use strict';
  var STORAGE_KEY = 'devito-review-progress-v1';

  var searchInput = document.getElementById('search-input');
  var modeRadios = document.querySelectorAll('input[name="filter"]');
  var verdictRadios = document.querySelectorAll('input[name="verdict-filter"]');
  var mainList = document.getElementById('main-list');
  var zeroGroup = document.getElementById('zero-group');
  var matchCount = document.getElementById('match-count');
  var reviewedCount = document.getElementById('reviewed-count');
  var expandAllBtn = document.getElementById('expand-all');
  var collapseAllBtn = document.getElementById('collapse-all');
  var sidebarToggle = document.getElementById('sidebar-toggle');
  var sidebarBackdrop = document.getElementById('sidebar-backdrop');
  var sidebarList = document.getElementById('sidebar-list');

  var allIaEls = Array.prototype.slice.call(document.querySelectorAll('details.ia'));
  var allSidebarEls = sidebarList ? Array.prototype.slice.call(sidebarList.querySelectorAll('.sidebar-item')) : [];
  var TOTAL_MENTIONS = allIaEls.reduce(function (sum, el) {
    return sum + (parseInt(el.getAttribute('data-count'), 10) || 0);
  }, 0);

  /* Render "<strong>N</strong> of M things" into a container without innerHTML. */
  function setCount(container, boldText, restText) {
    if (!container) return;
    while (container.firstChild) container.removeChild(container.firstChild);
    var strong = document.createElement('strong');
    strong.textContent = boldText;
    container.appendChild(strong);
    container.appendChild(document.createTextNode(restText));
  }

  /* ---------------- reviewed-state persistence ---------------- */
  var reviewed = {};
  try {
    var raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) reviewed = JSON.parse(raw) || {};
  } catch (e) {
    reviewed = {};
  }

  function saveReviewed() {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(reviewed));
    } catch (e) {
      /* localStorage unavailable (e.g. private mode) - progress just won't persist */
    }
  }

  var iaProgress = {}; /* ref_safe -> { total, done } */
  var totalReviewed = 0;

  function initProgress() {
    var checkboxes = document.querySelectorAll('.reviewed-checkbox');
    checkboxes.forEach(function (cb) {
      var id = cb.getAttribute('data-mention-id');
      var ia = cb.getAttribute('data-ia');
      if (!iaProgress[ia]) iaProgress[ia] = { total: 0, done: 0 };
      iaProgress[ia].total += 1;
      if (reviewed[id]) {
        cb.checked = true;
        var article = cb.closest('.mention');
        if (article) article.classList.add('is-reviewed');
        iaProgress[ia].done += 1;
        totalReviewed += 1;
      }
    });
    Object.keys(iaProgress).forEach(updateIaProgressDisplay);
    updateOverallCount();
  }

  function updateIaProgressDisplay(ia) {
    var p = iaProgress[ia];
    if (!p) return;
    var text = p.done + '/' + p.total + ' reviewed';
    var summarySpan = document.getElementById('progress-' + ia);
    if (summarySpan) summarySpan.textContent = text;
    var sidebarSpan = document.getElementById('sidebar-progress-' + ia);
    if (sidebarSpan) sidebarSpan.textContent = text;
  }

  function updateOverallCount() {
    setCount(reviewedCount, String(totalReviewed), ' of ' + TOTAL_MENTIONS + ' mentions reviewed');
  }

  function recomputeIaProgress(ia) {
    if (!iaProgress[ia]) return;
    var scope = document.getElementById('ia-' + ia);
    if (!scope) return;
    var boxes = scope.querySelectorAll('.reviewed-checkbox');
    var done = 0;
    boxes.forEach(function (b) { if (b.checked) done += 1; });
    var delta = done - iaProgress[ia].done;
    iaProgress[ia].done = done;
    totalReviewed += delta;
    updateIaProgressDisplay(ia);
    updateOverallCount();
  }

  function onCheckboxChange(evt) {
    var cb = evt.target;
    if (!cb.classList || !cb.classList.contains('reviewed-checkbox')) return;
    var id = cb.getAttribute('data-mention-id');
    var ia = cb.getAttribute('data-ia');
    var article = cb.closest('.mention');
    if (cb.checked) {
      reviewed[id] = true;
      if (article) article.classList.add('is-reviewed');
    } else {
      delete reviewed[id];
      if (article) article.classList.remove('is-reviewed');
    }
    recomputeIaProgress(ia);
    saveReviewed();
  }

  document.addEventListener('change', onCheckboxChange);

  /* ---------------- search / filter ---------------- */
  var mode = 'all';
  var verdictMode = 'any';
  var searchDebounceTimer = null;

  function matches(el) {
    var hasMentions = el.getAttribute('data-has-mentions') === 'true';
    var kind = el.getAttribute('data-kind') || '';
    var haystack = el.getAttribute('data-search') || '';
    if (mode === 'with' && !hasMentions) return false;
    if (mode === 'without' && hasMentions) return false;
    if (verdictMode !== 'any' && kind !== verdictMode) return false;
    var term = searchInput ? searchInput.value.trim().toLowerCase() : '';
    if (term && haystack.indexOf(term) === -1) return false;
    return true;
  }

  function apply() {
    var visibleCount = 0;
    allIaEls.forEach(function (el) {
      var ok = matches(el);
      el.hidden = !ok;
      if (ok) visibleCount += 1;
    });
    allSidebarEls.forEach(function (el) {
      el.hidden = !matches(el);
    });

    if (mainList) mainList.style.display = mode === 'without' ? 'none' : '';
    if (zeroGroup) {
      zeroGroup.style.display = mode === 'with' ? 'none' : '';
      if (mode === 'without') zeroGroup.open = true;
    }

    setCount(matchCount, String(visibleCount), ' of ' + allIaEls.length + ' IAs match');
  }

  modeRadios.forEach(function (r) {
    r.addEventListener('change', function () {
      if (r.checked) mode = r.value;
      apply();
    });
  });
  verdictRadios.forEach(function (r) {
    r.addEventListener('change', function () {
      if (r.checked) verdictMode = r.value;
      apply();
    });
  });
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(apply, 160);
    });
  }

  /* ---------------- expand / collapse all ---------------- */
  if (expandAllBtn) {
    expandAllBtn.addEventListener('click', function () {
      allIaEls.forEach(function (el) { el.open = true; });
      if (zeroGroup) zeroGroup.open = true;
    });
  }
  if (collapseAllBtn) {
    collapseAllBtn.addEventListener('click', function () {
      allIaEls.forEach(function (el) { el.open = false; });
      if (zeroGroup) zeroGroup.open = false;
    });
  }

  /* ---------------- sidebar navigation + drawer ---------------- */
  function closeSidebar() {
    document.body.classList.remove('sidebar-open');
    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', 'false');
  }
  function openSidebar() {
    document.body.classList.add('sidebar-open');
    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', 'true');
  }
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function () {
      if (document.body.classList.contains('sidebar-open')) closeSidebar();
      else openSidebar();
    });
  }
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', closeSidebar);
  }
  if (sidebarList) {
    sidebarList.addEventListener('click', function (evt) {
      var link = evt.target.closest ? evt.target.closest('.sidebar-link') : null;
      if (!link) return;
      evt.preventDefault();
      var targetId = link.getAttribute('data-target');
      var target = document.getElementById(targetId);
      if (target) {
        target.open = true;
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (history.pushState) history.pushState(null, '', '#' + targetId);
      }
      closeSidebar();
    });
  }

  /* ---------------- deep links (e.g. from the spreadsheet) ---------------- */
  function focusHashTarget() {
    var hash = location.hash || '';
    if (hash.indexOf('#ia-') !== 0) return;
    var target = document.getElementById(hash.slice(1));
    if (!target) return;
    /* Declutter: filter the page down to just this IA, open it, scroll. */
    var ref = target.querySelector('.ia-ref');
    if (searchInput && ref) {
      searchInput.value = ref.textContent;
      apply();
    }
    target.open = true;
    target.classList.add('deep-linked');
    setTimeout(function () {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }
  window.addEventListener('hashchange', focusHashTarget);

  initProgress();
  apply();
  focusHashTarget();
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
    sidebar_items = []
    total_mentions = 0
    for reference in ordered_refs:
        ia = ias[reference]
        ia_m = mention_ias.get(reference, {})
        n = len(ia_m.get("mentions", []))
        total_mentions += n
        draft = draft_ias.get(reference, {})
        topic = draft_topics.get(reference, "")
        section = ia_section(reference, ia, ia_m, draft, topic)
        if n:
            with_mentions.append(section)
            kind = draft.get("kind") if draft.get("kind") in ("embedded", "contextual") else ""
            sidebar_items.append(sidebar_item(reference, ia, n, kind, topic))
        else:
            without_mentions.append(section)

    generated_at = esc(mentions.get("generated_at", ""))
    primary_term = esc(mentions.get("primary_term", config.PRIMARY_TERM))
    n_ias = len(ordered_refs)

    main_html = "\n".join(with_mentions) or '<p class="no-mentions">No IAs with mentions.</p>'
    zero_html = "\n".join(without_mentions) or '<p class="no-mentions">None.</p>'
    sidebar_html = "\n".join(sidebar_items) or '<li class="no-mentions">No IAs with mentions.</li>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foresight in EU Impact Assessments &ndash; review</title>
<style>{CSS}</style>
</head>
<body>
<header class="topbar">
  <div class="wrap">
    <div class="topbar-row1">
      <div>
        <h1>Foresight in EU Impact Assessments &ndash; review</h1>
        <p class="meta">
          Generated {generated_at} &middot; primary term &quot;{primary_term}&quot; &middot;
          {n_ias} IAs &middot; {total_mentions} mention{"s" if total_mentions != 1 else ""}
        </p>
      </div>
      <button type="button" id="sidebar-toggle" class="sidebar-toggle" aria-expanded="false" aria-controls="sidebar">
        &#9776; IA list
      </button>
    </div>
    <div class="controls">
      <input type="search" id="search-input" placeholder="Search by reference, title, department, or draft topic&hellip;" aria-label="Search IAs">
      <div class="filters" role="group" aria-label="Filter IAs by mentions">
        <label><input type="radio" name="filter" value="all" checked> All</label>
        <label><input type="radio" name="filter" value="with"> With mentions</label>
        <label><input type="radio" name="filter" value="without"> Without mentions</label>
      </div>
      <div class="filters" role="group" aria-label="Filter IAs by AI draft verdict">
        <label><input type="radio" name="verdict-filter" value="any" checked> Any verdict</label>
        <label><input type="radio" name="verdict-filter" value="embedded"> Embedded</label>
        <label><input type="radio" name="verdict-filter" value="contextual"> Contextual</label>
      </div>
      <div class="expand-controls">
        <button type="button" id="expand-all">Expand all</button>
        <button type="button" id="collapse-all">Collapse all</button>
      </div>
    </div>
    <p class="counts">
      <span id="match-count"><strong>{n_ias}</strong> of {n_ias} IAs match</span>
      <span id="reviewed-count"><strong>0</strong> of {total_mentions} mentions reviewed</span>
    </p>
    <p class="review-note">
      Reviewed ticks are stored in this browser only (localStorage), as a personal working aid &mdash;
      they are not shared with anyone else and the spreadsheet remains the real record.
    </p>
  </div>
</header>
<div class="wrap layout">
  <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
  <nav class="sidebar" id="sidebar" aria-label="IAs with mentions">
    <h2>IAs with mentions ({len(sidebar_items)})</h2>
    <ul id="sidebar-list">{sidebar_html}
    </ul>
  </nav>
  <main>
    <div id="main-list">{main_html}
    </div>
    <details class="zero-group" id="zero-group">
      <summary>IAs with no foresight mentions ({len(without_mentions)})</summary>
      {zero_html}
    </details>
  </main>
</div>
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
