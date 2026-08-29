from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.io_utils import atomic_write_json
from src.tags import (
    DEFAULT_TAG_CATALOGUE_PATH,
    TagCatalogue,
    next_tag_id,
    normalize_tag_name,
)


MANIFEST_SCHEMA_VERSION = 1
MANIFEST_SCOPE = "corpus_owner_tag_discovery"
REQUIRED_REASONING_FIELDS = (
    "relationship_contract",
    "click_through_expectation",
    "known_for_basis",
    "existing_active_review",
    "broader_tag_review",
    "facet_review",
    "dossier_metadata_review",
    "information_value",
)


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


def _strings(value: Any, path: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{path} must be a list of non-empty strings")
    cleaned = [item.strip() for item in value]
    normalized = [normalize_tag_name(item) for item in cleaned]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{path} must be unique after normalization")
    if required and not cleaned:
        raise ValueError(f"{path} must not be empty")
    return cleaned


def _dossier_records(value: Any, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError(
            f"{path} must contain at least two dossier records; individual "
            "owner research cannot create a formal candidate"
        )
    records: list[dict[str, Any]] = []
    person_ids: set[int] = set()
    dossier_paths: set[str] = set()
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_path} must be an object")
        person_id = item.get("person_id")
        if (
            not isinstance(person_id, int)
            or isinstance(person_id, bool)
            or person_id <= 0
        ):
            raise ValueError(f"{item_path}.person_id must be a positive integer")
        dossier = _text(item.get("dossier"), f"{item_path}.dossier")
        membership_basis = _text(
            item.get("membership_basis"),
            f"{item_path}.membership_basis",
        )
        normalized_dossier = dossier.casefold()
        if person_id in person_ids or normalized_dossier in dossier_paths:
            raise ValueError(
                f"{item_path} duplicates another owner or dossier record"
            )
        person_ids.add(person_id)
        dossier_paths.add(normalized_dossier)
        records.append(
            {
                "person_id": person_id,
                "dossier": dossier,
                "membership_basis": membership_basis,
            }
        )
    return records


def _existing_collision(
    catalogue: TagCatalogue,
    labels: list[str],
) -> dict[str, Any] | None:
    matching_ids: set[str] = set()
    for label in labels:
        matching_ids.update(
            catalogue.all_lookup.get(normalize_tag_name(label), set())
        )
    if not matching_ids:
        return None
    if len(matching_ids) > 1:
        detail = ", ".join(
            f"{tag_id} ({catalogue.all_tags_by_id[tag_id].name}; "
            f"{catalogue.all_tags_by_id[tag_id].status})"
            for tag_id in sorted(matching_ids)
        )
        raise ValueError(
            "candidate labels collide with multiple lifecycle records: " + detail
        )
    tag = catalogue.all_tags_by_id[next(iter(matching_ids))]
    result = {
        "id": tag.id,
        "name": tag.name,
        "status": tag.status,
    }
    if tag.status == "merged":
        canonical = catalogue.resolve(tag_id=tag.id, name=tag.name)
        result["canonical"] = {"id": canonical.id, "name": canonical.name}
    return result


def prepare_registration(
    catalogue_document: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a corpus review and queue only non-colliding formal candidates."""
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"manifest schema_version must be {MANIFEST_SCHEMA_VERSION}"
        )
    if manifest.get("scope") != MANIFEST_SCOPE:
        raise ValueError(f"manifest scope must be {MANIFEST_SCOPE!r}")
    if manifest.get("review_status") != "approved_for_candidate_queue":
        raise ValueError(
            "manifest review_status must be 'approved_for_candidate_queue'"
        )
    review_reference = _text(
        manifest.get("review_reference"),
        "manifest.review_reference",
    )
    concepts = manifest.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        raise ValueError("manifest.concepts must be a non-empty list")

    updated = deepcopy(catalogue_document)
    results: list[dict[str, Any]] = []
    manifest_names: set[str] = set()
    for index, concept in enumerate(concepts):
        path = f"manifest.concepts[{index}]"
        if not isinstance(concept, dict):
            raise ValueError(f"{path} must be an object")
        name = _text(concept.get("name"), f"{path}.name")
        normalized_name = normalize_tag_name(name)
        if normalized_name in manifest_names:
            raise ValueError(f"{path}.name duplicates another concept")
        manifest_names.add(normalized_name)
        aliases = _strings(concept.get("aliases", []), f"{path}.aliases")
        facets = _strings(
            concept.get("facets"),
            f"{path}.facets",
            required=True,
        )
        labels = [name, *aliases]
        normalized_labels = [normalize_tag_name(label) for label in labels]
        if len(normalized_labels) != len(set(normalized_labels)):
            raise ValueError(
                f"{path}.name and aliases must be unique after normalization"
            )
        reasoning = {
            field: _text(concept.get(field), f"{path}.{field}")
            for field in REQUIRED_REASONING_FIELDS
        }
        records = _dossier_records(
            concept.get("dossier_records"),
            f"{path}.dossier_records",
        )

        catalogue = TagCatalogue(updated)
        existing = _existing_collision(catalogue, labels)
        if existing is not None:
            results.append(
                {
                    "requested_name": name,
                    "outcome": "existing_lifecycle_record",
                    "existing": existing,
                    "dossier_record_count": len(records),
                    "dossier_records": records,
                    "reasoning": reasoning,
                }
            )
            continue

        tag = {
            "id": next_tag_id(updated),
            "name": name,
            "normalized_name": normalized_name,
            "aliases": aliases,
            "facets": facets,
            "status": "candidate",
            "merged_into": None,
            "lifecycle": {
                "reason": "corpus_level_taxonomy_discovery",
                "review_reference": review_reference,
                "dossier_record_count": len(records),
            },
        }
        updated["tags"].append(tag)
        updated["tags"].sort(key=lambda item: item["name"].casefold())
        TagCatalogue(updated)
        count = len(records)
        results.append(
            {
                "requested_name": name,
                "outcome": "candidate_created",
                "candidate": tag,
                "dossier_record_count": count,
                "dossier_records": records,
                "soft_frequency_signal": (
                    "below_soft_range"
                    if count < 5
                    else "above_soft_range"
                    if count > 50
                    else "within_soft_range"
                ),
                "reasoning": reasoning,
            }
        )

    return updated, {
        "scope": MANIFEST_SCOPE,
        "review_reference": review_reference,
        "automatic_activation": False,
        "results": results,
    }


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: could not load JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or register formal owner-tag candidates from an explicit "
            "cross-owner corpus taxonomy review. This command never activates tags."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=DEFAULT_TAG_CATALOGUE_PATH,
    )
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.apply and args.audit is None:
        parser.error("--apply requires --audit so the global review is retained")

    catalogue_document = _load_object(args.catalogue)
    manifest = _load_object(args.manifest)
    updated, report = prepare_registration(catalogue_document, manifest)
    report["mode"] = "apply" if args.apply else "dry-run"
    report["catalogue"] = str(args.catalogue.resolve())
    report["manifest"] = str(args.manifest.resolve())
    if args.apply:
        atomic_write_json(args.catalogue, updated)
    if args.audit is not None:
        atomic_write_json(args.audit, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.apply:
        print("Dry-run only; no catalogue state was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
