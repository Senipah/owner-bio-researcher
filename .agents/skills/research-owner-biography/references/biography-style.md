# Biography style

## Two biography outputs

Every `record_type=person` dossier contains two standalone biographies:

- `biography`: a short identity card of 50-55 words in one paragraph;
- `long_biography`: a concise profile of 90-190 words in exactly two
  paragraphs.

The longer version must stand alone. It may overlap the short biography's core
facts, but it must not repeat the short text verbatim and must add a meaningful
narrative layer. Do not target the midpoint of the permitted range. For a
sparse public record, stop at 90-119 strong words rather than padding.

Institutions and unresolved placeholders do not receive biographies. They use
the schema-v5 `editorial_note` path described in the research contract.

## Editorial separation

Research and publication are separate passes:

1. Complete identity, source, social, and wealth research.
2. Build `biography_brief` from durable verified facts.
3. Exclude source publishers, confidence language, wealth-taxonomy
   deliberation, current vessel data, rankings, and transient figures from the
   writing brief.
4. Draft both biographies from that brief and the calibration set.
5. Reverse-check every material claim against the full source ledger.

The published prose must not reveal that a researcher searched sources,
resolved a database record, assigned classifications, or evaluated confidence.
Do not write “Forbes identifies”, “Reuters reports”, “available evidence”,
“records show”, “supports a classification”, or similar research narration.
Those details belong in the dossier metadata.

## Short biography

Answer two questions:

1. Who is this person?
2. Where did their wealth or prominence principally come from?

Use this order:

1. Identify the person by nationality/background and main role.
2. Explain the origin of wealth or prominence in concrete terms.
3. Add one later chapter, major holding, public role, or distinctive context.

The result should read like a character-lore card rather than a financial fact
sheet.

Keep it to two or three sentences. Do not solve the word limit with a dense
inventory of companies, offices, charities, or investments.

## Longer biography

Answer four questions:

1. Who is this person?
2. How did they reach their position?
3. What turning point, working style, or well-sourced detail distinguishes
   them?
4. What relevant later chapter completes the profile?

Use two short paragraphs:

- Paragraph one covers identity, background, the wealth mechanism, and an
  important turning point or development.
- Paragraph two adds one or two layers of character colour: a later business
  chapter, investment, public role, philanthropy, sport, or another durable
  part of the person's public story.

Useful character colour explains or makes the person memorable. Examples
include an unusual route into an industry, a formative early job, an invention,
a calculated acquisition, a documented hands-on role, or a sustained interest
that became a serious investment or philanthropic programme.

Use trivia sparingly. Include it only when it illuminates the person's path or
character rather than merely being surprising.

Do not default to birth and education. Lead with the decisive mechanism,
turning point, or formative episode when it explains the person more directly.
Paragraph two may continue the causal story, change direction, or add a
durable public role; it must not become a standard “later activities” slot.
End on a concrete insight or consequence, not a classification verdict,
research caveat, or summary of what could not be proved.

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
  industrial route.
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
- Avoid stock conclusions such as “remains rooted in”, “broadened his public
  profile”, “best understood as”, and “the principal source of his wealth”.
- Prefer facts with a useful shelf life. Current roles may be stated, but
  current percentages, annual sales, rankings, store counts, or “latest
  filing” details require a clear narrative purpose.

Prefer causality:

> engineering training -> bumper design -> Bumper Works -> Flex-N-Gate -> sports

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

1. `causal_clarity`: the route to wealth or prominence is concrete.
2. `human_specificity`: at least one detail makes this person distinct without
   resorting to trivia.
3. `durability`: the profile survives vessel sales and ordinary changes in
   holdings, rankings, and annual figures.
4. `source_invisibility`: the prose contains facts, not research narration.
5. `natural_voice`: the biography does not read like a template, résumé,
   classification explanation, or AI-generated conclusion.

For batches, compare the whole tranche as a publication. Revise repeated
openings, sentence rhythms, paragraph transitions, endings, and stock phrases.
Run `scripts/audit_biography_corpus.py` before compilation.

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
It provides distinct patterns for a founder/operator, heir/custodian, royal,
investor/philanthropist, sparse public record, and maritime professional.
Use the set to calibrate quality and variation; do not imitate one example
across an entire tranche.
