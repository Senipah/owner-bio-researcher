from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAG_CATALOGUE_PATH = REPO_ROOT / "config" / "owner-tags.json"
TAG_CATALOGUE_SCHEMA_VERSION = 2
SUPPORTED_TAG_CATALOGUE_SCHEMA_VERSIONS = {1, 2}
TAG_LIFECYCLE_STATUSES = {"active", "candidate", "inactive", "merged"}
ASSIGNABLE_TAG_STATUSES = {"active", "merged"}
TAG_ID_PATTERN = re.compile(r"^tag_(\d+)$")
SEMANTIC_CONTRACT_FIELDS = {
    "dimension",
    "membership",
    "exclusions",
    "temporal_scope",
    "click_through_expectation",
}
FORBIDDEN_CANONICAL_TAGS = {
    "arts and culture philanthropy",
    "children and youth philanthropy",
    "education philanthropy",
    "family business",
    "family office",
    "health philanthropy",
    "philanthropy",
    "property development",
    "science philanthropy",
}


class TagCatalogueError(ValueError):
    """Raised when a tag catalogue is malformed."""


class TagResolutionError(ValueError):
    """Raised when one or more dossier tag proposals cannot be resolved."""


def normalize_tag_name(value: str) -> str:
    """Return the shared comparison form for names and aliases."""
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    expanded = without_marks.replace("&", " and ").replace("_", " ")
    return re.sub(r"[^\w]+", " ", expanded, flags=re.UNICODE).strip()


def next_tag_id(document: dict[str, Any]) -> str:
    """Return the next monotonic stable ID across every lifecycle state."""
    numbers = []
    for tag in document.get("tags", []):
        match = TAG_ID_PATTERN.fullmatch(str(tag.get("id", "")))
        if match:
            numbers.append(int(match.group(1)))
    return f"tag_{max(numbers, default=0) + 1:04d}"


@dataclass(frozen=True)
class CanonicalTag:
    id: str
    name: str
    normalized_name: str
    aliases: tuple[str, ...]
    facets: tuple[str, ...]
    status: str
    merged_into: str | None
    lifecycle: dict[str, Any]
    semantic_contract: dict[str, Any]

    @property
    def is_assignable(self) -> bool:
        return self.status in ASSIGNABLE_TAG_STATUSES


class TagCatalogue:
    """Lifecycle-aware tag registry with an active-only production view."""

    def __init__(self, document: dict[str, Any], *, source: str = "<memory>"):
        self.source = source
        self.document = document
        self.schema_version: int | None = None
        self.all_tags_by_id: dict[str, CanonicalTag] = {}
        # Production consumers intentionally see active canonical tags only.
        self.tags_by_id: dict[str, CanonicalTag] = {}
        self.merged_tags_by_id: dict[str, CanonicalTag] = {}
        self.non_assignable_tags_by_id: dict[str, CanonicalTag] = {}
        self.lookup: dict[str, set[str]] = {}
        self.non_assignable_lookup: dict[str, set[str]] = {}
        self.all_lookup: dict[str, set[str]] = {}
        self._load()

    @property
    def source_reference(self) -> str:
        try:
            return str(Path(self.source).resolve().relative_to(REPO_ROOT)).replace(
                "\\", "/"
            )
        except (OSError, ValueError):
            return self.source.replace("\\", "/")

    @property
    def lifecycle_counts(self) -> dict[str, int]:
        return {
            status: sum(
                tag.status == status for tag in self.all_tags_by_id.values()
            )
            for status in sorted(TAG_LIFECYCLE_STATUSES)
        }

    def _load(self) -> None:
        schema_version = self.document.get("schema_version")
        if schema_version not in SUPPORTED_TAG_CATALOGUE_SCHEMA_VERSIONS:
            raise TagCatalogueError(
                f"{self.source}: schema_version must be one of "
                f"{sorted(SUPPORTED_TAG_CATALOGUE_SCHEMA_VERSIONS)}"
            )
        self.schema_version = schema_version
        raw_tags = self.document.get("tags")
        if not isinstance(raw_tags, list) or not raw_tags:
            raise TagCatalogueError(f"{self.source}: tags must be a non-empty list")

        canonical_names: dict[str, str] = {}
        for index, raw in enumerate(raw_tags):
            path = f"{self.source}: tags[{index}]"
            if not isinstance(raw, dict):
                raise TagCatalogueError(f"{path} must be an object")
            tag_id = raw.get("id")
            name = raw.get("name")
            normalized_name = raw.get("normalized_name")
            aliases = raw.get("aliases")
            facets = raw.get("facets")
            merged_into = raw.get("merged_into")
            raw_status = raw.get("status")
            lifecycle = raw.get("lifecycle", {})
            semantic_contract = raw.get("semantic_contract", {})
            if not isinstance(tag_id, str) or not tag_id.strip():
                raise TagCatalogueError(f"{path}.id must be non-empty")
            if tag_id in self.all_tags_by_id:
                raise TagCatalogueError(f"{path}.id is duplicated: {tag_id}")
            if not isinstance(name, str) or not name.strip():
                raise TagCatalogueError(f"{path}.name must be non-empty")
            expected_normalized = normalize_tag_name(name)
            if normalized_name != expected_normalized:
                raise TagCatalogueError(
                    f"{path}.normalized_name must be {expected_normalized!r}"
                )
            if normalized_name in FORBIDDEN_CANONICAL_TAGS:
                raise TagCatalogueError(
                    f"{path}.name is deliberately excluded from the catalogue"
                )
            if normalized_name in canonical_names:
                raise TagCatalogueError(
                    f"{path}.name duplicates canonical tag "
                    f"{canonical_names[normalized_name]!r} after normalization"
                )
            if not isinstance(aliases, list) or any(
                not isinstance(alias, str) or not alias.strip()
                for alias in aliases
                if isinstance(aliases, list)
            ):
                raise TagCatalogueError(f"{path}.aliases must be a list of strings")
            if not isinstance(facets, list) or any(
                not isinstance(facet, str) or not facet.strip()
                for facet in facets
                if isinstance(facets, list)
            ):
                raise TagCatalogueError(f"{path}.facets must be a list of strings")
            if merged_into is not None and (
                not isinstance(merged_into, str) or not merged_into.strip()
            ):
                raise TagCatalogueError(f"{path}.merged_into must be null or an ID")
            if schema_version == 1:
                status = "merged" if merged_into is not None else "active"
            else:
                status = raw_status
                if status not in TAG_LIFECYCLE_STATUSES:
                    raise TagCatalogueError(
                        f"{path}.status must be one of "
                        f"{sorted(TAG_LIFECYCLE_STATUSES)}"
                    )
                if not isinstance(lifecycle, dict):
                    raise TagCatalogueError(f"{path}.lifecycle must be an object")
            if not isinstance(semantic_contract, dict):
                raise TagCatalogueError(
                    f"{path}.semantic_contract must be an object"
                )
            if (
                schema_version == 2
                and self.document.get("consolidation")
                and status == "active"
            ):
                missing_contract_fields = (
                    SEMANTIC_CONTRACT_FIELDS - semantic_contract.keys()
                )
                if missing_contract_fields:
                    raise TagCatalogueError(
                        f"{path}.semantic_contract is missing "
                        f"{sorted(missing_contract_fields)}"
                    )
                if any(
                    not isinstance(semantic_contract[field], str)
                    or not semantic_contract[field].strip()
                    for field in SEMANTIC_CONTRACT_FIELDS
                ):
                    raise TagCatalogueError(
                        f"{path}.semantic_contract fields must be non-empty strings"
                    )
            if status == "merged" and merged_into is None:
                raise TagCatalogueError(
                    f"{path}.merged_into is required when status is 'merged'"
                )
            if status != "merged" and merged_into is not None:
                raise TagCatalogueError(
                    f"{path}.merged_into is allowed only when status is 'merged'"
                )
            if status == "inactive" and schema_version == 2:
                reason = lifecycle.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    raise TagCatalogueError(
                        f"{path}.lifecycle.reason is required for inactive tags"
                    )

            tag = CanonicalTag(
                id=tag_id,
                name=name.strip(),
                normalized_name=normalized_name,
                aliases=tuple(aliases),
                facets=tuple(facets),
                status=status,
                merged_into=merged_into,
                lifecycle=dict(lifecycle),
                semantic_contract=dict(semantic_contract),
            )
            self.all_tags_by_id[tag_id] = tag
            canonical_names[normalized_name] = name

        for tag in self.all_tags_by_id.values():
            if tag.merged_into is not None and tag.merged_into not in self.all_tags_by_id:
                raise TagCatalogueError(
                    f"{self.source}: tag {tag.id} merges into unknown ID "
                    f"{tag.merged_into}"
                )
            if tag.status == "active":
                self.tags_by_id[tag.id] = tag
            elif tag.status == "merged":
                self.merged_tags_by_id[tag.id] = tag
            else:
                self.non_assignable_tags_by_id[tag.id] = tag

        for tag in self.all_tags_by_id.values():
            terminal = self._terminal_tag(tag.id)
            if tag.status == "merged" and terminal.status != "active":
                raise TagCatalogueError(
                    f"{self.source}: merged tag {tag.id} must terminate at an "
                    "active tag"
                )
            for label in (tag.name, *tag.aliases):
                normalized = normalize_tag_name(label)
                if not normalized:
                    raise TagCatalogueError(
                        f"{self.source}: tag {tag.id} has an empty normalized label"
                    )
                self.all_lookup.setdefault(normalized, set()).add(tag.id)
                if tag.is_assignable:
                    self.lookup.setdefault(normalized, set()).add(tag.id)
                else:
                    self.non_assignable_lookup.setdefault(normalized, set()).add(
                        tag.id
                    )

    def _terminal_tag(self, tag_id: str) -> CanonicalTag:
        seen: set[str] = set()
        current = self.all_tags_by_id[tag_id]
        while current.merged_into is not None:
            if current.id in seen:
                raise TagCatalogueError(
                    f"{self.source}: merged_into cycle includes {current.id}"
                )
            seen.add(current.id)
            current = self.all_tags_by_id[current.merged_into]
        return current

    def inspect(self, *, tag_id: str | None, name: str) -> dict[str, Any]:
        """Classify a reference without treating non-active states as assignable."""
        normalized_name = normalize_tag_name(name)
        if tag_id is not None:
            selected = self.all_tags_by_id.get(tag_id)
            if selected is None:
                return {
                    "status": "unknown",
                    "message": f"unknown tag_id {tag_id!r}",
                }
            accepted_names = {
                normalize_tag_name(label)
                for label in (selected.name, *selected.aliases)
            }
            terminal = self._terminal_tag(selected.id)
            if selected.status == "merged":
                accepted_names.update(
                    normalize_tag_name(label)
                    for label in (terminal.name, *terminal.aliases)
                )
            if normalized_name not in accepted_names:
                return {
                    "status": "mismatch",
                    "tag": selected,
                    "message": (
                        f"tag_id {tag_id!r} does not match name {name!r}"
                    ),
                }
            if selected.status == "active":
                return {
                    "status": "active",
                    "tag": selected,
                    "canonical": selected,
                }
            if selected.status == "merged":
                return {
                    "status": "merged",
                    "tag": selected,
                    "canonical": terminal,
                    "message": (
                        f"merged tag {selected.id} redirects to "
                        f"{terminal.id} ({terminal.name})"
                    ),
                }
            return {
                "status": selected.status,
                "tag": selected,
                "message": (
                    f"tag_id {selected.id!r} has lifecycle status "
                    f"{selected.status!r} and is not assignable"
                ),
            }

        assignable_ids = self.lookup.get(normalized_name, set())
        terminal = {
            self._terminal_tag(candidate_id).id: self._terminal_tag(candidate_id)
            for candidate_id in assignable_ids
        }
        if len(terminal) > 1:
            candidates = ", ".join(
                f"{tag.id} ({tag.name})"
                for tag in sorted(terminal.values(), key=lambda item: item.id)
            )
            return {
                "status": "ambiguous",
                "message": (
                    f"ambiguous tag name {name!r}; candidates: {candidates}"
                ),
            }
        if terminal:
            canonical = next(iter(terminal.values()))
            holders = [self.all_tags_by_id[item] for item in assignable_ids]
            merged_only = bool(holders) and all(
                item.status == "merged" for item in holders
            )
            return {
                "status": "merged" if merged_only else "active",
                "tag": holders[0] if merged_only else canonical,
                "canonical": canonical,
            }

        reserved_ids = self.non_assignable_lookup.get(normalized_name, set())
        if reserved_ids:
            reserved = [self.all_tags_by_id[item] for item in sorted(reserved_ids)]
            statuses = sorted({item.status for item in reserved})
            labels = ", ".join(
                f"{item.id} ({item.name}; {item.status})" for item in reserved
            )
            return {
                "status": statuses[0] if len(statuses) == 1 else "non_assignable",
                "tag": reserved[0] if len(reserved) == 1 else None,
                "matches": reserved,
                "message": (
                    f"tag name {name!r} is reserved by non-assignable "
                    f"catalogue entries: {labels}"
                ),
            }
        return {
            "status": "unknown",
            "message": f"unknown tag name {name!r}",
        }

    def resolve(self, *, tag_id: str | None, name: str) -> CanonicalTag:
        """Resolve an active ID/name or a merged reference to its active target."""
        result = self.inspect(tag_id=tag_id, name=name)
        if result["status"] in ASSIGNABLE_TAG_STATUSES:
            return result["canonical"]
        raise TagResolutionError(result["message"])


def load_tag_catalogue(path: Path = DEFAULT_TAG_CATALOGUE_PATH) -> TagCatalogue:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TagCatalogueError(
            f"Could not load tag catalogue {path}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise TagCatalogueError(f"{path}: catalogue root must be an object")
    return TagCatalogue(document, source=str(path))


def inspect_dossier_tags(
    dossier: dict[str, Any],
    catalogue: TagCatalogue,
    *,
    person_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return active canonical assignments and lifecycle-aware reference issues."""
    resolved: list[dict[str, Any]] = []
    resolved_ids: dict[str, int] = {}
    references: list[dict[str, Any]] = []
    proposals = dossier.get("proposed_tags")
    if not isinstance(proposals, list):
        return [], [
            {
                "status": "invalid",
                "message": "proposed_tags must be a list",
            }
        ]
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            references.append(
                {
                    "index": index,
                    "status": "invalid",
                    "message": f"proposed_tags[{index}] must be an object",
                }
            )
            continue
        name = str(proposal.get("name", ""))
        tag_id = proposal.get("tag_id")
        result = catalogue.inspect(tag_id=tag_id, name=name)
        status = result["status"]
        reference = {
            "index": index,
            "tag_id": tag_id,
            "name": name,
            "status": status,
        }
        if result.get("message"):
            reference["message"] = result["message"]
        tag = result.get("tag")
        if isinstance(tag, CanonicalTag):
            reference["catalogue_id"] = tag.id
            reference["catalogue_name"] = tag.name
        canonical = result.get("canonical")
        if isinstance(canonical, CanonicalTag):
            reference["canonical_id"] = canonical.id
            reference["canonical_name"] = canonical.name
        references.append(reference)
        if status not in ASSIGNABLE_TAG_STATUSES:
            continue
        if canonical.id in resolved_ids:
            references[-1] = {
                **reference,
                "status": "duplicate",
                "message": (
                    f"resolves to duplicate canonical tag {canonical.id} "
                    f"({canonical.name}); first proposed at index "
                    f"{resolved_ids[canonical.id]}"
                ),
            }
            continue
        resolved_ids[canonical.id] = index
        resolved.append(
            {
                "id": canonical.id,
                "name": canonical.name,
                "summary": proposal.get("summary"),
                "confidence": proposal.get("confidence"),
                "source_ids": proposal.get("source_ids"),
                "relationship_type": proposal.get("relationship_type"),
                "temporal_scope": proposal.get("temporal_scope"),
                "taxonomy_value": proposal.get("taxonomy_value"),
            }
        )
    return resolved, references


def resolve_dossier_tags(
    dossier: dict[str, Any],
    catalogue: TagCatalogue,
    *,
    person_id: int,
) -> list[dict[str, Any]]:
    resolved, references = inspect_dossier_tags(
        dossier,
        catalogue,
        person_id=person_id,
    )
    issues = [
        item
        for item in references
        if item.get("status") not in ASSIGNABLE_TAG_STATUSES
    ]
    if issues:
        detail = "; ".join(
            f"proposed_tags[{item.get('index', '?')}] {item.get('message')}"
            for item in issues
        )
        raise TagResolutionError(f"Owner {person_id} tag resolution failed: {detail}")
    return resolved
