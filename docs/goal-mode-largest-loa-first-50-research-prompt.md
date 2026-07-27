# Goal Mode prompt: first 50 owners by largest-yacht LOA

This prompt researches only the first 50 fully ranked owners in the existing
LOA-prioritised owner document. It produces review artifacts only; it does not
approve research or update the live system.

The source report already contains system-exported identity data such as name,
nationality, image URL, profile URL, and yacht relationships. A false
`workflow.owner_details_enriched` flag means only that the separate editable
details and social forms were not fetched. It is not a blocker for this
review-only AI research run, and the prompt must not change that flag.

## Prompt

Use `$research-owner-biography`.

Your goal is to research exactly the first 50 fully ranked owners by largest
current-vessel LOA from
`output/owners-list.vessel-enriched.json` and produce a review-ready research
enrichment batch.

At the start, load the input once and use
`src.research_batch.select_research_owners(document, "largest-loa", 50)` to
freeze the ordered target list. Record the input file hash and the selected
person IDs. Do not substitute Top-100 rank, array position, gross tonnage, fame,
net worth, or editorial judgment for this selection.

Preflight every selected owner before researching:

- `vessel_ownership.ranking_status` is `ranked`;
- `vessel_ownership.loa_rank` and `largest_current_loa_m` are present;
- the report contains an identity name or the profile can resolve one; and
- `person_id` and `profile_url` are present.

If any selected owner fails that preflight, do not research a replacement or
silently reduce the batch. Stop and report the affected person IDs and the
missing prerequisite.

Treat `report`, `profile_url`, `top_100`, and `vessel_ownership` as the
available system context. Do not treat an empty `details` object as evidence
that every website field is blank, and do not invent field or social proposals
that cannot be mapped to an exposed input control or social type. The
biographies and wealth classifications must still be populated in the dossier
and will remain available in compiled `ai_research` metadata.

Continue until all 50 selected owners have:

1. one schema-v4 dossier beneath
   `output/owner-research/largest-loa-first-50/`;
2. validated, evidence-backed short and longer biographies plus
   `primary_industry`, `wealth_origin`, and `wealth_relationship`
   classifications;
3. an explicit Forbes result;
4. an inventory of missing details and supported link types;
5. only confidence-85-or-higher proposed details and links; and
6. `review.status=pending`.

Use a bounded worker pool of at most three research subagents. Give each
subagent exactly one owner at a time and this skill. When one finishes and its
dossier validates, give that worker the next unprocessed owner. Do not allow
subagents to edit the shared owner JSON, source code, skill files, or another
owner's dossier. The main agent owns target selection, identity review,
validation, cross-owner consistency, checkpoint tracking, and compilation.

For every owner:

- run `inventory_owner.py` against the exact input and person ID;
- resolve identity using name, public role or business, geography, and yacht
  context before collecting facts;
- search Forbes first and record `verified`, `not_found`, `ambiguous`, or
  `unavailable`;
- classify industry, wealth origin, and wealth relationship independently
  using `references/wealth-classification.md`;
- explain how wealth or prominence arose rather than foregrounding net worth;
- search supported person-relevant social types, prioritising Instagram,
  LinkedIn, and Personal Website;
- reject namesake, company, fan, family-member, and uncorroborated accounts;
- use a distinct Company Website proposal only when official evidence connects
  the person to the company;
- keep lower-confidence facts and links in review candidates or uncertainties;
- draft a neutral 50-55 word short biography and a standalone,
  two-paragraph longer biography of 90-190 words, preferably 120-170;
- use the longer biography for the formative route, an important turning
  point, and one or two strongly sourced layers of character colour, later
  activity, or meaningful yachting context;
- do not pad sparse profiles, repeat the short text verbatim, append yacht
  names without a meaningful story, or infer character from ownership alone;
- save the dossier using the person ID in its filename; and
- validate the dossier with:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  DOSSIER_PATH `
  --owner-input output\owners-list.vessel-enriched.json
```

Resume safely by treating an existing dossier as complete only when it belongs
to one of the frozen person IDs and passes that exact validation command.
Re-research invalid or stale dossiers. Maintain at most three active research
agents and provide concise checkpoint updates after each group of ten
validated owners.

After all 50 dossiers validate, perform a main-agent consistency review:

- both biography tones, structures, and lengths match the Shahid Khan
  calibration;
- royal, sovereign, family, and personal wealth are not conflated, and an
  oil-producing state is not treated as evidence of personal `Energy` wealth;
- inherited, self-made, dynastic/royal, family-transfer, mixed, and unknown
  origin classifications are applied consistently;
- industry follows the principal identifiable private assets, while
  relationship distinguishes founders, operators, investors, heirs, family
  office principals, royal beneficiaries, custodians, and passive owners;
- proposed select values use labels supported by the owner form;
- social type IDs match the input lookup; and
- no dossier is approved on the user's behalf.

Compile the review artifacts:

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.vessel-enriched.json `
  --dossier-dir output\owner-research\largest-loa-first-50 `
  --selection largest-loa `
  --limit 50 `
  --output output\research-enriched-owners-list.largest-loa.first-50.json `
  --report output\research-enriched-owners-list.largest-loa.first-50.html
```

Acceptance criteria:

- the compiled JSON contains exactly the frozen 50 person IDs in descending
  largest-current-vessel LOA order;
- every compiled owner has a validated dossier;
- `_baseline`, `person_id`, `profile_url`, vessel ownership data, and existing
  `profile_key` values remain unchanged;
- pending output owners retain `workflow.ai_enriched=false`;
- the HTML report shows, per owner, LOA rank, largest current vessel and metric
  LOA, both biographies, all three wealth classifications, proposed details
  and links, confidence, evidence links, unresolved gaps, and uncertainties;
- the original input hash is unchanged;
- the offline test suite, compile checks, dossier validation, and
  `git diff --check` all pass; and
- nothing is applied to the live website.

Do not stop merely because an owner has a sparse public footprint. Produce a
limited or insufficient-evidence dossier with explicit uncertainties. Stop and
request user direction only for a systemic blocker that prevents safe progress
across the remaining batch.

When complete, return the JSON and HTML paths, the frozen person-ID list, owner
and proposal counts, validation results, unresolved or limited-owner count,
and an explicit statement that all dossiers remain pending review and nothing
was applied.

## After review

Approval is a separate task. For accepted dossiers, a human must set
`review.status=approved` plus `reviewed_by` and `reviewed_at`. Only then compile
an approved file with `--mark-ai-enriched`, run `update_owners.py` without
`--apply`, inspect its audit, and obtain separate authorisation before any live
apply. Dossiers marked `rejected` retain the original owner values and remain
ineligible for update.
