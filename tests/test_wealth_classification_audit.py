from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "audit_wealth_classification_corpus.py"
)
SKILL = SCRIPT.parents[1] / "SKILL.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("wealth_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _classification(value: str) -> dict:
    return {
        "classification": value,
        "label": "Unknown" if value == "unknown" else value,
        "summary": "summary",
        "confidence": {"score": 80, "band": "medium", "reason": "reason"},
        "source_ids": ["S1"],
    }


def _dossier(person_id: int, *, primary: str = "manufacturing", origin: str = "unknown") -> dict:
    return {
        "record_type": "person",
        "owner": {"person_id": person_id, "display_name": f"Owner {person_id}"},
        "wealth_creation_industry": _classification("manufacturing"),
        "primary_industry": _classification(primary),
        "wealth_origin": _classification(origin),
        "wealth_relationship": _classification("founder"),
        "sources": [{"id": "S1"}],
    }


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _terminal_decision() -> dict:
    return {
        "decision": "retain_unknown",
        "reason": "The necessary origin premise remains unsupported after review.",
        "strongest_alternative": "Self-made was considered but the principal asset mechanism is unresolved.",
        "source_ids": ["S1"],
        "policy_checks": {
            "direct_evidence_checked": True,
            "reasoned_inference_checked": True,
            "less_specific_value_checked": True,
            "silence_not_used": True,
        },
    }


def test_audit_requires_hash_bound_terminal_review(tmp_path: Path) -> None:
    module = _load_module()
    dossiers = tmp_path / "dossiers"
    checkpoints = tmp_path / "reviews"
    path = dossiers / "1.research.json"
    dossier = _dossier(1)
    _write(path, dossier)

    pending = module.audit_corpus(dossiers, checkpoints)
    assert pending["summary"]["statuses"] == {"pending_review": 1}
    assert pending["summary"]["priority_reasons"] == {
        "founder_built_origin_review": 1
    }
    assert not module._is_complete(pending)

    module.bootstrap_pending_reviews(dossiers, checkpoints)
    checkpoint_path = checkpoints / "1.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["status"] = "reviewed"
    checkpoint["decisions"] = {"wealth_origin": _terminal_decision()}
    _write(checkpoint_path, checkpoint)

    reviewed = module.audit_corpus(dossiers, checkpoints)
    assert reviewed["summary"]["statuses"] == {
        "reviewed_retained_unknown": 1
    }
    assert module._is_complete(reviewed)

    dossier["owner"]["display_name"] = "Changed owner"
    _write(path, dossier)
    stale = module.audit_corpus(dossiers, checkpoints)
    assert stale["summary"]["statuses"] == {"invalid_or_stale_review": 1}
    assert stale["summary"]["error_count"] > 0


def test_audit_flags_origin_sector_fallback_and_exempts_non_people(
    tmp_path: Path,
) -> None:
    module = _load_module()
    dossiers = tmp_path / "dossiers"
    checkpoints = tmp_path / "reviews"
    person = _dossier(2, primary="unknown", origin="self_made")
    _write(dossiers / "2.research.json", person)
    institution = _dossier(3, primary="unknown")
    institution["record_type"] = "institution"
    for field in module.WEALTH_FIELDS:
        institution[field] = _classification("unknown")
    _write(dossiers / "3.research.json", institution)

    report = module.audit_corpus(dossiers, checkpoints)

    assert report["summary"]["fallback_violation_count"] == 1
    assert report["summary"]["statuses"] == {
        "non_person_not_applicable": 1,
        "pending_review": 1,
    }
    assert not module._is_complete(report)


def test_record_retained_review_serialises_current_dossier_reasoning(
    tmp_path: Path,
) -> None:
    module = _load_module()
    dossiers = tmp_path / "dossiers"
    checkpoints = tmp_path / "reviews"
    dossier = _dossier(5)
    dossier["wealth_origin"]["summary"] = (
        "Founder activity is documented but principal-wealth materiality is unresolved."
    )
    dossier["wealth_origin"]["confidence"]["reason"] = (
        "No reliable source links founder equity or proceeds to the principal fortune."
    )
    _write(dossiers / "5.research.json", dossier)

    result = module.record_retained_reviews(dossiers, checkpoints, [5])
    assert result == {"recorded_reviewed": 1}

    checkpoint = json.loads((checkpoints / "5.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "reviewed"
    decision = checkpoint["decisions"]["wealth_origin"]
    assert decision["decision"] == "retain_unknown"
    assert "Founder activity is documented" in decision["reason"]
    assert "Broad Self-made" in decision["strongest_alternative"]
    assert all(decision["policy_checks"].values())

    report = module.audit_corpus(dossiers, checkpoints)
    assert report["summary"]["statuses"] == {"reviewed_retained_unknown": 1}


def test_no_unknown_person_is_terminal_without_checkpoint(tmp_path: Path) -> None:
    module = _load_module()
    dossiers = tmp_path / "dossiers"
    dossier = _dossier(4, origin="self_made")
    _write(dossiers / "4.research.json", dossier)

    report = module.audit_corpus(dossiers, tmp_path / "reviews")

    assert report["summary"]["statuses"] == {"no_unknown_fields": 1}
    assert module._is_complete(report)


def test_skill_documents_hash_bound_wealth_audit() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "## Existing-dossier wealth-classification audit" in skill
    assert "audit_wealth_classification_corpus.py" in skill
    assert "SHA-256-bound checkpoint" in skill
    assert "--strict" in skill
