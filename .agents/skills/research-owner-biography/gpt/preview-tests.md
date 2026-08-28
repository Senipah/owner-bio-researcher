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

Pass when `Apple` is included once with its canonical local ID, evidence,
materiality summary, and confidence if the wealth and family history supports
it. The GPT must not omit it because it is a one-record tail, and must not infer
unrelated family or company tags from surname alone.

## 13. Gambling and video-game disambiguation

Prompt:

> Research one owner whose fortune came from casino gaming and another whose
> fortune came from a video-game publisher. Apply all relevant tags.

Pass when casino gaming resolves to `Gambling` (including when described as
`Gaming`) and never to `Video games`; the publisher resolves to `Video games`
only with explicit interactive-entertainment evidence. Neither result may use
`Family office` or a generic philanthropy-domain tag.

## 14. Open-world tag discovery

Prompt:

> During a future owner research run, strong sources establish a durable,
> material subindustry that meets the taxonomy rule but is absent from the
> uploaded tag catalogue. Explain and show how you handle the tag.

Pass when the GPT does not omit the tag or invent an ID. It first checks for a
reasonable semantic alias; if the concept is genuinely distinct, it returns a
source-supported proposal with `tag_id: null`, labels it **New catalogue
candidate**, and explicitly says the uploaded `tag-catalogue.json` Knowledge
must be updated before a canonical ID or compilation-ready dossier is possible.

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
- `proposed_tags` contains all applicable tags with ID/name pairs (or a null ID
  when genuinely unknown), summary, confidence, and direct source IDs;
- all source IDs resolve;
- review is marked complete; and
- the response says the dossier was not owner-input-validated or applied.
