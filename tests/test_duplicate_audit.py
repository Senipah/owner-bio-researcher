from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from audit_owner_duplicates import build_parser
from duplicate_audit.adjudication import adjudicate_candidate
from duplicate_audit.core import (
    build_identity_card,
    connected_candidate_clusters,
    discover_candidates,
    embedding_views,
    pair_signals,
    resolve_final_classification,
)
from duplicate_audit.live import export_owner_snapshot
from duplicate_audit.openai_api import OpenAIAPIClient, StructuredResult
from duplicate_audit.report import render_audit_report, summarize_candidates
from src.io_utils import new_owner


def _owner(person_id: int, first_name: str, last_name: str) -> dict[str, Any]:
    owner = new_owner(
        person_id=person_id,
        profile_url=f"https://example.test/person?id={person_id}",
        report={
            "first_name": first_name,
            "last_name": last_name,
            "akas": "",
            "known_for": "",
            "employers": [],
            "employer_display": "",
            "nationality": "",
            "image_url": "",
        },
    )
    return owner


def _card(person_id: int, name: str) -> dict[str, Any]:
    first_name, last_name = name.split(" ", 1)
    return build_identity_card(_owner(person_id, first_name, last_name))


def test_identity_card_is_an_explicit_privacy_boundary() -> None:
    owner = _owner(10, "Ada", "Lovelace")
    owner["details"] = {
        "display_name": {"value": "Countess of Lovelace"},
        "birth_year": {"value": "1815"},
        "biography": {"value": "Sensitive biography"},
        "long_biography": {"value": "Sensitive long biography"},
        "internal_notes": {"value": "Never upload this"},
    }
    owner["social_media_profiles"] = [
        {"type": "Website", "url": "https://example.test/ada"}
    ]

    card = build_identity_card(owner)

    serialized = json.dumps(card)
    assert card["details"]["display_name"] == "Countess of Lovelace"
    assert card["details"]["birth_year"] == "1815"
    assert "Sensitive" not in serialized
    assert "Never upload" not in serialized
    assert "biography" not in serialized
    assert "internal_notes" not in serialized


def test_embedding_views_keep_name_and_context_separate() -> None:
    owner = _owner(11, "Grace", "Hopper")
    owner["report"]["employer_display"] = "US Navy"
    card = build_identity_card(owner)

    views = embedding_views(card)

    assert "Grace Hopper" in views["name"]
    assert "US Navy" not in views["name"]
    assert "US Navy" in views["identity"]


def test_embedding_neighbours_create_ai_candidate_without_name_rule() -> None:
    cards = [
        _card(1, "Alpha Person"),
        _card(2, "Completely Different"),
        _card(3, "Third Record"),
    ]
    embeddings = {
        "name": np.asarray([[1.0, 0.0], [0.999, 0.001], [0.0, 1.0]]),
        "identity": np.asarray([[1.0, 0.0], [0.998, 0.002], [0.0, 1.0]]),
    }

    candidates = discover_candidates(
        cards,
        embeddings,
        thresholds={"name": 0.95, "identity": 0.95},
        top_k=1,
    )

    assert [candidate["person_ids"] for candidate in candidates] == [[1, 2]]
    assert candidates[0]["retrieval"]["embedding_scores"]["name"] > 0.99
    assert candidates[0]["retrieval"]["signals"] == []


def test_exact_signal_retrieves_pair_but_does_not_classify_it() -> None:
    left = _card(20, "Same Name")
    right = _card(21, "Same Name")
    embeddings = {
        "name": np.asarray([[1.0, 0.0], [0.0, 1.0]]),
        "identity": np.asarray([[1.0, 0.0], [0.0, 1.0]]),
    }

    candidates = discover_candidates(
        [left, right],
        embeddings,
        thresholds={"name": 0.99, "identity": 0.99},
        top_k=1,
    )

    assert len(candidates) == 1
    assert candidates[0]["retrieval"]["maximum_embedding_score"] is None
    assert candidates[0].get("final_classification") is None
    assert pair_signals(left, right)[0]["type"] == "shared_normalized_name"


def test_probable_duplicate_requires_verifier_agreement() -> None:
    primary = {"classification": "probable_duplicate"}

    assert resolve_final_classification(primary, None) == "needs_manual_review"
    assert (
        resolve_final_classification(
            primary, {"classification": "probable_duplicate"}
        )
        == "probable_duplicate"
    )
    assert (
        resolve_final_classification(
            primary, {"classification": "possible_duplicate"}
        )
        == "possible_duplicate"
    )
    assert (
        resolve_final_classification(
            primary, {"classification": "probably_distinct"}
        )
        == "needs_manual_review"
    )


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, Any]:
        return self.payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


def test_openai_client_uses_embeddings_endpoint_and_preserves_order() -> None:
    session = _FakeSession(
        [
            _FakeResponse(
                {
                    "data": [
                        {"index": 1, "embedding": [0.0, 1.0]},
                        {"index": 0, "embedding": [1.0, 0.0]},
                    ]
                }
            )
        ]
    )
    client = OpenAIAPIClient("secret", session=session)

    vectors = client.create_embeddings(
        ["first", "second"], model="embedding-test", dimensions=2
    )

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert session.calls[0]["url"].endswith("/embeddings")
    assert session.calls[0]["json"]["dimensions"] == 2


def test_openai_structured_response_disables_storage() -> None:
    judgment = {
        "classification": "possible_duplicate",
        "confidence": 68,
        "summary": "Plausible but incomplete.",
        "evidence_for": ["Names are related."],
        "evidence_against": [],
        "missing_evidence": ["Birth dates"],
        "more_complete_person_id": None,
        "completeness_reason": "Neither is clearly richer.",
    }
    session = _FakeSession(
        [
            _FakeResponse(
                {
                    "id": "resp_test",
                    "model": "judge-test",
                    "status": "completed",
                    "usage": {"total_tokens": 100},
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": json.dumps(judgment)}
                            ],
                        }
                    ],
                }
            )
        ]
    )
    client = OpenAIAPIClient("secret", session=session)

    result = client.create_structured_response(
        model="judge-test",
        instructions="Judge safely.",
        input_text="{}",
        schema_name="test_schema",
        schema={"type": "object"},
    )

    assert result.value == judgment
    request = session.calls[0]["json"]
    assert request["store"] is False
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True


class _FakeJudgmentClient:
    def __init__(self, values: list[dict[str, Any]]) -> None:
        self.values = list(values)
        self.calls = 0

    def create_structured_response(self, **_: Any) -> StructuredResult:
        self.calls += 1
        return StructuredResult(
            value=self.values.pop(0),
            response_id=f"resp_{self.calls}",
            model="test-model",
            usage={},
        )


def _judgment(classification: str) -> dict[str, Any]:
    return {
        "classification": classification,
        "confidence": 90,
        "summary": "Test judgment",
        "evidence_for": [],
        "evidence_against": [],
        "missing_evidence": [],
        "more_complete_person_id": None,
        "completeness_reason": "Equal",
    }


def test_probable_primary_runs_independent_verifier() -> None:
    client = _FakeJudgmentClient(
        [_judgment("probable_duplicate"), _judgment("possible_duplicate")]
    )

    result = adjudicate_candidate(
        client,  # type: ignore[arg-type]
        left=_card(31, "One Person"),
        right=_card(32, "Won Person"),
        retrieval={},
        judge_model="primary",
        verifier_model="verifier",
    )

    assert client.calls == 2
    assert result["final_classification"] == "possible_duplicate"
    assert result["verifier"] is not None


def test_candidate_clusters_only_include_review_worthy_edges() -> None:
    candidates = [
        {"person_ids": [1, 2], "final_classification": "probable_duplicate"},
        {"person_ids": [2, 3], "final_classification": "possible_duplicate"},
        {"person_ids": [3, 4], "final_classification": "probably_distinct"},
    ]

    assert connected_candidate_clusters(candidates) == [[1, 2, 3]]


def test_live_export_marks_snapshot_complete(monkeypatch: Any, tmp_path: Path) -> None:
    page = """
    <table class="jsYayContactResultsTable"><tr><th>x</th></tr><tr>
      <td></td><td><a href="/detail.htm?id=42"><span>Ada</span> Lovelace</a></td>
      <td></td><td></td><td></td><td>British</td><td></td><td></td>
    </tr></table><ul class="jsPagination"></ul>
    """
    monkeypatch.setattr("duplicate_audit.live.fetch_html", lambda *args, **kwargs: page)
    destination = tmp_path / "live.json"

    document = export_owner_snapshot(object(), output_path=destination)  # type: ignore[arg-type]

    assert document["source"]["complete"] is True
    assert document["source"]["owner_count"] == 1
    assert document["owners"][0]["person_id"] == 42
    assert json.loads(destination.read_text(encoding="utf-8"))["source"]["complete"]


def test_html_report_escapes_owner_data_and_has_manual_export() -> None:
    card = _card(50, "Unsafe Name")
    card["known_for"] = "<script>alert(1)</script>"
    candidate = {
        "candidate_id": "pair_50_51",
        "person_ids": [50, 51],
        "retrieval": {"embedding_scores": {}, "signals": []},
        "records": [card, _card(51, "Other Person")],
        "primary": None,
        "verifier": None,
        "final_classification": "insufficient_evidence",
        "processing_error": None,
    }
    audit = {
        "generated_at": "2026-08-30T00:00:00Z",
        "source": {"owner_count": 2, "owner_snapshot_sha256": "abc"},
        "configuration": {},
        "candidates": [candidate],
        "summary": summarize_candidates([candidate]),
    }

    rendered = render_audit_report(audit)

    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "Export manual decisions" in rendered
    assert "live write or merge operation" in rendered


def test_cli_exposes_no_apply_or_replace_flags() -> None:
    destinations = {action.dest for action in build_parser()._actions}

    assert "apply" not in destinations
    assert "replace" not in destinations
    assert "allow_clear" not in destinations
