from __future__ import annotations

import re
from collections.abc import Iterable


WORD_PATTERN = re.compile(r"\b[\w]+(?:[’'-][\w]+)*\b")
YEAR_PATTERN = re.compile(r"\b(?:18|19|20)\d{2}\b")
FINANCIAL_FIGURE_PATTERN = re.compile(
    r"(?:[$£€]\s?\d[\d,.]*|\b\d+(?:\.\d+)?\s*"
    r"(?:%|percent|million|billion|trillion)\b)",
    re.IGNORECASE,
)
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")

SOURCE_LEAK_PATTERNS = (
    ("Forbes attribution", re.compile(r"\bForbes\b", re.IGNORECASE)),
    (
        "publisher attribution",
        re.compile(
            r"\b(?:Bloomberg|Reuters|Interfax)\s+"
            r"(?:identif(?:y|ies)|classif(?:y|ies)|describ(?:e|es)|"
            r"trac(?:e|es)|estimat(?:e|es)|attribut(?:e|es)|"
            r"report(?:s|ed)?|says?|lists?|document(?:s|ed)?)\b",
            re.IGNORECASE,
        ),
    ),
    ("according-to attribution", re.compile(r"\baccording to\b", re.IGNORECASE)),
    (
        "research-source narration",
        re.compile(
            r"\b(?:available|independent|public|official|court|company|"
            r"corporate|government|regulatory|current|UK|European Union)"
            r"\s+(?:evidence|records?|reporting|sources?|filings?|"
            r"disclosures?)\b",
            re.IGNORECASE,
        ),
    ),
)

PROCESS_LEAK_PATTERNS = (
    (
        "classification narration",
        re.compile(
            r"\b(?:classification|classified as|classifies (?:him|her|"
            r"the fortune)|wealth relationship|private-wealth industry|"
            r"remains? unclassified|all three wealth classifications)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "source-of-wealth label",
        re.compile(
            r"\bsource of (?:his|her|their|the) (?:wealth|fortune)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "research-process narration",
        re.compile(
            r"\b(?:source record|owner record|database placeholder|"
            r"identity to research|no .* (?:was|is) proposed|"
            r"fields? (?:are|remain) inapplicable)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "classification verdict",
        re.compile(
            r"\b(?:supports?|making)\s+(?:a |an |the )?.{0,45}"
            r"(?:classification|clearest description)\b",
            re.IGNORECASE,
        ),
    ),
)

STOCK_PHRASES = (
    "built his fortune",
    "built her fortune",
    "remains rooted in",
    "fortune remains rooted",
    "underlying fortune remains",
    "broadened his public profile",
    "broadened her public profile",
    "his later work",
    "her later work",
    "his public story",
    "her public story",
    "best understood as",
    "the principal source of his wealth",
    "the principal source of her wealth",
)

PERSONAL_YACHT_PATTERN = re.compile(
    r"\b(?:yacht|yachts|yachting|superyacht|superyachts)\b",
    re.IGNORECASE,
)


def word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def sentence_word_counts(text: str) -> list[int]:
    flattened = text.replace("\n\n", " ")
    return [
        word_count(sentence)
        for sentence in SENTENCE_PATTERN.split(flattened)
        if sentence.strip()
    ]


def explicit_years(text: str) -> list[str]:
    return YEAR_PATTERN.findall(text)


def financial_figures(text: str) -> list[str]:
    return FINANCIAL_FIGURE_PATTERN.findall(text)


def pattern_hits(
    text: str,
    patterns: Iterable[tuple[str, re.Pattern[str]]],
) -> list[str]:
    return [label for label, pattern in patterns if pattern.search(text)]


def editorial_findings(
    text: str,
    *,
    section: str,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for label in pattern_hits(text, SOURCE_LEAK_PATTERNS):
        errors.append(f"{section} contains {label}")
    for label in pattern_hits(text, PROCESS_LEAK_PATTERNS):
        errors.append(f"{section} contains {label}")

    if section == "long_biography":
        years = explicit_years(text)
        if len(years) > 2:
            errors.append(
                f"{section} contains {len(years)} explicit years; maximum is 2"
            )
        figures = financial_figures(text)
        if len(figures) > 1:
            errors.append(
                f"{section} contains {len(figures)} financial or percentage "
                "figures; maximum is 1"
            )

    long_sentences = [
        count for count in sentence_word_counts(text) if count > 30
    ]
    if long_sentences:
        warnings.append(
            f"{section} contains sentence lengths over 30 words: "
            f"{long_sentences}"
        )

    if PERSONAL_YACHT_PATTERN.search(text):
        warnings.append(
            f"{section} mentions yacht terminology; confirm it is durable "
            "maritime work and not personal asset ownership"
        )

    return errors, warnings
