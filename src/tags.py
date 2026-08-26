from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAG_CATALOGUE_PATH = REPO_ROOT / "config" / "owner-tags.json"
TAG_CATALOGUE_SCHEMA_VERSION = 1
FORBIDDEN_CANONICAL_TAGS = {"family business", "property development"}


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


@dataclass(frozen=True)
class CanonicalTag:
    id: str
    name: str
    normalized_name: str
    aliases: tuple[str, ...]
    facets: tuple[str, ...]
    merged_into: str | None


class TagCatalogue:
    def __init__(self, document: dict[str, Any], *, source: str = "<memory>"):
        self.source = source
        self.document = document
        self.tags_by_id: dict[str, CanonicalTag] = {}
        self.lookup: dict[str, set[str]] = {}
        self._load()

    @property
    def source_reference(self) -> str:
        try:
            return str(Path(self.source).resolve().relative_to(REPO_ROOT)).replace(
                "\\", "/"
            )
        except (OSError, ValueError):
            return self.source.replace("\\", "/")

    def _load(self) -> None:
        if self.document.get("schema_version") != TAG_CATALOGUE_SCHEMA_VERSION:
            raise TagCatalogueError(
                f"{self.source}: schema_version must be "
                f"{TAG_CATALOGUE_SCHEMA_VERSION}"
            )
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
            if not isinstance(tag_id, str) or not tag_id.strip():
                raise TagCatalogueError(f"{path}.id must be non-empty")
            if tag_id in self.tags_by_id:
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
                for facet in facets if isinstance(facets, list)
            ):
                raise TagCatalogueError(f"{path}.facets must be a list of strings")
            if merged_into is not None and (
                not isinstance(merged_into, str) or not merged_into.strip()
            ):
                raise TagCatalogueError(f"{path}.merged_into must be null or an ID")

            tag = CanonicalTag(
                id=tag_id,
                name=name.strip(),
                normalized_name=normalized_name,
                aliases=tuple(aliases),
                facets=tuple(facets),
                merged_into=merged_into,
            )
            self.tags_by_id[tag_id] = tag
            canonical_names[normalized_name] = name

        for tag in self.tags_by_id.values():
            if (
                tag.merged_into is not None
                and tag.merged_into not in self.tags_by_id
            ):
                raise TagCatalogueError(
                    f"{self.source}: tag {tag.id} merges into unknown ID "
                    f"{tag.merged_into}"
                )
            self._terminal_tag(tag.id)
            for label in (tag.name, *tag.aliases):
                normalized = normalize_tag_name(label)
                if not normalized:
                    raise TagCatalogueError(
                        f"{self.source}: tag {tag.id} has an empty normalized label"
                    )
                self.lookup.setdefault(normalized, set()).add(tag.id)

    def _terminal_tag(self, tag_id: str) -> CanonicalTag:
        seen: set[str] = set()
        current = self.tags_by_id[tag_id]
        while current.merged_into is not None:
            if current.id in seen:
                raise TagCatalogueError(
                    f"{self.source}: merged_into cycle includes {current.id}"
                )
            seen.add(current.id)
            current = self.tags_by_id[current.merged_into]
        return current

    def resolve(self, *, tag_id: str | None, name: str) -> CanonicalTag:
        """Resolve an authoritative ID or, when absent, a name/alias."""
        if tag_id is not None:
            selected = self.tags_by_id.get(tag_id)
            if selected is None:
                raise TagResolutionError(f"unknown tag_id {tag_id!r}")
            accepted_names = {
                normalize_tag_name(label)
                for label in (selected.name, *selected.aliases)
            }
            terminal = self._terminal_tag(selected.id)
            accepted_names.update(
                normalize_tag_name(label)
                for label in (terminal.name, *terminal.aliases)
            )
            if normalize_tag_name(name) not in accepted_names:
                raise TagResolutionError(
                    f"tag_id {tag_id!r} does not match name {name!r}"
                )
            return terminal

        normalized = normalize_tag_name(name)
        candidate_ids = self.lookup.get(normalized, set())
        terminal = {
            self._terminal_tag(candidate_id).id: self._terminal_tag(candidate_id)
            for candidate_id in candidate_ids
        }
        if not terminal:
            raise TagResolutionError(f"unknown tag name {name!r}")
        if len(terminal) > 1:
            candidates = ", ".join(
                f"{tag.id} ({tag.name})"
                for tag in sorted(terminal.values(), key=lambda item: item.id)
            )
            raise TagResolutionError(
                f"ambiguous tag name {name!r}; candidates: {candidates}"
            )
        return next(iter(terminal.values()))


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


def resolve_dossier_tags(
    dossier: dict[str, Any],
    catalogue: TagCatalogue,
    *,
    person_id: int,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    resolved_ids: dict[str, int] = {}
    issues: list[str] = []
    proposals = dossier.get("proposed_tags")
    if not isinstance(proposals, list):
        raise TagResolutionError(
            f"Owner {person_id} tag resolution failed: "
            "proposed_tags must be a list"
        )
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            issues.append(f"proposed_tags[{index}] must be an object")
            continue
        try:
            tag = catalogue.resolve(
                tag_id=proposal.get("tag_id"),
                name=str(proposal.get("name", "")),
            )
        except TagResolutionError as exc:
            issues.append(f"proposed_tags[{index}] {exc}")
            continue
        if tag.id in resolved_ids:
            issues.append(
                f"proposed_tags[{index}] resolves to duplicate canonical tag "
                f"{tag.id} ({tag.name}); first proposed at index "
                f"{resolved_ids[tag.id]}"
            )
            continue
        resolved_ids[tag.id] = index
        resolved.append(
            {
                "id": tag.id,
                "name": tag.name,
                "summary": proposal.get("summary"),
                "confidence": proposal.get("confidence"),
                "source_ids": proposal.get("source_ids"),
            }
        )
    if issues:
        detail = "; ".join(issues)
        raise TagResolutionError(f"Owner {person_id} tag resolution failed: {detail}")
    return resolved
