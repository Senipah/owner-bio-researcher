# Goal Mode prompt: Top-100 owner research enrichment

Paste the prompt below into Goal Mode from the repository root. It produces
review artifacts only; it does not approve research or update the live system.

## Prompt

Use `$research-owner-biography`.

Your goal is to research every unique current owner represented in
`output/owners-list.top-100.enriched.json`, in ascending order of their minimum
current Top-100 vessel rank, and produce a review-ready research enrichment
batch.

Continue until all selected owners have:

1. one schema-v4 dossier beneath `output/owner-research/top-100/`;
2. validated, evidence-backed short and longer biographies plus
   `primary_industry`, `wealth_origin`, and `wealth_relationship`
   classifications;
3. an explicit Forbes result;
4. an inventory of missing details and supported link types;
5. only confidence-85-or-higher proposed details and links;
6. `review.status=pending`.

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
- classify industry, origin, and relationship independently using
  `references/wealth-classification.md`;
- explain where wealth or prominence came from rather than foregrounding net
  worth;
- search supported person-relevant social types, prioritising Instagram,
  LinkedIn, and Personal Website;
- reject namesake, company, fan, family-member, and uncorroborated accounts;
- use a distinct Company Website proposal only when official evidence connects
  the person to the company;
- keep lower-confidence facts and links in review candidates or uncertainties;
- draft a neutral 50-55 word short biography and a standalone, two-paragraph
  longer biography of 90-190 words, preferably 120-170;
- use the longer biography for the formative route, an important turning
  point, and one or two strongly sourced layers of character colour, later
  activity, or meaningful yachting context;
- do not pad sparse profiles, repeat the short text verbatim, append yacht
  names without a meaningful story, or infer character from ownership alone;
- validate the dossier with:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  DOSSIER_PATH `
  --owner-input output\owners-list.top-100.enriched.json
```

Resume safely by treating an existing dossier as complete only when it passes
that exact validation command. Re-research invalid or stale dossiers. Maintain
at most three active research agents and provide concise checkpoint updates
after each group of ten validated owners.

After all dossiers validate, perform a main-agent consistency review:

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
- social type IDs match the input lookup;
- no dossier is approved on the CEO's behalf.

Compile the review artifacts:

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.top-100.enriched.json `
  --dossier-dir output\owner-research\top-100 `
  --selection top-100 `
  --output output\research-enriched-owners-list.top-100.json `
  --report output\research-enriched-owners-list.top-100.html
```

Acceptance criteria:

- the compiled JSON contains every and only unique current Top-100 owner,
  ordered by minimum current vessel rank;
- every compiled owner has a validated dossier;
- `_baseline`, `person_id`, `profile_url`, and existing `profile_key` values
  remain unchanged;
- pending output owners retain `workflow.ai_enriched=false`;
- the HTML report shows, per owner, vessel rank/context, both biographies, all
  three wealth classifications, missing fields added, existing fields
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
that all dossiers remain pending review and nothing was applied.

## After CEO review

Approval is a separate task. For accepted dossiers, a human must set
`review.status=approved` plus `reviewed_by` and `reviewed_at`. Only then compile
an approved file with `--mark-ai-enriched`, run `update_owners.py` without
`--apply`, inspect its audit, and obtain separate authorization before any live
apply. Dossiers marked `rejected` retain the original owner values and remain
ineligible for update.
