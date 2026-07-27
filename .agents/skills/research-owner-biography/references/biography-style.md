# Biography style

## Two biography outputs

Every dossier contains two standalone biographies:

- `biography`: a short identity card of 50-55 words in one paragraph;
- `long_biography`: a concise profile of 90-190 words in exactly two
  paragraphs, preferably 120-170 words.

The longer version must stand alone. It may overlap the short biography's core
facts, but it must not repeat the short text verbatim and must add a meaningful
narrative layer. For a sparse public record, write 90-119 strong words rather
than padding to the preferred range.

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

## Longer biography

Answer four questions:

1. Who is this person?
2. How did they reach their position?
3. What turning point, working style, or well-sourced detail distinguishes
   them?
4. What relevant later chapter or yachting connection completes the profile?

Use two short paragraphs:

- Paragraph one covers identity, background, the wealth mechanism, and an
  important turning point or development.
- Paragraph two adds one or two layers of character colour: a later business
  chapter, investment, public role, philanthropy, sport, or meaningful yachting
  background.

Useful character colour explains or makes the person memorable. Examples
include an unusual route into an industry, a formative early job, an invention,
a calculated acquisition, a documented hands-on role, or a sustained interest
that became a serious investment or philanthropic programme.

Use trivia sparingly. Include it only when it illuminates the person's path or
character rather than merely being surprising.

## Yachting context

Do not append a yacht name to every biography. The vessel relationship is
already available elsewhere in the system.

Include yachting only when reliable sources establish a meaningful story, such
as:

- a long history of ownership or several successive commissions;
- material involvement in a yacht's design or construction;
- competitive sailing or regatta participation;
- exploration, research, or philanthropy conducted through a yacht;
- a commission that materially influenced yacht design;
- another documented personal connection to the sea.

Do not infer personality, intended use, design involvement, or lifestyle from
ownership alone. If there is no meaningful and sourced yachting angle, omit it.

## Voice

- Use neutral third-person prose.
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

Prefer causality:

> engineering training -> bumper design -> Bumper Works -> Flex-N-Gate -> sports

Avoid inventories:

> billionaire, worth $X, ranked #Y, owns A/B/C/D

## Exclusions

Neither biography should become a compressed Wikipedia article. Avoid:

- a year-by-year chronology;
- lists of every company, asset, office, relative, or yacht;
- repeated yacht specifications;
- generic praise or reputation claims without strong evidence;
- gossip and weakly sourced personality claims;
- private family information that does not explain the public story;
- controversies merely because they dominate search results;
- padding added to meet a target length.

As a rule of thumb, use no more than two dates and very few financial figures
in the longer biography.

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

## Shahid Khan calibration

Preferred short biography:

> Shahid "Shad" Khan is a Pakistani-born American industrialist who built his
> fortune in automotive manufacturing. After moving to Illinois as a teenager
> and studying engineering, he developed a one-piece truck bumper, founded
> Bumper Works and acquired Flex-N-Gate. He subsequently expanded into sport
> through the Jacksonville Jaguars, Fulham F.C. and All Elite Wrestling.

Preferred longer biography:

> Shahid "Shad" Khan was born in Lahore and moved to the United States as a
> teenager to study industrial engineering at the University of Illinois.
> While working for automotive-parts manufacturer Flex-N-Gate, he developed a
> one-piece truck bumper designed to resist corrosion. Khan founded Bumper
> Works to manufacture the design and, in 1980, bought Flex-N-Gate from his
> former employer, building it into a global automotive supplier.
>
> His later investments have centred on sport and entertainment. He acquired
> the Jacksonville Jaguars in 2012, becoming the NFL's first ethnic-minority
> team owner, and later bought Fulham F.C. in London. Through his son Tony, the
> family also backs All Elite Wrestling. These holdings broadened his public
> profile, but the underlying fortune remains rooted in automotive
> manufacturing and the combination of engineering, product development and
> acquisition that transformed a small supplier into an international
> business.

Why they work:

- both lead with identity rather than net worth;
- the short version captures the complete arc in 53 words;
- the longer version explains the formative route and pivotal acquisition;
- sport is treated as a later chapter rather than the source of wealth;
- neither becomes a chronology or inventory.

Avoid:

> Shahid Khan is a $15 billion billionaire and one of the world's richest
> sports owners, ranked by Forbes...

That version is stat-heavy and does not explain where the position came from.
