# Custom GPT Preview tests

Run these scenarios in the GPT Builder Preview after every Instructions,
Knowledge, model, or capability change. Start a new conversation for each
scenario because Custom GPT conversations do not share prior context.

## 1. Name-only obvious identity

Prompt:

> Mark Zuckerberg

Pass when the GPT treats the name as a complete research request, resolves the
Facebook and Meta founder without demanding more context, and returns supported
personal details, verified links, classifications, both biographies, sources,
suggested canonical tags, and confidence. It must not discuss uploaded guidance,
missing repository scripts, schema validation, or offer to provide biographies later
instead of actually providing them.

## 2. Misspelt name with disambiguator

Prompt:

> Mark Zucherberg, Facebook founder

Pass when the GPT identifies the intended person as Mark Zuckerberg, states
that correction, and completes the research without an unnecessary follow-up.

## 3. Well-documented yacht owner

Prompt:

> Research Shahid Khan, the Flex-N-Gate owner associated with the Jacksonville
> Jaguars.

Pass when:

- identity is resolved before drafting;
- Forbes is explicitly checked;
- all four wealth classifications use exact labels and supported confidence;
- the two biographies are complementary and meet their length and paragraph
  contracts;
- verified social and website links, supported personal details, sources, and
  limitations are included;
- suggested tags include all durable, material, dossier-supported groupings
  with a materiality explanation and confidence; and
- no JSON dossier or repository-validation disclaimer is inserted unless
  requested.

## 4. Ambiguous name

Prompt:

> Research John Smith.

Pass when the GPT asks for one focused disambiguator and does not search,
select an identity, classify wealth, or draft biographies prematurely.

## 5. Sparse public record

Prompt:

> Research a yacht owner named Roger Samuelsson, associated with SHL Medical.

Pass when the GPT uses the supplied company to resolve identity, produces a
shorter evidence-led profile without padding, records genuine gaps, and does
not invent personal social accounts.

## 6. Royal or dynastic owner

Prompt:

> Research Sheikh Tamim bin Hamad Al Thani, Amir of Qatar. Keep state, crown,
> office-held, family and personal assets distinct.

Pass when public role and formation are described positively, state energy
assets are not assumed to be personal wealth, unsupported industries are
`Unknown`, and no negative wealth-taxonomy contrast appears in either
biography.

The suggested tags must include canonical `Al Thani` and `Royalty` entries when
the dynasty and status are supported; do not emit duplicate alias variants.

## 7. Institution or placeholder

Prompt:

> Research an owner record named Government of Dubai. First decide whether it
> is a natural person.

Pass when `record_type` is non-person, biographies and personal candidates are
null or empty as required, wealth classifications are unknown, and an
evidence-backed editorial note explains the result.

## 8. Vessel independence

Prompt:

> Research Dimitris Procopiou, the Greek shipping entrepreneur associated with
> Golden Yachts. Use the yacht relationship only to disambiguate him.

Pass when independently central commercial shipping work may appear, but no
current yacht name, dimensions, builder, delivery, commission, or ownership
history is used as biography colour.

## 9. Social-profile namesake

Prompt:

> Research an owner and include an Instagram account only if it is linked from
> an official personal or company source or strongly cross-corroborated.

Pass when name-only, fan, company-only, and family-member accounts are rejected
as personal profiles; accepted links are candidates rather than proposals.

## 10. Advantaged self-made founder

Prompt:

> Research Abbas Hussain Sajwani, founder and chief executive of AHS
> Properties and son of DAMAC founder Hussain Sajwani.

Pass when:

- `wealth_origin` is `self_made_advantaged` with the exact label
  `Self-made — advantaged start`, rather than treating founder ownership as an
  unassisted start;
- the short biography is 50–55 words and, where supported, efficiently
  combines Emirati background, Dubai business geography, founder role,
  `billionaire` as a broad wealth descriptor, and his formative family
  context;
- the wording distinguishes his separately founded company from the family
  platform without diminishing either; and
- the family context appears in published biography prose rather than only in
  uncertainties.

## 11. Canonical alias resolution

Prompt:

> Research Lawrence Stroll and include all applicable tags. Treat F1, Formula
> One and Formula_1 as possible aliases rather than separate topics.

Pass when `Formula 1` appears once under canonical name and local catalogue ID,
with `Motorsport` and any other material dossier-supported tags assessed
independently. It must not output three Formula 1 variants or use `Family
business` or `Property development`.

## 12. One-record company tail

Prompt:

> Research Laurene Powell Jobs. Include Apple only if the dossier supports a
> durable material association, not merely a passing mention.

Pass when `Apple` is included once with its active canonical ID, evidence,
relationship, temporal scope and taxonomy-value judgement if the defining
family and wealth history supports the catalogue relationship contract. Its
record frequency neither approves nor disqualifies it. The GPT must not infer
unrelated family or company tags from surname alone.

## 13. Gambling and video-game disambiguation

Prompt:

> Research one owner whose fortune came from casino gaming and another whose
> fortune came from a video-game publisher. Apply all relevant tags.

Pass when casino gaming resolves to `Gambling` plus `Casino operations`
(including when described as `Gaming`) and never to `Video games`; the
publisher resolves to `Video games` only with explicit interactive-
entertainment evidence. Directly supported active gambling detail is assessed
alongside `Gambling` without exhaustive overlapping children. Neither result
may use `Family office` or a generic philanthropy-
domain tag.

## 14. Closed-world taxonomy gap

Prompt:

> During a future owner research run, strong sources establish a durable,
> material subindustry that meets the taxonomy rule but is absent from the
> uploaded tag catalogue. Explain and show how you handle the tag.

Pass when the GPT checks the supplied active catalogue and aliases, assigns no
tag when none fits, and preserves the underlying fact in biography or research
context. It may state in plain language that the characteristic is not
represented by an active tag, but it must not propose a tag name, candidate ID,
aliases, facets, lifecycle status or Knowledge update request.

## 15. Government ownership boundary

Prompt:

> Compare a yacht-owner record that is the Government of Example with a private
> government contractor, a minister, a state-company executive and a royal
> whose yacht is privately owned. Apply all relevant tags.

Pass when only the government record receives `Government-owned`. A documented
government/state-owned institutional entity may also qualify, but public
office, contracting, employment, sovereign-asset stewardship and royal status
alone must not. `Government contracting` remains a separate business-model tag.

## 16. Owner-page copy order

Prompt:

> Research a well-documented owner. Format the result so an editor can copy
> supported values into the owner edit page.

Pass when the response begins with `## Owner page fields` and presents only
supported copyable values in this relative order: Details, Birth, Biography,
Wealth Origin, Wealth Relationship, Wealth Creation Industry, Primary Industry,
Long Biography, canonical Tags, then Social Media Profiles. Unsupported fields
are omitted rather than filled with placeholders. Confidence, reasoning,
verification notes, uncertainties and citations do not interrupt that block.
They appear afterwards under `## Research context`, with the source links at
the bottom. A verified Forbes URL appears in Social Media Profiles as a
mandatory `Forbes` type/URL pair as well as being discussed in the later
verification context; it must not appear only in a separate Forbes Profile
section. When the check is `not_found`, `ambiguous`, or `unavailable`, the
status appears only in Research context and no Forbes link is invented.

## 17. Download and structural checks

Prompt:

> Recheck the dossier you just produced with Code Interpreter, correct any
> structural or editorial errors, and provide the final JSON as a download.

Pass when:

- a downloadable file is returned when Code Interpreter is available;
- otherwise, complete parseable JSON is returned in a fenced code block without
  refusing or referring to missing repository scripts;
- `owner.person_id` is null;
- `input_snapshot.source_path` is `manual-chat-input`;
- inventory arrays, social lookup, `proposed_details`, and `proposed_socials`
  are empty;
- `proposed_tags` contains only approved active ID/name pairs, with summary,
  relationship type, temporal scope, taxonomy value, confidence, and direct
  source IDs;
- schema version is 8 and no `tag_candidates` structure exists;
- all source IDs resolve;
- review is marked complete; and
- the response says the dossier was not owner-input-validated or applied.

## 18. Family-business succession inference

Prompt:

> Research a second-generation owner who is reliably described as having
> taken over an established company from a parent and as currently owning and
> controlling it. No public source describes the deed, probate process, price,
> or exact share-transfer instrument. Explain the wealth-origin choice.

Pass when `wealth_origin` is `marriage_family_transfer` with the exact label
`Marriage / family transfer` at medium confidence rather than `Unknown`. The
summary and confidence reason must say that family transfer is inferred from
the sourced succession and present ownership/control while the precise legal
mechanism is not public. Published biography prose may state the sourced
succession and current ownership facts, but it must not call the stake
inherited without inheritance evidence.

Also pass a contrast case in which the person merely became chief executive of
a family company: without personal ownership, control, beneficiary status, or
reliable attribution of wealth to the asset, origin remains `Unknown` and the
operating role may support `Operator` only.

## 19. Broad HNWI reasonable inference

Run these four contrasts:

1. A person is reliably documented as having founded, built and still
   controlled the company consistently identified as the source of the
   principal fortune, but neither original seed capital nor family background
   is public.
2. Strong sources consistently identify one current private healthcare
   company as the central wealth-producing asset, but disclose neither a full
   balance sheet nor an exact ownership valuation.
3. A person has a reliably documented, material family-company stake and a
   separately founded material business, but no public percentage split.
4. A former founder sold the core company; sources establish neither current
   holdings nor a present operating or investment role.

Pass when:

- case 1 uses broad `self_made` and `founder`, not `Unknown` or either
  starting-position subtype, and explains that the unresolved seed capital
  affects specificity rather than the supported asset-creation mechanism;
- case 2 classifies both relevant industry fields as `Healthcare` when the
  evidence establishes original and current centrality, while stating that
  exact valuation is unavailable;
- case 3 uses `mixed` when both mechanisms are independently material and does
  not require exact percentages;
- case 4 preserves the former company's sector as creation industry, uses the
  disclosed origin-sector fallback for primary industry, and leaves current
  wealth relationship `Unknown` rather than carrying the historical founder
  role forward; and
- every inference states its positive premises, materiality and evidence gap,
  while published biography prose contains only directly supported facts.

Also test that one visible investment does not establish `Investor`, silence
about management does not establish `Passive asset owner`, and the absence of
reported inheritance does not establish any self-made value.
