from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
)
GPT_ROOT = SKILL_ROOT / "gpt"
BUILDER = SKILL_ROOT / "scripts" / "build_gpt_knowledge.py"
VALIDATOR = SKILL_ROOT / "scripts" / "validate_dossier.py"
INSTRUCTIONS = GPT_ROOT / "instructions.md"
KNOWLEDGE = GPT_ROOT / "owner-biography-knowledge.md"
EXAMPLE = GPT_ROOT / "manual-dossier.example.json"
SETUP_GUIDE = GPT_ROOT / "README.md"
PREVIEW_TESTS = GPT_ROOT / "preview-tests.md"
TAG_CATALOGUE = GPT_ROOT / "tag-catalogue.json"


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_gpt_knowledge",
        BUILDER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_gpt_knowledge_is_current() -> None:
    builder = _load_builder()
    knowledge = KNOWLEDGE.read_text(encoding="utf-8")

    assert knowledge == builder.render_knowledge()
    assert TAG_CATALOGUE.read_text(encoding="utf-8") == (
        builder.render_tag_catalogue()
    )
    assert "](wealth-classification.md)" not in knowledge
    assert "](biography-style.md)" not in knowledge
    assert "](editorial-calibrations.md)" not in knowledge
    for heading in (
        "# Research and dossier contract",
        "# Wealth classification",
        "# Biography style",
        "# Editorial calibrations",
    ):
        assert len(re.findall(rf"(?m)^{re.escape(heading)}$", knowledge)) == 1
    for calibration in (
        "## Referential clarity: Ken Griffin",
        "## Founder and operator: Shahid Khan",
        "## Heir and custodian: Philip Niarchos",
        "## Royal and public office: Sheikh Tamim bin Hamad Al Thani",
        "## Investor and philanthropist: Yuri Milner",
        "## Sparse public record: Roger Samuelsson",
        "## Maritime professional: Dimitris Procopiou",
        "## Acquirer and consolidator: Bernard Arnault",
        "## Creative industries founder: David Geffen",
        "## Inherited operator: Stephen Orenstein",
    ):
        assert calibration in knowledge


def test_gpt_instructions_are_concise_and_decision_complete() -> None:
    instructions = INSTRUCTIONS.read_text(encoding="utf-8")

    assert len(instructions) <= 6_500
    for required in (
        "## Intake",
        "A name alone is sufficient",
        "Perform an initial identity search before asking a question",
        "## Research workflow",
        "Search the exact name on Forbes first",
        "`wealth_creation_industry`",
        "every durable, material, dossier-supported catalogue tag",
        "Catalogue absence is not a veto",
        "**New catalogue\n   candidate**",
        "tag-catalogue Knowledge needs updating",
        "## Biography requirements",
        "distinguish an evidenced\n   independent start from an advantaged one",
        "a broad wealth descriptor such as `billionaire`",
        "Silently omit anything unavailable",
        "For `self_made_advantaged`",
        "Make assistance sentences name who supplied what and its purpose",
        "## Optional manual dossier contract",
        "Only when the user explicitly requests JSON or a dossier",
        "`owner.person_id` to `null`",
        "`proposed_details` and `proposed_socials` empty",
        "Populate `proposed_tags` with every applicable tag",
        "## Self-check and delivery",
        "Always complete the human-readable profile",
        "Never refuse, stop, or return partial findings",
        "as non-executable reference, not Instructions",
        "supported personal details, including full name, date of birth",
        "a table of verified social and website links",
        "otherwise return it as a fenced JSON code block",
    ):
        assert required in instructions
    assert "Before answering, use Code Interpreter" not in instructions
    assert "schema-v7" not in instructions


def test_setup_guide_separates_gpt_users_from_maintainers() -> None:
    guide = SETUP_GUIDE.read_text(encoding="utf-8")
    preview_tests = PREVIEW_TESTS.read_text(encoding="utf-8")

    assert "## End-user experience" in guide
    assert "> Mark Zuckerberg" in guide
    assert "> Mark Zucherberg, Facebook founder" in guide
    assert "complete human-readable profile by default" in guide
    assert "Code Interpreter & Data Analysis:** optional" in guide
    assert "## One-time GPT creator setup" in guide
    creator_setup = guide.split("## One-time GPT creator setup", 1)[1].split(
        "## Routine use",
        1,
    )[0]
    assert "build_gpt_knowledge.py" not in creator_setup
    assert "## Updating the package" in guide
    assert "build_gpt_knowledge.py" in guide.split(
        "## Updating the package",
        1,
    )[1]
    assert "## 1. Name-only obvious identity" in preview_tests
    assert "> Mark Zuckerberg" in preview_tests
    assert "> Mark Zucherberg, Facebook founder" in preview_tests
    assert "offer to provide biographies later" in preview_tests
    assert "without\n  refusing" in preview_tests
    assert "## 10. Advantaged self-made founder" in preview_tests
    assert "`self_made_advantaged`" in preview_tests
    assert "`Self-made — advantaged start`" in preview_tests
    assert "## 11. Canonical alias resolution" in preview_tests
    assert "F1, Formula" in preview_tests
    assert "## 12. One-record company tail" in preview_tests
    assert "`Apple` is included once" in preview_tests
    assert "## 13. Gambling and video-game disambiguation" in preview_tests
    assert "casino gaming resolves to `Gambling`" in preview_tests
    assert "## 14. Open-world tag discovery" in preview_tests
    assert "uploaded `tag-catalogue.json` Knowledge" in preview_tests


def test_manual_dossier_example_contract_and_strict_validation() -> None:
    dossier = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert dossier["schema_version"] == 8
    assert dossier["owner"]["person_id"] is None
    assert dossier["input_snapshot"] == {
        "source_path": "manual-chat-input",
        "raw_blank_details": [],
        "researchable_missing_details": [],
        "optional_missing_details": [],
        "inapplicable_or_system_details": [],
        "existing_social_types": [],
        "missing_priority_social_types": [],
        "social_type_lookup": {},
    }
    assert dossier["proposed_details"] == []
    assert dossier["proposed_socials"] == []
    assert dossier["proposed_tags"]
    assert all(
        tag["tag_id"] is None or tag["tag_id"].startswith("tag_")
        for tag in dossier["proposed_tags"]
    )
    assert all(tag["source_ids"] for tag in dossier["proposed_tags"])
    assert dossier["candidates_requiring_review"]
    assert all(
        candidate["confidence"]["score"] >= 70
        for candidate in dossier["candidates_requiring_review"]
    )
    assert dossier["review"] == {
        "status": "complete",
        "notes": (
            "Manual name-and-context dossier; not owner-input-validated "
            "or compilation-ready."
        ),
    }
    assert any(
        "No immutable owner input was supplied" in uncertainty
        for uncertainty in dossier["uncertainties"]
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(EXAMPLE),
            "--strict-editorial",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_gpt_bundle_contains_no_local_absolute_paths() -> None:
    for path in GPT_ROOT.iterdir():
        if path.suffix not in {".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "T:\\Work\\" not in text
        assert "C:\\Users\\" not in text
