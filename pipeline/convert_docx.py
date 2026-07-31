"""data/md/<ref_safe>/part<N>.md -> data/docx/<ref_safe>/part<N>.docx via pandoc.

Docx files are a convenience, not pipeline-critical (see SPEC.md "Non-goals").
If pandoc is not installed, print one clear instruction line and exit 0 so
the rest of the pipeline (run_all.py) is not blocked. Idempotent: an
existing docx is left alone unless --force is passed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config

PANDOC_INSTALL_HINT = (
    "pandoc not found on PATH - install it (e.g. 'brew install pandoc' on macOS, "
    "or see https://pandoc.org/installing.html) to enable docx conversion; "
    "skipping docx conversion for now."
)


def find_md_files(md_dir: Path) -> list[Path]:
    if not md_dir.exists():
        return []
    return sorted(md_dir.glob("*/part*.md"))


def convert_one(pandoc: str, md_path: Path, docx_path: Path) -> None:
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        # markdown-yaml_metadata_block: extracted PDF text can contain "---"
        # lines that pandoc would otherwise misread as YAML metadata.
        [pandoc, "-f", "markdown-yaml_metadata_block", str(md_path), "-o", str(docx_path)],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--md-dir", type=Path, default=config.MD_DIR)
    parser.add_argument("--docx-dir", type=Path, default=config.DOCX_DIR)
    parser.add_argument(
        "--force", action="store_true", help="re-convert even if the docx already exists"
    )
    args = parser.parse_args()

    pandoc = shutil.which("pandoc")
    if pandoc is None:
        print(PANDOC_INSTALL_HINT)
        return 0

    md_files = find_md_files(args.md_dir)
    if not md_files:
        print(f"no markdown files found under {args.md_dir}; nothing to convert")
        return 0

    converted = 0
    skipped = 0
    failed = 0
    for md_path in md_files:
        ref_safe = md_path.parent.name
        docx_path = args.docx_dir / ref_safe / (md_path.stem + ".docx")
        if docx_path.exists() and not args.force:
            skipped += 1
            continue
        try:
            convert_one(pandoc, md_path, docx_path)
            converted += 1
        except subprocess.CalledProcessError as exc:
            print(
                f"error converting {md_path} -> {docx_path}: {exc.stderr.strip()}",
                file=sys.stderr,
            )
            failed += 1

    print(f"docx conversion: {converted} converted, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
