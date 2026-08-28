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

`research_status=complete` means the identity and every proposed conclusion
have reached a terminal research decision. It does not mean that every desired
field is publicly knowable. Use supported `Unknown` classifications and record
evidence limits under `uncertainties`; do not use `limited` merely because a
resolved person has a sparse public profile.

## Forbes check

Search the exact name on Forbes and with `site:forbes.com/profile`. A verified
profile must match the target's business, geography, and other identity facts.
Record:

- `verified`: exact matching profile;
- `not_found`: focused searches produced no credible profile;
- `ambiguous`: a profile exists but identity is not secure;
- `unavailable`: access or search failure prevented a reliable check.

For `verified`, retain the exact profile URL and always include it as a
`Forbes` type/URL entry in the staff-facing `Social Media Profiles` table. The
verified URL must not exist only in the separate `forbes_profile` research
object or a narrative Forbes-check section. In a repo-backed dossier, do not
duplicate an identical existing social link; propose it when the owner record
lacks it. For `not_found`, `ambiguous`, or `unavailable`, add no Forbes link and
report the status only in `Research context`.

Forbes is a priority source for both industry classifications,
`source of wealth`, and
self-made/inherited classification, but corroborate the underlying history
where possible.

## Wealth classification

Read [wealth-classification.md](wealth-classification.md) and always populate
its four independent objects:

- `wealth_creation_industry`: the sector principally responsible for creating
  the original fortune;
- `primary_industry`: the sector principally underpinning current identifiable
  private wealth;
- `wealth_origin`: how the person acquired or gained access to it;
- `wealth_relationship`: the person's principal relationship to the
  wealth-producing assets.

Each object must contain a valid `classification`, its exact mapped `label`, a
concrete `summary`, `confidence`, and `source_ids`. Non-`unknown`
classifications require confidence 70 or higher. Inherited and royal status
describe origin, not either industry. Do not treat state, crown, sovereign, or
office-held assets as personal property without strong evidence.

Within self-made wealth, distinguish a materially independent start from an
advantaged one when strong sources establish the person's family and starting
platform. Retain broad `self_made` when the person demonstrably created the
core asset but the starting position cannot be classified reliably. This
distinction recognises founder-built success without turning an affluent,
connected, or industry-embedded upbringing into a blank-slate story.

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

Only scores of 70 or higher belong in `proposed_details`, `proposed_socials`,
or `proposed_tags`. Put lower-confidence candidates in
`candidates_requiring_review` or `uncertainties`.

## Biographies

Read [biography-style.md](biography-style.md). For `record_type=person`,
populate:

- `biography`: a standalone 50-55 word short biography in one paragraph;
- `long_biography`: a standalone 90-190 word biography in exactly two
  paragraphs.
- `biography_brief`: the durable, source-backed fact bridge used for the
  separate editorial pass.

The short biography is an information-rich identity card. When reliable
sources make them available, it should compactly establish nationality or
background, defining work, geographic base, a broad durable wealth descriptor
such as `billionaire`, the concrete origin of wealth or prominence, and
causally relevant family context. Do not force, infer, or announce the absence
of any unavailable element. Prefer a broad sourced descriptor over a current
net-worth figure or ranking.

The longer biography is an edited profile, not an expanded wealth-origin
answer. It must orient the reader, select the strongest narrative angle, and
use only the formative, decisive, operating, public, or personal material that
improves the portrait. When `wealth_origin` is
`self_made_advantaged`, at least one biography must state the material starting
advantage naturally while preserving the person's separately evidenced
achievement. Put it in the short biography when omission would create a
misleading blank-slate impression.

Each biography has its own `confidence` and `source_ids`. Its confidence cannot
exceed the weakest material claim it contains. Every material claim must be
supported by the source ledger. Do not pad sparse profiles or repeat, reorder,
or paraphrase the short biography's complete fact bundle in the long profile.
Both biographies must remain accurate and coherent if the person later sells
every vessel in the owner record.

Never include a personally owned vessel merely because it is current, large,
recently commissioned, successively owned, or used to determine cohort rank.
Vessel names, dimensions, builders, and ownership histories belong in the
system's vessel data. Independently significant maritime careers or sustained
competitive, research, or philanthropic work may be described, but the
biography must focus on that durable activity rather than the transient asset.

The schema-v8 brief is an unordered editorial fact pool, not a paragraph
outline. It contains:

- `durable_identity`: the clearest durable description of the person;
- `defining_work`: the product, institution, asset, achievement, or public
  contribution that most clearly explains why the person matters;
- nullable `formative_context` and `decisive_moment`; material family or
  starting-position context belongs in `formative_context`;
- `enduring_dimensions`: one to three durable aspects that may deepen either
  paragraph;
- optional `character_detail`;
- `opening_options`: at least two fact-level angles using distinct opening
  modes;
- `excluded_transient_context`; and
- `source_ids`.

Do not include the schema-v5 outline fields `wealth_or_prominence_route`,
`turning_point`, or `later_chapter`. Wealth-origin reasoning remains in its
classification object and source ledger. An opening option is an editorial
angle, not drafted prose.

Before drafting, make a temporary fact-allocation table with no more than two
shared anchors, at least one short-only fact or dimension, at least two
substantive long-only facts or dimensions, and explicit short-biography
material the long version will omit. This table is working editorial material;
do not add it to the schema-v8 dossier.

Draft without source publishers, confidence language, classification
deliberation, current-vessel context, or the order of the brief fields. Select
and record one `opening_mode` and one `narrative_shape`, then review the texts
as a pair and reverse-check claims against the source ledger. Record all seven
4-or-5 editorial rubric scores, relevant calibration archetype(s), and a
concise revision note under `editorial_assessment`. The note should identify
the shared anchor and the material unique to the long profile. Do not award
`structural_independence=5` while a pair-audit finding remains.

Allowed opening modes are:

- `present_identity`
- `defining_achievement`
- `decisive_event`
- `institution_or_asset`
- `formative_episode`
- `inherited_responsibility`
- `public_contribution`

Allowed narrative shapes are:

- `identity_then_origin`
- `achievement_then_backstory`
- `decision_then_consequence`
- `institution_then_person`
- `formative_episode_then_payoff`
- `inheritance_then_stewardship`
- `core_work_deepened`
- `public_role_then_foundation`

For a batch, distribute these choices according to the material. They are
editorial planning metadata, not labels to mention in published prose.

For `record_type=institution`, set `biography_brief` and
`editorial_assessment` to `null`, populate the existing `biography` and
`long_biography` objects with a durable description of the public body, and
use `research_status=complete`. Also populate a 20-120 word `editorial_note`
explaining the non-person classification. The biographies are mapped to the
website fields; the note remains review context only.

Institution dossiers may propose only the existing `biography` and
`long_biography` detail fields; they must not propose person-specific details
or social links.

For `record_type=unresolved_placeholder`, set `biography_brief`,
`editorial_assessment`, `biography`, and `long_biography` to `null`. Populate a
20-120 word `editorial_note` explaining the identity limitation. Unresolved
placeholders must not propose details or social links.

The compiler always maps `biography.html` to the existing `details.biography`.
When the source owner exposes `details.long_biography`, it also maps
`long_biography.html` there. Both biography objects remain available under
compiled `ai_research` metadata even when the longer website field does not yet
exist.

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

- `display_name`
- `title`, `first_name`, `middle_names`, `last_name`, and `name_suffix`
- `nationality` and `secondary_nationality`
- `main_residence_country` and `secondary_residence_country`
- `known_for_title`
- `gender`
- `place_of_birth` and `birth_country`
- `birth_day`, `birth_month`, and `birth_year`
- `mortality_status`
- `death_day`, `death_month`, and `death_year` when applicable
- `biography`
- `wealth_origin`
- `wealth_relationship`
- `wealth_creation_industry`
- `primary_industry`
- `long_biography`

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

## Tag selection

Populate `proposed_tags` during every new research pass. Apply the agreed test:
include every durable, material, dossier-supported tag that would create a
meaningful grouping. Tags are additive research metadata, so they are not
limited to blank owner fields and may cover industries, sports, royal houses,
business families, durable roles, distinctive causes, named companies, or
other catalogued associations.

The catalogue is an evolving canonical registry, not a closed whitelist. Only
part of the owner corpus has completed research, so absence from the current
catalogue or completed dossiers must never prevent a qualifying tag from being
proposed or created. A tag qualifies when it does at least one of the following:

- adds a useful subindustry below a broad industry classification;
- captures a durable, interesting occupation, sport, status, or public role;
- creates a meaningful cross-industry grouping; or
- supports a plausible user question about owner or yacht patterns.

Reject a candidate that merely renames an industry classification, repeats
wealth origin or wealth relationship, describes a commonplace billionaire
attribute, represents a minor portfolio holding, or lacks durable materiality.
For analytical subindustries, prefer concepts likely to form a useful cohort;
rare but inherently browse-worthy identities such as actors or professional
athletes do not require a minimum count.

Use `Government-owned` as a status tag when the owner record itself is a
government, ministry, municipality, state agency, comparable public body, or an
institution explicitly documented as government- or state-owned. This tag
describes public ownership of the owner entity and therefore enables analysis
of the yachts associated with those entities. Do not apply it to a person
merely because they hold public office, chair or work for a state enterprise,
manage sovereign assets, or supply a government. `Government contracting`
remains the separate private-business model tag. Royal or crown-associated
assets qualify only when reliable evidence establishes public/state ownership
rather than the ruler's or royal family's private ownership.

Apply this canonicalisation workflow in order:

1. Normalize the candidate and compare it with every canonical name and alias.
2. Check semantic equivalence. If it is reasonably the same concept, use the
   existing canonical tag; in a repo-backed run, add a durable missing alias
   when that will improve future resolution.
3. Do not collapse broader and narrower concepts into aliases. `Banking` is not
   an alias of `Finance & Investments`, and `Luxury goods` is not an alias of
   `Fashion & Retail`; their extra granularity is the point.
4. If a distinct candidate passes the taxonomy rule in a repo-backed run,
   allocate the next unused monotonic local ID, add its canonical name,
   aliases, and facets to `config/owner-tags.json`, then resolve the dossier to
   that new ID. Use a type facet such as `subindustry`, `occupation`, `sport`,
   `company`, `status`, or `business model`; subindustries also use every
   applicable `parent:<classification>` facet, such as
   `parent:finance_investments`.
5. In a batch, research subagents return null-ID candidates. Only the main
   agent consolidates semantic duplicates, updates the shared catalogue, and
   replaces candidate null IDs before final validation.
6. In Custom GPT mode the uploaded Knowledge cannot be mutated. Keep the
   defensible candidate in `proposed_tags` with `tag_id: null`, identify it
   separately as a **New catalogue candidate**, and explicitly tell the user
   that `tag-catalogue.json` Knowledge must be updated before the tag can have
   a canonical ID or become compilation-ready. Never invent an ID.

After any repo-backed catalogue change, rebuild the tracked Custom GPT
Knowledge and tag catalogue with `scripts/build_gpt_knowledge.py`, run its
`--check` mode, and validate tag resolution. Existing parent-aligned
compatibility tags such as `Cryptocurrency` and `Gambling` are not precedent
for creating new duplicates of industry labels.

Use the dry-run-first helper for repo-backed additions after completing the
semantic review:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\add_catalogue_tag.py `
  --name "Luxury goods" `
  --alias "Luxury brands" `
  --facet subindustry `
  --facet parent:fashion_retail `
  --facet luxury
```

Rerun with `--apply` only after inspecting the proposed canonical entry. The
helper catches normalized name or alias reuse, allocates the next monotonic
local ID, requires exactly one type facet, requires a parent for subindustries,
sorts the catalogue, validates it, and writes atomically. It cannot decide
semantic equivalence; that remains the research agent's responsibility.

When semantic review shows that a new label is an alias of an existing tag,
teach that alias to the registry instead of creating a tag:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\add_catalogue_tag.py `
  --name "Luxury sector" `
  --alias-for "Luxury goods"
```

Inspect the dry-run and rerun with `--apply`. `--alias-for` accepts a canonical
name, existing alias, or local ID and rejects labels already owned by another
canonical tag.

Use `config/owner-tags.json` as the canonical research-layer registry. Store
both `tag_id` and `name` when the local ID is known. `tag_id` may be `null` for
a Custom GPT catalogue candidate; never invent an ID. Compilation resolves
names and aliases, follows `merged_into`, and stops with an explicit unknown or
ambiguous result instead of silently creating a tag.
When `tag_id` is present it is authoritative, and `name` must match that tag's
canonical name or one of its aliases; the name remains a readable snapshot.

Each proposal contains:

- `tag_id`: a catalogue ID or `null`;
- `name`: the canonical name when known, otherwise the researched name;
- `summary`: a concise explanation of the durable, material association;
- confidence of at least 70; and
- one or more `source_ids` directly supporting the association.

Do not add tangential employers, transient interests, unsupported surname-only
family links, or tags inferred only from another classification. Do not use
`Family business`, `Property development`, `Family office`, `Arts & culture
philanthropy`, `Children & youth philanthropy`, `Education philanthropy`,
`Health philanthropy`, or `Science philanthropy`. These generic tags are
deliberately excluded; this does not remove the separate
`family_office_principal` wealth-relationship classification or distinctive
cause tags such as `Humanitarian aid` and `Marine / ocean conservation`.

Treat bare `Gaming` as an alias for the casino, betting, and gambling-industry
`Gambling` tag. Use `Video games` only when evidence explicitly concerns video
games, game development, game publishing, or an equivalent interactive-
entertainment business. Do not repeat names that normalize to the same
casefolded, punctuation-insensitive form; compilation also rejects different
aliases that resolve to the same canonical tag. An empty list is valid only
when no supported tag meets the applicability test. Unresolved placeholders
must use an empty list.

## Staff-facing owner-page response

The default human-readable response is an entry aid for editorial staff. Put
the copyable owner values first under `## Owner page fields`, using the site's
visible labels and this page order:

1. **Details:** `Display Name`, `Title`, `First Name`, `Middle Names`,
   `Last Name`, `Name Suffix`, `Nationality`, `Secondary Nationality`,
   `Main Residence Country`, `Secondary Residence Country`,
   `Known For Title`.
2. **Birth:** `Gender`, `Place Of Birth`, `Birth Country`, `Birth Day`,
   `Birth Month`, `Birth Year`, `Mortality Status`, `Death Day`, `Death Month`,
   `Death Year`.
3. **Descriptions & Notes:** `Biography`.
4. **HNWI Profile — Wealth:** `Wealth Origin`, `Wealth Relationship`,
   `Wealth Creation Industry`, `Primary Industry`.
5. **HNWI Profile — Long Biography:** `Long Biography`.
6. **Aliases & Tags:** `Tags`.
7. **Social Media Profiles:** verified profile type and URL pairs. A verified
   Forbes result is mandatory here as a `Forbes` row with its exact profile
   URL; it must not be relegated to a separate Forbes section.

Within each section, include only supported values and preserve the listed
relative order. Omit unsupported fields entirely; do not insert speculative
values, `Unknown`, dashes, or copyable placeholders. Render scalar values as
`**Visible Field Label:** value`. Put biography prose beneath its field label,
list canonical tags one per line, and use a two-column `Type` / `URL` table for
social profiles. Use exact visible dropdown labels for the four wealth fields.
Keep explanations, confidence, citations, source IDs, verification notes, and
research narration out of this copy block. New null-ID catalogue candidates do
not yet belong in its canonical `Tags` list.

Do not reproduce fields the research workflow does not populate, including
`Unknown Name`, sort-name fields, internal notes, calculated ages, net-worth
fields, addresses, vessel relationships, employment relationships, and system
metadata.

After the copy block, put supporting material under `## Research context`:
identity resolution and confidence, the Forbes check, wealth and tag reasoning
with confidence, strongest evidence, new catalogue candidates and their
Knowledge-update notice, other verified candidate facts, uncertainties,
limitations, and the linked source list. This secondary section may explain
why a field was omitted, but it must never interrupt the owner-page sequence.

## Dossier shape

Use this top-level structure:

```json
{
  "schema_version": 8,
  "record_type": "person",
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
  "biography_brief": {
    "durable_identity": "Example industrial founder.",
    "defining_work": "A product innovation became the foundation of an operating company.",
    "formative_context": "Engineering training supplied the technical background.",
    "decisive_moment": "The founder acquired a larger former employer.",
    "enduring_dimensions": [
      "Direct operating control",
      "Investment in sport"
    ],
    "character_detail": "The business combined engineering with retained control.",
    "opening_options": [
      {
        "mode": "defining_achievement",
        "angle": "Use the product innovation to establish why the founder matters."
      },
      {
        "mode": "decisive_event",
        "angle": "Use the acquisition to establish the scale-changing decision."
      }
    ],
    "excluded_transient_context": [
      "Current vessel ownership",
      "Current net worth"
    ],
    "source_ids": ["S1", "S2"]
  },
  "editorial_assessment": {
    "causal_clarity": 5,
    "human_specificity": 4,
    "durability": 5,
    "source_invisibility": 5,
    "natural_voice": 4,
    "reader_orientation": 5,
    "structural_independence": 4,
    "opening_mode": "defining_achievement",
    "narrative_shape": "achievement_then_backstory",
    "calibration_archetypes": ["founder_operator"],
    "notes": "The long profile opens on a defining product, deepens the operating story, and ends on a concrete role."
  },
  "editorial_note": null,
  "forbes_profile": {
    "status": "verified",
    "url": "https://www.forbes.com/profile/example-owner/",
    "confidence": {
      "score": 95,
      "band": "very_high",
      "reason": "..."
    }
  },
  "wealth_creation_industry": {
    "classification": "manufacturing",
    "label": "Manufacturing",
    "summary": "...",
    "confidence": {
      "score": 92,
      "band": "high",
      "reason": "..."
    },
    "source_ids": ["S1", "S2"]
  },
  "primary_industry": {
    "classification": "manufacturing",
    "label": "Manufacturing",
    "summary": "...",
    "confidence": {
      "score": 92,
      "band": "high",
      "reason": "..."
    },
    "source_ids": ["S1", "S2"]
  },
  "wealth_origin": {
    "classification": "self_made",
    "label": "Self-made",
    "summary": "...",
    "confidence": {
      "score": 92,
      "band": "high",
      "reason": "..."
    },
    "source_ids": ["S1", "S2"]
  },
  "wealth_relationship": {
    "classification": "founder",
    "label": "Founder",
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
    "word_count": 53,
    "confidence": {
      "score": 90,
      "band": "high",
      "reason": "..."
    },
    "source_ids": ["S1", "S2"]
  },
  "long_biography": {
    "plain_text": "First paragraph...\n\nSecond paragraph...",
    "html": "<p>First paragraph...</p>\r\n<p>Second paragraph...</p>\r\n",
    "word_count": 140,
    "confidence": {
      "score": 90,
      "band": "high",
      "reason": "..."
    },
    "source_ids": ["S1", "S2"]
  },
  "proposed_details": [],
  "proposed_socials": [],
  "proposed_tags": [],
  "candidates_requiring_review": [],
  "sources": [],
  "uncertainties": [],
  "review": {
    "status": "complete",
    "notes": null
  }
}
```

Each proposed item must contain `confidence` and `source_ids`. Each source must
contain `id`, `url`, `title`, `publisher`, `tier`, `accessed_at`, and
`supports`. Proposed detail items must also contain `action`; corrections must
contain `existing_value`; proposed social items must contain `type_id` copied
from `input_snapshot.social_type_lookup`. Proposed tag items must also contain
`tag_id`, `name`, and `summary` as defined above.

Research agents emit `review.status=complete` only after the dossier reaches a
terminal research decision and passes validation. This status is automatic
acceptance for compilation; no reviewer identity is required. Legacy
`pending`, `approved`, and `rejected` states remain validator-compatible for
existing dossiers, and legacy approved or rejected states retain their
`reviewed_by` and `reviewed_at` requirements.

## Non-person dossier shape

An institution retains the same evidence, classification, Forbes-check,
uncertainty, and review objects, with these differences:

```json
{
  "schema_version": 8,
  "record_type": "institution",
  "research_status": "complete",
  "biography_brief": null,
  "editorial_assessment": null,
  "biography": {
    "plain_text": "A 50-55 word user-facing description of the institution.",
    "html": "<p>A 50-55 word user-facing description of the institution.</p>\r\n",
    "word_count": 50,
    "confidence": {
      "score": 98,
      "band": "very_high",
      "reason": "Official sources establish the institution and its role."
    },
    "source_ids": ["S1"]
  },
  "long_biography": {
    "plain_text": "A 90-190 word institutional profile in two paragraphs.",
    "html": "<p>A 90-190 word institutional profile in two paragraphs.</p>\r\n<p>The second paragraph supplies complementary durable context.</p>\r\n",
    "word_count": 90,
    "confidence": {
      "score": 98,
      "band": "very_high",
      "reason": "Official sources establish the institution and its role."
    },
    "source_ids": ["S1"]
  },
  "editorial_note": {
    "plain_text": "This owner record represents a public institution rather than a natural person. Person-specific biography, private-wealth, and social-profile proposals are therefore not applicable.",
    "confidence": {
      "score": 98,
      "band": "very_high",
      "reason": "Official records establish the institutional identity."
    },
    "source_ids": ["S1"]
  },
  "proposed_details": [],
  "proposed_socials": [],
  "proposed_tags": []
}
```

Institution biographies describe the continuing public body, its structure,
and its durable functions. They must not be biographies of a current
officeholder and must remain accurate after elections, appointments, or other
changes of personnel.

Use `record_type=unresolved_placeholder` with `research_status` set to
`identity_conflict` or `insufficient_evidence` when the record purports to be
a person but no defensible identity can be resolved. These dossiers retain
null biography fields and use only the editorial note.
