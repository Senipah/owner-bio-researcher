from __future__ import annotations

import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
)
VALIDATOR = SKILL_ROOT / "scripts" / "validate_dossier.py"
CALIBRATION = SKILL_ROOT / "references" / "shahid-khan-calibration.json"


def _calibration() -> dict:
    return json.loads(CALIBRATION.read_text(encoding="utf-8"))


def _validate(
    tmp_path: Path,
    dossier: dict,
    *,
    strict: bool = False,
) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "dossier.json"
    path.write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    command = [sys.executable, str(VALIDATOR), str(path)]
    if strict:
        command.append("--strict-editorial")
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_calibration_dossier_matches_wealth_classification_contract(
    tmp_path: Path,
) -> None:
    result = _validate(tmp_path, _calibration(), strict=True)

    assert result.returncode == 0, result.stderr


def test_validator_rejects_mismatched_classification_label(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["primary_industry"]["label"] = "Manufacturing"

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "primary_industry.label must be 'Automotive'" in result.stderr


def test_validator_requires_unknown_below_classification_threshold(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["wealth_origin"]["confidence"] = {
        "score": 80,
        "band": "medium",
        "reason": "The available evidence is plausible but inconclusive.",
    }

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert (
        "wealth_origin must use classification 'unknown' below confidence 85"
        in result.stderr
    )


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


def test_validator_accepts_non_person_editorial_note(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    dossier["record_type"] = "institution"
    dossier["research_status"] = "not_applicable"
    dossier["biography_brief"] = None
    dossier["editorial_assessment"] = None
    dossier["biography"] = None
    dossier["long_biography"] = None
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
    for field in (
        "primary_industry",
        "wealth_origin",
        "wealth_relationship",
    ):
        dossier[field]["classification"] = "unknown"
        dossier[field]["label"] = "Unknown"
        dossier[field]["summary"] = "Not applicable to an institutional record."

    result = _validate(tmp_path, dossier)

    assert result.returncode == 0, result.stderr
