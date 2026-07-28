from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
)
sys.path.insert(0, str(SKILL_SCRIPTS))

from editorial_rules import biography_pair_findings  # noqa: E402


def test_pair_rules_warn_when_same_fact_bundle_is_reordered() -> None:
    short = (
        "Alex Example founded Northstar Tools through direct factory sourcing "
        "and product testing. Private ownership supported manufacturing "
        "expansion and international distribution."
    )
    long = (
        "Direct factory sourcing and product testing shaped Northstar Tools "
        "under Alex Example. Private ownership supported the manufacturer as "
        "it expanded international distribution.\n\n"
        "Engineering teams also created apprenticeship programmes for "
        "regional schools and vocational teachers."
    )

    errors, warnings, metrics = biography_pair_findings(
        short,
        long,
        display_name="Alex Example",
    )

    assert errors == []
    assert any("fact-allocation review" in warning for warning in warnings)
    assert metrics["content_containment"] >= 0.60
    assert metrics["shared_trigrams"] >= 5


def test_pair_rules_ignore_repeated_owner_name_tokens() -> None:
    short = (
        "Sheikh Example bin Example is a public official responsible for "
        "national planning and municipal administration."
    )
    long = (
        "Scientific education became Sheikh Example bin Example's principal "
        "public contribution through a university research endowment.\n\n"
        "The programme funds laboratories, scholarships and international "
        "exchange for early-career researchers."
    )

    errors, warnings, metrics = biography_pair_findings(
        short,
        long,
        display_name="Sheikh Example bin Example",
    )

    assert errors == []
    assert warnings == []
    assert metrics["content_containment"] < 0.60


def test_pair_rules_reject_near_restated_sentence() -> None:
    short = (
        "Alex Example built Northstar Tools through factory sourcing, product "
        "testing, private ownership and manufacturing investment."
    )
    long = (
        "Alex Example built Northstar Tools through factory sourcing, product "
        "testing, private ownership and manufacturing investment.\n\n"
        "The company later created apprenticeship programmes for regional "
        "schools and vocational teachers."
    )

    errors, _, metrics = biography_pair_findings(
        short,
        long,
        display_name="Alex Example",
    )

    assert any("near-restated sentence" in error for error in errors)
    assert metrics["max_sentence_similarity"] >= 0.85
