from __future__ import annotations

import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
)
VALIDATOR = SKILL_ROOT / "scripts" / "validate_dossier.py"
CALIBRATION = SKILL_ROOT / "references" / "shahid-khan-calibration.json"
UNCLEAR_KEN_GRIFFIN_BIOGRAPHY = (
    "Ken Griffin is an American billionaire investor, founder and chief "
    "executive of Citadel. His grandmother helped fund Harvard, while family "
    "members and other investors supplied capital for his student trading. "
    "He used those results to attract institutional backing and build "
    "Citadel, later founding the separate electronic market-making company "
    "Citadel Securities."
)
CLEAR_KEN_GRIFFIN_BIOGRAPHY = (
    "Ken Griffin is an American billionaire investor, founder and chief "
    "executive of Citadel. While studying at Harvard, he traded with capital "
    "from his grandmother, other relatives and outside investors. His early "
    "returns attracted institutional backing for Citadel, which he developed "
    "into a hedge-fund business before establishing the separately operated "
    "electronic market-maker Citadel Securities."
)


def _calibration() -> dict:
    return json.loads(CALIBRATION.read_text(encoding="utf-8"))


def _set_short_biography(dossier: dict, plain: str) -> None:
    dossier["biography"]["plain_text"] = plain
    dossier["biography"]["html"] = f"<p>{plain}</p>\r\n"
    dossier["biography"]["word_count"] = len(
        re.findall(r"\b[\w]+(?:[â€™'-][\w]+)*\b", plain)
    )


def _editorial_findings(
    text: str,
    *,
    section: str = "biography",
) -> tuple[list[str], list[str]]:
    scripts_path = str(SKILL_ROOT / "scripts")
    sys.path.insert(0, scripts_path)
    try:
        from editorial_rules import editorial_findings

        return editorial_findings(text, section=section)
    finally:
        sys.path.remove(scripts_path)


def _validate(
    tmp_path: Path,
    dossier: dict,
    *,
    strict: bool = False,
    catalogue: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "dossier.json"
    path.write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    command = [sys.executable, str(VALIDATOR), str(path)]
    if strict:
        command.append("--strict-editorial")
    if catalogue is not None:
        command.extend(["--tag-catalogue", str(catalogue)])
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _vessel_name_mention(
    text: str, vessel_name: str, reviewed_phrases: tuple[str, ...] = (),
) -> bool:
    scripts_path = str(SKILL_ROOT / "scripts")
    sys.path.insert(0, scripts_path)
    try:
        from validate_dossier import _mentions_vessel_name

        return _mentions_vessel_name(text, vessel_name, reviewed_phrases)
    finally:
        sys.path.remove(scripts_path)


@pytest.mark.parametrize(
    ("vessel", "phrase", "text"),
    [
        ("Athina", "Athina Kyriakou", "Athina Kyriakou bought shares"),
        ("Azizi", "Mirwais Azizi", "Mirwais Azizi's property firm"),
        ("Azizi", "Azizi used his resources", "Azizi used his resources"),
        ("Azizi", "Azizi Bank", "Azizi Bank grew"),
        ("Azizi", "Azizi Town", "The settlement is Azizi Town"),
        ("Lafayette", "Pharmacie Lafayette", "Pharmacie Lafayette grew"),
    ],
)
def test_reviewed_vessel_collision_masks_only_exact_span(
    vessel: str, phrase: str, text: str,
) -> None:
    assert not _vessel_name_mention(text, vessel, (phrase,))
    assert _vessel_name_mention(f"{text}. He boarded {vessel}.", vessel, (phrase,))


def test_reviewed_commercial_yacht_terms_preserve_personal_asset_warning() -> None:
    scripts_path = str(SKILL_ROOT / "scripts")
    sys.path.insert(0, scripts_path)
    try:
        from editorial_rules import editorial_findings

        phrases = ("FantaSea Yachts", "private yacht hire")
        _, warnings = editorial_findings(
            "FantaSea Yachts offers private yacht hire.",
            section="biography",
            reviewed_commercial_yacht_phrases=phrases,
        )
        assert not warnings
        _, warnings = editorial_findings(
            "FantaSea Yachts offers private yacht hire. He keeps a personal yacht.",
            section="biography",
            reviewed_commercial_yacht_phrases=phrases,
        )
        assert any("yacht terminology" in warning for warning in warnings)
    finally:
        sys.path.remove(scripts_path)


def test_phrase_exception_requires_specific_sourced_review() -> None:
    scripts_path = str(SKILL_ROOT / "scripts")
    sys.path.insert(0, scripts_path)
    try:
        from validate_dossier import _reviewed_phrase_exceptions

        item = {
            "kind": "person_name", "phrase": "Athina Kyriakou",
            "vessel_name": "Athina", "source_ids": ["S1"],
            "reason": "The verified full personal name.",
        }
        document = {
            "editorial_assessment": {"reviewed_phrase_exceptions": [item]},
            "biography": {"plain_text": "Athina Kyriakou holds shares."},
        }
        errors: list[str] = []
        assert _reviewed_phrase_exceptions(document, {"S1"}, errors) == [item]
        assert not errors
        document["editorial_assessment"]["reviewed_phrase_exceptions"] = [
            {**item, "source_ids": ["missing"]}
        ]
        assert not _reviewed_phrase_exceptions(document, {"S1"}, errors)
        assert any("source_ids" in error for error in errors)
    finally:
        sys.path.remove(scripts_path)


def test_duplicate_company_website_proposals_fail_before_compilation(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["proposed_socials"].append({
        **dossier["proposed_socials"][0],
        "url": "https://another-owned-company.example/",
    })

    result = _validate(tmp_path, dossier, strict=True)

    assert result.returncode == 1
    assert "proposed_socials[1].type_id duplicates proposed_socials[0].type_id" in result.stderr


@pytest.mark.parametrize(("score", "accepted"), [(74, False), (75, True)])
def test_validator_resolved_identity_threshold_is_75(
    tmp_path: Path, score: int, accepted: bool,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["owner"]["identity_confidence"] = {
        "score": score,
        "band": "medium",
        "reason": "The linked company and personal context support this identity.",
    }

    result = _validate(tmp_path, dossier, strict=True)

    if accepted:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode == 1
        assert "owner.identity_confidence.score must be at least 75" in result.stderr


def test_calibration_dossier_matches_wealth_classification_contract(
    tmp_path: Path,
) -> None:
    result = _validate(tmp_path, _calibration(), strict=True)

    assert result.returncode == 0, result.stderr


def test_validator_warns_about_unclear_ken_griffin_references(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    _set_short_biography(dossier, UNCLEAR_KEN_GRIFFIN_BIOGRAPHY)

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr
    assert (
        "WARNING: biography uses the bare causal referent 'those results'"
        in result.stderr
    )
    assert (
        "WARNING: biography says 'His grandmother' helped fund 'Harvard' "
        "without naming what was financed and for what purpose"
        in result.stderr
    )


def test_strict_validator_rejects_unclear_ken_griffin_references(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    _set_short_biography(dossier, UNCLEAR_KEN_GRIFFIN_BIOGRAPHY)

    result = _validate(tmp_path, dossier, strict=True)

    assert result.returncode == 1
    assert (
        "strict editorial: biography uses the bare causal referent "
        "'those results'"
        in result.stderr
    )
    assert (
        "strict editorial: biography says 'His grandmother' helped fund "
        "'Harvard' without naming what was financed and for what purpose"
        in result.stderr
    )


def test_strict_validator_accepts_clear_ken_griffin_references(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    _set_short_biography(dossier, CLEAR_KEN_GRIFFIN_BIOGRAPHY)

    result = _validate(tmp_path, dossier, strict=True)

    assert result.returncode == 0, result.stderr


def test_referential_clarity_rules_allow_explicit_constructions() -> None:
    clear_examples = (
        (
            "A lifetime gift and family-company loans supplied capital for "
            "his investment platform. Li used that support to acquire and "
            "redevelop Japanese property."
        ),
        (
            "Lewis sold the restaurant group before entering currency "
            "trading. He reinvested that capital through Tavistock Group."
        ),
        (
            "After losses on North American investments, Packer reduced "
            "leverage. That experience produced a more conservative balance "
            "sheet."
        ),
        (
            "Her family helped fund the acquisition of a controlling interest "
            "in the Dallas Mavericks."
        ),
        (
            "Dividends from Inditex fund Pontegadea, his investment vehicle "
            "for property and infrastructure."
        ),
    )

    for text in clear_examples:
        errors, warnings = _editorial_findings(text)
        assert errors == []
        assert warnings == []


def test_referential_clarity_automation_skips_internal_brief_text() -> None:
    errors, warnings = _editorial_findings(
        UNCLEAR_KEN_GRIFFIN_BIOGRAPHY,
        section="biography_brief",
    )

    assert errors == []
    assert warnings == []


def test_vessel_name_checker_allows_independent_company_name() -> None:
    assert not _vessel_name_mention(
        "He founded and leads AHS Properties in Dubai.",
        "AHS",
    )
    assert _vessel_name_mention(
        "He is the current owner of AHS.",
        "AHS",
    )


def test_validator_rejects_mismatched_classification_label(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["primary_industry"]["label"] = "Manufacturing"

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "primary_industry.label must be 'Automotive'" in result.stderr


def test_validator_accepts_self_made_starting_position_subtypes(
    tmp_path: Path,
) -> None:
    for classification, label in (
        ("self_made_independent", "Self-made — independent start"),
        ("self_made_advantaged", "Self-made — advantaged start"),
    ):
        dossier = deepcopy(_calibration())
        dossier["wealth_origin"].update(
            {
                "classification": classification,
                "label": label,
                "summary": (
                    "The founder built the principal company, with the "
                    "starting position classified from supported context."
                ),
            }
        )

        result = _validate(tmp_path, dossier)

        assert result.returncode == 0, result.stderr


def test_validator_uses_shared_industry_dictionary_independently(
    tmp_path: Path,
) -> None:
    creation_crypto = deepcopy(_calibration())
    creation_crypto["wealth_creation_industry"].update(
        {
            "classification": "cryptocurrency",
            "label": "Cryptocurrency",
            "summary": "The original fortune was created through cryptocurrency.",
        }
    )
    creation_crypto["primary_industry"].update(
        {
            "classification": "finance_investments",
            "label": "Finance & Investments",
            "summary": "Current principal interests are in investment management.",
        }
    )

    creation_result = _validate(tmp_path, creation_crypto)

    assert creation_result.returncode == 0, creation_result.stderr

    primary_crypto = deepcopy(_calibration())
    primary_crypto["primary_industry"].update(
        {
            "classification": "cryptocurrency",
            "label": "Cryptocurrency",
            "summary": "Current principal interests are in cryptocurrency.",
        }
    )

    primary_result = _validate(tmp_path, primary_crypto)

    assert primary_result.returncode == 0, primary_result.stderr


def test_validator_requires_wealth_creation_industry(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    del dossier["wealth_creation_industry"]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "wealth_creation_industry" in result.stderr


def test_validator_requires_schema_v8_proposed_tags(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    del dossier["proposed_tags"]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "proposed_tags" in result.stderr


def test_validator_resolves_active_alias_with_canonical_id(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["proposed_tags"] = [
        {
            "tag_id": "tag_0078",
            "name": "Formula_1",
            "summary": "A durable material Formula 1 role is established.",
            "confidence": {
                "score": 95,
                "band": "very_high",
                "reason": "Official evidence supports the role.",
            },
            "source_ids": ["S1"],
        }
    ]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr


def test_validator_rejects_unknown_tag_even_with_high_confidence(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["proposed_tags"] = [
        {
            "tag_id": None,
            "name": "Quantum maritime choreography",
            "summary": "The fact is established beyond doubt.",
            "confidence": {
                "score": 100,
                "band": "very_high",
                "reason": "Official evidence establishes the fact.",
            },
            "source_ids": ["S1"],
        }
    ]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "closed-world catalogue" in result.stderr
    assert "not an approved active assignment" in result.stderr


def test_validator_rejects_candidate_and_inactive_assignments(
    tmp_path: Path,
) -> None:
    catalogue = json.loads(
        (REPO_ROOT / "config" / "owner-tags.json").read_text(encoding="utf-8")
    )
    assert not [tag for tag in catalogue["tags"] if tag["status"] == "candidate"]
    inactive = next(
        item for item in catalogue["tags"] if item["status"] == "inactive"
    )
    for lifecycle_status in ("candidate", "inactive"):
        reviewed_catalogue = deepcopy(catalogue)
        tag = next(
            item
            for item in reviewed_catalogue["tags"]
            if item["id"] == inactive["id"]
        )
        tag["status"] = lifecycle_status
        if lifecycle_status == "candidate":
            tag["lifecycle"] = {}
        catalogue_path = tmp_path / f"owner-tags-{lifecycle_status}.json"
        catalogue_path.write_text(
            json.dumps(reviewed_catalogue, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        dossier = deepcopy(_calibration())
        dossier["proposed_tags"] = [
            {
                "tag_id": tag["id"],
                "name": tag["name"],
                "summary": "A factual association is not taxonomy approval.",
                "confidence": {
                    "score": 99,
                    "band": "very_high",
                    "reason": "The association is strongly evidenced.",
                },
                "source_ids": ["S1"],
            }
        ]

        result = _validate(tmp_path, dossier, catalogue=catalogue_path)

        assert result.returncode == 1
        assert f"lifecycle status '{lifecycle_status}'" in result.stderr


def test_owner_dossier_rejects_formal_candidate_structure(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    dossier["tag_candidates"] = []

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "tag_candidates is not part of the owner-research" in result.stderr


def test_owner_dossier_cannot_hide_taxonomy_candidate_in_review_items(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["candidates_requiring_review"] = [
        {
            "candidate_type": "taxonomy_candidate",
            "proposed_tag_name": "Hidden formal proposal",
        }
    ]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "must not encode a formal taxonomy candidate" in result.stderr


def test_schema_v9_is_rejected_after_candidate_contract_retirement(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["schema_version"] = 9

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "schema_version must be 8" in result.stderr


def test_empty_tags_and_unrepresented_fact_are_valid_owner_research(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["proposed_tags"] = []
    dossier["uncertainties"].append(
        "A notable specialist manufacturing characteristic is preserved here "
        "but is not represented by a suitable active tag."
    )

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr


def test_repeated_unknown_owner_outputs_do_not_mutate_taxonomy(
    tmp_path: Path,
) -> None:
    source = REPO_ROOT / "config" / "owner-tags.json"
    catalogue = tmp_path / "owner-tags.json"
    catalogue.write_bytes(source.read_bytes())
    before = catalogue.read_bytes()
    dossier = deepcopy(_calibration())
    dossier["proposed_tags"] = [
        {
            "tag_id": None,
            "name": "Repeated owner-level phrase",
            "summary": "The same unsupported taxonomy phrase recurred.",
            "confidence": {
                "score": 99,
                "band": "very_high",
                "reason": "The underlying fact is strongly evidenced.",
            },
            "source_ids": ["S1"],
        }
    ]

    first = _validate(tmp_path, dossier, catalogue=catalogue)
    second = _validate(tmp_path, dossier, catalogue=catalogue)

    assert first.returncode == 1
    assert second.returncode == 1
    assert catalogue.read_bytes() == before


def test_validator_rejects_normalized_duplicate_tags(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    proposal = {
        "tag_id": None,
        "name": "Formula 1",
        "summary": "A durable material Formula 1 role is established.",
        "confidence": {
            "score": 95,
            "band": "very_high",
            "reason": "Official evidence supports the role.",
        },
        "source_ids": ["S1"],
    }
    duplicate = deepcopy(proposal)
    duplicate["name"] = "formula_1"
    dossier["proposed_tags"] = [proposal, duplicate]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "duplicates proposed_tags[0].name after normalization" in result.stderr


def test_validator_requires_tag_summary_confidence_and_sources(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["proposed_tags"] = [
        {
            "tag_id": None,
            "name": "Apple",
            "summary": "",
            "confidence": {
                "score": 69,
                "band": "low",
                "reason": "The evidence is incomplete.",
            },
            "source_ids": [],
        }
    ]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "proposed_tags[0].summary must be non-empty" in result.stderr
    assert "proposed_tags[0] confidence must be at least 70" in result.stderr
    assert "proposed_tags[0].source_ids must be a non-empty list" in result.stderr


@pytest.mark.parametrize(
    "excluded_name",
    (
        "Family_business",
        "Family office",
        "Philanthropy",
        "Education philanthropy",
    ),
)
def test_validator_rejects_deliberately_excluded_tags(
    tmp_path: Path,
    excluded_name: str,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["proposed_tags"][0]["tag_id"] = None
    dossier["proposed_tags"][0]["name"] = excluded_name

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "proposed_tags[0].name is deliberately excluded" in result.stderr


def test_validator_maps_wealth_creation_industry_proposal_to_shared_label(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["wealth_creation_industry"].update(
        {
            "classification": "cryptocurrency",
            "label": "Cryptocurrency",
            "summary": "The original fortune was created through cryptocurrency.",
        }
    )
    for field in ("raw_blank_details", "researchable_missing_details"):
        dossier["input_snapshot"][field].append("wealth_creation_industry")
    dossier["proposed_details"].append(
        {
            "action": "fill_missing",
            "field": "wealth_creation_industry",
            "value": "Cryptocurrency",
            "confidence": deepcopy(
                dossier["wealth_creation_industry"]["confidence"]
            ),
            "source_ids": list(
                dossier["wealth_creation_industry"]["source_ids"]
            ),
        }
    )

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr


def test_validator_requires_unknown_wealth_creation_industry_below_threshold(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["wealth_creation_industry"]["confidence"] = {
        "score": 60,
        "band": "low",
        "reason": "The available evidence is plausible but inconclusive.",
    }

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "wealth_creation_industry must use classification 'unknown' below "
        "confidence 70"
    ) in result.stderr


def test_validator_requires_unknown_below_classification_threshold(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["wealth_origin"]["confidence"] = {
        "score": 60,
        "band": "low",
        "reason": "The available evidence is plausible but inconclusive.",
    }

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "wealth_origin must use classification 'unknown' below confidence 70"
        in result.stderr
    )


def test_validator_accepts_classification_at_70(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    dossier["wealth_origin"]["confidence"] = {
        "score": 70,
        "band": "medium",
        "reason": "The evidence reaches the configured import threshold.",
    }

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr


def test_validator_enforces_short_biography_length(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    dossier["biography"]["plain_text"] = "This biography is too short."
    dossier["biography"]["html"] = "<p>This biography is too short.</p>\r\n"
    dossier["biography"]["word_count"] = 5

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "biography must contain 50-55 words" in result.stderr


def test_validator_requires_two_long_biography_paragraphs(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["long_biography"]["plain_text"].replace("\n\n", " ")
    dossier["long_biography"]["plain_text"] = plain
    dossier["long_biography"]["html"] = f"<p>{plain}</p>\r\n"

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "long_biography.plain_text must contain exactly two paragraphs"
        in result.stderr
    )


def test_validator_rejects_long_biography_that_expands_short_fact_bundle(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    short = dossier["biography"]["plain_text"]
    long_plain = (
        f"{short}\n\n"
        "Flex-N-Gate remains privately controlled, and Khan continues as "
        "chief executive. The group expanded internationally under his "
        "ownership. He also acquired the Jacksonville Jaguars and Fulham "
        "F.C., while his son Tony leads the family's involvement in All "
        "Elite Wrestling."
    )
    dossier["long_biography"]["plain_text"] = long_plain
    dossier["long_biography"]["html"] = "".join(
        f"<p>{paragraph}</p>\r\n"
        for paragraph in long_plain.split("\n\n")
    )
    dossier["long_biography"]["word_count"] = len(
        re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", long_plain)
    )
    dossier["editorial_assessment"]["structural_independence"] = 4

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "long_biography appears to expand the short biography's fact bundle"
        in result.stderr
    )


def test_validator_requires_person_biography_brief(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    dossier["biography_brief"] = None

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "biography_brief must be an object for person records" in result.stderr


def test_validator_requires_multiple_opening_options(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    dossier["biography_brief"]["opening_options"] = [
        dossier["biography_brief"]["opening_options"][0]
    ]

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "biography_brief.opening_options must contain at least two options"
        in result.stderr
    )


def test_validator_rejects_abstract_opening_option(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["biography_brief"]["opening_options"][0]["angle"] = (
        "Open with his route into business."
    )

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "biography_brief.opening_options[0].angle uses abstract "
        "career-route scaffolding"
        in result.stderr
    )


def test_validator_requires_editorial_scores_of_at_least_four(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["editorial_assessment"]["natural_voice"] = 3

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "editorial_assessment.natural_voice must be 4 or 5"
        in result.stderr
    )


def test_validator_requires_selected_opening_mode_from_brief(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["editorial_assessment"]["opening_mode"] = "public_contribution"

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "editorial_assessment.opening_mode must select one of "
        "biography_brief.opening_options"
        in result.stderr
    )


def test_validator_rejects_research_narration_in_biography(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["biography"]["plain_text"].replace(
        "The acquisition gave him",
        "Forbes identifies his success, and the acquisition gave him",
    )
    dossier["biography"]["plain_text"] = plain
    dossier["biography"]["html"] = f"<p>{plain}</p>\r\n"
    dossier["biography"]["word_count"] = len(plain.split())

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "biography contains Forbes attribution" in result.stderr


def test_validator_rejects_negative_wealth_taxonomy_contrast(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["biography"]["plain_text"].replace(
        "The acquisition gave him",
        "His career reflects public service rather than commercial enterprise. "
        "The acquisition gave him",
    )
    dossier["biography"]["plain_text"] = plain
    dossier["biography"]["html"] = f"<p>{plain}</p>\r\n"
    dossier["biography"]["word_count"] = len(plain.split())

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "biography contains negative wealth-taxonomy contrast"
        in result.stderr
    )


def test_validator_rejects_abstract_career_route_opening(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["long_biography"]["plain_text"].replace(
        'Private ownership has kept Shahid "Shad" Khan closely involved in '
        "Flex-N-Gate, the automotive-parts group at the centre of his business.",
        'Shahid "Shad" Khan\'s business path began with automotive parts.',
    )
    dossier["long_biography"]["plain_text"] = plain
    dossier["long_biography"]["html"] = "".join(
        f"<p>{paragraph}</p>\r\n"
        for paragraph in plain.split("\n\n")
    )
    dossier["long_biography"]["word_count"] = len(
        re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", plain)
    )

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "long_biography opens with abstract career-route scaffolding"
        in result.stderr
    )


def test_strict_validator_rejects_formulaic_second_paragraph(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["long_biography"]["plain_text"].replace(
        "Khan carried that ownership model",
        "Khan later carried that ownership model",
    )
    dossier["long_biography"]["plain_text"] = plain
    dossier["long_biography"]["html"] = "".join(
        f"<p>{paragraph}</p>\r\n"
        for paragraph in plain.split("\n\n")
    )
    dossier["long_biography"]["word_count"] = len(
        re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", plain)
    )

    result = _validate(tmp_path, dossier, strict=True)

    assert result.returncode == 1
    assert (
        "strict editorial: long_biography uses a formulaic "
        "later-chapter transition"
        in result.stderr
    )


def test_strict_validator_rejects_synthetic_tie_back_ending(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["long_biography"]["plain_text"].replace(
        "American football, English football and wrestling now sit alongside "
        "the manufacturing group, where Khan continues to serve as chief "
        "executive under direct private ownership.",
        "The same pattern runs through his industrial and sporting interests.",
    )
    dossier["long_biography"]["plain_text"] = plain
    dossier["long_biography"]["html"] = "".join(
        f"<p>{paragraph}</p>\r\n"
        for paragraph in plain.split("\n\n")
    )
    dossier["long_biography"]["word_count"] = len(
        re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", plain)
    )

    result = _validate(tmp_path, dossier, strict=True)

    assert result.returncode == 1
    assert (
        "strict editorial: long_biography ends with a synthetic "
        "tie-back conclusion"
        in result.stderr
    )


def test_validator_rejects_more_than_two_long_biography_years(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["long_biography"]["plain_text"].replace(
        "American football, English football and wrestling now sit alongside "
        "the manufacturing group, where Khan continues to serve as chief "
        "executive under direct private ownership.",
        "Khan expanded in 2001, 2002 and 2003.",
    )
    dossier["long_biography"]["plain_text"] = plain
    dossier["long_biography"]["html"] = "".join(
        f"<p>{paragraph}</p>\r\n"
        for paragraph in plain.split("\n\n")
    )
    dossier["long_biography"]["word_count"] = len(
        re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", plain)
    )

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "explicit years; maximum is 2" in result.stderr


def test_validator_accepts_institution_biographies_and_note(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["record_type"] = "institution"
    dossier["research_status"] = "complete"
    dossier["biography_brief"] = None
    dossier["editorial_assessment"] = None
    dossier["editorial_note"] = {
        "plain_text": (
            "This owner record represents a public institution rather than a "
            "natural person. Person-specific biography, private-wealth, and "
            "social-profile proposals are therefore not applicable."
        ),
        "confidence": {
            "score": 98,
            "band": "very_high",
            "reason": "Official records establish the institutional identity.",
        },
        "source_ids": ["S1"],
    }
    dossier["proposed_details"] = []
    dossier["proposed_socials"] = []
    dossier["proposed_tags"] = []
    for field in (
        "wealth_creation_industry",
        "primary_industry",
        "wealth_origin",
        "wealth_relationship",
    ):
        dossier[field]["classification"] = "unknown"
        dossier[field]["label"] = "Unknown"
        dossier[field]["summary"] = "Not applicable to an institutional record."

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr


def test_validator_allows_sole_government_owned_tag_for_unresolved_public_label(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["record_type"] = "unresolved_placeholder"
    dossier["research_status"] = "identity_conflict"
    dossier["owner"]["identity_confidence"] = {
        "score": 35,
        "band": "insufficient",
        "reason": "The exact historic administration cannot be resolved.",
    }
    dossier["biography_brief"] = None
    dossier["editorial_assessment"] = None
    dossier["biography"] = None
    dossier["long_biography"] = None
    dossier["editorial_note"] = {
        "plain_text": (
            "This label is certainly a public government owner, although the "
            "available evidence cannot identify the exact historic administration. "
            "No personal biography, private-wealth classification or social-profile "
            "proposal can therefore be made safely."
        ),
        "confidence": {
            "score": 99,
            "band": "very_high",
            "reason": "Every plausible identity is a government body.",
        },
        "source_ids": ["S1"],
    }
    dossier["proposed_details"] = []
    dossier["proposed_socials"] = []
    dossier["proposed_tags"] = [
        {
            "tag_id": "tag_0249",
            "name": "Government-owned",
            "summary": "Every plausible owner identity is a public government body.",
            "confidence": {
                "score": 99,
                "band": "very_high",
                "reason": "The unresolved distinction is only between governments.",
            },
            "source_ids": ["S1"],
        }
    ]
    for field in (
        "wealth_creation_industry",
        "primary_industry",
        "wealth_origin",
        "wealth_relationship",
    ):
        dossier[field]["classification"] = "unknown"
        dossier[field]["label"] = "Unknown"

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr
