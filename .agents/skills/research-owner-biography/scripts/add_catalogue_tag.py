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
    TagResolutionError,
    next_tag_id,
    normalize_tag_name,
)


TAG_TYPE_FACETS = {
    "arts",
    "award",
    "business model",
    "cause",
    "company",
    "family",
    "occupation",
    "organisation",
    "philanthropy",
    "sport",
    "status",
    "subindustry",
}


def prepare_addition(
    document: dict[str, Any],
    *,
    name: str,
    aliases: list[str],
    facets: list[str],
    approval_reference: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return a validated catalogue addition or the matching existing tag."""
    catalogue = TagCatalogue(document)
    cleaned_name = name.strip()
    cleaned_aliases = [alias.strip() for alias in aliases if alias.strip()]
    cleaned_facets = [facet.strip() for facet in facets if facet.strip()]
    if not cleaned_name:
        raise ValueError("name must be non-empty")
    cleaned_approval = approval_reference.strip()
    if not cleaned_approval:
        raise ValueError("approval_reference must be non-empty")
    normalized_labels = [
        normalize_tag_name(label) for label in (cleaned_name, *cleaned_aliases)
    ]
    if len(normalized_labels) != len(set(normalized_labels)):
        raise ValueError("name and aliases must be unique after normalization")
    type_facets = TAG_TYPE_FACETS & set(cleaned_facets)
    if len(type_facets) != 1:
        raise ValueError(
            "facets must contain exactly one tag type: "
            + ", ".join(sorted(TAG_TYPE_FACETS))
        )
    if "subindustry" in type_facets and not any(
        facet.startswith("parent:") for facet in cleaned_facets
    ):
        raise ValueError("subindustry tags require at least one parent:<classification>")

    matches = {}
    for label in (cleaned_name, *cleaned_aliases):
        try:
            existing = catalogue.resolve(tag_id=None, name=label)
        except TagResolutionError as exc:
            if not str(exc).startswith("unknown tag name"):
                raise
        else:
            matches[existing.id] = existing
    if len(matches) > 1:
        detail = ", ".join(
            f"{tag.id} ({tag.name})" for tag in matches.values()
        )
        raise ValueError(f"candidate labels resolve to different tags: {detail}")
    if matches:
        existing = next(iter(matches.values()))
        return None, {
            "id": existing.id,
            "name": existing.name,
            "status": "existing",
        }

    new_tag = {
        "id": next_tag_id(document),
        "name": cleaned_name,
        "normalized_name": normalize_tag_name(cleaned_name),
        "aliases": cleaned_aliases,
        "facets": cleaned_facets,
        "status": "active",
        "merged_into": None,
        "lifecycle": {
            "approval_basis": "explicit_global_taxonomy_review",
            "approval_reference": cleaned_approval,
        },
    }
    updated = deepcopy(document)
    updated["tags"].append(new_tag)
    updated["tags"].sort(key=lambda tag: tag["name"].casefold())
    TagCatalogue(updated)
    return updated, {**new_tag, "status": "new"}


def prepare_alias_addition(
    document: dict[str, Any],
    *,
    canonical_label: str,
    alias: str,
    approval_reference: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return a validated alias update for a semantically reviewed concept."""
    catalogue = TagCatalogue(document)
    if canonical_label in catalogue.tags_by_id:
        selected = catalogue.tags_by_id[canonical_label]
        canonical = catalogue.resolve(tag_id=selected.id, name=selected.name)
    else:
        canonical = catalogue.resolve(tag_id=None, name=canonical_label)
    cleaned_alias = alias.strip()
    cleaned_approval = approval_reference.strip()
    if not cleaned_alias:
        raise ValueError("alias must be non-empty")
    if not cleaned_approval:
        raise ValueError("approval_reference must be non-empty")
    try:
        existing = catalogue.resolve(tag_id=None, name=cleaned_alias)
    except TagResolutionError as exc:
        if not str(exc).startswith("unknown tag name"):
            raise
    else:
        if existing.id != canonical.id:
            raise ValueError(
                f"alias resolves to {existing.id} ({existing.name}), not "
                f"{canonical.id} ({canonical.name})"
            )
        return None, {
            "id": canonical.id,
            "name": canonical.name,
            "alias": cleaned_alias,
            "status": "existing",
        }

    updated = deepcopy(document)
    target = next(tag for tag in updated["tags"] if tag["id"] == canonical.id)
    target["aliases"].append(cleaned_alias)
    target["aliases"].sort(key=str.casefold)
    target.setdefault("lifecycle", {})["last_alias_approval_reference"] = (
        cleaned_approval
    )
    TagCatalogue(updated)
    return updated, {
        "id": canonical.id,
        "name": canonical.name,
        "alias": cleaned_alias,
        "status": "alias_added",
    }


def prepare_promotion(
    document: dict[str, Any],
    *,
    tag_id: str,
    approval_reference: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Promote one existing formal candidate after explicit global approval."""
    catalogue = TagCatalogue(document)
    cleaned_approval = approval_reference.strip()
    if not cleaned_approval:
        raise ValueError("approval_reference must be non-empty")
    selected = catalogue.all_tags_by_id.get(tag_id)
    if selected is None:
        raise ValueError(f"unknown tag ID {tag_id!r}")
    if selected.status == "active":
        return None, {
            "id": selected.id,
            "name": selected.name,
            "status": "existing",
        }
    if selected.status != "candidate":
        raise ValueError(
            f"tag {selected.id} ({selected.name}) has status {selected.status!r}; "
            "only formal candidates can be promoted by this command"
        )
    collisions: set[str] = set()
    for label in (selected.name, *selected.aliases):
        collisions.update(
            catalogue.all_lookup.get(normalize_tag_name(label), set())
            - {selected.id}
        )
    if collisions:
        detail = ", ".join(
            f"{other_id} ({catalogue.all_tags_by_id[other_id].name}; "
            f"{catalogue.all_tags_by_id[other_id].status})"
            for other_id in sorted(collisions)
        )
        raise ValueError(
            f"candidate {selected.id} cannot be promoted until label "
            f"collisions are resolved: {detail}"
        )

    updated = deepcopy(document)
    target = next(tag for tag in updated["tags"] if tag["id"] == selected.id)
    lifecycle = target.setdefault("lifecycle", {})
    lifecycle.update(
        {
            "approval_basis": "explicit_global_taxonomy_review",
            "approval_reference": cleaned_approval,
            "promoted_from": "candidate",
        }
    )
    target["status"] = "active"
    TagCatalogue(updated)
    return updated, {
        "id": selected.id,
        "name": selected.name,
        "status": "promoted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or atomically add one explicitly approved active tag, "
            "add an approved alias, or promote one reviewed candidate."
        )
    )
    parser.add_argument("--name")
    parser.add_argument(
        "--promote-id",
        help="Existing candidate ID to promote after explicit global approval.",
    )
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument("--facet", action="append", default=[])
    parser.add_argument(
        "--alias-for",
        help=(
            "Existing canonical name, alias, or ID that --name should be added to."
        ),
    )
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=DEFAULT_TAG_CATALOGUE_PATH,
    )
    parser.add_argument(
        "--approval-reference",
        required=True,
        help=(
            "Human/global taxonomy review reference authorising activation or "
            "alias mutation. A single owner dossier is not sufficient."
        ),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    document = json.loads(args.catalogue.read_text(encoding="utf-8"))
    if bool(args.name) == bool(args.promote_id):
        parser.error("supply exactly one of --name or --promote-id")
    if args.promote_id:
        if args.alias_for or args.alias or args.facet:
            parser.error(
                "--promote-id cannot be combined with --alias-for, --alias, "
                "or --facet"
            )
        updated, result = prepare_promotion(
            document,
            tag_id=args.promote_id,
            approval_reference=args.approval_reference,
        )
    elif args.alias_for:
        if args.alias or args.facet:
            parser.error("--alias-for cannot be combined with --alias or --facet")
        updated, result = prepare_alias_addition(
            document,
            canonical_label=args.alias_for,
            alias=args.name,
            approval_reference=args.approval_reference,
        )
    else:
        updated, result = prepare_addition(
            document,
            name=args.name,
            aliases=args.alias,
            facets=args.facet,
            approval_reference=args.approval_reference,
        )
    if updated is None:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("Use the existing canonical tag; no catalogue change is needed.")
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.apply:
        print("Dry-run only; rerun with --apply after semantic review.")
        return 0
    atomic_write_json(args.catalogue, updated)
    action = {
        "alias_added": "Updated",
        "promoted": "Promoted",
    }.get(result["status"], "Added")
    print(f"{action} {result['id']} ({result['name']}) in {args.catalogue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
