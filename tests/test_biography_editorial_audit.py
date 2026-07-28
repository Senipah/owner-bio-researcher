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
AUDITOR = SKILL_ROOT / "scripts" / "audit_biography_corpus.py"
CALIBRATION = SKILL_ROOT / "references" / "shahid-khan-calibration.json"


def _calibration() -> dict:
    return json.loads(CALIBRATION.read_text(encoding="utf-8"))


def _run(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDITOR), str(directory), "--strict"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_corpus_auditor_accepts_clean_single_calibration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "1164.research.json"
    path.write_text(
        json.dumps(_calibration(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Audited 1 schema-v5 person dossiers." in result.stdout


def test_corpus_auditor_rejects_repeated_stock_phrase(
    tmp_path: Path,
) -> None:
    for person_id in (1, 2, 3):
        dossier = deepcopy(_calibration())
        dossier["owner"]["person_id"] = person_id
        dossier["owner"]["display_name"] = f"Owner {person_id}"
        (tmp_path / f"{person_id}.research.json").write_text(
            json.dumps(dossier, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    result = _run(tmp_path)

    assert result.returncode == 1
    assert "stock phrase 'built his fortune'" in result.stderr
