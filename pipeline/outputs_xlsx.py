"""manifest.json + mentions.json -> data/out/dataset.xlsx

See SPEC.md ("data/out/dataset.xlsx") for the exact sheet/column contract.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

from pipeline import config

# --- Scope heuristic -------------------------------------------------------

_COUNCIL_DIRECTIVE_RE = re.compile(r"\bcouncil directive\b", re.IGNORECASE)
_DIRECTIVE_RE = re.compile(r"\bdirective\b", re.IGNORECASE)
_REGULATION_RE = re.compile(r"\bregulation\b", re.IGNORECASE)
_DECISION_RE = re.compile(r"\bdecision\b", re.IGNORECASE)
_AMENDING_RE = re.compile(r"\bamending\b", re.IGNORECASE)


def derive_scope(title: str) -> str:
    """Best-effort enum classification of the legal act from the IA title.

    Regex over the title's act phrases; if more than one distinct act type
    is present the result is "multiple acts". See SPEC.md and CONTEXT.md
    ("Scope") - definition to be confirmed with the research team.
    """
    types: set[str] = set()
    if _COUNCIL_DIRECTIVE_RE.search(title):
        types.add("council directive")
    elif _DIRECTIVE_RE.search(title):
        types.add("directive")
    if _REGULATION_RE.search(title):
        types.add("regulation")
    if _DECISION_RE.search(title):
        types.add("decision")

    if len(types) > 1:
        return "multiple acts"
    if not types:
        return "other"

    only = next(iter(types))
    amending = bool(_AMENDING_RE.search(title))
    if only == "council directive":
        return "council directive"
    if only == "decision":
        return "decision"
    if only == "directive":
        return "amending directive" if amending else "new directive"
    if only == "regulation":
        return "amending regulation" if amending else "new regulation"
    return "other"  # pragma: no cover - unreachable, kept for safety


# --- Data loading ------------------------------------------------------------


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def link_stub_name(mention_id: str) -> str:
    """Mention id -> safe redirect filename, e.g. SWD(2026)616#p2-14-1 -> SWD_2026_616_p2-14-1.html"""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in mention_id)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") + ".html"


def write_link_stubs(manifest: dict, mentions: dict, links_dir: Path) -> int:
    """One tiny redirect page per mention: Excel opens it (no fragment needed),
    the browser forwards to the PDF with #page= intact. Keeps jump-to-page
    working from spreadsheet hyperlinks, which strip URL fragments on files."""
    links_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for reference, ia in mentions.get("ias", {}).items():
        ref_safe = manifest["ias"][reference].get("ref_safe", config.ref_safe(reference))
        for mention in ia.get("mentions", []):
            target = f"../pdfs/{ref_safe}/part{mention['part']}.pdf#page={mention['page']}"
            stub = links_dir / link_stub_name(mention["id"])
            stub.write_text(
                "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                f"<meta http-equiv=\"refresh\" content=\"0;url={target}\">"
                f"<script>location.replace(\"{target}\");</script>"
                f"<title>{reference} p.{mention['page']}</title></head>"
                f"<body><a href=\"{target}\">{reference}, part {mention['part']}, "
                f"page {mention['page']}</a></body></html>",
                encoding="utf-8",
            )
            written += 1
    return written


def _draft_justification(verdict: dict) -> str:
    quote = (verdict.get("evidence_quote") or "").strip()
    why = (verdict.get("justification") or "").strip()
    if quote and why:
        return f'"{quote}" : {why}'
    return why or quote


# --- Workbook building --------------------------------------------------------

IA_HEADER_BASE = [
    "Reference",
    "Title",
    "Date",
    "Responsible service",
    "Topic",
    "AI draft: topic",
    "Scope",
    "Foresight mention",
    "Mention count",
    "Kind of foresight (final)",
    "AI draft: kind",
    "AI draft: methods",
    "AI draft: material influence",
    "AI draft: how",
    "AI draft: notes",
    "Other / notes",
]
IA_HEADER_TAIL = [
    "Parts",
    "PDF folder",
    "Markdown folder",
    "Docx folder",
    "Flags",
]

MENTION_HEADER = [
    "Reference",
    "Part",
    "Page",
    "Page label",
    "Open PDF at page",
    "Excerpt",
    "In reference section",
    "AI draft verdict",
    "AI draft justification",
    "Human verdict",
    "Human notes",
]


def _set_col_widths(ws, widths: dict[str, int]) -> None:
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


def _add_list_validation(ws, col_letter: str, values: list[str], last_row: int) -> None:
    if last_row < 2:
        return
    dv = DataValidation(
        type="list",
        formula1='"{}"'.format(",".join(values)),
        allow_blank=True,
        showDropDown=False,  # False = show the dropdown arrow (openpyxl quirk)
    )
    ws.add_data_validation(dv)
    dv.add(f"{col_letter}2:{col_letter}{last_row}")


def build_workbook(manifest: dict, mentions: dict, drafts: dict | None = None) -> Workbook:
    drafts = drafts or {}
    draft_ias = drafts.get("ias", {})
    draft_topics = drafts.get("topics", {})
    related_terms = mentions.get("related_terms") or list(config.RELATED_TERMS)
    ia_header = IA_HEADER_BASE + [f"Related: {t}" for t in related_terms] + IA_HEADER_TAIL

    ias = manifest.get("ias", {})
    mention_ias = mentions.get("ias", {})

    # order by date descending
    ordered_refs = sorted(
        ias.keys(), key=lambda r: ias[r].get("date", ""), reverse=True
    )

    wb = Workbook()
    ws_ia = wb.active
    ws_ia.title = "IAs"
    ws_ia.append(ia_header)
    for cell in ws_ia[1]:
        cell.font = Font(bold=True)
    ws_ia.freeze_panes = "A2"

    ws_mentions = wb.create_sheet("Mentions")
    ws_mentions.append(MENTION_HEADER)
    for cell in ws_mentions[1]:
        cell.font = Font(bold=True)
    ws_mentions.freeze_panes = "A2"

    for reference in ordered_refs:
        ia = ias[reference]
        ref_safe = ia.get("ref_safe", config.ref_safe(reference))
        m = mention_ias.get(reference, {})
        mention_list = m.get("mentions", [])
        foresight_mention = m.get("foresight_mention", bool(mention_list))
        related_counts = m.get("related_term_counts", {})
        flags = ia.get("flags", [])
        parts = ia.get("parts", [])
        draft = draft_ias.get(reference, {})
        draft_verdicts = draft.get("mention_verdicts", {})

        row = [
            reference,
            ia.get("title", ""),
            ia.get("date", ""),
            ia.get("responsible_department", ""),
            "",  # Topic - final, human-owned against controlled vocabulary
            draft_topics.get(reference, ""),
            derive_scope(ia.get("title", "")),
            "YES" if foresight_mention else "no",
            len(mention_list),
            "",  # Kind of foresight (final) - human
            draft.get("kind", ""),
            "; ".join(draft.get("methods", [])),
            draft.get("material_influence", ""),
            draft.get("influence_how", ""),
            draft.get("notes", ""),
            "",  # Other / notes - human-owned
        ]
        row += [related_counts.get(t, 0) for t in related_terms]
        row += [
            len(parts),
            f"pdfs/{ref_safe}/",
            f"md/{ref_safe}/",
            f"docx/{ref_safe}/",
            ", ".join(flags),
        ]
        ws_ia.append(row)
        ref_cell = ws_ia.cell(row=ws_ia.max_row, column=1)
        if ia.get("detail_url"):
            ref_cell.hyperlink = ia["detail_url"]
            ref_cell.font = Font(color="0B5FA5", underline="single")
        pdf_cell = ws_ia.cell(
            row=ws_ia.max_row, column=ia_header.index("PDF folder") + 1
        )
        pdf_cell.hyperlink = f"../pdfs/{ref_safe}/"
        pdf_cell.font = Font(color="0B5FA5", underline="single")

        for mention in mention_list:
            ws_mentions.append(
                [
                    reference,
                    mention.get("part"),
                    mention.get("page"),
                    mention.get("page_label", ""),
                    f"p.{mention.get('page')}",
                    mention.get("excerpt", ""),
                    "yes" if mention.get("in_reference_section") else "no",
                    draft_verdicts.get(mention.get("id"), {}).get("verdict", ""),
                    _draft_justification(draft_verdicts.get(mention.get("id"), {})),
                    "",  # Human verdict
                    "",  # Human notes
                ]
            )
            link_cell = ws_mentions.cell(
                row=ws_mentions.max_row,
                column=MENTION_HEADER.index("Open PDF at page") + 1,
            )
            link_cell.hyperlink = f"../links/{link_stub_name(mention['id'])}"
            link_cell.font = Font(color="0B5FA5", underline="single")

    # --- IAs sheet formatting ---
    from openpyxl.utils import get_column_letter as _cl

    def col(header_name: str) -> str:
        return _cl(ia_header.index(header_name) + 1)

    ia_last_row = ws_ia.max_row
    _add_list_validation(ws_ia, col("Kind of foresight (final)"), config.KIND_VALUES, ia_last_row)
    _add_list_validation(ws_ia, col("AI draft: kind"), config.KIND_VALUES, ia_last_row)
    _add_list_validation(ws_ia, col("AI draft: material influence"), config.INFLUENCE_VALUES, ia_last_row)

    _set_col_widths(
        ws_ia,
        {
            "A": 18,
            "B": 60,
            "C": 12,
            "D": 14,
            "E": 16,
            "F": 16,
            "G": 18,
            "H": 14,
            "I": 12,
            "J": 20,
            "K": 16,
            "L": 30,
            "M": 20,
            "N": 30,
            "O": 30,
        },
    )
    # related-term columns + tail columns get a plain default-ish width
    from openpyxl.utils import get_column_letter

    n_related = len(related_terms)
    tail_start = 17 + n_related  # 1-based index of first tail column
    for i in range(n_related):
        _set_col_widths(ws_ia, {get_column_letter(17 + i): 16})
    tail_widths = [10, 22, 22, 22, 20]
    for i, w in enumerate(tail_widths):
        _set_col_widths(ws_ia, {get_column_letter(tail_start + i): w})

    # --- Mentions sheet formatting ---
    m_last_row = ws_mentions.max_row

    def mcol(header_name: str) -> str:
        return _cl(MENTION_HEADER.index(header_name) + 1)

    _add_list_validation(ws_mentions, mcol("Human verdict"), config.KIND_VALUES, m_last_row)
    _add_list_validation(ws_mentions, mcol("AI draft verdict"), config.KIND_VALUES, m_last_row)

    _set_col_widths(
        ws_mentions,
        {
            "A": 18,
            "B": 8,
            "C": 8,
            "D": 12,
            "E": 14,
            "F": 90,
            "G": 16,
            "H": 16,
            "I": 40,
            "J": 16,
            "K": 40,
        },
    )
    excerpt_alignment = Alignment(wrap_text=True, vertical="top")
    excerpt_col = MENTION_HEADER.index("Excerpt") + 1
    for row_cells in ws_mentions.iter_rows(
        min_row=2, max_row=m_last_row, min_col=excerpt_col, max_col=excerpt_col
    ):
        for cell in row_cells:
            cell.alignment = excerpt_alignment

    return wb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=config.MANIFEST_PATH)
    parser.add_argument("--mentions", type=Path, default=config.MENTIONS_PATH)
    parser.add_argument(
        "--out", type=Path, default=config.OUT_DIR / "dataset.xlsx"
    )
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

    wb = build_workbook(manifest, mentions, drafts)
    n_stubs = write_link_stubs(manifest, mentions, config.DATA_DIR / "links")
    print(f"wrote {n_stubs} redirect stubs to data/links/")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)

    n_ias = len(manifest.get("ias", {}))
    n_mentions = wb["Mentions"].max_row - 1
    print(f"wrote {args.out} ({n_ias} IAs, {n_mentions} mentions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
