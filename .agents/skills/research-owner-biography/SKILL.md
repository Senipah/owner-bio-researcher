---
name: research-owner-biography
description: Research a yacht owner, resolve their identity, classify primary industry, wealth origin, and relationship to wealth, verify Forbes and social profiles, draft short and longer evidence-backed biographies, and produce a confidence-scored review dossier. Use for one-owner biography work, CEO calibration rounds, or review-only batch enrichment of owner JSON; do not use to apply live website updates.
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
- Read
  [references/wealth-classification.md](references/wealth-classification.md)
  before classifying industry, wealth origin, or relationship to wealth.
- Read [references/biography-style.md](references/biography-style.md) before
  drafting or revising biography text.
- Read
  [references/editorial-calibrations.md](references/editorial-calibrations.md)
  before drafting and use the archetypes to vary structure across a batch.

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
   before drafting anything. Non-person records use `editorial_note` and never
   receive biography proposals.
3. Search for an exact Forbes profile first. Record `verified`, `not_found`,
   `ambiguous`, or `unavailable`; never silently omit the check.
4. Research the origin story and current underlying private assets using
   first-party sources, Forbes, reputable business reporting, and well-cited
   reference sources. Populate `primary_industry`, `wealth_origin`, and
   `wealth_relationship` independently under the wealth-classification
   reference. Prefer how wealth or prominence was created over its current
   amount.
5. Search all person-relevant link types supported by the input lookup,
   prioritising public personal Instagram, LinkedIn, and personal websites.
   A company website may be proposed under its distinct type when the owner
   founded, owns, or leads it. Verify identity from direct official links or
   strong cross-corroboration and reject name-only matches.
6. Propose only missing or clearly improvable personal fields. Do not infer
   nationality from birthplace, residence from yacht location, or family facts
   from surname.
7. For a person, build the schema-v5 `biography_brief` after research. Include
   only durable identity, the wealth or prominence route, a turning point, a
   later chapter, optional character detail, explicit transient exclusions,
   and source IDs. Do not place publishers, confidence, classification
   deliberation, vessel context, rankings, or transient figures in the brief.
8. Perform a separate editorial pass from that source-hidden brief. Draft a
   50-55 word short identity card and a 90-190 word, two-paragraph concise
   profile. Reverse-check material claims against the full ledger only after
   drafting. Score the five-part editorial rubric in the style reference and
   revise any dimension below 4.
9. Save a separate dossier with `review.status=pending`. Put uncertain facts or
   links in `candidates_requiring_review`, not proposed changes.
10. Run:

   ```powershell
   .\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\validate_dossier.py PATH --owner-input INPUT --strict-editorial
   ```

11. For a batch, run the corpus auditor before compilation:

    ```powershell
    .\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\audit_biography_corpus.py DOSSIER_DIRECTORY --strict
    ```

12. Return the dossier path, both biographies or non-person editorial note,
    strongest evidence, confidence summary, unresolved questions, and explicit
    statement that nothing was applied.

For a batch of four or more owners, use subagents when available: give each
subagent one owner and this skill, allow at most three research agents at once,
and require one dossier per owner. Keep the main agent responsible for identity
checks, cross-owner consistency, validation, reviewer feedback, and checkpoint
tracking. Do not let parallel agents edit the shared owner dataset.

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
- Exclude a proposed field or social link below confidence 85.
- Score each biography independently and keep its confidence no higher than
  its weakest material claim.
- Do not pad the longer biography or repeat the short biography verbatim.
- Keep source attribution, evidence gaps, confidence, and classification
  reasoning out of published prose. The biography must not reveal the research
  process or database contract.
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
- Use British English except in official names, titles, and quotations.
- Preserve source access dates because Forbes and business roles change.
- Never infer an industry's sector from inheritance status, current occupation,
  yacht ownership, nationality, or public office.
- Never treat state, sovereign-wealth-fund, crown, or office-held assets as a
  royal person's private wealth without strong evidence of personal ownership.
- Never set review approval or workflow flags on behalf of the CEO.

# Validation

- Confirm every material claim in both biographies maps to one or more source
  IDs.
- Confirm the dossier inventory matches the exact source owner record.
- Confirm Forbes was explicitly checked.
- Confirm all three wealth classifications are populated, use exact
  classification-to-label mappings, and are supported by source IDs.
- Confirm every non-`unknown` wealth classification scores at least 85.
- Confirm inherited wealth follows its underlying industry, and royal or
  dynastic records do not assume `Energy` from an oil-producing state.
- Confirm proposed facts and socials score at least 85.
- Confirm the short biography is one paragraph and 50-55 words.
- Confirm the longer biography is exactly two paragraphs and 90-190 words,
  without padding or targeting a preferred midpoint.
- Confirm person dossiers contain a source-hidden `biography_brief`; confirm
  institution and unresolved-placeholder dossiers contain no biography and use
  `editorial_note` instead.
- Confirm neither biography names sources, narrates evidence or confidence,
  explains classifications, or exposes database/process language.
- Confirm the longer biography uses no more than two explicit years, no more
  than one monetary or percentage figure, and normally no sentence over 30
  words.
- Confirm both biographies pass the sale-independence test and contain no
  vessel fact introduced solely from the owner record or LOA-ranked cohort.
- Confirm both biographies use canonical CKEditor HTML and have independent
  confidence and source IDs.
- Confirm each link matches its type: personal accounts are identity-verified,
  and company websites are official with an ownership or leadership source.
- Run `scripts/validate_dossier.py` with `--owner-input --strict-editorial` and
  fix all errors and warnings.
- For batches, run `scripts/audit_biography_corpus.py --strict` and revise
  repeated openings, stock phrases, structures, and conclusions.
- For skill revisions, validate the schema-v5 Shahid Khan calibration dossier
  and compare the result against every archetype in the calibration set.

# Expected output

A schema-v5 JSON dossier matching `references/research-contract.md`, saved
separately from owner inputs. It contains:

- record type, identity, and research status;
- source-record gap inventory and existing link types;
- Forbes status;
- primary-industry, wealth-origin, and wealth-relationship classifications,
  each with an explanation, confidence, and source IDs;
- a source-hidden biography brief plus short and longer biographies for people,
  or a non-applicable editorial note for institutions and unresolved
  placeholders;
- a five-dimension editorial assessment with every person score at least 4;
- proposed personal fields and verified socials;
- per-item confidence and source IDs;
- source ledger, uncertainties, and pending review state.
