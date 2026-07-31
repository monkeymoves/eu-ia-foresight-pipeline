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


def ref_safe(reference: str) -> str:
    """SWD(2026)616 -> SWD_2026_616. One-way; the manifest keeps the mapping."""
    return (
        reference.replace("(", "_").replace(")", "_").replace("/", "_").strip("_").replace("__", "_")
    )
