from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
for import_path in (REPO_ROOT, SCRIPT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from register_corpus_tag_candidates import prepare_registration
from src.io_utils import atomic_write_json
from src.tags import DEFAULT_TAG_CATALOGUE_PATH, TagCatalogue, normalize_tag_name


SEMANTIC_CONTRACT_FIELDS = (
    "dimension",
    "membership",
    "exclusions",
    "temporal_scope",
    "click_through_expectation",
)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: could not load JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def _semantic_contract(value: Any, path: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    extra = set(value) - set(SEMANTIC_CONTRACT_FIELDS)
    missing = set(SEMANTIC_CONTRACT_FIELDS) - set(value)
    if missing or extra:
        raise ValueError(
            f"{path} must contain exactly {', '.join(SEMANTIC_CONTRACT_FIELDS)}; "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    contract: dict[str, str] = {}
    for field in SEMANTIC_CONTRACT_FIELDS:
        field_value = value[field]
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(f"{path}.{field} must be a non-empty string")
        contract[field] = field_value.strip()
    return contract


def _matching_tag_id(catalogue: TagCatalogue, concept: dict[str, Any]) -> str:
    labels = [concept["name"], *concept.get("aliases", [])]
    matching_ids: set[str] = set()
    for label in labels:
        matching_ids.update(
            catalogue.all_lookup.get(normalize_tag_name(label), set())
        )
    if not matching_ids:
        raise ValueError(
            f"{concept['name']}: no lifecycle record exists; register the "
            "reviewed candidate manifest before activation"
        )
    if len(matching_ids) != 1:
        raise ValueError(
            f"{concept['name']}: labels resolve to multiple lifecycle records: "
            + ", ".join(sorted(matching_ids))
        )
    return next(iter(matching_ids))


def prepare_activation(
    catalogue_document: dict[str, Any],
    manifest: dict[str, Any],
    *,
    approval_reference: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Activate every registered manifest concept after explicit approval."""
    cleaned_approval = approval_reference.strip()
    if not cleaned_approval:
        raise ValueError("approval_reference must be non-empty")

    _, registration_report = prepare_registration(catalogue_document, manifest)
    unregistered = [
        result["requested_name"]
        for result in registration_report["results"]
        if result["outcome"] != "existing_lifecycle_record"
    ]
    if unregistered:
        raise ValueError(
            "manifest concepts must be registered before activation: "
            + ", ".join(unregistered)
        )

    updated = deepcopy(catalogue_document)
    results: list[dict[str, Any]] = []
    for index, concept in enumerate(manifest["concepts"]):
        contract = _semantic_contract(
            concept.get("semantic_contract"),
            f"manifest.concepts[{index}].semantic_contract",
        )
        catalogue = TagCatalogue(updated)
        tag_id = _matching_tag_id(catalogue, concept)
        selected = catalogue.all_tags_by_id[tag_id]
        if selected.status == "merged":
            raise ValueError(
                f"{selected.id} ({selected.name}) is merged and cannot be activated"
            )
        if selected.status == "active":
            target = next(tag for tag in updated["tags"] if tag["id"] == tag_id)
            if target.get("semantic_contract") != contract:
                raise ValueError(
                    f"{selected.id} ({selected.name}) is already active with a "
                    "different semantic contract"
                )
            results.append(
                {"id": selected.id, "name": selected.name, "status": "existing"}
            )
            continue
        if selected.status not in {"candidate", "inactive"}:
            raise ValueError(
                f"{selected.id} ({selected.name}) has unsupported status "
                f"{selected.status!r}"
            )

        previous_status = selected.status
        target = next(tag for tag in updated["tags"] if tag["id"] == tag_id)
        target["status"] = "active"
        target["merged_into"] = None
        target["semantic_contract"] = contract
        lifecycle = target.setdefault("lifecycle", {})
        lifecycle.update(
            {
                "approval_basis": "explicit_global_taxonomy_review",
                "approval_reference": cleaned_approval,
            }
        )
        if previous_status == "candidate":
            lifecycle["promoted_from"] = "candidate"
        else:
            if "reason" in lifecycle:
                lifecycle["previous_inactive_reason"] = lifecycle.pop("reason")
            if "consolidation_decision" in lifecycle:
                lifecycle["previous_consolidation_decision"] = lifecycle[
                    "consolidation_decision"
                ]
            lifecycle["consolidation_decision"] = "reactivated_active"
            lifecycle["reactivated_from"] = "inactive"

        results.append(
            {
                "id": selected.id,
                "name": selected.name,
                "status": (
                    "promoted" if previous_status == "candidate" else "reactivated"
                ),
            }
        )

    TagCatalogue(updated)
    return updated, {
        "review_reference": manifest["review_reference"],
        "approval_reference": cleaned_approval,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or activate every registered concept in an approved corpus "
            "tag manifest. Activation requires a separate explicit approval."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--catalogue", type=Path, default=DEFAULT_TAG_CATALOGUE_PATH
    )
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.apply and args.audit is None:
        parser.error("--apply requires --audit so the approval is retained")

    catalogue_document = _load_object(args.catalogue)
    manifest = _load_object(args.manifest)
    updated, report = prepare_activation(
        catalogue_document,
        manifest,
        approval_reference=args.approval_reference,
    )
    report.update(
        {
            "mode": "apply" if args.apply else "dry-run",
            "catalogue": str(args.catalogue.resolve()),
            "manifest": str(args.manifest.resolve()),
        }
    )
    if args.apply:
        atomic_write_json(args.catalogue, updated)
    if args.audit is not None:
        atomic_write_json(args.audit, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if not args.apply:
        print("Dry-run only; no catalogue state was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
