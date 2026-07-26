# Research and dossier contract

## Source hierarchy

Use the strongest available source for each claim:

1. **Tier 1:** official personal/company/team pages, company filings, government
   records, direct interviews, and profiles linked by an official entity.
2. **Tier 2:** Forbes profiles and reporting, Bloomberg, Reuters, major
   newspapers, and established business publications.
3. **Tier 3:** well-cited Wikipedia sections and reputable specialist press.
4. **Tier 4:** aggregators, scraped biographies, unsourced lists, search
   snippets, and user posts. Use only as discovery leads.

Two weak sources do not equal one strong source. Prefer a primary source plus
independent corroboration for identity, wealth origin, and social profiles.

## Identity resolution

Score identity separately from individual facts. Match as many of these as
available:

- full name and aliases;
- company, profession, or public role;
- yacht ownership or family relationship;
- nationality, age, and geography;
- spouse, child, or associate names;
- official profile cross-links.

Do not continue below identity confidence 85. Use `identity_conflict` for
contradictory matches and `insufficient_evidence` when no match is strong
enough.

## Forbes check

Search the exact name on Forbes and with `site:forbes.com/profile`. A verified
profile must match the target's business, geography, and other identity facts.
Record:

- `verified`: exact matching profile;
- `not_found`: focused searches produced no credible profile;
- `ambiguous`: a profile exists but identity is not secure;
- `unavailable`: access or search failure prevented a reliable check.

Forbes is a priority source for `source of wealth` and self-made/inherited
classification, but corroborate the underlying history where possible.

## Wealth-origin classification

Choose the closest evidence-backed classification:

- `self_made_operating_business`
- `self_made_finance_investment`
- `inherited`
- `inherited_and_expanded`
- `family_business`
- `privatization_or_state_assets`
- `natural_resources`
- `real_estate`
- `entertainment_or_sport`
- `mixed`
- `unclear`

The summary must explain the mechanism: inherited stake, founded company,
industrial invention, acquisition, resource concession, property development,
investment career, or another specific route. Do not substitute a net-worth
number for this explanation.

## Confidence

Every confidence object has:

```json
{
  "score": 92,
  "band": "high",
  "reason": "Exact official biography corroborated by Forbes."
}
```

Bands are deterministic:

| Score | Band | Use |
| --- | --- | --- |
| 95-100 | `very_high` | Direct primary evidence or an exact official profile |
| 85-94 | `high` | Strong source with independent corroboration |
| 70-84 | `medium` | Plausible but needs human review |
| 50-69 | `low` | Weak or incomplete evidence |
| 0-49 | `insufficient` | Do not use |

Only scores of 85 or higher belong in `proposed_details` or
`proposed_socials`. Put lower-confidence candidates in
`candidates_requiring_review` or `uncertainties`.

## Social links

Inventory the exact `lookups.social_media_types` values from the supplied owner
document. Prioritise Instagram, LinkedIn, and Personal Website, then other
person-relevant platforms. Treat directory or property types such as Trip
Advisor and Zillow as unsupported unless the owner's public role makes them
material.

Accept a personal social URL only when one of these is true:

- it is linked from the person's official website or official organisation
  profile;
- the social profile links back to an official domain and matches multiple
  identity facts;
- two strong independent sources identify the same account.

A verified badge, matching name, follower count, or search ranking alone is not
enough. Do not substitute company, sports-team, fan, family-member, or parody
accounts for a personal account. Record a genuine absence as a useful result.
Never guess the website's `type_id`; copy it from the owner document lookup or
leave it null for reviewer mapping.

A company URL is not a personal URL. It may be proposed only as `Company
Website`, when the person founded, owns, or leads the company and a Tier 1 or
Tier 2 source establishes the relationship.

## Personal fields

Common proposal fields include:

- `known_for_title`
- `nationality` and `secondary_nationality`
- `main_residence_country` and `secondary_residence_country`
- `place_of_birth` and `birth_country`
- `birth_day`, `birth_month`, and `birth_year`
- `gender`
- `mortality_status`
- `biography`

Propose only fields that are missing or demonstrably wrong in the supplied
record. Do not propose calculated age fields. Preserve the site's visible
select labels and existing field structure when later integration is approved.

## Input gap inventory

Run `scripts/inventory_owner.py` against the exact source record before
research. Preserve its `source_path`, raw blanks, researchable blanks, existing
social types, missing priority social types, and social lookup in
`input_snapshot`.

Pass that same source document to `scripts/validate_dossier.py --owner-input`
so the validator can reject stale or invented snapshots.

Classify blanks before research:

- `researchable`: a public fact could usefully fill the field;
- `optional`: honorifics, suffixes, or secondary fields that may legitimately
  be empty;
- `not_applicable_while_alive`: death fields for a living person;
- `calculated_or_system`: calculated age and internal workflow fields.

Only `researchable` gaps should normally become `proposed_details`. Use
`action=fill_missing` for a blank and `action=correct_existing` only when
strong evidence demonstrates an existing value is wrong. Every correction must
copy the input value into `existing_value` so stale proposals can be rejected.

## Dossier shape

Use this top-level structure:

```json
{
  "schema_version": 2,
  "owner": {
    "person_id": null,
    "display_name": "Example Owner",
    "identity_confidence": {
      "score": 95,
      "band": "very_high",
      "reason": "..."
    }
  },
  "input_snapshot": {
    "source_path": "output/owners-list.top-100.enriched.json",
    "raw_blank_details": ["middle_names", "place_of_birth"],
    "researchable_missing_details": ["middle_names", "place_of_birth"],
    "optional_missing_details": [],
    "inapplicable_or_system_details": [],
    "existing_social_types": ["Wikipedia", "Forbes"],
    "missing_priority_social_types": ["Instagram", "LinkedIn", "Personal Website"],
    "social_type_lookup": {
      "5": "LinkedIn",
      "9": "Instagram",
      "14": "Company Website",
      "15": "Personal Website"
    }
  },
  "research_status": "complete",
  "forbes_profile": {
    "status": "verified",
    "url": "https://www.forbes.com/profile/example-owner/",
    "confidence": {
      "score": 95,
      "band": "very_high",
      "reason": "..."
    }
  },
  "wealth_origin": {
    "classification": "self_made_operating_business",
    "summary": "...",
    "confidence": {
      "score": 92,
      "band": "high",
      "reason": "..."
    },
    "source_ids": ["S1", "S2"]
  },
  "biography": {
    "plain_text": "...",
    "html": "<p>...</p>\r\n",
    "word_count": 70,
    "confidence": {
      "score": 90,
      "band": "high",
      "reason": "..."
    },
    "source_ids": ["S1", "S2"]
  },
  "proposed_details": [],
  "proposed_socials": [],
  "candidates_requiring_review": [],
  "sources": [],
  "uncertainties": [],
  "review": {
    "status": "pending",
    "notes": null
  }
}
```

Each proposed item must contain `confidence` and `source_ids`. Each source must
contain `id`, `url`, `title`, `publisher`, `tier`, `accessed_at`, and
`supports`. Proposed detail items must also contain `action`; corrections must
contain `existing_value`; proposed social items must contain `type_id` copied
from `input_snapshot.social_type_lookup`.

Research agents always emit `review.status=pending`. A human reviewer may later
change it to `approved` or `rejected`; either final state must also include
non-empty `reviewed_by` and `reviewed_at` values. Approval is a separate human
action and must never be inferred from confidence.
