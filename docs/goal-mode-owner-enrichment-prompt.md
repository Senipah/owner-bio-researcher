# Goal Mode prompt: Top-100 owner research enrichment

Paste the prompt below into Goal Mode from the repository root. It produces
completed research artifacts only; it does not update the live system.

## Prompt

Use `$research-owner-biography`.

Your goal is to research every unique current owner represented in
`output/owners-list.top-100.enriched.json`, in ascending order of their minimum
current Top-100 vessel rank, and produce a review-ready research enrichment
batch.

Continue until all selected owners have:

1. one schema-v8 dossier beneath `output/owner-research/top-100/`;
2. an unordered source-hidden biography fact pool with at least two distinct
   opening options, plus validated short and longer biographies and editorial
   assessment for people, or a non-person editorial note with null
   biography/editorial fields;
3. validated `wealth_creation_industry`, `primary_industry`,
   `wealth_origin`, and `wealth_relationship` classifications;
4. an explicit Forbes result;
5. an inventory of missing details and supported link types;
6. a minimal, coherent set of approved active tags, with unrepresented facts
   preserved in ordinary research structures rather than formal candidates;
7. only confidence-70-or-higher proposed details, links, and tags;
8. `review.status=complete` after strict validation.

Use a bounded worker pool of at most three research subagents. Give each
subagent exactly one owner at a time and this skill. When one finishes and its
dossier validates, give that worker the next unprocessed owner. Do not allow
subagents to edit the shared owner JSON, source code, skill files, or another
owner's dossier. The main agent owns selection, identity review, validation,
cross-owner consistency, and compilation.

For every owner:

- run `inventory_owner.py` against the exact input and person ID;
- resolve identity using name, public role/business, geography, and yacht
  context before collecting facts;
- search Forbes first and record `verified`, `not_found`, `ambiguous`, or
  `unavailable`;
- classify wealth-creation industry, current primary industry, wealth origin,
  and wealth relationship independently using
  `references/wealth-classification.md`; use the shared Cryptocurrency
  industry only when reliable evidence establishes crypto as the relevant
  wealth-creation or current sector, not merely a later investment;
- explain where wealth or prominence came from rather than foregrounding net
  worth;
- follow `docs/ai/OWNER_TAG_GOVERNANCE.md`; treat current first-pass dossier
  tags as untrusted recommendations, apply only approved active catalogue tags
  to `proposed_tags`, and use the minimum literal set that preserves meaningful
  click-through cohorts; preserve an unrepresented fact in ordinary research
  structures and do not create a formal candidate, promote, reactivate or edit
  the catalogue from an individual dossier;
- search supported person-relevant social types, prioritising Instagram,
  LinkedIn, and Personal Website;
- reject namesake, company, fan, family-member, and uncorroborated accounts;
- use a distinct Company Website proposal only when official evidence connects
  the person to the company;
- keep lower-confidence facts and links in review candidates or uncertainties;
- set `record_type` before drafting; institutions and unresolved placeholders
  receive `editorial_note`, null biographies, and no personal proposals;
- complete research first, then build the schema-v8 `biography_brief` as an
  unordered fact pool containing durable identity, defining work, nullable
  formative context and decisive moment, one to three enduring dimensions,
  optional character detail, at least two fact-level opening options with
  distinct modes, transient exclusions, and source IDs;
- never use the schema-v5 route-turning-point-later-chapter outline;
- perform a separate editorial pass from the fact pool, deliberately select
  and record one opening mode and narrative shape, and reverse-check its claims
  against the full source ledger;
- draft a neutral 50-55 word short biography and a standalone, two-paragraph
  longer biography of 90-190 words without targeting a preferred midpoint;
- treat the longer biography as a standalone edited profile rather than an
  expanded wealth-origin answer; establish the person's defining identity,
  achievement, institution, asset, decision, inherited responsibility, or
  public contribution before supplying routine chronology;
- never open with "route into business", "path to wealth", "career began",
  "commercial footing", or "gave them their start"; use a formative episode
  only when its relevance is immediately clear;
- allow paragraph two to deepen the core work rather than force a later
  investment, sport, or philanthropy slot;
- end on a concrete fact, role, decision, or consequence, not a synthetic
  tie-back using "linking", "extending the same approach", "the arc",
  "second strand", "second thread", or equivalent phrasing;
- keep publishers, source attribution, evidence gaps, confidence,
  classification reasoning, database language, and research narration out of
  both biographies;
- keep public-versus-private asset analysis in dossier metadata; for royal and
  dynastic owners, describe verified formation, succession, public work,
  interests, and influence without contrasting them against commercial
  enterprise, entrepreneurship, or personal wealth;
- apply the sale-independence test and never use current vessel names,
  specifications, builders, delivery, commissioning, or ownership history as
  biography material;
- use British English, no more than two explicit years, no more than one
  monetary or percentage figure, normally no sentence over 30 words, and no
  dense inventory of companies, offices, charities, or investments;
- vary opening modes, narrative shapes, transitions, rhythms, and endings
  against the complete editorial calibration set;
- do not pad sparse profiles or repeat the short text verbatim;
- validate the dossier with:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  DOSSIER_PATH `
  --owner-input output\owners-list.top-100.enriched.json `
  --strict-editorial
```

Resume safely by treating an existing dossier as complete only when it passes
that exact validation command. Re-research invalid or stale dossiers. Maintain
at most three active research agents and provide concise checkpoint updates
after each group of ten validated owners.

After all dossiers validate, perform a main-agent consistency review:

- biographies meet the seven-part editorial rubric and use the complete
  calibration set without copying one structure across the cohort;
- published prose contains no source narration, classification deliberation,
  negative wealth-taxonomy contrasts, database/process language, or repeated
  AI-style conclusions;
- royal, sovereign, family, and personal wealth are not conflated, and an
  oil-producing state is not treated as evidence of personal `Energy` wealth;
- inherited, self-made, dynastic/royal, family-transfer, mixed, and unknown
  origin classifications are applied consistently;
- HNWI fields use the best-supported confidence-70-or-higher value from direct
  evidence or a disclosed reasoned inference, with every material premise and
  the asset or role's importance positively sourced; a missing exact label,
  valuation, ownership percentage, holdings schedule, or transfer instrument
  does not by itself require `Unknown`;
- the least-specific supported value is used before `Unknown`: broad
  `self_made` for a demonstrably founder-built principal asset with unresolved
  starting position, and `mixed` when multiple independently evidenced origin
  mechanisms are material without a reliable percentage split;
- industries may follow a clearly central wealth-producing business without
  an exact balance sheet; `diversified` requires several positively material
  sectors, not merely incomplete research;
- wealth relationships describe the principal current asset role:
  `founder`, `operator`, `investor`, `heir_family_shareholder`, and
  `family_office_principal` may follow their documented positive premises,
  while a historical role, title, board seat, isolated investment, or silence
  about management is insufficient; `passive_asset_owner` requires positive
  support for both ownership and passive or delegated stewardship;
- family-business succession plus present personal ownership, control,
  shareholding, beneficiary status, or reliable wealth attribution is treated
  as a medium-confidence family transfer when the exact route is not public;
  family association or a management title alone is not;
- every inference summary and confidence reason records its positive premises,
  materiality, conclusion, and important gap; no inferred field is used as
  circular support for another and no conclusion rests on absent contrary
  evidence;
- `inherited` requires supported inheritance, while
  `inherited_and_expanded` additionally requires a material, evidenced
  personal expansion or transformation;
- wealth-creation industry follows the sector that principally created the
  original fortune, current primary industry follows the principal
  identifiable private interests as of research; when current primary industry
  is unknown but the wealth-creation sector is known, use that origin sector
  for both industry fields and disclose the fallback without asserting
  current holdings;
- identity confidence must reach 75 for a resolved owner;
- wealth relationship distinguishes founders, operators, investors, heirs, family office
  principals, royal beneficiaries, custodians, and passive owners;
- proposed select values use labels supported by the owner form;
- social type IDs match the input lookup;
- no legacy approval metadata is created.

Then perform a dedicated cross-owner editorial pass. Create a working table
containing owner, opening mode, narrative shape, first sentence,
paragraph-two opening, and final sentence. Revise semantic repetition even
when exact wording differs. No single opening mode or narrative shape may
dominate business profiles, origin-story openings must be a minority, and
formulaic later-chapter transitions or synthetic tie-back conclusions must be
exceptional.

Run the cohort editorial audit and revise all issues before compilation:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\audit_biography_corpus.py `
  output\owner-research\top-100 `
  --strict
```

Compile the review artifacts:

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.top-100.enriched.json `
  --dossier-dir output\owner-research\top-100 `
  --selection top-100 `
  --output output\research-enriched-owners-list.top-100.json `
  --report output\research-enriched-owners-list.top-100.html `
  --mark-ai-enriched
```

Acceptance criteria:

- the compiled JSON contains every and only unique current Top-100 owner,
  ordered by minimum current vessel rank;
- every compiled owner has a validated dossier;
- every schema-v8 person dossier passes the strict corpus editorial audit;
- `_baseline`, `person_id`, `profile_url`, and existing `profile_key` values
  remain unchanged;
- usable completed output owners have `workflow.ai_enriched=true`, while
  unresolved placeholders remain false;
- the HTML report shows, per owner, vessel rank/context, both biographies, all
  four wealth classifications, resolved canonical tags, missing fields added, existing fields
  improved, verified links, confidence, evidence links, unresolved gaps, and
  uncertainties;
- the original input hash is unchanged;
- the offline test suite, compile checks, skill validation, dossier validation,
  and `git diff --check` all pass;
- nothing is applied to the live website.

Do not stop merely because an owner has a sparse footprint. Produce a limited
or insufficient-evidence dossier with explicit uncertainties. Stop and request
user direction only for a systemic blocker that prevents safe progress across
the remaining batch.

When complete, return the JSON and HTML paths, owner and proposal counts,
validation results, unresolved/limited owner count, and an explicit statement
that all dossiers are complete and nothing was applied.

## After research compilation

Run owner and tag update tools as dry runs only. Before any later tag apply,
compare the corrected assignments with successfully read live state and review
the exact additions and removals.

Treat pre-guardrail dossier proposals and every existing catalogue candidate
as untrusted legacy material. A later corpus consolidation may globally
promote, merge, facet, inactivate or reject candidates, but must correct owner
dossiers in place as schema v8 and must not expect future owner research to
discover taxonomy. After consolidation, ordinary research uses the resulting
active catalogue only. Future taxonomy growth is a separate corpus-level
discovery operation followed by explicit curation and later assignment
reconciliation.

Promote candidates or reactivate inactive concepts only through a separate
global decision with a recorded human approval reference. Apply the 5–50
dossier-record heuristic as a review signal, never a hard acceptance rule.
Leave source-record deduplication for the separate clerical in-system task and
obtain separate authorization before any live apply.
