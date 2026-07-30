# Goal Mode prompt: next 50 LOA-prioritised owners

Paste the prompt below from the repository root after details-and-socials
enrichment has completed. No position or filename edits are required between
runs: it derives the next fixed 50-owner tranche from the immutable cohort and
the last completed checkpoint.

The first 50 dossiers remain the authorised frozen schema-v7 baseline. Every
later completed tranche also becomes frozen. A rerun resumes the same
incomplete tranche, reusing its valid dossiers, rather than moving the window
forward or selecting 50 scattered gaps. The prompt produces pending-review
artifacts only; it does not approve research, commit generated output, or
update the live system.

## Prompt

Use `$research-owner-biography`.

Set:

- `BASELINE_PREFIX = 50`
- `TRANCHE_SIZE = 50`

Goal: resume and complete exactly the next fixed `TRANCHE_SIZE` positions
after the last completed cumulative checkpoint in the immutable
LOA-prioritised owner cohort, then compile cumulative pending-review artifacts
through the end of that tranche.

Do not mark this goal complete until every acceptance criterion below is
satisfied. Do not mark it blocked merely because positions
`1..BASELINE_PREFIX` contain the already authorised baseline editorial
findings.

## Authoritative files

- Owner input:
  `output/owners-list.vessel-enriched.enriched.json`
- Immutable cohort:
  `output/owner-research/all-by-loa/cohort.json`
- Dossier directory:
  `output/owner-research/all-by-loa/`
- Baseline migration and exception record:
  `output/owner-research/all-by-loa-schema-v7-migration-summary.json`
- Baseline cumulative artifacts:
  `output/research-enriched-owners-list.all-by-loa.first-50.json`
  `output/research-enriched-owners-list.all-by-loa.first-50.html`
- Later cumulative artifacts:
  `output/research-enriched-owners-list.all-by-loa.first-{PREFIX}.json`
  `output/research-enriched-owners-list.all-by-loa.first-{PREFIX}.html`
- Completed-tranche summaries:
  `output/owner-research/all-by-loa-tranche-{START}-{END}-summary.json`

Read the repository `AGENTS.md`, `README.md`, relevant AI documentation, and
the complete `$research-owner-biography` skill and its required references
before acting.

## Preflight

1. Verify that the baseline migration summary records:

   - 50 migrated schema-v7 dossiers;
   - 50 structured-diff passes;
   - zero migration-related validation failures;
   - 23 frozen baseline strict-validation failures;
   - 27 inherited baseline corpus-audit findings;
   - `status.compilation_status` equal to
     `completed_with_authorised_baseline_editorial_exception`;
   - 50 compiled owners; and
   - all compiled owners still having `workflow.ai_enriched=false`.

2. Verify that the immutable cohort contains 4,197 owners and has source hash:

   `4477729a535d9cdf216efa7155a6a7ed0aae4ddf1c5e554b46f856aaf7f2a346`

   A different normalised source path is acceptable only if the content hash,
   cohort membership, ordering, person IDs, and recorded LOA values are
   unchanged. Never regenerate or reorder the manifest. Stop for user
   direction if any of those immutable properties changed.

3. Derive `PRIOR_PREFIX`, the last completed checkpoint:

   - begin with `BASELINE_PREFIX`, but only after verifying the baseline
     summary and both baseline cumulative artifacts;
   - inspect later completed-tranche summaries in ascending contiguous order;
   - advance only by a complete `TRANCHE_SIZE` window, except for a possible
     final short window at the end of the cohort;
   - accept a later checkpoint only when its summary, cumulative JSON and
     HTML exist and their recorded hashes, owner range, dossier validation,
     tranche audit, review states, and compilation checks all agree; and
   - do not advance because some later dossier happens to exist or validate.

   A partial or failed prior run therefore leaves `PRIOR_PREFIX` at the
   preceding completed checkpoint and resumes the same fixed tranche.

4. Set:

   - `COHORT_SIZE` from the immutable manifest;
   - `TRANCHE_START = PRIOR_PREFIX + 1`;
   - `TRANCHE_END = min(PRIOR_PREFIX + TRANCHE_SIZE, COHORT_SIZE)`;
   - `PREVIOUS_JSON` and `PREVIOUS_HTML` to the cumulative artifacts ending
     at `PRIOR_PREFIX`;
   - `CURRENT_JSON` and `CURRENT_HTML` to cumulative artifacts ending at
     `TRANCHE_END`; and
   - `TRANCHE_SUMMARY` to
     `output/owner-research/all-by-loa-tranche-{TRANCHE_START}-{TRANCHE_END}-summary.json`.

   If `PRIOR_PREFIX == COHORT_SIZE`, report that the cohort is complete and do
   not start another research tranche.

5. Print the derived tranche boundaries and the cohort position, person ID,
   display name, vessel, and LOA at both boundaries. Verify those records
   against the enriched input. Stop for user direction if membership,
   ordering, IDs, or LOA values differ.

6. Record SHA-256 hashes for:

   - every dossier at positions `1..PRIOR_PREFIX`;
   - the cohort manifest;
   - the enriched owner input;
   - the baseline migration summary; and
   - `PREVIOUS_JSON` and `PREVIOUS_HTML`.

7. Inventory every owner at positions `TRANCHE_START..TRANCHE_END`. This run
   is resumable. Reuse a dossier only if it belongs to the correct cohort
   owner, is schema v7, and passes this exact command against the current
   owner input:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  DOSSIER_PATH `
  --owner-input output\owners-list.vessel-enriched.enriched.json `
  --strict-editorial
```

   Treat an absent, stale, mismatched, or invalid dossier as pending. Preserve
   a backup of an invalid partial dossier before replacing it. Never
   substitute an owner after `TRANCHE_END`.

8. Freeze every dossier at positions `1..PRIOR_PREFIX`. Do not modify it in
   this run. The authorised exception applies only to the exact baseline
   findings already recorded for positions `1..BASELINE_PREFIX`; it does not
   apply to any later dossier.

## Research scope

Research every pending owner at positions `TRANCHE_START..TRANCHE_END`.
Complete the whole fixed tranche even when an identity is difficult or the
public record is sparse. Do not skip an owner in favour of a later one.

For the target tranche, produce one schema-v7 dossier per owner beneath
`output/owner-research/all-by-loa/`. Every dossier must contain:

1. `record_type=person`, `institution`, or `unresolved_placeholder`;
2. an unordered, source-hidden `biography_brief` fact pool with at least two
   distinct opening options, plus validated short and longer biographies and
   `editorial_assessment` for a person, or a non-applicable `editorial_note`
   and null biography/editorial fields for a non-person record;
3. `wealth_creation_industry`, `primary_industry`, `wealth_origin`, and
   `wealth_relationship` classifications;
4. an explicit Forbes result;
5. an inventory of missing details and supported link types;
6. only confidence-85-or-higher proposed details and links; and
7. `review.status=pending`.

Use a bounded worker pool of at most three research subagents. Give each
subagent exactly one owner at a time and `$research-owner-biography`. When a
subagent finishes, the main agent must validate its dossier before assigning
that worker another owner. Subagents may edit only their assigned target
owner's dossier. They must not edit the owner input, cohort manifest, frozen
dossiers, source code, documentation, tests, skill files, compiled artifacts,
tranche summary, or another owner's dossier. The main agent owns cohort
selection, identity review, validation, cross-owner consistency, integrity
checks, checkpoint tracking, and compilation.

For every target owner:

- run `inventory_owner.py` against the exact enriched input and person ID;
- resolve identity using name, public role or business, geography, family, and
  yacht context before collecting facts;
- search Forbes first and record `verified`, `not_found`, `ambiguous`, or
  `unavailable`;
- classify wealth-creation industry, current primary industry, wealth origin,
  and wealth relationship independently using
  `references/wealth-classification.md`; use the shared Cryptocurrency
  industry only when reliable evidence establishes crypto as the relevant
  wealth-creation or current sector, not merely a later investment;
- explain how wealth or prominence arose rather than foregrounding net worth;
- search supported person-relevant social types, prioritising Instagram,
  LinkedIn, and Personal Website;
- reject namesake, company, fan, family-member, and uncorroborated accounts;
- use a distinct Company Website proposal only when official evidence connects
  the person to the company;
- keep lower-confidence facts and links in review candidates or uncertainties;
- complete all research before drafting and build the schema-v7
  `biography_brief` as an unordered editorial fact pool containing durable
  identity, defining work, nullable formative context and decisive moment, one
  to three enduring dimensions, optional character detail, at least two
  fact-level opening options with distinct modes, transient exclusions, and
  source IDs;
- never use the schema-v5
  `wealth_or_prominence_route`/`turning_point`/`later_chapter` outline, and
  explicitly exclude source publishers, confidence language, classification
  deliberation, vessel context, ranking, net worth, and transient figures from
  the brief;
- before drafting, make a working fact-allocation table with no more than two
  shared anchors, at least one short-only fact or dimension, at least two
  substantive long-only facts or dimensions, and the short-biography material
  the long profile will deliberately omit; do not store this working table in
  the schema-v7 dossier;
- perform a separate editorial pass from that fact pool, deliberately select
  and record one opening mode and narrative shape, then reverse-check every
  material claim against the full source ledger;
- draft a neutral 50-55 word short biography and a standalone,
  two-paragraph longer biography of 90-190 words without targeting a preferred
  midpoint;
- treat the longer biography as a standalone edited profile, not an expanded
  answer to how wealth began; orient the reader through the person's defining
  identity, achievement, institution, asset, consequential decision,
  inherited responsibility, or public contribution;
- do not repeat, reorder, or paraphrase all three components of the short
  biography across the long profile; allow essential identity and one core
  mechanism to overlap, but require the long version to answer a different
  editorial question with its allocated long-only material;
- use a formative episode as the opening only when its relevance is immediately
  clear, and never open with abstract scaffolding such as "route into
  business", "path to wealth", "career began", "commercial footing", or
  "gave them their start";
- allow paragraph two to deepen the core work instead of forcing a later
  investment, sport, or philanthropy slot; include a second domain only when it
  genuinely distinguishes the person;
- end on a concrete fact, role, decision, or consequence, never a synthetic
  tie-back using "linking", "extending the same approach", "the arc",
  "second strand", "second thread", or equivalent phrasing;
- keep publisher names, source attribution, evidence gaps, confidence,
  classification reasoning, database language, and research-process narration
  out of both biographies;
- keep public-versus-private asset analysis in dossier metadata; for royal and
  dynastic owners, describe verified formation, succession, public work,
  interests, and influence without contrasting them against commercial
  enterprise, entrepreneurship, or personal wealth;
- use British English, no more than two explicit years, no more than one
  monetary or percentage figure, normally no sentence over 30 words, and no
  inventory of more than three representative companies, investments,
  offices, or institutions;
- vary openings, paragraph transitions, rhythms, and endings against
  `references/editorial-calibrations.md`; vary both opening mode and narrative
  shape, and do not default to birthplace, career-entry chronology, “His
  later...”, or a concluding wealth-classification verdict;
- treat current-vessel relationships and LOA rank as selection and identity
  context only, never as a reason to mention a vessel in either biography;
- apply the sale-independence test: both biographies must remain accurate,
  coherent, and complete if the owner sells every current vessel tomorrow;
- never use vessel names, dimensions, builders, delivery dates, commissions,
  or ownership histories as biography colour; independently significant
  maritime careers or sustained competitive, research, or philanthropic work
  may be described only by focusing on the enduring activity;
- do not pad sparse profiles or repeat the short text verbatim;
- review the pair before acceptance: state what the long profile adds, which
  secondary short-biography fact it omits, and whether reducing it to the short
  version would discard meaningful material; rewrite the pair if not;
- save the dossier using the person ID in its filename;
- leave `review.status=pending`; and
- run the exact validation command above, fixing all failures before marking
  that owner complete.

If a record represents an institution, government, municipality, unresolved
placeholder, or otherwise is not a natural person, do not invent a human
identity or personal wealth story. Set the appropriate non-person
`record_type`, leave `biography_brief`, `biography`, and `long_biography` null,
populate `editorial_note`, and make no personal detail or social proposals.
Preserve its cohort position; do not silently replace it with a later owner.

## Tranche and cumulative editorial validation

After every target dossier validates, perform a main-agent consistency review
across the target tranche and the cumulative prefix ending at `TRANCHE_END`:

- biographies meet the seven-part editorial rubric and use the complete
  calibration set without copying one structure across the tranche;
- every person passes the short-long pair audit, and no dossier claims
  `structural_independence=5` while a near-restated sentence, expanded fact
  bundle, or overlap warning remains;
- published prose contains no source narration, classification deliberation,
  negative wealth-taxonomy contrasts, database/process language, or repeated
  AI-style conclusions;
- both biographies pass the sale-independence test and contain no vessel fact
  introduced from the LOA-ranked owner relationship;
- royal, sovereign, family, and personal wealth are not conflated, and an
  oil-producing state is not treated as evidence of personal `Energy` wealth;
- inherited, self-made, dynastic/royal, family-transfer, mixed, and unknown
  origin classifications are applied consistently;
- wealth-creation industry follows the sector that principally created the
  original fortune, current primary industry follows the principal
  identifiable private interests as of research, and relationship
  distinguishes founders, operators, investors, heirs, family office
  principals, royal beneficiaries, custodians, and passive owners;
- proposed select values use labels supported by the owner form;
- social type IDs match the input lookup; and
- no dossier is approved on the user's behalf.

Then perform a dedicated cross-owner editorial pass over the target tranche.
Create a working table containing owner, opening mode, narrative shape, first
sentence, paragraph-two opening, and final sentence. Use it to revise semantic
repetition even where exact wording differs. No single opening mode or
narrative shape may dominate business profiles, origin-story openings must be
a minority, and formulaic later-chapter transitions or synthetic tie-back
conclusions must be exceptional. This table is temporary review material.

1. Create a temporary directory containing only dossiers for positions
   `TRANCHE_START..TRANCHE_END`. Run:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\audit_biography_corpus.py `
  TEMP_TRANCHE_DIRECTORY `
  --strict
```

   Revise only target dossiers until this tranche-only audit passes with zero
   issues.

2. Create a second temporary directory containing exactly the dossiers for
   positions `1..TRANCHE_END`, run the same strict corpus-audit command
   against it, and compare the result with the 27 inherited findings in the
   baseline migration summary.

   - The only permitted unresolved findings are exact inherited findings
     involving only positions `1..BASELINE_PREFIX`.
   - Fix every finding involving a target owner by editing only that target
     owner's dossier.
   - Fix every new cross-owner repetition involving the target tranche.
   - A finding involving only frozen post-baseline positions is not covered by
     the baseline exception. Preserve those dossiers, report the integrity
     conflict, and stop for user direction.
   - Do not interpret the inherited baseline validation failures or audit
     findings as evidence that this goal is blocked.

Delete both temporary audit directories after retaining the command results
needed for the tranche summary.

## Cumulative compilation

Compile cumulative pending-review artifacts for exactly positions
`1..TRANCHE_END` to `CURRENT_JSON` and `CURRENT_HTML`.

The normal `compile_owner_research.py` CLI will reject the inherited baseline
editorial failures because it applies current strict validation to every
selected dossier. Do not weaken or modify that CLI. Use the already authorised
baseline exception through a temporary one-off Python process that calls the
normal repository functions directly:

- `src.io_utils.load_json`
- `src.research_batch.load_dossiers`
- `src.research_batch.compile_research_batch`
- `src.research_batch.render_research_report`
- `src.io_utils.atomic_write_json`
- `src.io_utils.atomic_write_text`

Use selection `all-by-loa`, limit `TRANCHE_END`,
`mark_ai_enriched=False`, the exact enriched owner input and dossier
directory, and the derived `CURRENT_JSON` and `CURRENT_HTML` paths. Do not
attach biography comparisons unless a complete comparison backup exists for
the whole cumulative prefix.

Before bypassing the CLI validation gate, independently prove that:

- every target dossier passes strict per-owner validation;
- the target-tranche strict corpus audit passes;
- the cumulative audit contains no unresolved issue beyond the exact recorded
  baseline findings;
- every frozen dossier hash is unchanged;
- every selected dossier is schema v7 and belongs to the expected frozen
  cohort owner;
- every review remains pending; and
- the owner input, cohort manifest, baseline summary, and previous checkpoint
  hashes are unchanged.

After compilation, verify:

- exactly `TRANCHE_END` owners were compiled in cohort order;
- the first and last IDs match positions 1 and `TRANCHE_END` in the immutable
  manifest;
- every compiled owner has `workflow.ai_enriched=false`;
- every compiled `ai_research` object contains all four wealth
  classifications;
- positions `1..PRIOR_PREFIX` match `PREVIOUS_JSON` for biographies,
  classifications, proposals, and protected owner values, allowing only
  regenerated compilation timestamps and cumulative batch metadata; and
- `_baseline`, `person_id`, `profile_url`, vessel ownership data, and existing
  `profile_key` values remain unchanged.

## Tranche summary

Write `TRANCHE_SUMMARY` with:

- schema version and timestamps;
- the prior prefix, tranche range, and exact owner list with positions, IDs,
  names, vessels, and LOAs;
- newly created, resumed, and already-valid dossier counts;
- per-owner strict-validation results;
- identity conflicts, unresolved identities, and limited-evidence owners;
- all four classifications and confidence scores;
- Cryptocurrency count and named owners;
- Unknown counts by classification;
- source and Forbes-result summaries;
- target-tranche and cumulative audit results;
- the exact inherited baseline findings permitted by the authorised exception;
- confirmation that no later owner used the exception;
- preflight and final hashes for protected inputs, frozen dossiers, and the
  previous checkpoint;
- compiled artifact paths, owner counts, and SHA-256 hashes; and
- the next pending cohort position and remaining owner count, derived from
  `TRANCHE_END` and `COHORT_SIZE`.

## Safety constraints

- Never overwrite the enriched owner input or cohort manifest.
- Never modify positions `1..PRIOR_PREFIX`.
- Do not edit source code, documentation, tests, or skills while executing
  this research prompt.
- Do not approve dossiers.
- Do not run `update_owners.py`.
- Do not perform any live website write.
- Do not commit generated research output.
- Do not begin any owner after `TRANCHE_END`.

## Acceptance criteria

The goal is complete only when:

- every position `TRANCHE_START..TRANCHE_END` has the correct schema-v7
  dossier;
- every target dossier passes strict per-owner validation;
- the target-tranche strict corpus audit passes;
- cumulative audit debt is limited to the exact authorised baseline;
- all frozen dossier and protected input hashes are unchanged;
- `CURRENT_JSON`, `CURRENT_HTML`, and `TRANCHE_SUMMARY` exist and contain the
  expected cumulative prefix;
- every dossier remains pending and every compiled owner has
  `workflow.ai_enriched=false`;
- processing stopped before `TRANCHE_END + 1`;
- nothing was committed; and
- nothing was applied live.

Return a concise final report containing:

- processed positions and owner count;
- new, resumed, already-valid, and cumulative dossier counts;
- validation and target/cumulative audit results;
- Cryptocurrency and Unknown classification counts;
- unresolved or limited-evidence owners;
- cumulative artifact and tranche-summary paths and hashes;
- confirmation that all earlier positions remained frozen;
- the derived next pending position and remaining count; and
- confirmation that all reviews remain pending, nothing was committed, and
  nothing was applied live.

## After review

Approval is a separate task. For accepted dossiers, a human must set
`review.status=approved` plus `reviewed_by` and `reviewed_at`. Only then compile
an approved file with `--mark-ai-enriched`, run `update_owners.py` without
`--apply`, inspect its audit, and obtain separate authorisation before any live
apply. Dossiers marked `rejected` retain the original owner values and remain
ineligible for update.
