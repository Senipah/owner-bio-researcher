from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from src.io_utils import atomic_write_json
from src.tags import (
    DEFAULT_TAG_CATALOGUE_PATH,
    TagCatalogue,
    normalize_tag_name,
)
from validate_dossier import validate as validate_dossier


DEFAULT_CONFIG = REPO_ROOT / "config" / "owner-tag-consolidation.json"
DEFAULT_DOSSIERS = REPO_ROOT / "output" / "owner-research" / "all-by-loa"
DEFAULT_AUDIT_DIR = (
    REPO_ROOT / "output" / "audits" / "corpus-owner-tag-consolidation"
)
FACT_NOTE_HEADING = "Owner-tag consolidation research context:"
TAG_TYPE_FACETS = {
    "arts",
    "award",
    "business model",
    "cause",
    "company",
    "company association",
    "family",
    "industry",
    "occupation",
    "organisation",
    "philanthropy",
    "royal family",
    "sport",
    "status",
    "subindustry",
}
GENERIC_COMPANY_POSITIVE = re.compile(
    r"\b(?:co-?found(?:er|ed)?|found(?:er|ed)?|control(?:s|led|ling)?|"
    r"owner(?:ship)?|principal family|family owner|chief executive|\bceo\b|"
    r"chair(?:man|woman|person|ed)?|president|built|created|established|"
    r"led|leads|leadership|three decades|long-?term|longstanding)\b",
    re.IGNORECASE,
)
GENERIC_COMPANY_NEGATIVE = re.compile(
    r"\b(?:acquirer|acquired by|sold to|exit to|customer|supplier|donor|"
    r"brief board|short tenure|passive (?:stake|holding|investment)|"
    r"one[- ]off investment)\b",
    re.IGNORECASE,
)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: could not load JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        normalized = normalize_tag_name(cleaned)
        if cleaned and normalized not in seen:
            seen.add(normalized)
            result.append(cleaned)
    return result


def _load_git_dossiers(
    reference: str,
    dossier_directory: Path,
) -> dict[str, dict[str, Any]]:
    relative = dossier_directory.resolve().relative_to(REPO_ROOT).as_posix()
    result = subprocess.run(
        ["git", "archive", "--format=tar", reference, relative],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            f"Could not read approved dossier baseline {reference}:{relative}: "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    dossiers: dict[str, dict[str, Any]] = {}
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            name = Path(member.name).name
            if not member.isfile() or not name.endswith(".research.json"):
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            value = json.loads(handle.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"{reference}:{member.name}: root must be an object")
            dossiers[name] = value
    return dossiers


def _status_by_id(document: dict[str, Any]) -> dict[str, str]:
    return {
        str(tag["id"]): str(tag["status"])
        for tag in document.get("tags", [])
        if isinstance(tag, dict)
    }


def validate_config(
    configuration: dict[str, Any],
    catalogue_document: dict[str, Any],
) -> None:
    if configuration.get("schema_version") != 1:
        raise ValueError("consolidation configuration schema_version must be 1")
    if configuration.get("repository_is_source_of_truth") is not True:
        raise ValueError("repository_is_source_of_truth must be true")
    if configuration.get("live_state_is_taxonomy_input") is not False:
        raise ValueError("live_state_is_taxonomy_input must be false")
    review_reference = configuration.get("review_reference")
    if not isinstance(review_reference, str) or not review_reference.strip():
        raise ValueError("review_reference must be non-empty")

    statuses = _status_by_id(catalogue_document)
    operations = {
        "promote": configuration.get("promote", []),
        "reactivate": configuration.get("reactivate", []),
        "inactivate_active": list(
            configuration.get("inactivate_active", {}).keys()
        ),
    }
    expected = {
        "promote": {"candidate", "active"},
        "reactivate": {"inactive", "active"},
        "inactivate_active": {"active", "inactive"},
    }
    selected: set[str] = set()
    for operation, tag_ids in operations.items():
        if not isinstance(tag_ids, list):
            raise ValueError(f"{operation} must be a list or object of tag IDs")
        for tag_id in tag_ids:
            if tag_id not in statuses:
                raise ValueError(f"{operation} references unknown tag {tag_id}")
            if statuses[tag_id] not in expected[operation]:
                raise ValueError(
                    f"{operation} requires one of {sorted(expected[operation])}; "
                    f"{tag_id} is {statuses[tag_id]}"
                )
            if tag_id in selected:
                raise ValueError(f"tag {tag_id} has conflicting lifecycle decisions")
            selected.add(tag_id)

    all_ids = set(statuses)
    rewrites = configuration.get("assignment_rewrites")
    if not isinstance(rewrites, dict):
        raise ValueError("assignment_rewrites must be an object")
    prospective_active = {
        tag_id
        for tag_id, status in statuses.items()
        if status == "active"
        and tag_id not in configuration.get("inactivate_active", {})
    } | set(configuration["promote"]) | set(configuration["reactivate"])
    for source_id, targets in rewrites.items():
        if source_id not in all_ids:
            raise ValueError(f"assignment rewrite source is unknown: {source_id}")
        if not isinstance(targets, list) or not targets:
            raise ValueError(f"assignment rewrite {source_id} needs target IDs")
        unknown_targets = set(targets) - prospective_active
        if unknown_targets:
            raise ValueError(
                f"assignment rewrite {source_id} has non-active targets: "
                f"{sorted(unknown_targets)}"
            )

    for child_id, companion_ids in configuration.get(
        "required_companions", {}
    ).items():
        if child_id not in prospective_active:
            raise ValueError(f"required companion child is not active: {child_id}")
        if set(companion_ids) - prospective_active:
            raise ValueError(
                f"required companion targets are not active for {child_id}"
            )

    for tag_id, allowed_ids in configuration.get(
        "manual_company_membership", {}
    ).items():
        if tag_id not in prospective_active:
            raise ValueError(f"manual company tag is not active: {tag_id}")
        if not isinstance(allowed_ids, list) or any(
            not isinstance(person_id, int) for person_id in allowed_ids
        ):
            raise ValueError(f"manual company membership for {tag_id} is invalid")


def _inactive_reason(tag: dict[str, Any], *, has_rewrite: bool) -> str:
    if has_rewrite:
        return (
            "consolidated_to_a_more_useful_active_concept_without_treating_"
            "broader_or_narrower_wording_as_an_alias"
        )
    facets = {str(value).casefold() for value in tag.get("facets", [])}
    if facets & {"company", "company association", "organisation"}:
        return "named_entity_failed_global_click_through_contract"
    if "business model" in facets:
        return "narrative_strategy_or_transaction_fact_belongs_in_dossier"
    if facets & {"cause", "philanthropy"}:
        return "cause_or_philanthropy_not_distinctive_enough_for_owner_taxonomy"
    if facets & {"award"}:
        return "honour_or_award_lacks_sufficient_cross_owner_information_value"
    if facets & {"family", "royal family", "dynasty", "business family"}:
        return "insufficient_current_cross_record_family_cohort"
    if "occupation" in facets:
        return "role_is_incidental_overlapping_or_insufficiently_salient"
    if facets & {"industry", "subindustry", "investment"}:
        return "industry_concept_is_overlapping_over_granular_or_incidental"
    if "sport" in facets:
        return "sport_concept_is_over_granular_event_specific_or_incidental"
    if facets & {"arts", "cultural interest"}:
        return "cultural_concept_is_over_granular_or_incidental"
    if "status" in facets:
        return "status_is_incidental_or_better_preserved_as_dossier_context"
    return "failed_global_information_value_and_cohort_coherence_test"


def _contract_profile(tag: dict[str, Any]) -> tuple[str, str, str, str]:
    tag_id = str(tag["id"])
    name = str(tag["name"])
    facets = {str(value).casefold() for value in tag.get("facets", [])}

    if tag_id == "tag_0249":
        return (
            "public_ownership",
            "The owner record is itself a government, sovereign, municipality, or directly state-owned public entity.",
            "Do not assign this to politicians, royals, public officials, executives of state-owned companies, or privately owned contractors.",
            "current",
        )
    if tag_id in {"tag_0212", "tag_0213", "tag_0225", "tag_0235", "tag_0250", "tag_0546", "tag_1982"}:
        return (
            "gambling_specialism",
            f"The owner's defining wealth creation or long-term operating identity materially involves {name}.",
            "Exclude incidental investments, customers, suppliers, and video-game businesses; use Gambling as the required umbrella.",
            "current_or_historically_defining",
        )
    if tag_id in {"tag_0307", "tag_0352"}:
        return (
            "video_games_specialism",
            f"The owner's defining wealth creation or operating identity materially involves {name}.",
            "Exclude casino gaming, betting, gambling equipment, passive investments, and incidental product exposure; use Video games as the required umbrella.",
            "current_or_historically_defining",
        )
    if "royal family" in facets or (
        "family" in facets and facets & {"dynasty", "business family"}
    ):
        return (
            "family_or_royal_affiliation",
            f"The owner is a documented member of the {name} family or dynasty, and that membership is material to wealth, status, or public identity.",
            "Never infer membership from surname alone; exclude marriage-only, advisory, employment, investment, and social relationships unless the canonical family contract explicitly includes them.",
            "durable",
        )
    if tag_id == "tag_0165" or "royalty" in facets:
        return (
            "royal_status",
            f"The owner personally and durably holds, or historically held as a defining identity, the status represented by {name}.",
            "Exclude government officials, royal advisers, state-company executives, and association with a royal family without personal royal status.",
            "current_or_historically_defining",
        )
    if "public office" in facets or tag_id in {
        "tag_0319",
        "tag_0353",
        "tag_0395",
    }:
        scope = "current_only" if tag_id == "tag_0279" else "current_or_historically_defining"
        return (
            "public_office",
            f"The owner formally holds, or held as a defining public role, the office or public-service identity {name}.",
            "Exclude honorary titles, advisory proximity, family association, brief incidental service, and inferred responsibility without formal office.",
            scope,
        )
    if "company" in facets or "company association" in facets:
        return (
            "company_affiliation",
            f"The owner is a founder or co-founder, controller, principal family owner, or genuinely defining long-term leader of {name}.",
            "Exclude passive investors, ordinary or short employment, customers, suppliers, donors, advisers, one board seat, and acquisition or exit counterparties.",
            "current_or_historically_defining",
        )
    if "organisation" in facets:
        return (
            "organisation_affiliation",
            f"The owner founded, controls, or is durably and publicly identified with {name} in a relationship central to their identity.",
            "Exclude attendance, donations, honorary links, ordinary membership, one board seat, and incidental institutional relationships.",
            "current_or_historically_defining",
        )
    if "sport" in facets:
        return (
            "sporting_identity",
            f"The owner has a sustained, defining professional, competitive, ownership, or senior-governance identity in {name}.",
            "Exclude fandom, recreation, sponsorship, attendance, a one-off event, and casual participation.",
            "current_or_historically_defining",
        )
    if "occupation" in facets:
        return (
            "profession_or_role",
            f"{name} is a substantial, recognised, and defining occupation or practiced role in the owner's public identity.",
            "Exclude education alone, a short early-career stage, honorary roles, isolated projects, and passive ownership without practicing the role.",
            "current_or_historically_defining",
        )
    if "award" in facets:
        return (
            "award_or_honour",
            f"The owner personally and formally received the award or honour {name}.",
            "Exclude nominations, institutional awards, honorary proximity, sponsorship, and awards received only by an associated company or team.",
            "durable",
        )
    if facets & {"arts", "collecting", "music", "genre", "creative"}:
        return (
            "cultural_identity",
            f"{name} is a sustained, defining creative practice, recognised body of work, or notable collection in the owner's public identity.",
            "Exclude a single purchase, casual interest, donation, sponsorship, passive investment, or incidental association.",
            "current_or_historically_defining",
        )
    if facets & {"philanthropy", "cause"}:
        return (
            "defining_public_interest",
            f"The owner has a sustained, unusually defining public identity or institution-building commitment to {name}.",
            "Exclude routine billionaire giving, one donation, general foundation activity, board membership alone, and weakly documented interests.",
            "current_or_historically_defining",
        )
    if "business model" in facets:
        return (
            "defining_business_model",
            f"{name} is a recognised, repeated, and defining operating or investment model through which the owner materially created wealth.",
            "Exclude one transaction, a generic strategy description, an analytical inference, or a model common to wealthy owners generally.",
            "current_or_historically_defining",
        )
    if facets & {"industry", "subindustry", "investment"}:
        return (
            "industry_or_investment_specialism",
            f"The owner created material wealth through, controlled substantial operations in, or had a defining long-term operating mandate in {name}.",
            "Exclude passive holdings, one deals or projects, customers and suppliers, short earlier jobs, and incidental portfolio exposure.",
            "current_or_historically_defining",
        )
    if "status" in facets:
        return (
            "defining_status",
            f"The owner personally and durably satisfies the precise status represented by {name}, and it is notable to their public identity.",
            "Exclude inferred, honorary, incidental, former-but-minor, and organisation-only status.",
            "current_or_historically_defining",
        )
    return (
        "other_defining_identity",
        f"{name} is a durable, material, and publicly defining characteristic of the owner.",
        "Exclude incidental, weakly documented, one-off, passive, or merely biographical associations.",
        "current_or_historically_defining",
    )


def _semantic_contract(tag: dict[str, Any]) -> dict[str, str]:
    dimension, membership, exclusions, temporal_scope = _contract_profile(tag)
    return {
        "dimension": dimension,
        "membership": membership,
        "exclusions": exclusions,
        "temporal_scope": temporal_scope,
        "click_through_expectation": (
            f"Owners grouped under {tag['name']} satisfy this same membership "
            "rule for a defining, evidence-backed reason."
        ),
    }


def prepare_catalogue(
    document: dict[str, Any],
    configuration: dict[str, Any],
    *,
    referenced_inactive_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_config(configuration, document)
    updated = deepcopy(document)
    review_reference = configuration["review_reference"]
    promote = set(configuration["promote"])
    reactivate = set(configuration["reactivate"])
    inactivate_active = configuration["inactivate_active"]
    rewrites = configuration["assignment_rewrites"]
    renames = configuration.get("renames", {})
    alias_decisions = configuration.get("aliases", {})
    before_catalogue = TagCatalogue(document)
    before_counts = before_catalogue.lifecycle_counts
    decisions: Counter[str] = Counter()
    lifecycle_rows: list[dict[str, Any]] = []

    for tag in updated["tags"]:
        tag_id = str(tag["id"])
        before_status = str(tag["status"])
        original_name = str(tag["name"])
        lifecycle = tag.setdefault("lifecycle", {})
        lifecycle.pop("pending_aliases", None)

        rename = renames.get(tag_id)
        if rename and tag["name"] != rename["name"].strip():
            old_name = tag["name"]
            tag["name"] = rename["name"].strip()
            tag["normalized_name"] = normalize_tag_name(tag["name"])
            if rename.get("retain_old_name_as_alias"):
                tag["aliases"] = _unique([*tag["aliases"], old_name])
            else:
                old_normalized = normalize_tag_name(old_name)
                tag["aliases"] = [
                    alias
                    for alias in tag["aliases"]
                    if normalize_tag_name(alias) != old_normalized
                ]
            lifecycle["renamed_from"] = old_name
            lifecycle["rename_review_reference"] = review_reference

        alias_review = alias_decisions.get(tag_id)
        if alias_review:
            rejected = {
                normalize_tag_name(alias) for alias in alias_review.get("reject", [])
            }
            tag["aliases"] = [
                alias
                for alias in tag["aliases"]
                if normalize_tag_name(alias) not in rejected
            ]
            tag["aliases"] = _unique(
                [*tag["aliases"], *alias_review.get("add", [])]
            )
            tag["aliases"].sort(key=str.casefold)
            lifecycle["alias_review"] = {
                "review_reference": review_reference,
                "accepted": alias_review.get("add", []),
                "rejected": alias_review.get("reject", []),
                "reason": alias_review["reason"],
            }

        if tag_id in inactivate_active:
            tag["status"] = "inactive"
            tag["merged_into"] = None
            lifecycle["reason"] = "active_tag_failed_corpus_semantic_review"
            lifecycle["decision_detail"] = inactivate_active[tag_id]
            decision = (
                "inactivated_active"
                if before_status == "active"
                else "retained_inactive"
            )
        elif tag_id in promote:
            tag["status"] = "active"
            tag["merged_into"] = None
            lifecycle.pop("reason", None)
            if before_status == "candidate":
                lifecycle["promoted_from"] = "candidate"
                decision = "promoted_candidate"
            else:
                decision = "retained_active"
        elif tag_id in reactivate:
            tag["status"] = "active"
            tag["merged_into"] = None
            lifecycle.pop("reason", None)
            if before_status == "inactive":
                lifecycle["reactivated_from"] = "inactive"
                decision = "reactivated_inactive"
            else:
                decision = "retained_active"
        elif before_status == "candidate":
            tag["status"] = "inactive"
            tag["merged_into"] = None
            lifecycle["reason"] = _inactive_reason(
                tag, has_rewrite=tag_id in rewrites
            )
            decision = "inactivated_candidate"
        elif before_status == "active":
            decision = "retained_active"
        elif before_status == "inactive":
            decision = "retained_inactive"
        else:
            decision = "retained_merged"

        lifecycle["consolidation_decision"] = decision
        lifecycle["consolidation_review_reference"] = review_reference
        if tag_id in referenced_inactive_ids and tag["status"] != "active":
            lifecycle["referenced_assignment_review"] = {
                "review_reference": review_reference,
                "outcome": (
                    "reassigned_to_active_concept"
                    if tag_id in rewrites
                    else "removed_from_literal_taxonomy_and_preserved_as_context"
                ),
            }
        if tag["status"] == "active":
            tag["semantic_contract"] = _semantic_contract(tag)
        else:
            tag.pop("semantic_contract", None)
        decisions.update([decision])
        lifecycle_rows.append(
            {
                "id": tag_id,
                "name_before": original_name,
                "name_after": tag["name"],
                "status_before": before_status,
                "status_after": tag["status"],
                "decision": decision,
                "reason": lifecycle.get("reason"),
            }
        )

    updated["description"] = (
        "Corpus-reviewed lifecycle-aware owner-tag registry. Production "
        "consumers expose only active canonical tags and approved aliases; "
        "every active tag carries a click-through semantic contract."
    )
    updated["consolidation"] = {
        "review_reference": review_reference,
        "approved_baseline_ref": configuration["approved_baseline_ref"],
        "repository_is_source_of_truth": True,
        "live_state_used": False,
        "decision_model": (
            "maximum information value with minimum semantic noise; cohort "
            "size is a diagnostic rather than an approval rule"
        ),
    }
    updated["tags"].sort(key=lambda item: str(item["name"]).casefold())
    validated = TagCatalogue(updated)
    after_counts = validated.lifecycle_counts
    report = {
        "lifecycle_counts_before": dict(sorted(before_counts.items())),
        "lifecycle_counts_after": dict(sorted(after_counts.items())),
        "decision_counts": dict(sorted(decisions.items())),
        "stable_id_count": len(validated.all_tags_by_id),
        "active_contract_count": sum(
            isinstance(tag.get("semantic_contract"), dict)
            for tag in updated["tags"]
            if tag["status"] == "active"
        ),
        "rows": lifecycle_rows,
    }
    return updated, report


def _proposal_score(proposal: dict[str, Any]) -> int:
    score = proposal.get("confidence", {}).get("score")
    return score if isinstance(score, int) else 0


def _known_source_ids(dossier: dict[str, Any]) -> set[str]:
    return {
        source["id"]
        for source in dossier.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }


def _normalize_proposal(
    proposal: dict[str, Any],
    target: Any,
    *,
    rewritten: bool,
) -> dict[str, Any]:
    normalized = deepcopy(proposal)
    source_name = str(proposal.get("name", "")).strip()
    normalized["tag_id"] = target.id
    normalized["name"] = target.name
    if rewritten and normalize_tag_name(source_name) != target.normalized_name:
        normalized["summary"] = (
            f"{proposal['summary']} This evidence qualifies for the broader "
            f"{target.name} cohort under the approved corpus taxonomy contract."
        )
        normalized["taxonomy_value"] = target.semantic_contract.get(
            "membership", target.name
        )
    return normalized


def _merge_proposals(
    existing: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    winner, other = (
        (candidate, existing)
        if _proposal_score(candidate) > _proposal_score(existing)
        else (existing, candidate)
    )
    merged = deepcopy(winner)
    merged["source_ids"] = list(
        dict.fromkeys(
            [
                *existing.get("source_ids", []),
                *candidate.get("source_ids", []),
            ]
        )
    )
    summaries = _unique(
        [str(existing.get("summary", "")), str(candidate.get("summary", ""))]
    )
    if len(summaries) > 1:
        merged["summary"] = " ".join(
            summary if summary.endswith((".", "!", "?")) else f"{summary}."
            for summary in summaries
        )
    return merged


def _company_qualifies(
    tag: Any,
    proposal: dict[str, Any],
    *,
    person_id: int,
    manual_membership: dict[str, list[int]],
) -> bool:
    if tag.id in manual_membership:
        return person_id in set(manual_membership[tag.id])
    facets = {facet.casefold() for facet in tag.facets}
    if not facets & {"company", "company association"}:
        return True
    summary = str(proposal.get("summary", ""))
    if GENERIC_COMPANY_NEGATIVE.search(summary) and not GENERIC_COMPANY_POSITIVE.search(
        summary
    ):
        return False
    return bool(GENERIC_COMPANY_POSITIVE.search(summary))


def _fact_line(proposal: dict[str, Any]) -> str | None:
    name = proposal.get("name")
    summary = proposal.get("summary")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None
    return f"{name.strip()}: {summary.strip()}"


def _set_fact_notes(dossier: dict[str, Any], facts: list[str]) -> None:
    review = dossier.setdefault("review", {})
    prior = review.get("notes")
    prior_text = prior.strip() if isinstance(prior, str) else ""
    existing_facts: list[str] = []
    if FACT_NOTE_HEADING in prior_text:
        prior_text, existing_context = prior_text.split(FACT_NOTE_HEADING, 1)
        prior_text = prior_text.rstrip()
        existing_facts = [
            match.strip()
            for match in re.findall(
                r"\[\d+\]\s*(.*?)(?=\s+\[\d+\]\s|$)",
                existing_context.strip(),
                flags=re.DOTALL,
            )
            if match.strip()
        ]
    unique_facts = _unique([*existing_facts, *facts])
    if unique_facts:
        context = FACT_NOTE_HEADING + " " + " ".join(
            f"[{index}] {fact}" for index, fact in enumerate(unique_facts, 1)
        )
        review["notes"] = f"{prior_text}\n\n{context}".strip()
    elif prior_text:
        review["notes"] = prior_text
    else:
        review.pop("notes", None)


def _tags_from_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    value = document.get("proposed_tags")
    if not isinstance(value, list):
        raise ValueError("proposed_tags must be a list")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError("proposed_tags entries must be objects")
    return value


def _prepare_one_dossier(
    current: dict[str, Any],
    baseline: dict[str, Any] | None,
    catalogue: TagCatalogue,
    configuration: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = deepcopy(current)
    owner = current.get("owner", {})
    person_id = owner.get("person_id")
    if not isinstance(person_id, int):
        raise ValueError("owner.person_id must be an integer")
    display_name = str(owner.get("display_name", ""))
    record_type = current.get("record_type")
    before = _tags_from_document(current)
    if record_type == "unresolved_placeholder":
        return updated, {
            "person_id": person_id,
            "display_name": display_name,
            "record_type": record_type,
            "status": "unresolved_preserved",
            "before_ids": [item.get("tag_id") for item in before],
            "after_ids": [item.get("tag_id") for item in before],
            "dropped_fact_count": 0,
        }

    known_sources = _known_source_ids(current)
    rewrites: dict[str, list[str]] = configuration["assignment_rewrites"]
    suppressions = set(
        configuration.get("assignment_suppressions", {}).get(str(person_id), [])
    )
    manual_membership = configuration.get("manual_company_membership", {})
    selected: dict[str, dict[str, Any]] = {}
    selected_origins: dict[str, set[str]] = defaultdict(set)
    facts: list[str] = []
    actions: Counter[str] = Counter()

    current_ids = {
        str(item.get("tag_id"))
        for item in before
        if isinstance(item.get("tag_id"), str)
    }
    proposals_with_origin: list[tuple[dict[str, Any], str]] = [
        (item, "current") for item in before
    ]
    if baseline is not None:
        for proposal in _tags_from_document(baseline):
            tag_id = proposal.get("tag_id")
            if not isinstance(tag_id, str) or tag_id in current_ids:
                continue
            cited = proposal.get("source_ids")
            if not isinstance(cited, list) or not set(cited) <= known_sources:
                actions.update(["historical_skipped_missing_sources"])
                continue
            proposals_with_origin.append((proposal, "historical"))

    for proposal, origin in proposals_with_origin:
        source_id = proposal.get("tag_id")
        if not isinstance(source_id, str):
            if origin == "current":
                fact = _fact_line(proposal)
                if fact:
                    facts.append(fact)
            actions.update(["invalid_source_reference_removed"])
            continue
        target_ids = rewrites.get(source_id)
        rewritten = target_ids is not None
        if target_ids is None:
            selected_tag = catalogue.all_tags_by_id.get(source_id)
            target_ids = (
                [selected_tag.id]
                if selected_tag is not None and selected_tag.status == "active"
                else []
            )
        accepted_target = False
        for target_id in target_ids:
            if target_id in suppressions:
                actions.update(["explicit_assignment_suppression"])
                continue
            target = catalogue.tags_by_id.get(target_id)
            if target is None:
                raise ValueError(f"rewrite target is not active: {target_id}")
            normalized = _normalize_proposal(
                proposal, target, rewritten=rewritten
            )
            if not set(normalized.get("source_ids", [])) <= known_sources:
                actions.update(["assignment_skipped_missing_sources"])
                continue
            if target.id == "tag_0249" and record_type != "institution":
                actions.update(["government_owned_person_removed"])
                continue
            if not _company_qualifies(
                target,
                normalized,
                person_id=person_id,
                manual_membership=manual_membership,
            ):
                actions.update(["company_contract_removal"])
                continue
            if target_id in selected:
                selected[target_id] = _merge_proposals(
                    selected[target_id], normalized
                )
            else:
                selected[target_id] = normalized
            selected_origins[target_id].add(source_id)
            accepted_target = True
            actions.update(
                [
                    "rewritten_assignment"
                    if rewritten
                    else f"retained_{origin}_assignment"
                ]
            )
        if origin == "current" and not accepted_target:
            fact = _fact_line(proposal)
            if fact:
                facts.append(fact)

    required_companions = configuration.get("required_companions", {})
    changed = True
    while changed:
        changed = False
        for child_id, companion_ids in required_companions.items():
            if child_id not in selected:
                continue
            child = selected[child_id]
            for companion_id in companion_ids:
                if companion_id in selected or companion_id in suppressions:
                    continue
                target = catalogue.tags_by_id[companion_id]
                companion = _normalize_proposal(
                    child, target, rewritten=True
                )
                selected[companion_id] = companion
                selected_origins[companion_id].add(child_id)
                actions.update(["required_companion_added"])
                changed = True

    for rule in configuration.get("specificity_rules", []):
        if not set(rule["when_any"]) & set(selected):
            continue
        for tag_id in rule["remove"]:
            removed = selected.pop(tag_id, None)
            if removed is None:
                continue
            fact = _fact_line(removed)
            if fact:
                facts.append(fact)
            selected_origins.pop(tag_id, None)
            actions.update(["specificity_parent_removed"])

    proposed = sorted(
        selected.values(), key=lambda item: str(item["name"]).casefold()
    )
    updated["proposed_tags"] = proposed
    _set_fact_notes(updated, facts)
    errors, warnings = validate_dossier(updated, tag_catalogue=catalogue)
    if errors:
        raise ValueError(
            f"{person_id} ({display_name}) failed dossier validation: "
            + "; ".join(errors)
        )
    before_ids = [str(item.get("tag_id")) for item in before]
    after_ids = [str(item.get("tag_id")) for item in proposed]
    status = (
        "changed"
        if _json_bytes(updated) != _json_bytes(current)
        else "unchanged"
    )
    return updated, {
        "person_id": person_id,
        "display_name": display_name,
        "record_type": record_type,
        "status": status,
        "before_ids": before_ids,
        "after_ids": after_ids,
        "added_ids": sorted(set(after_ids) - set(before_ids)),
        "removed_ids": sorted(set(before_ids) - set(after_ids)),
        "dropped_fact_count": len(_unique(facts)),
        "actions": dict(sorted(actions.items())),
        "validation_warning_count": len(warnings),
    }


def _distribution(values: list[int]) -> dict[str, float | int]:
    ordered = sorted(values)
    count = len(ordered)
    median: float | int
    if not ordered:
        median = 0
    elif count % 2:
        median = ordered[count // 2]
    else:
        median = (ordered[count // 2 - 1] + ordered[count // 2]) / 2
    return {
        "count": count,
        "total": sum(ordered),
        "average": round(sum(ordered) / count, 3) if count else 0,
        "median": median,
        "minimum": min(ordered, default=0),
        "maximum": max(ordered, default=0),
    }


def _cohort_metrics(
    dossiers: dict[str, dict[str, Any]],
    catalogue: TagCatalogue,
) -> dict[str, Any]:
    cohorts: dict[str, set[int]] = defaultdict(set)
    tag_counts: list[int] = []
    high_assignment_records: list[dict[str, Any]] = []
    for dossier in dossiers.values():
        if dossier.get("record_type") not in {"person", "institution"}:
            continue
        person_id = dossier["owner"]["person_id"]
        assignments = dossier.get("proposed_tags", [])
        tag_counts.append(len(assignments))
        if len(assignments) > 10:
            high_assignment_records.append(
                {
                    "person_id": person_id,
                    "display_name": dossier["owner"].get("display_name"),
                    "assignment_count": len(assignments),
                }
            )
        for proposal in assignments:
            cohorts[str(proposal["tag_id"])].add(person_id)

    frequencies = [
        {
            "tag_id": tag.id,
            "name": tag.name,
            "dossier_record_count": len(cohorts.get(tag.id, set())),
        }
        for tag in catalogue.tags_by_id.values()
    ]
    frequencies.sort(key=lambda row: (-row["dossier_record_count"], row["name"]))
    cohort_sets: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for tag_id, people in cohorts.items():
        if people:
            cohort_sets[tuple(sorted(people))].append(tag_id)
    identical = [
        {
            "person_ids": list(people),
            "tag_ids": sorted(tag_ids),
            "dossier_record_count": len(people),
        }
        for people, tag_ids in cohort_sets.items()
        if len(tag_ids) > 1
    ]
    return {
        "assignment_distribution": _distribution(tag_counts),
        "active_tag_count": len(catalogue.tags_by_id),
        "cohorts_below_5": sum(row["dossier_record_count"] < 5 for row in frequencies),
        "cohorts_5_to_50": sum(
            5 <= row["dossier_record_count"] <= 50 for row in frequencies
        ),
        "cohorts_above_50": sum(row["dossier_record_count"] > 50 for row in frequencies),
        "largest_cohorts": frequencies[:25],
        "zero_record_active_tags": [
            row for row in frequencies if row["dossier_record_count"] == 0
        ],
        "high_assignment_records": high_assignment_records,
        "identical_active_cohorts": sorted(
            identical,
            key=lambda row: (-row["dossier_record_count"], row["tag_ids"]),
        ),
        "frequencies": frequencies,
    }


def prepare_corpus(
    dossier_directory: Path,
    baseline_dossiers: dict[str, dict[str, Any]],
    catalogue: TagCatalogue,
    configuration: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    prepared: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    source_paths = sorted(dossier_directory.glob("*.research.json"))
    for index, path in enumerate(source_paths, 1):
        current = _load_object(path)
        updated, row = _prepare_one_dossier(
            current,
            baseline_dossiers.get(path.name),
            catalogue,
            configuration,
        )
        prepared[path.name] = updated
        row["batch"] = (index - 1) // 100 + 1
        rows.append(row)

    status_counts = Counter(row["status"] for row in rows)
    action_counts: Counter[str] = Counter()
    for row in rows:
        action_counts.update(row.get("actions", {}))
    report = {
        "dossier_count": len(rows),
        "usable_dossier_count": sum(
            row["record_type"] in {"person", "institution"} for row in rows
        ),
        "unresolved_preserved_count": status_counts["unresolved_preserved"],
        "changed_dossier_count": status_counts["changed"],
        "unchanged_dossier_count": status_counts["unchanged"],
        "status_counts": dict(sorted(status_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "dropped_fact_count": sum(row["dropped_fact_count"] for row in rows),
        "batch_count": max((row["batch"] for row in rows), default=0),
        "rows": rows,
    }
    return prepared, report


def _verify_backup(source: Path, backup: Path) -> None:
    source_files = sorted(path.name for path in source.glob("*.research.json"))
    backup_files = sorted(path.name for path in backup.glob("*.research.json"))
    if source_files != backup_files:
        raise ValueError("backup dossier inventory does not match source")
    for name in source_files:
        if _sha256(source / name) != _sha256(backup / name):
            raise ValueError(f"backup verification failed for {name}")


def _referenced_nonactive_ids(
    dossier_directory: Path,
    catalogue: TagCatalogue,
) -> set[str]:
    result: set[str] = set()
    for path in dossier_directory.glob("*.research.json"):
        dossier = _load_object(path)
        for proposal in dossier.get("proposed_tags", []):
            if not isinstance(proposal, dict):
                continue
            tag_id = proposal.get("tag_id")
            tag = catalogue.all_tags_by_id.get(str(tag_id))
            if tag is not None and tag.status != "active":
                result.add(tag.id)
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=(
            "Consolidate the repository owner-tag lifecycle catalogue and "
            "schema-v8 dossier corpus. Repository data is the sole source of "
            "truth; live state is never read. Dry-run is the default."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--catalogue", type=Path, default=DEFAULT_TAG_CATALOGUE_PATH
    )
    parser.add_argument("--dossiers", type=Path, default=DEFAULT_DOSSIERS)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    configuration = _load_object(args.config.resolve(strict=True))
    catalogue_path = args.catalogue.resolve(strict=True)
    dossier_directory = args.dossiers.resolve(strict=True)
    current_catalogue_document = _load_object(catalogue_path)
    current_catalogue = TagCatalogue(
        current_catalogue_document, source=str(catalogue_path)
    )
    referenced_nonactive_ids = _referenced_nonactive_ids(
        dossier_directory, current_catalogue
    )
    updated_catalogue_document, catalogue_report = prepare_catalogue(
        current_catalogue_document,
        configuration,
        referenced_inactive_ids=referenced_nonactive_ids,
    )
    updated_catalogue = TagCatalogue(
        updated_catalogue_document, source=str(catalogue_path)
    )
    baseline_ref = configuration["approved_baseline_ref"]
    baseline_dossiers = _load_git_dossiers(baseline_ref, dossier_directory)
    prepared_dossiers, dossier_report = prepare_corpus(
        dossier_directory,
        baseline_dossiers,
        updated_catalogue,
        configuration,
    )
    cohort_report = _cohort_metrics(prepared_dossiers, updated_catalogue)

    nonactive_references: list[dict[str, Any]] = []
    for name, dossier in prepared_dossiers.items():
        if dossier.get("record_type") == "unresolved_placeholder":
            continue
        for index, proposal in enumerate(dossier.get("proposed_tags", [])):
            inspected = updated_catalogue.inspect(
                tag_id=proposal.get("tag_id"), name=str(proposal.get("name", ""))
            )
            if inspected.get("status") != "active":
                nonactive_references.append(
                    {
                        "dossier": name,
                        "index": index,
                        "tag_id": proposal.get("tag_id"),
                        "name": proposal.get("name"),
                        "status": inspected.get("status"),
                    }
                )
    if nonactive_references:
        raise ValueError(
            f"prepared usable dossiers contain non-active tags: "
            f"{nonactive_references[:10]}"
        )

    generated_at = datetime.now(UTC)
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    audit_path = args.audit or (
        DEFAULT_AUDIT_DIR
        / f"corpus-consolidation-{'apply' if args.apply else 'dry-run'}-{stamp}.json"
    )
    audit: dict[str, Any] = {
        "schema_version": 1,
        "operation": "repository_owner_tag_corpus_consolidation",
        "generated_at": generated_at.isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "review_reference": configuration["review_reference"],
        "approved_baseline_ref": baseline_ref,
        "repository_is_source_of_truth": True,
        "live_read_performed": False,
        "live_comparison_performed": False,
        "live_write_performed": False,
        "catalogue": catalogue_report,
        "dossiers": dossier_report,
        "cohorts": cohort_report,
        "prepared_nonactive_reference_count": len(nonactive_references),
    }

    if args.apply:
        backup = args.backup or (
            REPO_ROOT
            / "output"
            / "backups"
            / f"owner-tag-corpus-pre-consolidation-{stamp}"
        )
        if backup.exists():
            parser.error(f"backup path already exists: {backup}")
        backup.mkdir(parents=True)
        shutil.copy2(catalogue_path, backup / catalogue_path.name)
        backup_dossiers = backup / "dossiers"
        shutil.copytree(dossier_directory, backup_dossiers)
        _verify_backup(dossier_directory, backup_dossiers)
        if _sha256(catalogue_path) != _sha256(backup / catalogue_path.name):
            raise ValueError("catalogue backup verification failed")

        atomic_write_json(catalogue_path, updated_catalogue_document)
        written = 0
        for name, document in prepared_dossiers.items():
            path = dossier_directory / name
            if path.read_bytes() == _json_bytes(document):
                continue
            atomic_write_json(path, document)
            if _sha256(path) != _sha256_bytes(_json_bytes(document)):
                raise ValueError(f"post-write verification failed for {path}")
            written += 1
        audit["backup_directory"] = str(backup.resolve())
        audit["backup_verified"] = True
        audit["written_dossier_count"] = written
        audit["catalogue_written"] = True

    atomic_write_json(audit_path, audit)
    summary = {
        "mode": audit["mode"],
        "live_read_performed": False,
        "catalogue": {
            "before": catalogue_report["lifecycle_counts_before"],
            "after": catalogue_report["lifecycle_counts_after"],
            "decisions": catalogue_report["decision_counts"],
        },
        "dossiers": {
            key: value
            for key, value in dossier_report.items()
            if key not in {"rows"}
        },
        "cohorts": {
            key: value
            for key, value in cohort_report.items()
            if key not in {"frequencies", "identical_active_cohorts"}
        },
        "audit": str(audit_path.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
