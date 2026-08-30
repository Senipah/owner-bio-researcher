# Duplicate owner review contract

Use this contract for every pair in a prepared review batch.

## Decision labels

- `probable_duplicate`: strong, specific evidence supports one real identity and
  a separate skeptical pass also concludes `probable_duplicate`.
- `possible_duplicate`: the identity connection is plausible but incomplete,
  ambiguous, or not independently strong enough.
- `probably_distinct`: supplied evidence positively favours two different
  people. Do not use this merely because fields are blank.
- `insufficient_evidence`: neither a match nor a distinction is supportable.

The compiler may emit `needs_manual_review` when a probable primary judgment
lacks a probable skeptical verification. Agents must not write that label
directly.

## Evidence weighting

Strong evidence can include a unique shared social URL, compatible full birth
details, a direct primary-name/AKA relationship plus independent context, or
several specific facts that coherently identify one person. Check that URLs or
images are not generic, institutional, placeholder, or reused.

Corroborating evidence includes compatible employers, occupation, nationality,
residence, vessel relationships, name order, transliteration, title, suffix,
and middle names. None is usually unique by itself.

Contradictions include incompatible complete birth dates, clearly different
middle or family names combined with distinct careers, separate personal social
accounts, or evidence that the records are relatives or colleagues. Missing
values are not contradictions.

Matching names, shared nationality, or shared employer alone never justify
`probable_duplicate`.

## Review sequence

1. Read both identity cards without assuming the retrieval reason is correct.
2. Explain the name relationship, including transliteration, abbreviation,
   reordering, suffix, title, or alias only when the fields support it.
3. Identify independent supporting and contradicting signals.
4. Choose a primary label and confidence from 0–100.
5. If the primary label is `probable_duplicate`, set it aside and perform a
   second skeptical pass looking specifically for namesakes, relatives, reused
   organisation data, placeholder images, and material contradictions.
6. Compare record completeness only. `more_complete_person_id` is not a merge,
   deletion, or keeper recommendation.

## Review result schema

One result file corresponds to one input batch:

```json
{
  "schema_version": 1,
  "dataset": "owner_duplicate_codex_review_batch",
  "batch_id": "batch-001",
  "reviewed_at": "ISO-8601 timestamp",
  "reviewer": "codex",
  "judgments": [
    {
      "candidate_id": "pair_12_34",
      "person_ids": [12, 34],
      "primary": {
        "classification": "possible_duplicate",
        "confidence": 72,
        "summary": "Concise conclusion grounded in the supplied fields.",
        "evidence_for": ["Specific supporting fact"],
        "evidence_against": ["Specific contradiction, or an empty array"],
        "missing_evidence": ["Evidence needed to decide more confidently"],
        "more_complete_person_id": 12,
        "completeness_reason": "Why this record is richer, without recommending deletion."
      },
      "verifier": null
    }
  ]
}
```

Every judgment field shown is required. `more_complete_person_id` must be one
of the pair IDs or `null`. A primary `probable_duplicate` requires a non-null
`verifier` with the same judgment object shape. Other primary labels use
`verifier: null` unless a genuine disagreement needs recording.

The result file must contain each candidate in its matching input batch exactly
once and no additional candidate IDs. Do not include chain-of-thought,
credentials, cookies, biographies, or internal notes.
