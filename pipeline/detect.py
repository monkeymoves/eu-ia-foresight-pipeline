"""Scan page-marked markdown for foresight mentions -> data/mentions.json.

Contract: SPEC.md. Case-insensitive substring match on the primary term,
excerpt of about 400 words centred on the hit, page provenance taken from the
`<!-- page:N -->` markers written by extract.py, plus counts and locations for
the related method terms.

Usage:
    python pipeline/detect.py [--limit N]
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import (  # noqa: E402
    DATA_DIR,
    EXCERPT_TARGET_WORDS,
    MENTIONS_PATH,
    PRIMARY_TERM,
    RELATED_TERMS,
)
from pipeline.harvest import load_manifest, now_iso  # noqa: E402

PAGE_MARKER = re.compile(r'^<!--\s*page:(\d+)(?:\s+label:"([^"]*)")?\s*-->$', re.MULTILINE)
# A whole line that is nothing but a references heading, optionally numbered
# ("6.", "ANNEX 3 -", "#") and optionally punctuated. Deliberately strict: a
# sentence starting with "References to ..." must not flag the rest of a part.
REFERENCE_HEADING = re.compile(
    r"^[#\s]*(?:annex\s*[\divx]*\s*[:.\-]?\s*)?[\d.ivx)\s\-]*"
    r"(references|bibliography|endnotes)\s*[:.]?$",
    re.IGNORECASE,
)
WHITESPACE = re.compile(r"\s+")


def parse_pages(markdown: str) -> tuple[str, list[int], list[tuple[int, str]]]:
    """Split page-marked markdown into flat text plus a page lookup table.

    Returns (text, offsets, pages) where offsets[i] is the character offset in
    `text` at which pages[i] = (page_number, page_label) begins.
    """
    text_parts: list[str] = []
    offsets: list[int] = []
    pages: list[tuple[int, str]] = []
    cursor = 0
    matches = list(PAGE_MARKER.finditer(markdown))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        chunk = markdown[start:end]
        offsets.append(cursor)
        pages.append((int(match.group(1)), match.group(2) or ""))
        text_parts.append(chunk)
        cursor += len(chunk)
    if not matches:  # markdown without markers: treat the whole part as page 1
        offsets.append(0)
        pages.append((1, ""))
        text_parts.append(markdown)
    return "".join(text_parts), offsets, pages


def page_at(offset: int, offsets: list[int], pages: list[tuple[int, str]]) -> tuple[int, str]:
    index = bisect.bisect_right(offsets, offset) - 1
    return pages[max(index, 0)]


def reference_section_offset(text: str) -> int | None:
    """Offset of the last references heading in a part, or None.

    Best-effort, as SPEC.md allows: a line that is nothing but a
    references/bibliography/endnotes heading. The last such heading wins, so a
    table of contents near the front cannot flag the whole part as
    bibliography.
    """
    candidate = None
    position = 0
    for line in text.splitlines(keepends=True):
        if REFERENCE_HEADING.match(line.strip()):
            candidate = position
        position += len(line)
    return candidate


def word_spans(text: str) -> tuple[list[int], list[int]]:
    """Start and end offsets of every whitespace-delimited word, for windowing."""
    starts, ends = [], []
    for match in re.finditer(r"\S+", text):
        starts.append(match.start())
        ends.append(match.end())
    return starts, ends


def excerpt_around(
    text: str, start: int, end: int, target_words: int,
    starts: list[int], ends: list[int],
) -> str:
    """About `target_words` words centred on text[start:end], newlines collapsed."""
    if not starts:
        return ""
    hit = max(bisect.bisect_right(starts, start) - 1, 0)
    half = target_words // 2
    first = max(hit - half, 0)
    last = min(hit + half, len(starts) - 1)
    window_start = starts[first]
    window_end = ends[last]
    excerpt = WHITESPACE.sub(" ", text[window_start:window_end]).strip()
    # Where cheap, trim the partial sentences at both ends without losing the hit.
    # Leading: drop only up to the FIRST sentence end near the start of the
    # window, so the excerpt keeps its context; trailing: cut at the last one.
    hit_offset = start - window_start
    lead_limit = min(max(hit_offset - 40, 0), len(excerpt) // 4)
    boundary = min(
        (position for position in
         (excerpt.find(mark, 0, lead_limit) for mark in (". ", "? ", "! "))
         if position != -1),
        default=-1,
    )
    if boundary != -1:
        excerpt = excerpt[boundary + 2:]
        hit_offset -= boundary + 2
    tail_from = hit_offset + (end - start) + 40
    if 0 < tail_from < len(excerpt):
        tail_boundary = max(
            excerpt.rfind(". "), excerpt.rfind("? "), excerpt.rfind("! ")
        )
        if tail_boundary >= tail_from:
            excerpt = excerpt[: tail_boundary + 1]
    return excerpt.strip()


def find_all(text: str, term: str):
    """Case-insensitive substring matches; yields (start, end)."""
    for match in re.finditer(re.escape(term), text, re.IGNORECASE):
        yield match.start(), match.end()


def scan_part(reference: str, part_number: int, markdown: str) -> tuple[list[dict], dict, list[dict]]:
    """Mentions, related-term counts and related-term locations for one part."""
    text, offsets, pages = parse_pages(markdown)
    refs_offset = reference_section_offset(text)
    starts, ends = word_spans(text)
    seen_on_page: dict[int, int] = {}

    mentions = []
    for start, end in find_all(text, PRIMARY_TERM):
        page, label = page_at(start, offsets, pages)
        seen_on_page[page] = seen_on_page.get(page, 0) + 1
        mentions.append({
            "id": f"{reference}#p{part_number}-{page}-{seen_on_page[page]}",
            "part": part_number,
            "page": page,
            "page_label": label,
            "excerpt": excerpt_around(
                text, start, end, EXCERPT_TARGET_WORDS, starts, ends
            ),
            "match_text": text[start:end],
            "in_reference_section": refs_offset is not None and start >= refs_offset,
        })

    counts = {}
    locations = []
    for term in RELATED_TERMS:
        hits = list(find_all(text, term))
        counts[term] = len(hits)
        for start, _ in hits:
            page, _label = page_at(start, offsets, pages)
            locations.append({"term": term, "part": part_number, "page": page})
    return mentions, counts, locations


def scan_ia(reference: str, entry: dict) -> dict:
    mentions: list[dict] = []
    counts = {term: 0 for term in RELATED_TERMS}
    locations: list[dict] = []

    for part in entry.get("parts", []):
        md_relative = part.get("md") or f"md/{entry['ref_safe']}/part{part['part']}.md"
        md_path = DATA_DIR / md_relative
        if not md_path.exists():
            continue
        markdown = md_path.read_text(encoding="utf-8", errors="replace")
        part_mentions, part_counts, part_locations = scan_part(
            reference, part["part"], markdown
        )
        mentions.extend(part_mentions)
        for term, count in part_counts.items():
            counts[term] += count
        locations.extend(part_locations)

    return {
        "foresight_mention": bool(mentions),
        "mentions": mentions,
        "related_term_counts": counts,
        "related_term_locations": locations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="process only the first N impact assessments")
    args = parser.parse_args()

    manifest = load_manifest()
    if not manifest["ias"]:
        print("manifest is empty; run harvest.py and extract.py first")
        return 1

    results = {}
    with_mentions = total_mentions = 0
    for index, (reference, entry) in enumerate(manifest["ias"].items()):
        if args.limit is not None and index >= args.limit:
            break
        result = scan_ia(reference, entry)
        results[reference] = result
        total_mentions += len(result["mentions"])
        with_mentions += 1 if result["foresight_mention"] else 0
        print(f"{reference}: {len(result['mentions'])} mention(s)")

    payload = {
        "generated_at": now_iso(),
        "primary_term": PRIMARY_TERM,
        "related_terms": list(RELATED_TERMS),
        "ias": results,
    }
    MENTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MENTIONS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(MENTIONS_PATH)

    print(f"done: {len(results)} impact assessments, {with_mentions} with foresight, "
          f"{total_mentions} mentions -> {MENTIONS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
