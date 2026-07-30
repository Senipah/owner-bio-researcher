# Goal Mode prompt: next 50 LOA-prioritised owners

Paste the prompt below from the repository root each time another tranche
should be researched. It reads the shared progress marker, resumes an
interrupted tranche when necessary, or selects the next contiguous 50 owners.
No positions, filenames, or prefix values need to be edited between runs.

The progress marker is the authority for tranche selection. Earlier production
dossiers are frozen, new dossiers remain pending review, and nothing is
applied to the live website.

## Prompt

```text
Use `$research-owner-biography`.

Goal: resume the active LOA-prioritised research tranche, or research the next
contiguous batch of 50 owners after the completed production prefix, then
compile cumulative pending-review artifacts through the end of that tranche.

This prompt is intentionally reusable without editing. Never choose a tranche
from filenames, scattered missing dossiers, or the highest dossier position.
Use the progress marker only.

Do not mark this goal complete until the selected tranche and every acceptance
criterion below are complete. An individual sparse or difficult owner is not a
reason to skip forward or mark the goal blocked.

## Authoritative files

- Owner input:
  `output/owners-list.vessel-enriched.enriched.json`
- Immutable LOA-sorted cohort:
  `output/owner-research/all-by-loa/cohort.json`
- Production dossiers:
  `output/owner-research/all-by-loa/`
- Progress marker:
  `output/owner-research/all-by-loa-progress.json`
- Tranche size: 50

Read `AGENTS.md`, the relevant repository documentation, and the complete
`$research-owner-biography` skill with all required references before acting.

This is a research-and-review task only. Do not approve dossiers, set
`workflow.ai_enriched=true`, call `update_owners.py`, apply website changes,
stage files, commit, or push.

## Read and verify progress

1. Load the cohort and progress marker. If the progress marker is missing,
   malformed, or incompatible, stop for user direction. Do not reconstruct
   progress from dossier filenames.
2. Verify:

   - `selection` is `all-by-loa`;
   - the recorded owner-input, cohort, and dossier paths are the authoritative
     paths above;
   - `cohort_size` equals the number of cohort entries;
   - `tranche_size` is 50;
   - `completed_prefix` is between 0 and `cohort_size`;
   - when `completed_prefix > 0`, `completed_through.person_id` matches the
     person at that cohort position; and
   - when owners remain, `next_owner` matches the cohort entry immediately
     after `completed_prefix`.

3. Do not modify dossiers at positions `1..completed_prefix`.
4. If `completed_prefix == cohort_size`, report that the cohort is complete
   and do not start another tranche.

## Select or resume the tranche

If `active_tranche` is not null:

- resume its exact `start_position` and `end_position`;
- require `start_position == completed_prefix + 1`;
- require `end_position` to equal
  `min(completed_prefix + tranche_size, cohort_size)`;
- verify every recorded owner ID against the cohort; and
- preserve its `completed_person_ids`.

If `active_tranche` is null:

1. Set:

   - `TRANCHE_START = completed_prefix + 1`
   - `TRANCHE_END = min(completed_prefix + tranche_size, cohort_size)`
   - `CURRENT_LIMIT = TRANCHE_END`
   - `TRANCHE_SUMMARY = output/owner-research/all-by-loa-tranche-{TRANCHE_START}-{TRANCHE_END}-summary.json`
   - `CURRENT_JSON = output/research-enriched-owners-list.all-by-loa.first-{TRANCHE_END}.json`
   - `CURRENT_HTML = output/research-enriched-owners-list.all-by-loa.first-{TRANCHE_END}.html`

2. Atomically set `active_tranche` in the progress marker with:

   - start and end positions;
   - the ordered target person IDs and display names;
   - `completed_person_ids=[]`;
   - start timestamp;
   - tranche summary path; and
   - cumulative JSON and HTML paths.

Use `src.io_utils.atomic_write_json` for every progress-marker update.

Print the selected range and the cohort position, person ID, display name,
largest current vessel and LOA at both boundaries.

Never substitute another owner for a target owner and never move beyond
`TRANCHE_END` during this run.

## Resume rules

For each target owner:

- if the person ID appears in `active_tranche.completed_person_ids`, reuse the
  production dossier only when it still matches the target identity and passes
  strict validation against the current owner input;
- if that recorded completed dossier is missing, stale, mismatched, or invalid,
  remove its ID from the completed list atomically and research it again;
- if a target dossier exists but its ID is not recorded as completed, treat it
  as interrupted partial work; preserve a copy beneath
  `output/owner-research/all-by-loa-partials/tranche-{TRANCHE_START}-{TRANCHE_END}/`
  before replacing it when necessary;
- never treat mere file existence as completion; and
- never inspect later dossiers as a reason to advance the tranche.

## Research the target owners

Complete every remaining owner at positions
`TRANCHE_START..TRANCHE_END` in cohort order.

Use at most three research subagents concurrently. Give each subagent exactly
one owner at a time and `$research-owner-biography`.

Subagents may edit only their assigned production dossier. They must not edit
the owner input, cohort, progress marker, source code, documentation, tests,
compiled artifacts, tranche summary, earlier dossiers, later dossiers, or
another owner's dossier.

The main agent owns tranche selection, identity review, dossier validation,
progress updates, cross-owner consistency, corpus auditing and compilation.

For every target owner:

1. Run `inventory_owner.py` against the exact owner input and person ID.
2. Resolve identity before enrichment using the name, business or public role,
   geography, family context and yacht context.
3. Search Forbes first and record `verified`, `not_found`, `ambiguous`, or
   `unavailable`.
4. Research the origin of wealth or prominence and the principal current
   private interests using strong public sources.
5. Populate independently:

   - `wealth_creation_industry`;
   - `primary_industry`;
   - `wealth_origin`; and
   - `wealth_relationship`.

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

7. Search supported person-relevant social types and reject namesake, fan,
   company-only, family-member and uncorroborated personal accounts.
8. Build the schema-v7 source-hidden `biography_brief` after completing the
   research.
9. Draft:

   - a standalone 50–55 word short biography in one paragraph; and
   - a standalone 90–190 word longer biography in exactly two paragraphs.

10. Where strongly sourced and naturally available, make the short identity
    card compactly informative about background, defining work, geographic
    base, broad wealth stature, concrete wealth mechanism and causally relevant
    family context. Silently omit unavailable signals.
11. For `self_made_advantaged`, state the material starting advantage naturally
    in at least one biography and in the short biography when omission would
    imply a blank-slate origin.
12. Keep the short and long biographies complementary:

    - no more than two shared anchors;
    - at least one short-only dimension;
    - at least two substantive long-only dimensions; and
    - no expanded, reordered or paraphrased short-biography bundle.

13. Apply the referential-clarity test to every sentence about family
    assistance, funding, financing, backing, support, capital, results or
    success. Name who supplied what, its purpose and relevant setting; replace
    a causal pronoun when its antecedent is not unmistakable. Do not describe
    education costs or student trading capital as funding the institution
    attended.
14. Keep source narration, confidence language, classification deliberation,
    database language, rankings, volatile net-worth figures and current vessel
    context out of published prose.
15. Apply the sale-independence test and use British English.
16. Set `review.status=pending`. Never approve on the user's behalf.
17. Save the dossier as
    `output/owner-research/all-by-loa/{PERSON_ID}.research.json`.
18. Run:

    `.\venv\Scripts\python.exe .agents\skills\research-owner-biography\scripts\validate_dossier.py DOSSIER_PATH --owner-input output\owners-list.vessel-enriched.enriched.json --strict-editorial`

19. Fix every validation error and warning.
20. After the dossier passes, atomically append its person ID to
    `active_tranche.completed_person_ids`.

Give the user a concise checkpoint after each group of ten newly completed
owners. A completed ID in the progress marker makes the run safely resumable.

For an institution, government, municipality or unresolved placeholder, do not
invent a human identity or personal wealth story. Use the appropriate
non-person schema-v7 path, preserve its cohort position, validate it and count
it as completed.

## Tranche and cumulative editorial review

After every target person ID is recorded as completed:

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

## Compile cumulative review artifacts

Run the normal compiler:

`.\venv\Scripts\python.exe .\compile_owner_research.py --input output\owners-list.vessel-enriched.enriched.json --dossier-dir output\owner-research\all-by-loa --selection all-by-loa --limit TRANCHE_END --output CURRENT_JSON --report CURRENT_HTML`

Do not pass `--mark-ai-enriched`.

Verify:

- exactly `TRANCHE_END` owners were compiled in cohort order;
- every selected owner has a validated production dossier;
- every compiled owner has `workflow.ai_enriched=false`;
- all four wealth classifications exist in every compiled `ai_research`
  object;
- `_baseline`, person IDs, profile URLs, profile keys and vessel data remain
  unchanged; and
- the first and last compiled IDs match cohort positions 1 and `TRANCHE_END`.

## Write the tranche summary

Atomically write `TRANCHE_SUMMARY` with:

- schema version and timestamps;
- tranche start and end positions;
- ordered target owner list;
- newly researched, resumed and reused counts;
- per-owner validation results;
- research-status and record-type counts;
- classification counts and self-made subtype counts;
- biography and proposal counts;
- corpus-audit result;
- cumulative JSON and HTML paths;
- compiled owner count;
- confirmation that earlier positions were not modified;
- confirmation that all dossiers remain pending;
- test and validation results; and
- the next cohort position and owner, when one remains.

The tranche summary is an audit record, not the authority for selecting the
next tranche.

## Advance progress only after success

Do not advance `completed_prefix` until every acceptance criterion passes.

After successful research, validation, audit, compilation and summary writing,
atomically update the progress marker:

- set `completed_prefix = TRANCHE_END`;
- set `completed_through` to the final target cohort position, person ID and
  display name;
- set `next_owner` to the next cohort entry, or null when the cohort is
  complete;
- set `last_completed_tranche` to its range, completion timestamp and summary
  path;
- set `last_artifacts` to `CURRENT_JSON` and `CURRENT_HTML`;
- set `active_tranche = null`; and
- update `updated_at`.

If the run stops before completion, leave `active_tranche` in place so the next
paste of this same prompt resumes it.

## Final acceptance criteria

- The exact selected contiguous tranche is complete.
- Every target owner ID is recorded as completed.
- Every target dossier passes strict validation.
- The production corpus audit has zero unresolved actionable issues.
- Earlier production positions were not modified.
- Cumulative JSON and HTML exist through `TRANCHE_END`.
- All compiled owners retain `workflow.ai_enriched=false`.
- Every dossier remains `review.status=pending`.
- The tranche summary exists.
- The progress marker advanced atomically and has `active_tranche=null`.
- The offline test suite passes.
- Python compilation passes.
- Custom GPT Knowledge is current.
- `git diff --check` passes.
- Nothing was approved, staged, committed, pushed or applied to the live
  website.

When complete, return the tranche range, owner count, new/resumed/reused
counts, dossier and corpus validation results, classification counts,
unresolved or limited owner count, cumulative JSON and HTML paths, tranche
summary path, next owner position, and an explicit statement that all dossiers
remain pending review and nothing was applied.
```
