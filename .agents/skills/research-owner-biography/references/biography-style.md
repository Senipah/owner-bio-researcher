# Biography style

## Two biography outputs

Every `record_type=person` dossier contains two standalone biographies:

- `biography`: a short identity card of 50-55 words in one paragraph;
- `long_biography`: a concise profile of 90-190 words in exactly two
  paragraphs.

The longer version must stand alone. It may share essential identity and
wealth-origin anchors with the short biography, but it must not repeat,
reorder, or paraphrase the short version's complete fact bundle. It must add a
meaningful narrative layer. Do not target the midpoint of the permitted range.
For a sparse public record, stop at 90-119 strong words rather than padding.

Institutions and unresolved placeholders do not receive biographies. They use
the schema-v6 `editorial_note` path described in the research contract.

## Editorial separation

Research and publication are separate passes:

1. Complete identity, source, social, and wealth research.
2. Build the schema-v6 `biography_brief` as an unordered fact pool, including
   at least two genuinely different opening angles.
3. Exclude source publishers, confidence language, wealth-taxonomy
   deliberation, current vessel data, rankings, and transient figures from the
   writing brief.
4. Allocate facts between shared anchors, short-only material and long-only
   material before drafting.
5. Select an opening mode and narrative shape deliberately. Do not draft in
   brief-field order.
6. Draft each biography from its allocation and the calibration set.
7. Review the two texts as a pair, then reverse-check every material claim
   against the full source ledger.

The published prose must not reveal that a researcher searched sources,
resolved a database record, assigned classifications, or evaluated confidence.
Do not write “Forbes identifies”, “Reuters reports”, “available evidence”,
“records show”, “supports a classification”, or similar research narration.
Those details belong in the dossier metadata.

## Short-long independence

Use a working allocation before drafting. It is editorial scratch material and
does not become part of the schema-v6 dossier:

| Bucket | Requirement |
| --- | --- |
| Shared anchors | No more than two facts essential to both standalone texts |
| Short-only | At least one fact or dimension |
| Long-only | At least two substantive facts or dimensions |
| Deliberate omissions | Short-biography material the long profile will not repeat |

Names, a durable identity and one core wealth-or-prominence mechanism may be
shared when needed for orientation. A date, example or extra adjective attached
to a repeated claim is not a new fact. Reordering the short biography's
identity, origin and final contextual dimension across two paragraphs is still
an expanded short biography.

The long profile should answer a different editorial question. It may explain
how a decisive choice worked, show an operating method, develop a formative
episode, trace a consequence, or explore a durable public contribution. It
should not feel obliged to mention every company, role or interest selected for
the short identity card.

Before acceptance, answer:

1. What does the long profile tell the reader that the short one does not?
2. Which secondary short-biography fact has the long version deliberately
   omitted?
3. Would reducing the long profile to the short version discard meaningful
   material? If not, rewrite it.

Treat automated overlap findings as editorial diagnostics, not an invitation
to substitute synonyms. The validator removes owner-name tokens and common
words, flags near-restated sentences, and combines short-content containment
with shared three-word phrases. Fix the fact allocation rather than wording
around the same claims.

The deterministic guardrails are deliberately conservative:

- sentence content similarity of 85% or more is an error; 65% or more is a
  warning;
- short-content containment of 70% or more combined with at least eight shared
  three-word phrases is an error; and
- containment of 60% or more combined with at least five shared three-word
  phrases is a warning.

Strict editorial validation treats warnings as failures. These measures catch
close expansions; the required pair review remains responsible for semantic
restatement expressed with different vocabulary.

## Short biography

Answer two questions:

1. Who is this person?
2. Where did their wealth or prominence principally come from?

Use this order:

1. Identify the person by nationality/background and main role.
2. Explain the origin of wealth or prominence in concrete terms.
3. Add one major holding, public role, or distinctive context.

The result should read like a character-lore card rather than a financial fact
sheet.

Keep it to two or three sentences. Do not solve the word limit with a dense
inventory of companies, offices, charities, or investments.

## Longer biography

Cover the material needed to answer four questions, without treating them as a
required sequence:

1. Who is this person?
2. What work, institution, or decision made them consequential?
3. What turning point, working style, or well-sourced detail distinguishes
   them?
4. What enduring dimension, if any, completes the profile?

Use two short paragraphs, but do not assign a fixed function to either one.
Paragraph two may deepen the central business story through operating style,
ownership, product strategy, or a decisive acquisition. A separate investment,
public role, philanthropy, or sport belongs only when it materially
distinguishes the person; it is never a mandatory "later chapter".

Useful character colour explains or makes the person memorable. Examples
include a formative early job, an invention, a calculated acquisition, a
documented hands-on role, or a sustained interest that became a serious
investment or philanthropic programme.

Use trivia sparingly. Include it only when it illuminates the person's choices
or character rather than merely being surprising.

The first sentence must orient a reader who has not seen the short biography.
It should establish the person's defining identity, achievement, institution,
asset, consequential decision, inherited responsibility, or public
contribution. A formative episode may lead only when its relevance is
immediately clear and the detail is genuinely distinctive.

Choose among opening modes such as:

- `present_identity`: establish the person's defining current or durable role;
- `defining_achievement`: lead with the product, institution, work, or idea
  that made the person consequential;
- `decisive_event`: begin with an acquisition, decision, or change that altered
  the person's trajectory;
- `institution_or_asset`: make the central business or inherited responsibility
  the orienting subject;
- `formative_episode`: use a concrete early episode whose significance is
  apparent in the same sentence;
- `inherited_responsibility`: establish what was inherited and what the person
  did with it; or
- `public_contribution`: lead with a durable public, cultural, scientific, or
  philanthropic role when it is the clearest identity anchor.

Do not default to birth, education, or first employment. Never open by
announcing a "route", "path", "entry", "start", "career beginning",
"commercial footing", or other abstract account of how business commenced.
Those phrases expose the underlying enrichment question without orienting the
reader.

The longer biography need not repeat the short biography's wealth-origin
sentence. It may move backwards after an orienting lead, remain with the core
work across both paragraphs, or add a genuinely distinct second dimension.
End on a concrete fact, role, decision, or consequence. Do not manufacture a
unifying moral with "linking", "extending the same approach", "the arc",
"second strand", "second thread", or similar tie-back language.

Apply two tests:

1. **Orientation test:** after the first sentence, can a new reader understand
   who the person is or why the opening detail matters?
2. **Enrichment-question test:** would the opening still sound natural if no
   one had asked how the person's wealth began? If not, rewrite it.

## Vessel independence

Owners are ordered by current-vessel LOA only to prioritise research. That
ranking does not make the vessel part of the person's biography.

Apply this counterfactual before accepting either biography:

> Would the profile remain accurate, coherent, and complete if the person sold
> every current vessel tomorrow?

If not, remove the vessel material. Never mention a personally owned vessel
merely because it appears in the source record, is unusually large, was
recently delivered, was one of several successive commissions, or has a
documented builder, designer, or name. Vessel names, dimensions, builders,
delivery dates, and ownership histories belong elsewhere in the system.

The short biography must not mention a personally owned vessel. The longer
biography may describe independently significant maritime work only when it
would remain part of the person's public story without the current ownership
record. Examples include a fortune built in commercial shipping or
shipbuilding, competitive sailing, or a sustained ocean-research or
philanthropic programme. Focus on the enduring career or programme, not the
transient asset used within it.

For governments, municipalities, unresolved placeholders, and other
non-natural records, explain the institutional or identity limitation without
turning the current vessel relationship into a substitute biography.

## Voice

- Use neutral third-person prose.
- Use British English except inside official names, titles, and quotations.
- Be confident but not promotional.
- Prefer active, concrete verbs: founded, inherited, acquired, expanded,
  designed, developed, invested.
- Use "self-made" only when supported; otherwise describe the mechanism.
- Treat "oligarch" and similar labels cautiously. Prefer the sourced
  industrial history.
- Avoid "visionary", "iconic", "renowned", "legendary", and other puffery.
- Avoid moral judgment and speculation about motives or personality.
- Omit current net worth unless essential to distinguish the person.
- Do not include citations inside either biography; keep them in the dossier.
- Do not name publishers, filings, databases, or source types in the prose.
- Do not narrate confidence, evidence gaps, or the reasoning behind a wealth
  classification. State the durable established position cleanly.
- Keep public-versus-private asset distinctions in the classification metadata,
  not the biography. For opaque royal or dynastic wealth, describe the person's
  verified formation, succession, public work, interests, and influence; omit
  an uncertain commercial wealth story instead of explaining its absence.
- Never define a person through a negative taxonomy contrast such as "rather
  than commercial enterprise", "governmental rather than commercial", "not a
  documented entrepreneurial fortune", or "state assets rather than personal
  wealth". These constructions reveal the enrichment brief and sound
  formulaic even when factually careful.
- Avoid abstract narrative scaffolding such as "route into business",
  "business path began", "commercial footing", "later chapter", "the arc",
  "second strand", and "second thread". Replace it with the event, decision,
  institution, or consequence itself.
- Avoid stock conclusions such as “remains rooted in”, “broadened his public
  profile”, “best understood as”, and “the principal source of his wealth”.
- Prefer facts with a useful shelf life. Current roles may be stated, but
  current percentages, annual sales, rankings, store counts, or “latest
  filing” details require a clear narrative purpose.

Prefer causality:

> engineering training -> bumper design -> Bumper Works -> Flex-N-Gate

Avoid inventories:

> billionaire, worth $X, ranked #Y, owns A/B/C/D

## Exclusions

Neither biography should become a compressed Wikipedia article. Avoid:

- a year-by-year chronology;
- lists of every company, asset, office, relative, or yacht;
- vessel names, specifications, builders, deliveries, or ownership histories
  imported from the ranking data;
- generic praise or reputation claims without strong evidence;
- gossip and weakly sourced personality claims;
- private family information that does not explain the public story;
- controversies merely because they dominate search results;
- padding added to meet a target length.

Use no more than two explicit years and one monetary or percentage figure in
the longer biography. Keep sentences at 30 words or fewer wherever possible.
Name no more than three representative companies, investments, offices, or
institutions unless additional names are indispensable to the causal story.

## Character-colour test

A detail qualifies only when it reveals how the person worked, made a
consequential choice, developed a sustained interest, or changed direction.
Generic philanthropy lists, sports-team inventories, current asset ownership,
and surprising trivia without explanatory value do not qualify. If no strong
detail exists, write a shorter profile.

## Editorial acceptance rubric

Score each person from 1 to 5 on every dimension and revise any score below 4:

1. `causal_clarity`: the work, decision, or asset behind wealth or prominence
   is concrete.
2. `human_specificity`: at least one detail makes this person distinct without
   resorting to trivia.
3. `durability`: the profile survives vessel sales and ordinary changes in
   holdings, rankings, and annual figures.
4. `source_invisibility`: the prose contains facts, not research narration.
5. `natural_voice`: the biography does not read like a template, résumé,
   classification explanation, or AI-generated conclusion.
6. `reader_orientation`: the first sentence establishes identity or earns a
   narrative opening through an immediately relevant concrete detail.
7. `structural_independence`: the longer biography is not simply an expanded
   version of the short biography or the default
   origin-to-later-activity-to-summary template. Score 5 only when no more than
   essential anchors overlap and the long profile adds at least two
   substantive dimensions. Score 4 when unavoidable overlap remains but the
   long profile adds one substantial independent dimension. A reordered or
   paraphrased version of the same fact bundle scores 3 or below and must be
   revised.

For batches, compare the whole tranche as a publication. Revise repeated
opening modes, narrative shapes, sentence rhythms, paragraph transitions,
endings, and stock phrases. No single opening mode or narrative shape should
dominate business profiles. Run `scripts/audit_biography_corpus.py` before
compilation.

## HTML

Store the short biography as exactly one CKEditor paragraph:

```html
<p>Short biography text.</p>
```

Store the longer biography as exactly two CKEditor paragraphs:

```html
<p>First long-biography paragraph.</p>
<p>Second long-biography paragraph.</p>
```

Each closing `</p>` in the JSON string must be followed by `\r\n`. Escape `&`,
`<`, and `>` in HTML while preserving ordinary punctuation in `plain_text`.
Separate the two `long_biography.plain_text` paragraphs with exactly `\n\n`.

## Calibration set

Read [editorial-calibrations.md](editorial-calibrations.md) before drafting.
It provides distinct patterns for a founder/operator, acquirer/consolidator,
inherited operator, creative-industries founder, heir/custodian, royal,
investor/philanthropist, sparse public record, and maritime professional. Use
the set to calibrate quality and structural variation; do not imitate one
example across an entire tranche.
