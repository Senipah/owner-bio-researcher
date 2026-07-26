---
name: research-owner-biography
description: Research a yacht owner, resolve their identity, find reliable personal and wealth-origin facts, verify Forbes and social profiles, draft a short evidence-backed biography, and produce a confidence-scored review dossier. Use for one-owner biography work, CEO calibration rounds, or review-only batch enrichment of owner JSON; do not use to apply live website updates.
---

# Purpose

Produce review-ready owner research that explains who a person is and how their
position or fortune arose. Emphasise background and character over net-worth
statistics.

# When to use

- Research one owner before editing `details.biography`.
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
- Treat vessel relationships as identity-disambiguation evidence, not automatic
  biography content.
- Write dossiers beneath `output/owner-research/`; never overwrite owner input.
- Read [references/research-contract.md](references/research-contract.md) for
  evidence, confidence, social-link, and dossier rules.
- Read [references/biography-style.md](references/biography-style.md) before
  drafting or revising biography text.

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
3. Search for an exact Forbes profile first. Record `verified`, `not_found`,
   `ambiguous`, or `unavailable`; never silently omit the check.
4. Research the origin story using first-party sources, Forbes, reputable
   business reporting, and well-cited reference sources. Prefer how wealth or
   prominence was created over its current amount.
5. Search all person-relevant link types supported by the input lookup,
   prioritising public personal Instagram, LinkedIn, and personal websites.
   A company website may be proposed under its distinct type when the owner
   founded, owns, or leads it. Verify identity from direct official links or
   strong cross-corroboration and reject name-only matches.
6. Propose only missing or clearly improvable personal fields. Do not infer
   nationality from birthplace, residence from yacht location, or family facts
   from surname.
7. Draft one short biography using the style reference. Include only claims
   supported by the dossier source ledger.
8. Save a separate dossier with `review.status=pending`. Put uncertain facts or
   links in `candidates_requiring_review`, not proposed changes.
9. Run:

   ```powershell
   .\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\validate_dossier.py PATH --owner-input INPUT
   ```

10. Return the dossier path, biography, strongest evidence, confidence
    summary, unresolved questions, and explicit statement that nothing was
    applied.

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
- Keep biography confidence no higher than its weakest material claim.
- Preserve source access dates because Forbes and business roles change.
- Never set review approval or workflow flags on behalf of the CEO.

# Validation

- Confirm every material biography claim maps to one or more source IDs.
- Confirm the dossier inventory matches the exact source owner record.
- Confirm Forbes was explicitly checked.
- Confirm proposed facts and socials score at least 85.
- Confirm biography is one paragraph, 45-110 words, and canonical CKEditor HTML.
- Confirm each link matches its type: personal accounts are identity-verified,
  and company websites are official with an ownership or leadership source.
- Run `scripts/validate_dossier.py` with `--owner-input` and fix all errors.
- For skill revisions, validate the Shahid Khan calibration dossier and compare
  its tone against the style reference.

# Expected output

A versioned JSON dossier matching `references/research-contract.md`, saved
separately from owner inputs. It contains:

- identity and research status;
- source-record gap inventory and existing link types;
- Forbes status;
- wealth-origin classification and explanation;
- short plain-text and CKEditor biography;
- proposed personal fields and verified socials;
- per-item confidence and source IDs;
- source ledger, uncertainties, and pending review state.
