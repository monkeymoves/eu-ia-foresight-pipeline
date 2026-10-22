"""Shared constants for the foresight pipeline. See SPEC.md for contracts."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
MD_DIR = DATA_DIR / "md"
DOCX_DIR = DATA_DIR / "docx"
OUT_DIR = DATA_DIR / "out"
MANIFEST_PATH = DATA_DIR / "manifest.json"
MENTIONS_PATH = DATA_DIR / "mentions.json"

API_BASE = "https://ec.europa.eu/transparency/documents-register/api"
SEARCH_URL = f"{API_BASE}/groupSearch"
FILE_URL = f"{API_BASE}/files/{{reference}}"  # + ?ersIds=<ers_id>
DATE_FROM = "2022-01-31"
PAGE_SIZE = 20

REQUEST_DELAY_SECONDS = 1.5
MAX_RETRIES = 3
USER_AGENT = (
    "eu-ia-foresight-pipeline (academic research; "
    "+https://github.com/monkeymoves/eu-ia-foresight-pipeline)"
)

PRIMARY_TERM = "foresight"
RELATED_TERMS = [
    "horizon scanning",
    "megatrend",
    "scenario planning",
    "delphi",
    "backcasting",
    "futures literacy",
]

EXCERPT_TARGET_WORDS = 400

SCOPE_VALUES = [
    "new regulation",
    "amending regulation",
    "new directive",
    "amending directive",
    "council directive",
    "decision",
    "multiple acts",
    "other",
]

KIND_VALUES = ["embedded", "contextual"]
INFLUENCE_VALUES = ["yes", "no", "unclear"]

# Provenance of the delivered AI draft layer (docs/adr/0001). Written into
# ai_drafts.json and the bundle README so a methods section can state which
# model produced the drafts, when, and from which prompt version. Update
# this block whenever the drafts are regenerated.
AI_DRAFT_PROVENANCE = {
    "model": "Claude Fable 5",
    "model_id": "claude-fable-5",
    "produced_on": "2026-07-31",
    "run_via": "Claude Code sessions under a Claude subscription (no API calls)",
    "prompt": "prompts/classification-prompt.md",
    "prompt_commit": "c1fc224",
}


def ref_safe(reference: str) -> str:
    """SWD(2026)616 -> SWD_2026_616. One-way; the manifest keeps the mapping."""
    return (
        reference.replace("(", "_").replace(")", "_").replace("/", "_").strip("_").replace("__", "_")
    )

# Public hosting of the data bundle (GitHub Pages). Spreadsheet links use
# this base so they work from Google Sheets, Excel, and anywhere else.
PUBLIC_BASE_URL = "https://monkeymoves.github.io/eu-ia-foresight-data"

# Browsable folder listings for the hosted spreadsheet (GitHub repo tree;
# GitHub Pages itself has no directory listings).
REPO_TREE_URL = "https://github.com/monkeymoves/eu-ia-foresight-data/tree/main"
