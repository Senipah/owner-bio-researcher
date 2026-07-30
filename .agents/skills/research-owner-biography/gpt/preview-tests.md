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
confidence, and a downloadable manual dossier.

## 2. Misspelt name with disambiguator

Prompt:

> Mark Zucherberg, Facebook founder

Pass when the GPT identifies the intended person as Mark Zuckerberg, states
that correction, and completes the research without an unnecessary follow-up.

## 3. Well-documented yacht owner

Prompt:

> Research Shahid Khan, the Flex-N-Gate owner associated with the Jacksonville
> Jaguars. Produce the complete manual dossier and review summary.

Pass when:

- identity is resolved before drafting;
- Forbes is explicitly checked;
- all four wealth classifications use exact labels and supported confidence;
- the two biographies are complementary and meet their length and paragraph
  contracts;
- a downloadable JSON dossier is returned; and
- the manual-validation limitation is stated.

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

## 10. Download and structural checks

Prompt:

> Recheck the dossier you just produced with Code Interpreter, correct any
> structural or editorial errors, and provide the final JSON as a download.

Pass when:

- the file parses as JSON;
- `owner.person_id` is null;
- `input_snapshot.source_path` is `manual-chat-input`;
- inventory arrays, social lookup, and both proposal arrays are empty;
- all source IDs resolve;
- review remains pending; and
- the response says the dossier was not owner-input-validated or applied.
