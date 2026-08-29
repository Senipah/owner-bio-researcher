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
AUDITOR = SKILL_ROOT / "scripts" / "audit_biography_corpus.py"
CALIBRATION = SKILL_ROOT / "references" / "shahid-khan-calibration.json"
UNCLEAR_KEN_GRIFFIN_BIOGRAPHY = (
    "Ken Griffin is an American billionaire investor, founder and chief "
    "executive of Citadel. His grandmother helped fund Harvard, while family "
    "members and other investors supplied capital for his student trading. "
    "He used those results to attract institutional backing and build "
    "Citadel, later founding the separate electronic market-making company "
    "Citadel Securities."
)


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
    assert "Audited 1 schema-v8/v9 person dossiers." in result.stdout


def test_corpus_auditor_rejects_unclear_references(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    dossier["biography"]["plain_text"] = UNCLEAR_KEN_GRIFFIN_BIOGRAPHY
    dossier["biography"]["html"] = (
        f"<p>{UNCLEAR_KEN_GRIFFIN_BIOGRAPHY}</p>\r\n"
    )
    dossier["biography"]["word_count"] = len(
        re.findall(
            r"\b[\w]+(?:[â€™'-][\w]+)*\b",
            UNCLEAR_KEN_GRIFFIN_BIOGRAPHY,
        )
    )
    (tmp_path / "9508.research.json").write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    result = _run(tmp_path)

    assert result.returncode == 1
    assert "uses the bare causal referent 'those results'" in result.stderr
    assert (
        "helped fund 'Harvard' without naming what was financed"
        in result.stderr
    )


def test_corpus_auditor_requires_wealth_creation_industry(
    tmp_path: Path,
) -> None:
    dossier = deepcopy(_calibration())
    del dossier["wealth_creation_industry"]
    (tmp_path / "1164.research.json").write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    result = _run(tmp_path)

    assert result.returncode == 1
    assert (
        "wealth_creation_industry.classification is missing"
        in result.stderr
    )


def test_corpus_auditor_rejects_expanded_short_biography(
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
    (tmp_path / "1164.research.json").write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    result = _run(tmp_path)

    assert result.returncode == 1
    assert (
        "pair: long_biography appears to expand the short biography's "
        "fact bundle"
        in result.stderr
    )


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


def test_corpus_auditor_rejects_semantically_repeated_origin_openings(
    tmp_path: Path,
) -> None:
    openings = (
        "Born in a manufacturing town,",
        "Raised near an industrial district,",
        "Trained as a mechanical engineer,",
        "At an automotive supplier,",
        "Owner Five entered manufacturing when",
        "Owner Six studied engineering before",
    )
    opening_modes = (
        "present_identity",
        "defining_achievement",
        "decisive_event",
        "institution_or_asset",
        "formative_episode",
        "public_contribution",
    )
    narrative_shapes = (
        "identity_then_origin",
        "achievement_then_backstory",
        "decision_then_consequence",
        "institution_then_person",
        "formative_episode_then_payoff",
        "core_work_deepened",
    )
    for index, opening in enumerate(openings, start=1):
        dossier = deepcopy(_calibration())
        dossier["owner"]["person_id"] = index
        dossier["owner"]["display_name"] = f"Owner {index}"
        dossier["biography"]["plain_text"] = (
            f"Owner {index} is a manufacturing executive with a durable "
            "operating role and a documented record of product development."
        )
        dossier["long_biography"]["plain_text"] = (
            f"{opening} Owner {index} developed technical expertise and "
            "eventually took responsibility for a manufacturing company. "
            "The work included product design, investment and operating "
            "control.\n\n"
            "The company expanded its production base and customer network. "
            "Owner oversight continues to shape capital allocation and "
            "long-term product development."
        )
        dossier["editorial_assessment"]["opening_mode"] = opening_modes[
            index - 1
        ]
        dossier["editorial_assessment"]["narrative_shape"] = narrative_shapes[
            index - 1
        ]
        (tmp_path / f"{index}.research.json").write_text(
            json.dumps(dossier, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    result = _run(tmp_path)

    assert result.returncode == 1
    assert (
        "6/6 business profiles use origin-story openings"
        in result.stderr
    )


def test_corpus_auditor_rejects_dominant_declared_structure(
    tmp_path: Path,
) -> None:
    for person_id in range(1, 7):
        dossier = deepcopy(_calibration())
        dossier["owner"]["person_id"] = person_id
        dossier["owner"]["display_name"] = f"Owner {person_id}"
        (tmp_path / f"{person_id}.research.json").write_text(
            json.dumps(dossier, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    result = _run(tmp_path)

    assert result.returncode == 1
    assert (
        "declared opening mode 'institution_or_asset'"
        in result.stderr
    )
    assert (
        "declared narrative shape 'core_work_deepened'"
        in result.stderr
    )
