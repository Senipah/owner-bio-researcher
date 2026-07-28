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
    (
        "negative wealth-taxonomy contrast",
        re.compile(
            r"\b(?:"
            r"rather than\s+(?:a |an |part of a |part of an )?"
            r"(?:documented |private )?"
            r"(?:commercial|entrepreneurial|business)"
            r"|(?:governmental|hereditary|dynastic)\s+rather than\s+"
            r"(?:commercial|entrepreneurial|business)"
            r"|(?:state|sovereign|national|public)\s+assets?\s+rather than\s+"
            r"(?:personal|private)"
            r"|(?:state|sovereign|national|public)\s+assets?\s+"
            r"rather than\s+evidence of\s+(?:a |an |his |her |their )?"
            r"(?:personal|private)?\s*(?:wealth|fortune|business)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)

STOCK_PHRASES = (
    "built his fortune",
    "built her fortune",
    "route into business",
    "path into business",
    "route to wealth",
    "path to wealth",
    "business path began",
    "career path began",
    "commercial footing",
    "second chapter",
    "second strand",
    "second thread",
    "later chapter",
    "the same pattern",
    "the arc from",
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

META_CAREER_OPENING_PATTERN = re.compile(
    r"^(?:"
    r"[^.!?]{0,140}\b(?:route|path)\s+(?:into|to)\b"
    r"|[^.!?]{0,140}\b(?:business|commercial|investment|industrial|"
    r"shipping|energy|logistics)?\s*(?:career|path)\s+began\b"
    r"|[^.!?]{0,140}\b(?:gave|provided)\s+[^.!?]{0,60}\b"
    r"(?:start|entry|route)\s+(?:in|into|to)\s+"
    r"(?:business|industry|commerce|wealth)\b"
    r"|[^.!?]{0,140}\b(?:commercial footing|entry into business)\b"
    r")",
    re.IGNORECASE,
)

ORIGIN_STORY_OPENING_PATTERN = re.compile(
    r"^(?:"
    r"born\b|raised\b|educated\b|trained\b|at\s+[^.!?]{0,55}\b|"
    r"[^.!?]{0,150}\b(?:"
    r"began|entered|started|studied|trained|arrived|reached|"
    r"first\s+(?:worked|built|explored|entered|invested)|"
    r"came early|preceded (?:his|her|their) career|"
    r"route|path|start|entry|commercial footing"
    r")\b"
    r")",
    re.IGNORECASE,
)

FORMULAIC_SECOND_PARAGRAPH_PATTERN = re.compile(
    r"^(?:"
    r"(?:[A-Z][\w’'-]+|His|Her|Their|The)\s+(?i:later|then)\b"
    r"|(?i:[^.!?]{0,130}\b(?:"
    r"second chapter|second strand|second thread|later chapter|"
    r"parallel test|parallel strand"
    r")\b)"
    r")",
)

SYNTHETIC_ENDING_PATTERN = re.compile(
    r"(?:"
    r"\b(?:link(?:s|ed|ing)?|connect(?:s|ed|ing)?|"
    r"extend(?:s|ed|ing)?)\b[^.!?]{0,130}"
    r"\b(?:with|to|into|back)\b"
    r"|\bthe (?:same pattern|arc)\b"
    r"|\b(?:second|durable) (?:strand|thread|chapter)\b"
    r"|\bdefines? (?:his|her|their|the) "
    r"(?:career|public profile|business career)\b"
    r"|\bgives? (?:his|her|their|the) [^.!?]{0,90}"
    r"\bconsistent theme\b"
    r")",
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


def paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split("\n\n")]


def final_sentence(text: str) -> str:
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_PATTERN.split(text.replace("\n\n", " "))
        if sentence.strip()
    ]
    return sentences[-1] if sentences else ""


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
        sections = paragraphs(text)
        opening = sections[0] if sections else ""
        if META_CAREER_OPENING_PATTERN.search(opening):
            errors.append(
                f"{section} opens with abstract career-route scaffolding"
            )
        if (
            len(sections) > 1
            and FORMULAIC_SECOND_PARAGRAPH_PATTERN.search(sections[1])
        ):
            warnings.append(
                f"{section} uses a formulaic later-chapter transition"
            )
        if SYNTHETIC_ENDING_PATTERN.search(final_sentence(text)):
            warnings.append(
                f"{section} ends with a synthetic tie-back conclusion"
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
