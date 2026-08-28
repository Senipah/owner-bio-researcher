---
name: research-owner-biography
description: Research a yacht owner, resolve their identity, classify wealth-creation industry, current primary industry, wealth origin, and relationship to wealth, verify Forbes and social profiles, draft short and longer evidence-backed biographies, and produce a confidence-scored review dossier. Use for one-owner biography work, CEO calibration rounds, or review-only batch enrichment of owner JSON; do not use to apply live website updates.
---

# Purpose

Produce review-ready owner research that explains who a person is and how their
position or fortune arose. Emphasise background and character over net-worth
statistics.

# When to use

- Research one owner before editing `details.biography` or
  `details.long_biography`.
- Find missing personal details or verified personal social links.
- Calibrate biography tone with a reviewer.
- Prepare independent dossiers for a Top-100 or larger owner batch.

# When not to use

- Do not export owners, scan Top-100 vessels, or enrich live form values.
- Do not merge research into owner JSON or set `workflow.ai_enriched`.
- Do not call `update_owners.py` or write to the live website.
- Do not investigate private individuals beyond public, relevant information.

# Repo assumptions

- Start from an enriched owner record when available.
- Treat vessel relationships and LOA ranking as selection and
  identity-disambiguation evidence, not biography content. Both biographies
  must remain accurate and coherent if every current vessel relationship
  changes after research.
- Write dossiers beneath `output/owner-research/`; never overwrite owner input.
- Read [references/research-contract.md](references/research-contract.md) for
  evidence, confidence, social-link, and dossier rules.
- Use the repo-level `config/owner-tags.json` as the canonical tag catalogue,
  not a closed whitelist. Apply every durable, material, dossier-supported tag
  that passes the taxonomy rule. Resolve aliases first; in a repo-backed run,
  add a genuinely distinct missing tag to the catalogue before using its new
  ID. Generic philanthropy tags and `Family office` remain excluded.
- Read
  [references/wealth-classification.md](references/wealth-classification.md)
  before classifying industries, wealth origin, or relationship to wealth.
- Read [references/biography-style.md](references/biography-style.md) before
  drafting or revising biography text.
- Read
  [references/editorial-calibrations.md](references/editorial-calibrations.md)
  before drafting and use the archetypes to vary structure across a batch.
- For one-off name-and-context research in a Custom GPT, use the tracked
  distribution documented in [gpt/README.md](gpt/README.md). The canonical
  skill and reference files remain its source of truth.

# Workflow

1. Inventory the target before searching. When an owner document is available,
   run:

   ```powershell
   .\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\inventory_owner.py --input INPUT --person-id PERSON_ID
   ```

   Record its immutable identifiers, every raw blank, the smaller set of
   researchable gaps, existing links, missing priority link types, and yacht
   relationships. A raw blank is not automatically a useful research target.
2. Resolve identity before enrichment. Require strong agreement among name,
   occupation/company, geography, family, and yacht context. Stop as
   `identity_conflict` when materially ambiguous.
   Set `record_type` to `person`, `institution`, or `unresolved_placeholder`
   before drafting anything. Institutions receive durable user-facing text in
   the existing biography fields plus an `editorial_note`; unresolved
   placeholders use only the note and never receive biography proposals.
3. Search for an exact Forbes profile first. Record `verified`, `not_found`,
   `ambiguous`, or `unavailable`; never silently omit the check.
4. Research the origin story and current underlying private assets using
   first-party sources, Forbes, reputable business reporting, and well-cited
   reference sources. Populate `wealth_creation_industry`,
   `primary_industry`, `wealth_origin`, and `wealth_relationship`
   independently under the wealth-classification reference. Distinguish the
   sector that created the fortune from the sector that currently best
   describes its principal private interests. Prefer how wealth or prominence
   was created over its current amount. Within self-made wealth, distinguish
   an evidenced independent start from an advantaged one; do not equate
   founder ownership with a blank-slate upbringing.
5. Generate all applicable tags after the identity and wealth research, even
   when the current catalogue lacks one. Apply the taxonomy and
   canonicalisation workflow in `references/research-contract.md`: resolve a
   reasonable alias to the existing concept; otherwise create a distinct tag
   in a repo-backed run, or report a null-ID catalogue candidate in Custom GPT
   mode. Give every proposal a materiality summary, confidence of at least 70,
   and direct source IDs. Preserve the documented exclusions and the
   gambling/video-game distinction. Use `Government-owned` only for a
   documented public owner/entity, never merely for an official, contractor,
   state-company employee, sovereign-asset chair, or private royal owner.
6. Search all person-relevant link types supported by the input lookup,
   prioritising public personal Instagram, LinkedIn, and personal websites.
   A company website may be proposed under its distinct type when the owner
   founded, owns, or leads it. Verify identity from direct official links or
   strong cross-corroboration and reject name-only matches.
7. Propose only missing or clearly improvable personal fields. Do not infer
   nationality from birthplace, residence from yacht location, or family facts
   from surname.
8. For a person, build the schema-v8 `biography_brief` after research as an
   unordered editorial fact pool. Include durable identity, defining work,
   nullable formative context and decisive moment, one to three enduring
   dimensions, optional character detail, at least two distinct opening
   options, explicit transient exclusions, and source IDs. Do not use the
   legacy route-turning-point-later-chapter outline or place publishers,
   confidence, classification deliberation, vessel context, rankings, or
   transient figures in the brief.
9. Perform a separate editorial pass from that source-hidden fact pool. Before
   drafting, make a working fact-allocation table with no more than two shared
   anchors, at least one short-only fact or dimension, at least two substantive
   long-only facts or dimensions, and the short-biography material the long
   version will deliberately omit. Do not store this working table in the
   schema-v8 dossier.
10. Select an opening mode and narrative shape deliberately; never draft in
   brief-field order. Draft a 50-55 word short identity card and a 90-190 word,
   two-paragraph concise profile from their allocated facts. When available,
   make the short identity card compactly informative about background,
   defining work, geographic base, broad wealth stature, wealth mechanism, and
   causally relevant family context. Omit unavailable signals silently. The
   long profile must stand alone without restating all three short-biography
   components or merely reordering and expanding the same fact bundle.
11. Review the pair before reverse-checking the source ledger. State what the
    long profile adds, which secondary short-biography fact it omits, and
    whether it would lose meaningful material if reduced to the short version.
    Perform the referential-clarity test for every sentence about assistance,
    funding, backing, support, capital, results, or success: name the provider,
    form, purpose, relevant setting, and any causal antecedent that could
    otherwise be ambiguous. Rewrite any paraphrased expansion, then score the
    seven-part editorial rubric and revise any dimension below 4.
12. Save a separate dossier with `review.status=complete` once the research
   decision is terminal. Put facts or links below the import threshold in
   `candidates_requiring_review`, not proposed changes.
13. Run:

   ```powershell
   .\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\validate_dossier.py PATH --owner-input INPUT --strict-editorial
   ```

14. For a batch, run the corpus auditor before compilation:

    ```powershell
    .\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\audit_biography_corpus.py DOSSIER_DIRECTORY --strict
    ```

15. Before compiling a batch, perform a dedicated cross-owner editorial pass.
    Tabulate every person's opening mode, narrative shape, paragraph-two
    transition, final sentence, and short-long pair findings. Revise semantic
    repetition within each owner and across owners even when the wording
    differs, and rerun the corpus auditor until strict mode passes.
16. Return the dossier path, resolved tag set, both biographies or unresolved editorial note,
    strongest evidence, confidence summary, unresolved questions, and explicit
    statement that nothing was applied.

For a batch of four or more owners, use subagents when available: give each
subagent one owner and this skill, allow at most three research agents at once,
and require one dossier per owner. Keep the main agent responsible for identity
checks, cross-owner consistency, validation, reviewer feedback, and checkpoint
tracking. Subagents may return null-ID tag candidates but must not edit the
shared catalogue; the main agent deduplicates candidates, creates approved
canonical entries once, refreshes their dossiers, and rebuilds GPT Knowledge.
Do not let parallel agents edit the shared owner dataset.

## Existing-dossier tag migration

For an explicitly authorised tag-only migration of a completed schema-v7
corpus, use `scripts/backfill_dossier_tags.py`. Run it without `--apply` first
and inspect its per-owner decisions, tag counts, and differences from the prior
whole-corpus review. The tool must use only accepted dossier narrative fields
and their source ledger; it must not browse, redraft biographies, change
classifications, or infer tags from unresolved placeholders. With `--apply`, it
creates and byte-verifies a complete v7 backup before atomically writing v8
dossiers. Independently validate and resolve every migrated tag before treating
the migration as complete.

# Guardrails

- Use public sources only and minimise collection of irrelevant personal data.
- Never invent facts, social handles, Forbes profiles, source URLs, or
  confidence.
- Treat Wikipedia as orientation and a route to sources, not sole support for a
  disputed, sensitive, or wealth-origin claim.
- Avoid people-search sites, scraped biography farms, anonymous claims, and
  search-result snippets as final evidence.
- Do not describe allegations, sanctions, crimes, health, religion, politics,
  or family disputes unless directly relevant, strongly sourced, and requested.
- Separate citizenship, nationality, birthplace, and residence.
- Exclude a proposed field or social link below confidence 70.
- Exclude a proposed tag below confidence 70 or without direct dossier sources.
- Require `proposed_tags` in every schema-v8 dossier. Include all and only
  durable, material, dossier-supported tags that create meaningful groupings;
  unresolved placeholders use an empty list.
- Never omit a qualifying tag merely because the current catalogue or the
  completed corpus does not contain it. Do not invent an ID: create the
  canonical entry first in a repo-backed run, or use a null ID and an explicit
  Knowledge-update notice in Custom GPT mode.
- Resolve bare `Gaming` to `Gambling`, never `Video games`. Use `Video games`
  only when the evidence explicitly concerns video games, game development,
  game publishing, or an equivalent interactive-entertainment business.
- Apply `Government-owned` only when the owner record is itself a government or
  public body, or an institution is explicitly government/state-owned. Public
  office, contracting, employment, stewardship, and royalty do not suffice.
- Treat `research_status=complete` as completion of the research decision, not
  proof that every field is known. Preserve supported `Unknown`
  classifications, confidence limits, and uncertainties instead of emitting
  an importer-ineligible `limited` status for a resolved identity.
- Score each biography independently and keep its confidence no higher than
  its weakest material claim.
- Do not pad the longer biography or repeat, reorder, or paraphrase the short
  biography's complete fact bundle.
- Treat the short biography as the concise wealth-origin answer and the longer
  biography as an edited profile. Do not expand the short biography's field
  order into a chronological long biography.
- For business profiles, establish the person's defining identity,
  achievement, institution, asset, decision, or public contribution before
  supplying routine career chronology. A formative episode may lead only when
  its relevance is immediately clear.
- Never open with abstract narrative scaffolding such as "route into
  business", "path to wealth", "career began", "commercial footing", or
  "gave them their start". Do not use "later chapter", "second strand", "the
  arc", or a synthetic tie-back to manufacture coherence.
- Keep source attribution, evidence gaps, confidence, and classification
  reasoning out of published prose. The biography must not reveal the research
  process or database contract.
- Keep public-versus-private asset distinctions in classification metadata.
  For royal and dynastic owners, write positively about verified formation,
  succession, public work, interests, and influence; never explain the subject
  by contrasting those things with commercial enterprise, entrepreneurship, or
  a personal fortune.
- Never mention a personally owned vessel merely because it appears in the
  source owner record, determines LOA rank, was commissioned or delivered, or
  has been owned for a long time. Vessel names, dimensions, builders, and
  ownership histories belong elsewhere in the system.
- Apply the sale-independence test: both biographies must still read as
  complete, accurate profiles if the person sells every current vessel
  tomorrow.
- Durable maritime work may be included only when it is independently central
  to the person's public life, such as commercial shipping, shipbuilding,
  competitive sailing, or sustained ocean research or philanthropy. Describe
  the enduring work rather than using a transient vessel as character colour.
- Prefer durable facts over current percentages, annual figures, rankings, and
  other details likely to date quickly.
- Treat `Self-made` as an asset-origin classification, not a claim that the
  person lacked privilege or assistance. When a substantial family or social
  platform materially shaped the start, classify and describe it neutrally
  while preserving the person's separately evidenced achievement.
- Do not make an institution the grammatical object of family funding when the
  supported fact concerns education costs, trading capital, or another
  specific purpose. Replace vague causal references such as "those results"
  with the event, return, decision, or achievement itself.
- Use British English except in official names, titles, and quotations.
- Preserve source access dates because Forbes and business roles change.
- Never infer either industry's sector from inheritance status, current
  occupation, yacht ownership, nationality, or public office.
- Never treat state, sovereign-wealth-fund, crown, or office-held assets as a
  royal person's private wealth without strong evidence of personal ownership.
- Use `review.status=complete` for finished research. Do not use legacy
  `approved` or `rejected` states or set live-update workflow flags.

# Validation

- Confirm every material claim in both biographies maps to one or more source
  IDs.
- Confirm the dossier inventory matches the exact source owner record.
- Confirm Forbes was explicitly checked.
- Confirm all four wealth classifications are populated, use exact
  classification-to-label mappings, and are supported by source IDs.
- Confirm self-made starting-position subtypes follow positive evidence:
  `self_made_independent` is not inferred from missing inheritance evidence,
  `self_made_advantaged` does not conceal a principal asset transfer, and
  broad `self_made` is retained when the distinction is unresolved.
- Confirm every non-`unknown` wealth classification scores at least 70.
- Confirm every tag candidate was checked against canonical names, aliases,
  and semantic equivalents; broader or narrower concepts are not aliases.
- Confirm every new repo-backed tag has a unique monotonic ID, a canonical
  name, useful aliases, a type facet, applicable `parent:<classification>`
  facets, and a rebuilt Custom GPT catalogue.
- Confirm tag selection uses `Gambling` for casino, betting, bookmaking, and
  gambling-industry gaming, and does not use `Video games` for that evidence.
- Confirm `Government-owned` is supported as an owner-entity status and is not
  inferred from public office, government business, sovereign stewardship, or
  royal status.
- Confirm no generic philanthropy-domain or `Family office` tag is proposed;
  the separate `family_office_principal` wealth relationship remains valid.
- Confirm inherited wealth follows its underlying industries, and royal or
  dynastic records do not assume `Energy` from an oil-producing state.
- Confirm proposed facts and socials score at least 70.
- Confirm the short biography is one paragraph and 50-55 words.
- Confirm the short biography uses every useful, strongly sourced identity
  signal that fits naturally—background, work, base, broad wealth stature,
  wealth mechanism, and material family context—while silently omitting
  unavailable facts.
- Confirm a `self_made_advantaged` person's material starting advantage appears
  naturally in at least one biography and in the short biography when omission
  would imply a blank-slate origin.
- Confirm every assistance or funding sentence identifies the provider, form,
  purpose, and relevant stage, and that every causal pronoun has one
  unmistakable antecedent. Treat this as part of `causal_clarity` and
  `reader_orientation`; do not add another dossier field.
- Confirm the longer biography is exactly two paragraphs and 90-190 words,
  without padding or targeting a preferred midpoint.
- Confirm the working fact allocation used no more than two shared anchors,
  retained at least one short-only fact or dimension, and supplied at least two
  substantive long-only facts or dimensions.
- Confirm person dossiers contain a schema-v8 source-hidden, unordered
  `biography_brief` with at least two distinct opening options. Confirm
  institution dossiers contain short and longer biographies plus an
  `editorial_note`, and unresolved-placeholder dossiers contain no biography
  and use only the note.
- Confirm all seven editorial scores are 4 or 5 and that `opening_mode` selects
  one of the brief options while `narrative_shape` uses an allowed value.
- Confirm neither biography names sources, narrates evidence or confidence,
  explains classifications, or exposes database/process language.
- Confirm neither biography contains a negative wealth-taxonomy contrast such
  as "rather than commercial enterprise", "governmental rather than
  commercial", or "state assets rather than personal wealth".
- Confirm the long biography passes the orientation and enrichment-question
  tests, does not open with career-route scaffolding, does not force a
  later-activities paragraph, and ends on a concrete fact or consequence.
- Confirm the longer biography uses no more than two explicit years, no more
  than one monetary or percentage figure, and normally no sentence over 30
  words.
- Confirm both biographies pass the sale-independence test and contain no
  vessel fact introduced solely from the owner record or LOA-ranked cohort.
- Confirm both biographies use canonical CKEditor HTML and have independent
  confidence and source IDs.
- Confirm the biography-pair audit reports no near-restated sentence, expanded
  fact bundle, or unresolved overlap warning. Do not award
  `structural_independence=5` when any pair finding remains.
- Confirm each link matches its type: personal accounts are identity-verified,
  and company websites are official with an ownership or leadership source.
- Run `scripts/validate_dossier.py` with `--owner-input --strict-editorial` and
  fix all errors and warnings.
- For batches, run `scripts/audit_biography_corpus.py --strict` and revise
  repeated opening modes, origin-story leads, narrative shapes, paragraph-two
  transitions, stock phrases, and synthetic conclusions.
- For skill revisions, validate the schema-v8 Shahid Khan calibration dossier
  and compare the result against every archetype in the calibration set.

# Expected output

A schema-v8 JSON dossier matching `references/research-contract.md`, saved
separately from owner inputs. It contains:

- record type, identity, and research status;
- source-record gap inventory and existing link types;
- Forbes status;
- wealth-creation-industry, primary-industry, wealth-origin, and
  wealth-relationship classifications, each with an explanation, confidence,
  and source IDs;
- a source-hidden biography brief plus complementary short and longer
  biographies for people, short and longer institutional descriptions plus an
  editorial note for institutions, or only an editorial note for unresolved
  placeholders;
- a seven-dimension editorial assessment, selected opening mode, and narrative
  shape, with every person score at least 4;
- proposed personal fields, verified socials, and every applicable canonical
  tag with its research ID/name pair, materiality summary, confidence, and
  source IDs;
- any canonical tags created during a repo-backed run, or Custom GPT null-ID
  candidates with an explicit tag-catalogue Knowledge-update notice;
- per-item confidence and source IDs;
- source ledger, uncertainties, and completed research state.
