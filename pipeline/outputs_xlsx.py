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


# --- Workbook building --------------------------------------------------------

IA_HEADER_BASE = [
    "Reference",
    "Title",
    "Date",
    "Responsible service",
    "Topic",
    "Scope",
    "Foresight mention",
    "Mention count",
    "Kind of foresight (final)",
    "AI draft: kind",
    "AI draft: methods",
    "AI draft: material influence",
    "AI draft: how",
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


def build_workbook(manifest: dict, mentions: dict) -> Workbook:
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

        row = [
            reference,
            ia.get("title", ""),
            ia.get("date", ""),
            ia.get("responsible_department", ""),
            "",  # Topic - filled later against controlled vocabulary
            derive_scope(ia.get("title", "")),
            "YES" if foresight_mention else "no",
            len(mention_list),
            "",  # Kind of foresight (final) - human
            "",  # AI draft: kind
            "",  # AI draft: methods
            "",  # AI draft: material influence
            "",  # AI draft: how
            "",  # Other / notes
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

        for mention in mention_list:
            ws_mentions.append(
                [
                    reference,
                    mention.get("part"),
                    mention.get("page"),
                    mention.get("page_label", ""),
                    mention.get("excerpt", ""),
                    "yes" if mention.get("in_reference_section") else "no",
                    "",  # AI draft verdict
                    "",  # AI draft justification
                    "",  # Human verdict
                    "",  # Human notes
                ]
            )

    # --- IAs sheet formatting ---
    ia_last_row = ws_ia.max_row
    kind_col = "I"  # Kind of foresight (final)
    ai_kind_col = "J"  # AI draft: kind
    influence_col = "L"  # AI draft: material influence
    _add_list_validation(ws_ia, kind_col, config.KIND_VALUES, ia_last_row)
    _add_list_validation(ws_ia, ai_kind_col, config.KIND_VALUES, ia_last_row)
    _add_list_validation(ws_ia, influence_col, config.INFLUENCE_VALUES, ia_last_row)

    _set_col_widths(
        ws_ia,
        {
            "A": 18,
            "B": 60,
            "C": 12,
            "D": 14,
            "E": 16,
            "F": 18,
            "G": 14,
            "H": 12,
            "I": 20,
            "J": 16,
            "K": 30,
            "L": 20,
            "M": 30,
            "N": 30,
        },
    )
    # related-term columns + tail columns get a plain default-ish width
    from openpyxl.utils import get_column_letter

    n_related = len(related_terms)
    tail_start = 15 + n_related  # 1-based index of first tail column
    for i in range(n_related):
        _set_col_widths(ws_ia, {get_column_letter(15 + i): 16})
    tail_widths = [10, 22, 22, 22, 20]
    for i, w in enumerate(tail_widths):
        _set_col_widths(ws_ia, {get_column_letter(tail_start + i): w})

    # --- Mentions sheet formatting ---
    m_last_row = ws_mentions.max_row
    _add_list_validation(ws_mentions, "I", config.KIND_VALUES, m_last_row)  # Human verdict
    _add_list_validation(ws_mentions, "G", config.KIND_VALUES, m_last_row)  # AI draft verdict

    _set_col_widths(
        ws_mentions,
        {
            "A": 18,
            "B": 8,
            "C": 8,
            "D": 12,
            "E": 90,
            "F": 16,
            "G": 16,
            "H": 40,
            "I": 16,
            "J": 40,
        },
    )
    excerpt_alignment = Alignment(wrap_text=True, vertical="top")
    for row_cells in ws_mentions.iter_rows(
        min_row=2, max_row=m_last_row, min_col=5, max_col=5
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
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    if not args.mentions.exists():
        print(f"error: mentions not found: {args.mentions}", file=sys.stderr)
        return 1

    manifest = load_json(args.manifest)
    mentions = load_json(args.mentions)

    wb = build_workbook(manifest, mentions)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)

    n_ias = len(manifest.get("ias", {}))
    n_mentions = wb["Mentions"].max_row - 1
    print(f"wrote {args.out} ({n_ias} IAs, {n_mentions} mentions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
