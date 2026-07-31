"""Run the full pipeline in order: harvest -> extract -> detect -> convert_docx
-> outputs_xlsx -> review_html (-> write_bundle_readme).

Each step runs as its own subprocess (so a crash in one step can't corrupt
the interpreter state of another) and the run stops at the first failure
with a clear message. See SPEC.md "Definition of done".
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent

# (script name, extra CLI args, description)
STEPS: list[tuple[str, list[str]]] = [
    ("harvest.py", []),  # --limit passed through, if given
    ("extract.py", []),
    ("detect.py", []),
    ("convert_docx.py", []),
    ("outputs_xlsx.py", []),
    ("review_html.py", []),
    ("write_bundle_readme.py", []),
]


def run_step(script: str, extra_args: list[str]) -> int:
    script_path = PIPELINE_DIR / script
    cmd = [sys.executable, str(script_path)] + extra_args
    print(f"\n=== running {script} ===", flush=True)
    result = subprocess.run(cmd)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="passed through to harvest.py (limit number of IAs harvested)",
    )
    args = parser.parse_args()

    for script, extra_args in STEPS:
        step_args = list(extra_args)
        if script == "harvest.py" and args.limit is not None:
            step_args += ["--limit", str(args.limit)]

        script_path = PIPELINE_DIR / script
        if not script_path.exists():
            print(f"\nstopping: {script} not found at {script_path}", file=sys.stderr)
            return 1

        rc = run_step(script, step_args)
        if rc != 0:
            print(
                f"\nstopping: {script} failed with exit code {rc}. "
                "Fix the error above and re-run pipeline/run_all.py "
                "(steps are idempotent, so completed work is not repeated).",
                file=sys.stderr,
            )
            return rc

    print("\n=== pipeline complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
