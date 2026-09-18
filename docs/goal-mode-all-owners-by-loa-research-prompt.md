# Goal Mode prompt: next 50 LOA-prioritised owners

Paste the prompt below from the repository root each time another tranche
should be researched. It reconciles terminal production dossiers into the
tracked cohort and selects the next contiguous 50 unresearched owners. No
positions, filenames, prefix values, or separate progress file need to be
maintained between runs.

The cohort is the sole authority for LOA order and workflow progress. Earlier
production dossiers are frozen, new dossiers are marked complete after strict
validation, and nothing is applied to the live website.

## Prompt

```text
Use `$research-owner-biography`.

Goal: research the next contiguous batch of up to 50 unresearched owners in
the canonical LOA-prioritised cohort, then validate a transient cumulative
compilation through the end of that tranche.

This prompt is intentionally reusable without editing. Never choose a tranche
from filenames, a compiled artifact, or an ignored progress file. Reconcile
terminal dossiers through `sync_owner_cohort_status.py`, then use only the
cohort's workflow flags and summary.

Do not mark this goal complete until the selected tranche and every acceptance
criterion below are complete. An individual sparse or difficult owner is not a
reason to skip forward or mark the goal blocked.

## Authoritative files

- Owner input:
  `output/owners-list.vessel-enriched.enriched.json`
- Canonical LOA-sorted cohort (identity and ranking fields are immutable;
  `workflow` status is mutable and tracked):
  `output/owner-research/all-by-loa/cohort.json`
- Production dossiers:
  `output/owner-research/all-by-loa/`
- Tranche size: 50

Read `AGENTS.md`, the relevant repository documentation, and the complete
`$research-owner-biography` skill with all required references before acting.

This is a research-and-compilation task only. Do not call `update_owners.py`,
apply website changes, stage files, commit, or push.

## Read and verify progress

1. Reconcile terminal production dossiers into the tracked cohort:

   `.\venv\Scripts\python.exe .\sync_owner_cohort_status.py`

   Review the dry-run, then run:

   `.\venv\Scripts\python.exe .\sync_owner_cohort_status.py --apply`

   Do not pass `--updated-owner-input` during ordinary research. Existing true
   update flags are monotonic and remain in the cohort.
2. Load the updated cohort and verify:

   - `selection` is `all-by-loa`;
   - `cohort_size` equals the number of cohort entries;
   - every owner has boolean `workflow.researched` and
     `workflow.updated_in_system` fields;
   - researched owners form one contiguous prefix with no researched owner
     after the first false flag;
   - `workflow_summary` exactly matches the per-owner flags;
   - `workflow_summary.completed_prefix` equals `researched_count`; and
   - `workflow_summary.next_unresearched_owner` matches the first false entry,
     or is null when none remain.

3. Do not modify any dossier whose cohort `workflow.researched` flag is true.
4. If `remaining_research_count == 0`, report that the cohort is complete
   and do not start another tranche.

## Select the tranche

1. Set:

   - `COMPLETED_PREFIX = workflow_summary.completed_prefix`
   - `TRANCHE_START = COMPLETED_PREFIX + 1`
   - `TRANCHE_END = min(COMPLETED_PREFIX + 50, cohort_size)`
   - `CURRENT_JSON = tmp/all-by-loa-current.json`
   - `CURRENT_HTML = tmp/all-by-loa-current.html`

2. Select exactly the cohort entries at
   `TRANCHE_START..TRANCHE_END`. Require every selected owner to have
   `workflow.researched=false`.

Print the selected range and the cohort position, person ID, display name,
largest current vessel and LOA at both boundaries.

Never substitute another owner for a target owner and never move beyond
`TRANCHE_END` during this run.

## Resume rules

For each target owner:

- if a terminal dossier existed at startup, the reconciliation step should
  already have marked it researched and it must not be in the selected range;
- if a selected owner's dossier exists, treat it as interrupted partial work;
  preserve a copy beneath
  `output/owner-research/all-by-loa-partials/tranche-{TRANCHE_START}-{TRANCHE_END}/`
  before replacing it when necessary;
- never treat mere file existence as completion; only a terminal dossier
  reconciled into the cohort changes progress; and
- never inspect later dossiers as a reason to advance the tranche.

## Research the target owners

Complete every remaining owner at positions
`TRANCHE_START..TRANCHE_END` in cohort order.

Use at most three research subagents concurrently. Give each subagent exactly
one owner at a time and `$research-owner-biography`.

Subagents may edit only their assigned production dossier. They must not edit
the owner input, cohort, source code, documentation, tests, transient compiled
artifacts, earlier dossiers, later dossiers, or another owner's dossier.

The main agent owns tranche selection, identity review, dossier validation,
progress updates, cross-owner consistency, corpus auditing and compilation.

For every target owner:

1. Run `inventory_owner.py` against the exact owner input and person ID.
2. Resolve identity before enrichment using the name, business or public role,
   geography, family context and yacht context. Require identity confidence
   of at least 75 for a resolved owner.
3. Search Forbes first and record `verified`, `not_found`, `ambiguous`, or
   `unavailable`.
4. Research the origin of wealth or prominence and the principal current
   private interests using strong public sources.
5. Research separately, then populate:

   - `wealth_creation_industry`;
   - `primary_industry`;
   - `wealth_origin`; and
   - `wealth_relationship`.

   If current `primary_industry` cannot be established but
   `wealth_creation_industry` is known, use the creation sector for both
   industry fields. Explain in the primary summary and confidence reason that
   this is an origin-sector fallback, without claiming verified current
   holdings. Keep `wealth_origin` as a separate acquisition mechanism.

   For every HNWI field, choose the best-supported classification that reaches
   confidence 70 from direct evidence or a transparent reasoned inference.
   Require positive, convergent evidence for every material premise and for
   the business, asset, transfer, or role's importance to the principal
   wealth. The source need not use the database's exact label or publish a
   full balance sheet, exact valuation, ownership percentage, deed, probate
   record, cap table, or transaction price. When a narrow subtype is
   unresolved, step back to the least-specific supported value before using
   `Unknown`.

   Apply the field-specific rules in `wealth-classification.md`, including:

   - use broad `self_made` when a founder-built, acquired, or career-earned
     principal asset is established but seed capital or starting advantage is
     unresolved;
   - use `mixed` when two or more origin mechanisms are independently
     supported and material, without requiring exact percentages;
   - infer an industry from a clearly central wealth-producing business even
     without an exact asset valuation, while using `diversified` only when
     several unrelated sectors are positively material and none dominates;
   - infer `founder`, `operator`, `investor`, `heir_family_shareholder`, or
     `family_office_principal` from the documented principal current asset
     relationship, not an isolated, honorary, or historical role;
   - use `passive_asset_owner` only when both ownership and passive or
     delegated stewardship are positively supported; and
   - use medium-confidence `marriage_family_transfer` when sources establish a
     pre-existing family asset, succession from a relative, and present
     personal ownership, control, shareholding, beneficiary status, or
     reliable attribution of wealth to that asset, even though the precise
     legal route is not public.

   Record the positive premises, materiality, inference, and important gap in
   the classification summary and confidence reason. Never reason from
   silence or use one inferred field as circular support for another. A
   surname, family association, title, board seat, one investment, or absent
   contrary evidence is insufficient. Use `inherited` only when inheritance
   is supported and `inherited_and_expanded` only when both inheritance and
   material expansion are supported.

6. Apply the current self-made starting-position distinctions:

   - use `self_made_independent` only with positive evidence of a materially
     independent start;
   - use `self_made_advantaged` when the separately built principal asset
     followed a material family, social, financial, industry or network
     advantage;
   - retain broad `self_made` when the asset was self-created but the starting
     position cannot be classified reliably;
   - never infer an independent start merely because no inheritance was found;
     and
   - do not conceal a material asset or capital transfer under
     `self_made_advantaged`.

7. Follow `docs/ai/OWNER_TAG_GOVERNANCE.md`. Owner research is closed-world:
   put only approved active catalogue assignments in `proposed_tags`, choosing
   the minimum coherent set that creates useful click-through cohorts. If no
   active tag fits, assign none and preserve the fact in existing narrative,
   evidence, uncertainty or review structures. Never create a formal
   candidate, promote, reactivate or edit the catalogue from an individual
   dossier; confidence, repetition and record frequency do not create taxonomy
   state.
8. Search supported person-relevant social types and reject namesake, fan,
   company-only, family-member and uncorroborated personal accounts.
9. Build the schema-v8 source-hidden `biography_brief` after completing the
   research.
10. Draft:

   - a standalone 50–55 word short biography in one paragraph; and
   - a standalone 90–190 word longer biography in exactly two paragraphs.

11. Where strongly sourced and naturally available, make the short identity
    card compactly informative about background, defining work, geographic
    base, broad wealth stature, concrete wealth mechanism and causally relevant
    family context. Silently omit unavailable signals.
12. For `self_made_advantaged`, state the material starting advantage naturally
    in at least one biography and in the short biography when omission would
    imply a blank-slate origin.
13. Keep the short and long biographies complementary:

    - no more than two shared anchors;
    - at least one short-only dimension;
    - at least two substantive long-only dimensions; and
    - no expanded, reordered or paraphrased short-biography bundle.

14. Apply the referential-clarity test to every sentence about family
    assistance, funding, financing, backing, support, capital, results or
    success. Name who supplied what, its purpose and relevant setting; replace
    a causal pronoun when its antecedent is not unmistakable. Do not describe
    education costs or student trading capital as funding the institution
    attended.
15. Keep source narration, confidence language, classification deliberation,
    database language, rankings, volatile net-worth figures and current vessel
    context out of published prose.
16. Apply the sale-independence test and use British English.
17. Set `review.status=complete` only after the research decision is terminal
    and the dossier passes strict validation.
18. Save the dossier as
    `output/owner-research/all-by-loa/{PERSON_ID}.research.json`.
19. Run:

    `.\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\validate_dossier.py DOSSIER_PATH --owner-input output\owners-list.vessel-enriched.enriched.json --strict-editorial`

20. Fix every validation error and warning.
21. Do not hand-edit the cohort flag. The terminal validated dossier will be
    reconciled into the cohort by `sync_owner_cohort_status.py`.

Give the user a concise checkpoint after each group of ten newly completed
owners. If the run is interrupted, its next invocation begins by reconciling
all terminal dossiers, so completed work is recovered without another state
file.

For an institution, government, municipality or unresolved placeholder, do not
invent a human identity or personal wealth story. Use the appropriate
non-person schema-v8 path, preserve its cohort position, validate it and count
it as completed.

## Tranche and cumulative editorial review

After every target dossier is terminal and strictly validated:

1. Re-run strict validation for every dossier in the target tranche.
2. Perform a main-agent consistency review across the target tranche:

   - wealth classifications are applied consistently;
   - self-made starting-position decisions follow positive evidence;
   - short biographies use useful sourced identity signals without becoming a
     template;
   - short and long biographies remain structurally independent;
   - funding and assistance sentences identify provider, form, purpose and
     setting, while causal pronouns have unmistakable antecedents;
   - source narration and classification deliberation stay out of published
     prose;
   - royal, sovereign, family and personal wealth are not conflated;
   - vessel context is absent unless maritime work is independently central;
     and
   - opening modes, narrative shapes, transitions and endings are varied.

3. Run the strict corpus auditor over the production dossier directory:

   `.\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\audit_biography_corpus.py output\owner-research\all-by-loa --strict`

4. Fix every actionable issue involving a target owner.
5. If the audit reports an issue involving only a frozen earlier owner, do not
   edit that owner. Report the unexpected frozen-corpus issue and stop for user
   direction.
6. Require zero unresolved actionable issues before compilation.

## Compile a transient cumulative review

Run the normal compiler:

`.\venv\Scripts\python.exe .\compile_owner_research.py --input output\owners-list.vessel-enriched.enriched.json --dossier-dir output\owner-research\all-by-loa --selection all-by-loa --limit TRANCHE_END --output CURRENT_JSON --report CURRENT_HTML --mark-ai-enriched`

Pass `--mark-ai-enriched` so usable completed dossiers are accepted into the
derived owner document. `CURRENT_JSON` and `CURRENT_HTML` are disposable
validation artifacts under ignored `tmp/`; they are not progress authorities
and must not be retained as numbered checkpoints.

Verify:

- exactly `TRANCHE_END` owners were compiled in cohort order;
- every selected owner has a validated production dossier;
- every usable compiled owner has `workflow.ai_enriched=true`, while unresolved
  placeholders remain false;
- all four wealth classifications exist in every compiled `ai_research`
  object;
- `_baseline`, person IDs, profile URLs, profile keys and vessel data remain
  unchanged; and
- the first and last compiled IDs match cohort positions 1 and `TRANCHE_END`.

## Advance progress only after success

After successful research, validation, corpus audit and transient compilation,
run `sync_owner_cohort_status.py` in dry-run mode and then with `--apply`.
Do not pass an unverified owner document as `--updated-owner-input`.

Confirm that:

- `workflow_summary.completed_prefix == TRANCHE_END`;
- `researched_count == TRANCHE_END`;
- `remaining_research_count == cohort_size - TRANCHE_END`;
- every target owner now has `workflow.researched=true`; and
- `next_unresearched_owner` is the cohort entry at `TRANCHE_END + 1`, or null
  when complete.

This status-only cohort change does not authorize editing any identity or
ranking field. Remove `CURRENT_JSON` and `CURRENT_HTML` after their validation;
they can always be regenerated from the enriched owner input and production
dossiers.

## Final acceptance criteria

- The exact selected contiguous tranche is complete.
- Every target owner ID is recorded as completed.
- Every target dossier passes strict validation.
- The production corpus audit has zero unresolved actionable issues.
- Earlier production positions were not modified.
- All usable compiled owners have `workflow.ai_enriched=true`; unresolved
  placeholders remain false.
- Every target dossier has `review.status=complete`.
- Cohort research flags and `workflow_summary` match `TRANCHE_END`.
- No progress marker, tranche summary, or numbered cumulative artifact was
  created or retained.
- The transient compilation artifacts were removed after validation.
- The offline test suite passes.
- Python compilation passes.
- Custom GPT Knowledge is current.
- `git diff --check` passes.
- Nothing was staged, committed, pushed or applied to the live website.

When complete, return the tranche range, owner count, new/resumed/reused
counts, dossier and corpus validation results, classification counts,
unresolved or limited owner count, next owner position, and an explicit
statement that all target dossiers are complete and nothing was applied.
```
