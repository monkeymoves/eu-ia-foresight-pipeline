"""Convert downloaded PDF parts to page-marked markdown with PyMuPDF.

Contract: SPEC.md. Each PDF page's text is preceded by a marker line
`<!-- page:N -->`, or `<!-- page:N label:"37" -->` when the PDF carries a
printed page label. The markers are the provenance backbone for detect.py,
review_html.py and the human workflow.

Usage:
    python pipeline/extract.py [--limit N] [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MD_DIR  # noqa: E402
from pipeline.harvest import load_manifest, now_iso, save_manifest  # noqa: E402


def page_marker(page: fitz.Page) -> str:
    """`<!-- page:N -->`, plus the printed label when the PDF defines one."""
    number = page.number + 1
    try:
        label = page.get_label()
    except Exception:
        label = ""
    if label:
        escaped = label.replace('"', "'")
        return f'<!-- page:{number} label:"{escaped}" -->'
    return f"<!-- page:{number} -->"


def pdf_to_markdown(pdf_path: Path, md_path: Path) -> int:
    """Write one page-marked .md. Returns the page count."""
    chunks = []
    with fitz.open(pdf_path) as document:
        for page in document:
            chunks.append(page_marker(page))
            text = page.get_text("text").strip("\n")
            if text:
                chunks.append(text)
            chunks.append("")
        page_count = document.page_count
    md_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = md_path.with_suffix(".md.tmp")
    tmp_path.write_text("\n".join(chunks), encoding="utf-8")
    tmp_path.replace(md_path)
    return page_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="process only the first N impact assessments")
    parser.add_argument("--force", action="store_true",
                        help="re-extract parts whose markdown already exists")
    args = parser.parse_args()

    manifest = load_manifest()
    if not manifest["ias"]:
        print("manifest is empty; run harvest.py first")
        return 1

    MD_DIR.mkdir(parents=True, exist_ok=True)
    extracted = skipped = missing = 0

    for index, (reference, entry) in enumerate(manifest["ias"].items()):
        if args.limit is not None and index >= args.limit:
            break
        for part in entry.get("parts", []):
            if not part.get("pdf"):
                continue
            pdf_path = DATA_DIR / part["pdf"]
            md_relative = f"md/{entry['ref_safe']}/part{part['part']}.md"
            md_path = DATA_DIR / md_relative
            part["md"] = md_relative

            if not pdf_path.exists():
                print(f"{reference} part {part['part']}: PDF missing, skipped")
                missing += 1
                continue
            if md_path.exists() and not args.force and part.get("pages"):
                skipped += 1
                continue

            print(f"{reference} part {part['part']}: extracting {md_relative}")
            part["pages"] = pdf_to_markdown(pdf_path, md_path)
            part["extracted_at"] = now_iso()
            extracted += 1
        save_manifest(manifest)

    print(f"done: {extracted} parts extracted, {skipped} already present, "
          f"{missing} PDFs missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
