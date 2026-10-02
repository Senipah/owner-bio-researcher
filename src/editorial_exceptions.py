"""Explicit, owner-specific human approvals for withholding biographies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY = Path(__file__).resolve().parents[1] / "config" / "owner-editorial-exceptions.json"


def biographies_withheld(dossier: dict[str, Any]) -> bool:
    """Fail closed for a claimed exception; absence keeps the normal contract."""
    reference = dossier.get("biography_exception")
    if reference is None:
        return False
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    matches = [
        item for item in registry["exceptions"]
        if item["id"] == reference
        and item["person_id"] == dossier.get("owner", {}).get("person_id")
        and item["kind"] == "withhold_biographies"
        and item.get("approved_by") == "user"
        and item.get("approval")
    ]
    if len(matches) != 1 or dossier.get("record_type") != "person":
        raise ValueError("biography_exception has no matching owner-specific human approval")
    if any(dossier.get(field) is not None for field in (
        "biography", "long_biography", "biography_brief", "editorial_assessment",
    )):
        raise ValueError("biography_exception requires both biographies, brief and assessment to be null")
    if not isinstance(dossier.get("editorial_note"), dict):
        raise ValueError("biography_exception requires a sourced editorial_note")
    if any(
        isinstance(proposal, dict)
        and proposal.get("field") in {"biography", "long_biography"}
        for proposal in dossier.get("proposed_details", [])
    ):
        raise ValueError("biography_exception must not propose biography field changes")
    return True
