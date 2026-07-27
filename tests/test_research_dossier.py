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
