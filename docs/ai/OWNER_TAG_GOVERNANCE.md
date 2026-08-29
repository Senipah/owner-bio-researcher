# Owner Tag Governance

This is the canonical policy for owner-tag research, catalogue maintenance,
audit and website reconciliation. Other repository documents and the
`research-owner-biography` skill reference this file rather than restating the
policy.

## Purpose and decision hierarchy

Owner tags exist to create meaningful, interesting and insightful correlations
between yacht-owner records. They are not an encoding of every known fact.

Every proposed association must pass three separate questions:

1. Is the fact true?
2. Is it notable or defining for the owner?
3. Would a literal tag create useful owner-to-owner intelligence?

Evidence confidence answers the first question. Salience answers the second.
Only information value answers the third and determines taxonomy suitability.

For cohort size, use this hierarchy:

1. A cohort of roughly 5 to 50 source records is a useful prior.
2. Cohort coherence is the test.
3. Information value is the final criterion.

Frequency never grants approval. A small royal-family cohort may be excellent;
a large coherent cohort may remain useful. Counts describe source records, not
deduplicated people.

## The click-through cohort test

Before assigning or approving a literal tag, ask what a user would reasonably
expect to see after clicking it. The returned records must fulfil that
expectation through a consistent relationship contract.

A company tag must not silently combine founders, controlling owners,
executives, former employees, passive shareholders, early investors, customers,
suppliers, donors and advisers. A documented relationship with the same entity
does not by itself create a coherent cohort.

Tags normally describe what knowledgeable people would say an owner is known
for. One artwork purchase does not make an `Art Collector`; one technology
investment does not make a `Technology Investor`; one board role, donation,
course or transaction does not normally justify an institution or industry
tag. A fact can be important biography material without becoming a tag.

## Minimum useful literal set

Group possible assignments into semantic dimensions such as:

- principal industry or subindustry;
- profession or operating role;
- investment background;
- defining company affiliation;
- family, dynasty or royal affiliation;
- sporting identity;
- cultural interest;
- public office;
- a distinctive cause or public-interest activity.

Ordinarily retain one principal literal tag per dimension. Add one narrower or
role-specific tag only when it answers a separate useful click-through
question. Further overlap needs an explicit explanation of the independent
information value.

Prevent synonyms, near-synonyms, singular/plural duplicates and parent/child
pairs that add no distinct intelligence. Do not describe one shipping career
with every variation of commercial shipping, ship ownership, ship management,
shipping executive, maritime entrepreneur, tanker shipping and shipping
investing.

Specificity remains valuable when it changes the question. `House of Saud`,
`Al Maktoum` or another specific family can carry more information than
`Royalty`. Consolidation removes semantic noise, not meaningful family,
dynasty or other precise cohorts.

## Facets and literal tags

Catalogue facets preserve broader concepts, dimensions and useful precision.
They are not currently user-facing browse relationships and must not be
automatically assigned as additional literal tags.

Choose the literal level that creates the strongest useful cohort. If
`Olympic sailor` would produce a tiny cohort while `Olympics` creates a
coherent group across sports, use `Olympics` and retain the sailing or medal
detail in facets, owner-specific evidence or narrative. Do not automatically
assign both.

The same reasoning applies to `Film Director` and `Filmmaking`: use the level
that best serves the current owner population, while preserving precise role
detail outside the literal tag when appropriate.

## Named entities and narrative analysis

Companies, universities, foundations, clubs, government bodies, teams, awards,
projects and transactions are not tags merely because they appear prominently
in a dossier. A named-entity tag needs a defined relationship such as founder,
co-founder, controlling owner, principal family owner or defining long-term
leader. Family and dynasty membership is a deliberate exception where
membership itself supplies the useful relationship.

Passive shares, one successful investment, a customer or supplier
relationship, one board appointment, a donation, an honorary degree, a short
course or a one-off transaction normally remain dossier facts.

Sentence-like descriptions of career progression, acquisition strategy,
succession, financing, governance, transaction mechanics or transformation are
presumed to be analysis, not tags. Examples include `Founder-to-son operating
succession`, `Regional-governor-to-monarch transition` and `Strategic-buyer
exits`. Such a concept needs a concise recognisable meaning, consistent
assessment across comparable records, a genuinely defining association and no
cleaner existing tag before it can enter global review.

## Documentation bias and temporal roles

Deeply researched owners must not accumulate more tags merely because more
facts are available. Ask whether comparable records can be assessed reasonably
consistently with the corpus actually available. Strategy, governance,
succession, management style, international expansion and vertical integration
carry a particularly high burden because they often identify the
best-documented records rather than a real cohort.

By default a role tag means that the person has held and remains notably
associated with the role, unless the tag is explicitly current-only. Do not
tag every career stage. A monarch normally receives `Monarch`, not also `Crown
Prince`; a former prime minister may retain `Prime Minister` when it remains a
defining identity. Owner evidence may record `current`,
`former_but_defining`, `historical`, `current_only`, `unknown` or
`not_applicable` temporal scope.

## Calibration examples

- **Amazon:** a financially decisive early investment does not automatically
  justify `Amazon`. Users would expect founders or defining leaders, not every
  outside investor whose wealth benefited from the shares.
- **Art Collector:** use it for owners genuinely known for serious collecting,
  not anyone who bought expensive art.
- **Olympics:** prefer a coherent broader Olympic cohort when precise sport or
  medal labels would fragment it into weak groups. Preserve precision outside
  the literal assignment.
- **Filmmaking:** it may be the stronger literal cohort while `Film Director`
  remains role detail. This does not permanently forbid the narrower tag.
- **Commercial shipping:** use the minimum canonical set that captures a
  defining shipping identity; do not reproduce every sector, role and strategy
  variant.
- **Royal families:** preserve specific family and dynasty cohorts when they
  add information beyond generic `Royalty`.
- **Gambling and video games:** gambling-industry `Gaming` resolves to
  `Gambling`, plus each directly supported granular active tag. `Video games`
  requires explicit interactive-entertainment evidence.
- **Government-owned:** use only when the owner record is a government or
  public body, or an institution is explicitly state-owned. Public office,
  contracting, employment, sovereign-asset stewardship and private royal
  ownership do not qualify.

## Catalogue lifecycle and storage decision

`config/owner-tags.json` is one status-aware registry. A single file was chosen
because all known consumers already target that explicit path, stable IDs and
cross-state aliases must remain discoverable, and legacy dossiers need precise
lifecycle diagnostics. Physical separation would require consumers to combine
files to diagnose old references and would increase the chance of losing a
tombstone.

Safety comes from the loader contract:

- `active`: human-approved canonical concept; available for assignment;
- `candidate`: unapproved global-review concept; never assignable;
- `inactive`: rejected, retired or suppressed concept; never assignable but
  preserved against accidental recreation;
- `merged`: former stable ID redirected to a canonical active target.

`src/tags.py` exposes active tags through its production view. Candidate and
inactive names remain in a separate non-assignable lookup. Merged references
resolve only when their terminal target is active. Broad consumers must use
the loader rather than reading and flattening the JSON `tags` array.

The tracked Custom GPT catalogue contains assignable active/merged entries in
`tags` and reduced candidate/inactive tombstones under
`reserved_non_assignable_labels`. Instructions explicitly prohibit assigning
the reserved entries.

## Research dossier contract

Schema v8 remains supported and unchanged as a legacy contract. Its historical
`proposed_tags` may contain null IDs or references that later became
non-active. Validators report such references as pending corpus consolidation
without rewriting the dossier. Compilation and live mutation fail safely when
an assignment cannot resolve to an active tag.

Schema v9 is the current researcher output. It makes the lifecycle boundary
enforceable:

- `proposed_tags` contains only approved active ID/name references;
- merged IDs must be replaced by their active canonical target;
- each assignment retains its owner-specific summary, evidence confidence and
  source IDs, plus relationship type, temporal scope and a separate taxonomy-
  value judgement;
- `tag_candidates` is a separate required list for exceptional unapproved
  concepts;
- a candidate has no production tag ID and cannot become active from an owner
  dossier;
- catalogue facets remain metadata and are not promoted automatically to
  literal assignments.

A candidate records its proposed and normalised name, possible aliases,
suggested facets, owner evidence, relationship and temporal scope, cross-owner
information value, review of existing active coverage, likelihood that it is
dossier metadata instead, confidence and source IDs. Before creating one, ask
whether an active tag, facet or narrative already preserves the information.

Candidate creation is exceptional. Omit a weak tag and retain the useful fact
in the biography or evidence rather than researching indefinitely to justify a
classification. Tag count is not a completeness metric.

## Global review and promotion

Individual owner research must never edit the active catalogue. It may assign
existing active tags or emit a separate candidate. A global taxonomy review
then:

1. searches active names, aliases and semantic equivalents;
2. checks inactive and candidate tombstones to prevent recreation;
3. reviews click-through coherence, salience, documentation bias and likely
   record-count range;
4. merges a semantic alias, rejects/retains the candidate, or approves a new
   canonical concept;
5. records a human/global `approval_reference`;
6. promotes or creates the active tag through the reviewed catalogue tooling;
7. rebuilds Custom GPT Knowledge and validates all consumers.

No minimum record count promotes a candidate. Existing active singletons stay
active unless a semantic review retires them. Reactivating an inactive concept
also requires deliberate global review.

## Audit and reconciliation contract

Audit output uses `dossier_record_count` terminology because source duplicates
remain. It separates active approved assignments, dossier candidates,
candidate/inactive/merged legacy references, unresolved classifications,
current live tags where a read occurred, and planned or blocked operations.

Offline mode is a frequency and lifecycle audit. It never authenticates, never
reads current website state, and reports additions and removals as unknown.
Terms such as `publishable` are prohibited for frequency-derived output.

A live process may describe additions, removals or unchanged assignments only
after a successful current-state read for that record. Destructive removal
requires all of:

- successful live reads;
- `--apply` and explicit `--replace-tags` authority;
- a supplied, previously reviewed live dry-run manifest;
- an exact match between current removals and those in that manifest;
- a production-ready dossier with no non-active or unresolved tag references.

Unresolved placeholders and incomplete legacy desired states remain outside
destructive reconciliation. Diagnostics are warnings and review signals, not
automatic semantic edits. Useful signals include cohorts below five or above
fifty records, unusually high per-record tag counts, more than two tags in one
dimension, sentence-like names, near-identical concepts or cohorts, non-active
references and dossier candidates duplicating active aliases.

## Identity safety

The upstream `person_id` is the authoritative source-record identity. Research
must not transfer dates, titles, offices or biographies between relatives with
similar names. Matching names or dates of birth never merge records. Conflicting
identity facts remain unresolved and cannot support automatic tag assignments.
Audit counts never infer unique people.

## Lifecycle migration record

The last clearly approved pre-run catalogue is Git commit `6982498`, the parent
of the runaway `1ccfc30` pass. It contains 244 tags. The offline audit
`owner-tag-update-offline-dry-run-20260829T175711Z.json` was used only to count
source dossier references and carries no live-state or approval authority.

The reversible migration preserved all 6,884 stable IDs and produced:

| Lifecycle state | Tag records | Basis |
| --- | ---: | --- |
| Active | 244 | Present in approved baseline `6982498` |
| Candidate | 1,664 | Added by `1ccfc30`, referenced by at least two dossier records, no explicit approval |
| Inactive | 4,976 | Added by `1ccfc30`, suppressed singleton concepts |
| Merged | 0 | No persisted merged entries existed in the source catalogue |

Fourteen approved baseline tags appeared in one audit record and one appeared
in none; all remain active because the offline audit cannot establish live
usage and frequency is not approval. Five baseline tags had post-run alias
changes: Disney, Hidrostroy, Private equity, Restaurant groups and Wine
production. Approved aliases were restored; the added aliases remain preserved
as non-resolving `pending_aliases` for later review. No tag was unclassified.

The migration changed no dossier and read or modified no live website state.
An ignored byte-verified backup was created at
`output/backups/owner-tags.pre-lifecycle-1ccfc30.json`.

## Handover for the later corpus consolidation

The later long-horizon task should edit the existing dossiers in place, upgrade
corrected records to schema v9, and treat every first-pass desired tag as an
untrusted reference. It should consolidate the active taxonomy semantically,
promote candidates only through explicit global review, and reactivate inactive
concepts only deliberately. Apply the 5 to 50 heuristic without making it a
hard rule.

After repository review, compare each production-ready proposed assignment
with freshly read live state before any application. Keep dossier deduplication
and person-ID repair for the separate clerical in-system task. Do not infer
unique people from names or dates of birth.
