from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


WORD_PATTERN = re.compile(r"\b[\w]+(?:[’'-][\w]+)*\b")
YEAR_PATTERN = re.compile(r"\b(?:18|19|20)\d{2}\b")
FINANCIAL_FIGURE_PATTERN = re.compile(
    r"(?:[$£€]\s?\d[\d,.]*|\b\d+(?:\.\d+)?\s*"
    r"(?:%|percent|million|billion|trillion)\b)",
    re.IGNORECASE,
)
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")

PAIR_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "became",
        "been",
        "being",
        "before",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "hers",
        "him",
        "his",
        "in",
        "into",
        "is",
        "it",
        "its",
        "later",
        "most",
        "of",
        "on",
        "or",
        "she",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "they",
        "this",
        "through",
        "to",
        "was",
        "were",
        "while",
        "who",
        "with",
        "without",
    }
)
PAIR_WARNING_CONTAINMENT = 0.60
PAIR_ERROR_CONTAINMENT = 0.70
PAIR_WARNING_SHARED_TRIGRAMS = 5
PAIR_ERROR_SHARED_TRIGRAMS = 8
PAIR_WARNING_SENTENCE_SIMILARITY = 0.65
PAIR_ERROR_SENTENCE_SIMILARITY = 0.85

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
            r"remains? unclassified|all (?:three|four) wealth "
            r"classifications)\b",
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


def _normalise_pair_token(token: str) -> str:
    value = token.casefold()
    if value.endswith(("'s", "’s")):
        value = value[:-2]
    return value


def _pair_tokens(
    text: str,
    *,
    excluded_tokens: set[str],
    content_only: bool,
) -> list[str]:
    tokens = [
        _normalise_pair_token(token)
        for token in WORD_PATTERN.findall(text)
    ]
    return [
        token
        for token in tokens
        if token
        and token not in excluded_tokens
        and (
            not content_only
            or (
                token not in PAIR_STOPWORDS
                and len(token) > 2
            )
        )
    ]


def _ngrams(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[index:index + size])
        for index in range(len(tokens) - size + 1)
    }


def _sentence_content_tokens(
    text: str,
    *,
    excluded_tokens: set[str],
) -> list[set[str]]:
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_PATTERN.split(text.replace("\n\n", " "))
        if sentence.strip()
    ]
    return [
        set(
            _pair_tokens(
                sentence,
                excluded_tokens=excluded_tokens,
                content_only=True,
            )
        )
        for sentence in sentences
    ]


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def biography_pair_metrics(
    short_text: str,
    long_text: str,
    *,
    display_name: str,
) -> dict[str, Any]:
    excluded_tokens = {
        _normalise_pair_token(token)
        for token in WORD_PATTERN.findall(display_name)
    }
    short_content = set(
        _pair_tokens(
            short_text,
            excluded_tokens=excluded_tokens,
            content_only=True,
        )
    )
    long_content = set(
        _pair_tokens(
            long_text,
            excluded_tokens=excluded_tokens,
            content_only=True,
        )
    )
    containment = (
        len(short_content & long_content) / len(short_content)
        if short_content
        else 0.0
    )
    short_tokens = _pair_tokens(
        short_text,
        excluded_tokens=excluded_tokens,
        content_only=False,
    )
    long_tokens = _pair_tokens(
        long_text,
        excluded_tokens=excluded_tokens,
        content_only=False,
    )
    shared_trigrams = len(
        _ngrams(short_tokens, 3) & _ngrams(long_tokens, 3)
    )
    short_sentences = _sentence_content_tokens(
        short_text,
        excluded_tokens=excluded_tokens,
    )
    long_sentences = _sentence_content_tokens(
        long_text,
        excluded_tokens=excluded_tokens,
    )
    sentence_similarities = [
        _jaccard(short_sentence, long_sentence)
        for short_sentence in short_sentences
        for long_sentence in long_sentences
        if len(short_sentence) >= 4 and len(long_sentence) >= 4
    ]
    return {
        "content_containment": containment,
        "shared_trigrams": shared_trigrams,
        "max_sentence_similarity": (
            max(sentence_similarities) if sentence_similarities else 0.0
        ),
        "short_content_word_count": len(short_content),
        "long_content_word_count": len(long_content),
    }


def biography_pair_findings(
    short_text: str,
    long_text: str,
    *,
    display_name: str,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics = biography_pair_metrics(
        short_text,
        long_text,
        display_name=display_name,
    )
    containment = float(metrics["content_containment"])
    shared_trigrams = int(metrics["shared_trigrams"])
    sentence_similarity = float(metrics["max_sentence_similarity"])

    if sentence_similarity >= PAIR_ERROR_SENTENCE_SIMILARITY:
        errors.append(
            "biography pair contains a near-restated sentence "
            f"(content similarity {sentence_similarity:.0%})"
        )
    elif sentence_similarity >= PAIR_WARNING_SENTENCE_SIMILARITY:
        warnings.append(
            "biography pair contains a closely overlapping sentence "
            f"(content similarity {sentence_similarity:.0%})"
        )

    if (
        containment >= PAIR_ERROR_CONTAINMENT
        and shared_trigrams >= PAIR_ERROR_SHARED_TRIGRAMS
    ):
        errors.append(
            "long_biography appears to expand the short biography's fact "
            f"bundle ({containment:.0%} short-content containment; "
            f"{shared_trigrams} shared three-word phrases)"
        )
    elif (
        containment >= PAIR_WARNING_CONTAINMENT
        and shared_trigrams >= PAIR_WARNING_SHARED_TRIGRAMS
    ):
        warnings.append(
            "biography pair needs fact-allocation review "
            f"({containment:.0%} short-content containment; "
            f"{shared_trigrams} shared three-word phrases)"
        )

    return errors, warnings, metrics


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
