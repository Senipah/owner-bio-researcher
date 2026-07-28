from __future__ import annotations

import json
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


def _validate(tmp_path: Path, dossier: dict) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "dossier.json"
    path.write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_calibration_dossier_matches_wealth_classification_contract(
    tmp_path: Path,
) -> None:
    result = _validate(tmp_path, _calibration())

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


def test_validator_requires_person_biography_brief(tmp_path: Path) -> None:
    dossier = deepcopy(_calibration())
    dossier["biography_brief"] = None

    result = _validate(tmp_path, dossier)

    assert result.returncode == 1
    assert "biography_brief must be an object for person records" in result.stderr


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


def test_validator_rejects_research_narration_in_biography(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["biography"]["plain_text"].replace(
        "He subsequently expanded",
        "Forbes identifies his success, and he subsequently expanded",
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
        "He subsequently expanded",
        "His career reflects public service rather than commercial enterprise. "
        "He expanded",
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


def test_validator_rejects_more_than_two_long_biography_years(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    plain = dossier["long_biography"]["plain_text"].replace(
        "Sport and entertainment became a second chapter.",
        "Sport expanded in 2001, 2002 and 2003.",
    )
    dossier["long_biography"]["plain_text"] = plain
    dossier["long_biography"]["html"] = "".join(
        f"<p>{paragraph}</p>\r\n"
        for paragraph in plain.split("\n\n")
    )
    dossier["long_biography"]["word_count"] = len(plain.split())

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
