from __future__ import annotations

import argparse
import itertools
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from duplicate_audit.core import (
    CANDIDATE_DATASET,
    build_identity_card,
    file_sha256,
    normalize_identity_text,
    normalize_url,
    pair_signals,
)
from src.io_utils import atomic_write_json, load_json, utc_now


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a broad deterministic candidate shortlist for later Codex "
            "semantic duplicate review. This command makes no duplicate decisions."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name-similarity", type=float, default=0.72)
    parser.add_argument("--ngram-jaccard", type=float, default=0.42)
    parser.add_argument("--employer-name-similarity", type=float, default=0.50)
    parser.add_argument("--maximum-block-size", type=int, default=60)
    return parser


def _words(value: Any) -> list[str]:
    text = unicodedata.normalize("NFKD", "" if value is None else str(value))
    characters = [
        character.casefold() if character.isalnum() else " " for character in text
    ]
    return [part for part in "".join(characters).split() if part]


def _variants(card: Mapping[str, Any]) -> set[str]:
    raw: list[Any] = [card.get("full_name")]
    report_names = card.get("report_names")
    if isinstance(report_names, Mapping):
        raw.append(
            f"{report_names.get('first_name', '')} {report_names.get('last_name', '')}"
        )
    details = card.get("details")
    if isinstance(details, Mapping):
        raw.extend(details.get(key) for key in ("display_name", "sort_name"))
    aliases = card.get("aliases")
    if isinstance(aliases, list):
        raw.extend(aliases)
    return {
        normalized
        for value in raw
        if (normalized := normalize_identity_text(value))
        and normalized != "unknownowner"
    }


def _best_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return max(
        SequenceMatcher(None, left_name, right_name).ratio()
        for left_name in left
        for right_name in right
    )


def _trigrams(value: str) -> set[str]:
    if len(value) < 3:
        return {value} if value else set()
    padded = f"^{value}$"
    return {padded[index : index + 3] for index in range(len(padded) - 2)}


def _consonant_skeleton(value: str) -> str:
    without_vowels = "".join(
        character for character in value if character not in "aeiouy"
    )
    collapsed: list[str] = []
    for character in without_vowels:
        if not collapsed or collapsed[-1] != character:
            collapsed.append(character)
    return "".join(collapsed)


def _bucket_pairs(
    bucket: Iterable[int], *, maximum_block_size: int
) -> Iterable[tuple[int, int]]:
    values = sorted(set(int(value) for value in bucket))
    if not 2 <= len(values) <= maximum_block_size:
        return ()
    return itertools.combinations(values, 2)


def build_shortlist(
    cards: list[dict[str, Any]],
    *,
    name_similarity: float,
    ngram_jaccard: float,
    employer_name_similarity: float,
    maximum_block_size: int,
) -> list[dict[str, Any]]:
    cards_by_id = {int(card["person_id"]): card for card in cards}
    variants_by_id = {
        person_id: _variants(card) for person_id, card in cards_by_id.items()
    }
    primary_by_id = {
        person_id: normalize_identity_text(card.get("full_name"))
        for person_id, card in cards_by_id.items()
    }
    pairs: dict[tuple[int, int], dict[str, Any]] = {}

    def add_pair(
        left_id: int,
        right_id: int,
        method: str,
        *,
        similarity: float | None = None,
    ) -> None:
        if left_id == right_id:
            return
        key = tuple(sorted((int(left_id), int(right_id))))
        item = pairs.setdefault(
            key,
            {
                "candidate_id": f"pair_{key[0]}_{key[1]}",
                "person_ids": list(key),
                "retrieval": {
                    "methods": [],
                    "maximum_name_similarity": None,
                    "embedding_scores": {},
                    "signals": [],
                },
            },
        )
        if method not in item["retrieval"]["methods"]:
            item["retrieval"]["methods"].append(method)
        if similarity is not None:
            previous = item["retrieval"]["maximum_name_similarity"]
            if previous is None or similarity > previous:
                item["retrieval"]["maximum_name_similarity"] = round(
                    float(similarity), 6
                )

    exact_buckets: dict[str, list[int]] = defaultdict(list)
    for person_id, variants in variants_by_id.items():
        for variant in variants:
            exact_buckets[variant].append(person_id)
    for bucket in exact_buckets.values():
        for left_id, right_id in _bucket_pairs(
            bucket, maximum_block_size=maximum_block_size
        ):
            add_pair(left_id, right_id, "exact_name_or_alias", similarity=1.0)

    structured_name_buckets: dict[str, list[int]] = defaultdict(list)
    for person_id, card in cards_by_id.items():
        words = _words(card.get("full_name"))
        if len(words) >= 2:
            structured_name_buckets[f"{words[0][0]}:{words[-1]}"].append(person_id)
            structured_name_buckets[f"{words[0]}:{words[-1][0]}"].append(person_id)
    for bucket in structured_name_buckets.values():
        for left_id, right_id in _bucket_pairs(
            bucket, maximum_block_size=maximum_block_size
        ):
            similarity = _best_similarity(
                variants_by_id[left_id], variants_by_id[right_id]
            )
            if similarity >= name_similarity:
                add_pair(
                    left_id,
                    right_id,
                    "structured_name_block",
                    similarity=similarity,
                )

    skeleton_buckets: dict[str, list[int]] = defaultdict(list)
    for person_id, primary in primary_by_id.items():
        skeleton = _consonant_skeleton(primary)
        if len(skeleton) >= 5:
            skeleton_buckets[skeleton].append(person_id)
    for bucket in skeleton_buckets.values():
        for left_id, right_id in _bucket_pairs(
            bucket, maximum_block_size=min(maximum_block_size, 25)
        ):
            similarity = _best_similarity(
                variants_by_id[left_id], variants_by_id[right_id]
            )
            if similarity >= name_similarity:
                add_pair(
                    left_id,
                    right_id,
                    "consonant_name_skeleton",
                    similarity=similarity,
                )

    ngrams_by_id = {
        person_id: _trigrams(primary)
        for person_id, primary in primary_by_id.items()
        if primary and primary != "unknownowner"
    }
    inverted_ngrams: dict[str, list[int]] = defaultdict(list)
    for person_id, grams in ngrams_by_id.items():
        for gram in grams:
            inverted_ngrams[gram].append(person_id)
    shared_counts: Counter[tuple[int, int]] = Counter()
    ngram_block_limit = min(maximum_block_size, 80)
    for bucket in inverted_ngrams.values():
        for pair in _bucket_pairs(bucket, maximum_block_size=ngram_block_limit):
            shared_counts[pair] += 1
    for (left_id, right_id), shared in shared_counts.items():
        union = len(ngrams_by_id[left_id] | ngrams_by_id[right_id])
        jaccard = shared / union if union else 0.0
        if jaccard < ngram_jaccard:
            continue
        similarity = _best_similarity(
            variants_by_id[left_id], variants_by_id[right_id]
        )
        if similarity >= name_similarity:
            add_pair(
                left_id,
                right_id,
                "character_ngram_neighbour",
                similarity=similarity,
            )

    employer_buckets: dict[str, list[int]] = defaultdict(list)
    for person_id, card in cards_by_id.items():
        for employer in card.get("employers", []):
            normalized = normalize_identity_text(employer)
            if normalized:
                employer_buckets[normalized].append(person_id)
    for bucket in employer_buckets.values():
        for left_id, right_id in _bucket_pairs(
            bucket, maximum_block_size=maximum_block_size
        ):
            similarity = _best_similarity(
                variants_by_id[left_id], variants_by_id[right_id]
            )
            if similarity >= employer_name_similarity:
                add_pair(
                    left_id,
                    right_id,
                    "shared_employer_with_name_similarity",
                    similarity=similarity,
                )

    image_buckets: dict[str, list[int]] = defaultdict(list)
    for person_id, card in cards_by_id.items():
        normalized = normalize_url(card.get("image_url"))
        if normalized:
            image_buckets[normalized].append(person_id)
    for bucket in image_buckets.values():
        for left_id, right_id in _bucket_pairs(bucket, maximum_block_size=5):
            similarity = _best_similarity(
                variants_by_id[left_id], variants_by_id[right_id]
            )
            add_pair(
                left_id,
                right_id,
                "shared_noncommon_image_url",
                similarity=similarity,
            )

    result = list(pairs.values())
    for candidate in result:
        left_id, right_id = candidate["person_ids"]
        candidate["retrieval"]["methods"].sort()
        candidate["retrieval"]["signals"] = pair_signals(
            cards_by_id[left_id], cards_by_id[right_id]
        )
        candidate["retrieval"]["maximum_embedding_score"] = None

    method_weights = {
        "shared_noncommon_image_url": 6,
        "exact_name_or_alias": 5,
        "shared_employer_with_name_similarity": 3,
        "consonant_name_skeleton": 2,
        "structured_name_block": 2,
        "character_ngram_neighbour": 1,
    }

    def sort_key(item: Mapping[str, Any]) -> tuple[float, float, str]:
        retrieval = item["retrieval"]
        method_score = sum(
            method_weights.get(method, 0) for method in retrieval["methods"]
        )
        similarity = retrieval.get("maximum_name_similarity") or 0.0
        return (-float(method_score), -float(similarity), str(item["candidate_id"]))

    result.sort(key=sort_key)
    return result


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists():
        print(f"Refusing to overwrite existing candidate file: {args.output}", file=sys.stderr)
        return 1
    if not 0.0 <= args.name_similarity <= 1.0:
        print("--name-similarity must be between 0 and 1", file=sys.stderr)
        return 1
    if not 0.0 <= args.ngram_jaccard <= 1.0:
        print("--ngram-jaccard must be between 0 and 1", file=sys.stderr)
        return 1
    if not 0.0 <= args.employer_name_similarity <= 1.0:
        print("--employer-name-similarity must be between 0 and 1", file=sys.stderr)
        return 1
    if args.maximum_block_size < 2:
        print("--maximum-block-size must be at least 2", file=sys.stderr)
        return 1
    try:
        document = load_json(args.input)
        cards = [build_identity_card(owner) for owner in document["owners"]]
        candidates = build_shortlist(
            cards,
            name_similarity=args.name_similarity,
            ngram_jaccard=args.ngram_jaccard,
            employer_name_similarity=args.employer_name_similarity,
            maximum_block_size=args.maximum_block_size,
        )
        method_counts = Counter(
            method
            for candidate in candidates
            for method in candidate["retrieval"]["methods"]
        )
        output = {
            "schema_version": 1,
            "dataset": CANDIDATE_DATASET,
            "generated_at": utc_now(),
            "source": {
                "owner_snapshot": str(args.input.resolve()),
                "owner_snapshot_sha256": file_sha256(args.input),
                "owner_exported_at": document.get("exported_at"),
                "owner_count": len(document["owners"]),
                "owner_snapshot_complete": bool(
                    document.get("source", {}).get("complete", True)
                ),
            },
            "configuration": {
                "review_mode": "codex_skill",
                "name_similarity": args.name_similarity,
                "ngram_jaccard": args.ngram_jaccard,
                "employer_name_similarity": args.employer_name_similarity,
                "maximum_block_size": args.maximum_block_size,
            },
            "summary": {
                "candidate_count": len(candidates),
                "candidate_owner_count": len(
                    {
                        person_id
                        for candidate in candidates
                        for person_id in candidate["person_ids"]
                    }
                ),
                "method_counts": dict(sorted(method_counts.items())),
            },
            "candidates": candidates,
        }
        atomic_write_json(args.output, output)
    except Exception as exc:
        print(f"Candidate shortlist failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Wrote {len(candidates)} candidate pair(s) to {args.output}; "
        f"retrieval methods={dict(sorted(method_counts.items()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
