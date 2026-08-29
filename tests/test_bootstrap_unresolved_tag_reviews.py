from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "bootstrap_unresolved_tag_reviews.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("bootstrap_unresolved_tag_reviews", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_eligible_requires_completed_empty_unresolved_placeholder():
    module = load_module()
    dossier = {
        "record_type": "unresolved_placeholder",
        "research_status": "insufficient_evidence",
        "review": {"status": "complete"},
        "proposed_tags": [],
        "sources": [{"id": "S1"}],
    }
    assert module.eligible(dossier)
    dossier["proposed_tags"] = [{"tag_id": "tag_0001"}]
    assert not module.eligible(dossier)


def test_checkpoint_records_identity_hash_and_zero_reason(tmp_path):
    module = load_module()
    path = tmp_path / "10.research.json"
    dossier = {"owner": {"person_id": 10, "display_name": "Unknown Owner"}}
    path.write_text(json.dumps(dossier), encoding="utf-8")
    checkpoint = module.checkpoint_for(path, dossier)
    assert checkpoint["person_id"] == 10
    assert checkpoint["canonical_tags"] == []
    assert checkpoint["catalogue_candidates"] == []
    assert checkpoint["zero_tag_reason"]
    assert len(checkpoint["dossier_sha256"]) == 64
