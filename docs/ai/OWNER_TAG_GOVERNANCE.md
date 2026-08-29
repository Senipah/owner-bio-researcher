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

The tracked Custom GPT catalogue is a closed-world assignment whitelist. It
contains only active canonical tags and their approved aliases. Candidate,
inactive and merged records remain in the repository registry for global
governance and collision detection, but stay outside ordinary GPT context.

Every active catalogue entry also carries a `semantic_contract` defining its
dimension, membership, exclusions, temporal scope and click-through
expectation. Individual research must satisfy that contract; matching a label
or alias alone is not enough.

## Research dossier contract

Owner research and taxonomy discovery are separate responsibilities. Owner-
level research is closed-world: it may assign approved active tags but may not
create formal taxonomy candidates. This applies to one-off Custom GPT work,
individual dossier execution and every owner within a batch.

Schema v8 is the current and sole owner-research output contract. Schema v9 was
introduced for owner-level `tag_candidates` and also made relationship type,
temporal scope and taxonomy-value reasoning mandatory on assignments. The
candidate structure is now obsolete, while those three additive semantic
fields can remain useful without defining a new dossier version. The v9 fork
was therefore retired before broad deployment. Stricter assignment semantics
do not change the JSON shape and do not require a schema bump.

Within schema v8:

- `proposed_tags` contains only approved active ID/name references;
- aliases resolve to their active canonical ID and name;
- merged IDs must be replaced by their active canonical target;
- candidate, inactive, unknown, ambiguous and mismatched references fail
  validation and cannot compile or reach live reconciliation;
- each assignment retains its owner-specific summary, evidence confidence and
  source IDs; relationship type, temporal scope and taxonomy-value reasoning
  may be retained as additive owner-specific metadata; and
- owner dossiers must not contain `tag_candidates`.

When no active tag represents an important fact, assign no tag. Preserve the
fact in the biography brief, source ledger, uncertainties,
`candidates_requiring_review`, or another existing narrative structure. An
optional plain-language taxonomy-gap note is a research observation, not a
candidate: it has no proposed name, aliases, facets, ID or lifecycle status.
Tag count is not a completeness metric.

## Global review and promotion

Individual owner research must never edit any catalogue state or emit a formal
candidate. Formal candidate creation requires either a dedicated corpus-level
cross-owner analysis or explicit human global curation. A global taxonomy
review then:

1. searches active names, aliases and semantic equivalents;
2. checks inactive and candidate tombstones to prevent recreation;
3. reviews click-through coherence, salience, documentation bias and likely
   record-count range;
4. merges a semantic alias, rejects/retains the candidate, or approves a new
   canonical concept;
5. records a human/global `approval_reference`;
6. may queue a formal candidate through the dry-run-first corpus registration
   tool, or promote/create an active tag through explicitly approved catalogue
   tooling;
7. rebuilds Custom GPT Knowledge and validates all consumers.

`register_corpus_tag_candidates.py` requires a reviewed corpus manifest with at
least two distinct owner dossier records and the policy's relationship,
cohort, broader-tag, facet, metadata and information-value reasoning. It
searches active, candidate, inactive and merged labels before allocating an ID,
and can create only `candidate` records. The two-record structural minimum
proves that the
code path is corpus-level; it is not an approval threshold. The 5 to 50 range
remains a soft prior. No frequency promotes a candidate. Existing active
singletons stay active unless a semantic review retires them. Reactivating an
inactive concept also requires deliberate global review.

The corpus manifest uses this reviewed shape:

```json
{
  "schema_version": 1,
  "scope": "corpus_owner_tag_discovery",
  "review_status": "approved_for_candidate_queue",
  "review_reference": "human-readable corpus review reference",
  "concepts": [
    {
      "name": "Proposed canonical name",
      "aliases": [],
      "facets": ["occupation"],
      "relationship_contract": "What membership means consistently.",
      "click_through_expectation": "What a user expects after clicking.",
      "known_for_basis": "Why the owners are genuinely known for it.",
      "existing_active_review": "Why active coverage is insufficient.",
      "broader_tag_review": "Why a broader active concept is weaker.",
      "facet_review": "Why facet-only treatment is insufficient.",
      "dossier_metadata_review": "Why this is taxonomy, not dossier detail.",
      "information_value": "The cross-owner question this cohort answers.",
      "dossier_records": [
        {
          "person_id": 1,
          "dossier": "path/to/1.research.json",
          "membership_basis": "Why this record meets the contract."
        },
        {
          "person_id": 2,
          "dossier": "path/to/2.research.json",
          "membership_basis": "Why this record meets the same contract."
        }
      ]
    }
  ]
}
```

Run registration without `--apply`, review its lifecycle-collision results,
then use `--apply --audit PATH` only to enter approved concepts into the
candidate queue while retaining the global reasoning record. Candidate
promotion is a later and separate human-approved action through
`add_catalogue_tag.py --promote-id TAG_ID --approval-reference REFERENCE`.

## Audit and reconciliation contract

Audit output uses `dossier_record_count` terminology because source duplicates
remain. It separates active approved assignments,
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
dimension, sentence-like names, near-identical concepts or cohorts and
non-active references.

## Identity safety

The upstream `person_id` is the authoritative source-record identity. Research
must not transfer dates, titles, offices or biographies between relatives with
similar names. Matching names or dates of birth never merge records. Conflicting
identity facts remain unresolved and cannot support automatic tag assignments.
Audit counts never infer unique people.

## Repository corpus consolidation record

The last clearly approved pre-run catalogue is Git commit `6982498`, the parent
of the runaway `1ccfc30` pass. It contained 244 active tags. The lifecycle
recovery then preserved all 6,884 stable IDs while placing the 1,664 unapproved
multi-record concepts in `candidate` and 4,976 other unapproved concepts in
`inactive`. That recovered repository state, not the website, was the starting
point for the completed corpus consolidation.

The reviewed repository-only consolidation produced:

| Lifecycle state | Before consolidation | Final | Decision |
| --- | ---: | ---: | --- |
| Active | 244 | 391 | 137 candidates promoted, 18 inactive concepts reactivated, 8 active concepts retired |
| Candidate | 1,664 | 0 | Every candidate resolved; 137 promoted and 1,527 inactivated |
| Inactive | 4,976 | 6,493 | Rejected, redundant, over-specific, incidental, or otherwise weak concepts retained as tombstones |
| Merged | 0 | 0 | No false-equivalence merges; true lexical equivalents are aliases |

The curation preserved every stable ID and added a machine-readable
`semantic_contract` to every active tag. Broader and narrower concepts were
not merged merely because their cohorts overlap. Specificity and companion
rules instead control assignment, including `Gambling` with directly supported
granular gambling tags, and `Video games` with video-game concepts. Casino and
betting meanings of "gaming" never qualify for `Video games`.

The alias review made the following explicit decisions:

- `Disney Plus` and `Disney+` are not aliases of `Disney` because the streaming
  service is narrower than the parent company.
- `Hidrostroy AD`, `Hydrostroy`, and `Hydrostroy AD` are accepted aliases of
  `Hidrostroy`.
- `Buyout investing`, `Buyout investment`, and `Private-equity buyouts` are not
  aliases of `Private equity`; they are narrower strategies.
- `Multi-brand restaurant group`, `Multi-brand restaurant operations`, and
  `Restaurant brand portfolio` are accepted aliases of `Restaurant groups`.
- `Winemaking business` is accepted as an alias of `Wine production`; `Wine`
  is too broad and is rejected as an alias.

Eight previously active concepts were retired because their historical
assignments represented passive holdings, counterparties, predecessor
employers, products, broad duplicates, or philanthropy noise: `Apple`,
`Citicorp Venture Capital`, `eBay`, `Filmmaking`, `Jim Moran Foundation`,
`Marlink`, `Royal Caribbean`, and `Steam`. Facts removed from literal tag sets
were preserved as internal review context rather than silently discarded.

The 989 tracked dossiers contain 950 usable person or institution records and
39 unresolved placeholders. All 950 usable dossiers were reviewed under the
final contracts; 941 tracked dossier files changed, while all 39 unresolved
placeholders were preserved. The runaway proposal set fell from 17,750
assignments (average 18.684, median 18, maximum 53 per usable dossier) to 3,655
(average 3.847, median 4, maximum 10). Final cohort diagnostics show 203 active
tags below five dossier records, 182 between five and fifty, and six above
fifty. These ranges are review signals, not approval rules. `Composer` remains
the sole zero-record active concept as a deliberate reusable occupational tag.

The consolidation is reproducible from
`config/owner-tag-consolidation.json` with
`scripts/consolidate_owner_tag_corpus.py`. Its post-application dry run reports
zero catalogue or dossier changes. The operation used only the approved Git
baseline, lifecycle catalogue, repository history, dossier corpus, canonical
governance rules, and reviewed curation configuration. It did not authenticate
to, read, compare, or write live website state. Live reconciliation is a
separate follow-up task after repository approval and may only produce a dry-
run operational diff unless independently authorised. Dossier deduplication
and person-ID repair also remain separate clerical work.
