"""Harvest EU register impact assessments: search -> manifest.json + PDF parts.

Contract: SPEC.md. Sequential requests only, minimum delay between them,
exponential backoff on 429/5xx/timeouts. Idempotent: a part whose PDF exists
with a recorded sha256 is skipped; new register entries are appended with
first_seen.

Usage:
    python pipeline/harvest.py [--limit N] [--redownload]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import (  # noqa: E402
    DATA_DIR,
    DATE_FROM,
    FILE_URL,
    MANIFEST_PATH,
    MAX_RETRIES,
    PAGE_SIZE,
    PDF_DIR,
    REQUEST_DELAY_SECONDS,
    SEARCH_URL,
    USER_AGENT,
    ref_safe,
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Content-Type": "application/json",
}

_last_request_at = 0.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _wait_turn() -> None:
    """Enforce the minimum gap between two register requests."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)
    _last_request_at = time.monotonic()


def request_with_backoff(method: str, url: str, **kwargs) -> requests.Response:
    """One sequential, rate-limited request with exponential backoff retries."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        if attempt:
            backoff = REQUEST_DELAY_SECONDS * (2**attempt)
            print(f"    retry {attempt}/{MAX_RETRIES - 1} in {backoff:.1f}s ({last_error})")
            time.sleep(backoff)
        _wait_turn()
        try:
            response = requests.request(
                method, url, headers=HEADERS, timeout=120, **kwargs
            )
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        if response.status_code == 429 or response.status_code >= 500:
            last_error = f"HTTP {response.status_code}"
            continue
        response.raise_for_status()
        return response
    raise RuntimeError(f"{method} {url} failed after {MAX_RETRIES} attempts: {last_error}")


def search_page(page: int) -> dict:
    """One page of the groupSearch result set. Pages are 1-based."""
    payload = {
        # categories/departments must be present (empty = no filter): the
        # service answers 503 for a query object missing them.
        "categories": [],
        "departments": [],
        "types": ["IMPACT_ASSESS"],
        "language": "en",
        "keywordsSearchType": "AT_LEAST_ONE",
        "target": "TITLE_AND_CONTENT",
        "sortBy": "DOCUMENT_DATE_DESC",
        "isRegular": True,
        "keywords": "",
        "reference": "",
        "page": page,
        "dateFrom": f"{DATE_FROM}T00:00:00.000Z",
    }
    url = f"{SEARCH_URL}?size={PAGE_SIZE}&page={page}"
    response = request_with_backoff("POST", url, json=payload)
    return response.json()


def iter_register_documents(limit: int | None = None):
    """Yield register entries, paging until totalResults is exhausted."""
    page = 1
    seen = 0
    total = None
    while True:
        data = search_page(page)
        if total is None:
            total = data.get("totalResults")
            print(f"register reports {total} impact assessments since {DATE_FROM}")
        documents = data.get("documents") or []
        if not documents:
            return
        for document in documents:
            yield document
            seen += 1
            if limit is not None and seen >= limit:
                return
        page += 1
        if total is not None and seen >= total:
            return


def english_version(attachment: dict) -> dict | None:
    """The `en` linguistic version of an attachment, if the register has one."""
    versions = attachment.get("linguisticVersions") or {}
    if isinstance(versions, dict):
        for key, value in versions.items():
            if str(key).lower() == "en" and value:
                return value if isinstance(value, dict) else None
    elif isinstance(versions, list):
        for value in versions:
            if isinstance(value, dict) and str(value.get("language", "")).lower() == "en":
                return value
    return None


def document_title(document: dict) -> str:
    """The register leaves document.title null; the title is on the en version."""
    if document.get("title"):
        return document["title"]
    attachments = sorted(
        document.get("attachments") or [],
        key=lambda a: (not a.get("main", False), a.get("part") or 0),
    )
    for attachment in attachments:
        version = english_version(attachment)
        if version and version.get("title"):
            return version["title"]
    for attachment in attachments:
        if attachment.get("title"):
            return attachment["title"]
    return ""


def available_languages(attachment: dict) -> list[str]:
    versions = attachment.get("linguisticVersions") or {}
    if isinstance(versions, dict):
        return sorted(str(key).lower() for key in versions)
    if isinstance(versions, list):
        return sorted(
            str(v.get("language", "")).lower() for v in versions if isinstance(v, dict)
        )
    return []


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest.setdefault("search", {})
        manifest.setdefault("ias", {})
        return manifest
    return {"search": {"date_from": DATE_FROM, "last_run": None}, "ias": {}}


def save_manifest(manifest: dict) -> None:
    """Write atomically: a half-written manifest would lose the download record."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MANIFEST_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(MANIFEST_PATH)


def add_flag(entry: dict, flag: str) -> None:
    if flag not in entry["flags"]:
        entry["flags"].append(flag)


def upsert_ia(manifest: dict, document: dict) -> dict:
    """Create or refresh the manifest entry for one register document."""
    reference = document["reference"]
    entry = manifest["ias"].get(reference)
    if entry is None:
        entry = {
            "ref_safe": ref_safe(reference),
            "title": "",
            "date": "",
            "responsible_department": "",
            "detail_url": "",
            "first_seen": now_iso(),
            "flags": [],
            "parts": [],
        }
        manifest["ias"][reference] = entry
    entry["ref_safe"] = ref_safe(reference)
    entry["title"] = document_title(document) or entry["title"]
    entry["date"] = (document.get("date") or entry["date"] or "")[:10]
    entry["responsible_department"] = (
        document.get("responsibleDepartment") or entry["responsible_department"] or ""
    )
    entry["detail_url"] = document.get("url") or entry["detail_url"] or (
        f"https://ec.europa.eu/transparency/documents-register/detail?ref={reference}"
    )
    return entry


def download_part(reference: str, ers_id: str, destination: Path) -> None:
    url = FILE_URL.format(reference=reference)
    response = request_with_backoff("GET", url, params={"ersIds": ers_id})
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError(f"{reference} ersId {ers_id}: {url} did not return a PDF")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Write via a temp file so an interrupted download never looks complete.
    tmp_path = destination.with_suffix(".pdf.tmp")
    tmp_path.write_bytes(response.content)
    tmp_path.replace(destination)


def harvest_ia(manifest: dict, document: dict, redownload: bool) -> tuple[int, int]:
    """Download every English part of one IA. Returns (downloaded, skipped)."""
    reference = document["reference"]
    entry = upsert_ia(manifest, document)
    parts_by_number = {part["part"]: part for part in entry["parts"]}
    downloaded = skipped = 0

    attachments = document.get("attachments") or []
    missing_english = []
    for attachment in attachments:
        part_number = attachment.get("part")
        if part_number is None:
            continue
        part_number = int(part_number)
        version = english_version(attachment)
        if version is None:
            missing_english.append((part_number, available_languages(attachment)))
            continue

        pdf_relative = f"pdfs/{entry['ref_safe']}/part{part_number}.pdf"
        pdf_path = DATA_DIR / pdf_relative
        part = parts_by_number.get(part_number)
        if part is None:
            part = {"part": part_number}
            parts_by_number[part_number] = part
        part["ers_id"] = version.get("ersId") or version.get("ers_id") or ""
        part["attachment_id"] = version.get("id") or attachment.get("id")
        part["title"] = version.get("title") or attachment.get("title") or ""
        part["pdf"] = pdf_relative

        already_have = pdf_path.exists() and part.get("sha256")
        if already_have and not redownload:
            skipped += 1
            continue

        print(f"  part {part_number}: downloading {pdf_relative}")
        try:
            download_part(reference, part["ers_id"], pdf_path)
        except RuntimeError as error:
            # Register-side failure for this file (e.g. persistent 503).
            # Flag it and carry on; the next run retries because no sha256
            # was recorded.
            print(f"  part {part_number}: download failed, flagged ({error})")
            add_flag(entry, f"download_failed_part{part_number}")
            pdf_path.unlink(missing_ok=True)
            continue
        part["sha256"] = sha256_of(pdf_path)
        part["downloaded_at"] = now_iso()
        part.setdefault("pages", None)
        entry["flags"] = [
            flag for flag in entry.get("flags", [])
            if flag != f"download_failed_part{part_number}"
        ]
        downloaded += 1

    if missing_english:
        add_flag(entry, "no_english_version")
        entry["no_english_parts"] = [
            {"part": part_number, "available_languages": languages}
            for part_number, languages in sorted(missing_english)
        ]
        print(
            f"  no English version for part(s) "
            f"{', '.join(str(p) for p, _ in sorted(missing_english))}; skipped"
        )
    if not attachments:
        add_flag(entry, "no_attachments")

    entry["parts"] = [parts_by_number[number] for number in sorted(parts_by_number)]
    return downloaded, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None,
        help="process only the first N register entries (for testing)",
    )
    parser.add_argument(
        "--redownload", action="store_true",
        help="re-fetch parts already recorded in the manifest",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    manifest["search"]["date_from"] = DATE_FROM

    ias = downloaded = skipped = 0
    for document in iter_register_documents(limit=args.limit):
        reference = document.get("reference")
        if not reference:
            continue
        is_new = reference not in manifest["ias"]
        print(f"{reference} ({'new' if is_new else 'known'}) {document.get('date', '')[:10]}")
        got, kept = harvest_ia(manifest, document, redownload=args.redownload)
        downloaded += got
        skipped += kept
        ias += 1
        # Persist after every IA so an interrupted run loses nothing.
        manifest["search"]["last_run"] = now_iso()
        save_manifest(manifest)

    print(
        f"done: {ias} impact assessments, {downloaded} parts downloaded, "
        f"{skipped} already present -> {MANIFEST_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
