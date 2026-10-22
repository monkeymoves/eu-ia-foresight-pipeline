"""Combine data/ai_drafts/chunk*.json + topics.json -> data/ai_drafts.json.

Validates coverage against mentions.json and the manifest before writing:
every foresight-mentioning IA classified, every mention id covered, every
topic label drawn from the taxonomy. See docs/adr/0001: these are drafts
for human review, so provenance and completeness matter more than speed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config

DRAFTS_DIR = config.DATA_DIR / "ai_drafts"
COMBINED_PATH = config.DATA_DIR / "ai_drafts.json"


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    mentions = load(config.MENTIONS_PATH)
    manifest = load(config.MANIFEST_PATH)

    combined_ias: dict = {}
    for chunk_path in sorted(DRAFTS_DIR.glob("chunk[0-9].json")):
        chunk = load(chunk_path)
        for reference, entry in chunk.get("ias", {}).items():
            if reference in combined_ias:
                print(f"error: {reference} classified in more than one chunk")
                return 1
            combined_ias[reference] = entry

    topics_path = DRAFTS_DIR / "topics.json"
    topics = load(topics_path) if topics_path.exists() else {}
    taxonomy = topics.get("taxonomy", [])
    topic_map = topics.get("topics", {})

    errors: list[str] = []

    expected_refs = {
        r for r, ia in mentions["ias"].items() if ia["foresight_mention"]
    }
    missing = expected_refs - set(combined_ias)
    extra = set(combined_ias) - expected_refs
    if missing:
        errors.append(f"unclassified IAs: {sorted(missing)}")
    if extra:
        errors.append(f"classified but not foresight-mentioning: {sorted(extra)}")

    for reference, entry in combined_ias.items():
        expected_ids = {m["id"] for m in mentions["ias"][reference]["mentions"]}
        got_ids = set(entry.get("mention_verdicts", {}))
        if expected_ids != got_ids:
            errors.append(
                f"{reference}: mention id mismatch "
                f"(missing {sorted(expected_ids - got_ids)}, "
                f"unexpected {sorted(got_ids - expected_ids)})"
            )
        for mention_id, verdict in entry.get("mention_verdicts", {}).items():
            if verdict.get("verdict") not in config.KIND_VALUES:
                errors.append(f"{mention_id}: bad verdict {verdict.get('verdict')!r}")
        if entry.get("kind") not in config.KIND_VALUES:
            errors.append(f"{reference}: bad kind {entry.get('kind')!r}")
        if entry.get("material_influence") not in config.INFLUENCE_VALUES:
            errors.append(
                f"{reference}: bad material_influence "
                f"{entry.get('material_influence')!r}"
            )
        verdicts = [
            v["verdict"] for v in entry.get("mention_verdicts", {}).values()
        ]
        rollup = "embedded" if "embedded" in verdicts else "contextual"
        if entry.get("kind") != rollup:
            errors.append(f"{reference}: kind {entry.get('kind')!r} != rollup {rollup!r}")

    if topic_map:
        manifest_refs = set(manifest["ias"])
        if set(topic_map) != manifest_refs:
            errors.append(
                f"topics cover {len(topic_map)} IAs, manifest has {len(manifest_refs)}"
            )
        bad_labels = {l for l in topic_map.values() if l not in taxonomy}
        if bad_labels:
            errors.append(f"topic labels outside taxonomy: {sorted(bad_labels)}")

    if errors:
        for e in errors:
            print(f"error: {e}")
        return 1

    combined = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": (
            "AI drafts produced in Claude sessions using "
            "prompts/classification-prompt.md; human review required "
            "(docs/adr/0001)"
        ),
        "provenance": config.AI_DRAFT_PROVENANCE,
        "taxonomy": taxonomy,
        "topics": topic_map,
        "ias": combined_ias,
    }
    with open(COMBINED_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=1, ensure_ascii=False)

    n_mentions = sum(len(e["mention_verdicts"]) for e in combined_ias.values())
    n_embedded = sum(1 for e in combined_ias.values() if e["kind"] == "embedded")
    print(
        f"wrote {COMBINED_PATH}: {len(combined_ias)} IAs "
        f"({n_embedded} embedded), {n_mentions} mention verdicts, "
        f"{len(taxonomy)} topic labels"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
