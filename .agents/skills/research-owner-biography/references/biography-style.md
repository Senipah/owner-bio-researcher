# Biography style

## Target

Write a compact background paragraph: closer to a character-lore card than a
financial fact sheet. Aim for 55-90 words; never exceed 110 words.

## Content order

1. Identify the person by nationality/background and main role.
2. Explain the origin of wealth or prominence in concrete terms.
3. Add one later chapter—major holdings, public role, or distinctive context.

Prefer causality:

> engineering training → bumper design → Bumper Works → Flex-N-Gate → sports

Avoid inventories:

> billionaire, worth $X, ranked #Y, owns A/B/C/D

## Voice

- Use one neutral third-person paragraph.
- Be confident but not promotional.
- Prefer active, concrete verbs: founded, inherited, acquired, expanded,
  designed, developed, invested.
- Use “self-made” only when supported; otherwise describe the mechanism.
- Treat “oligarch” and similar labels cautiously. Prefer the sourced industrial
  route, such as “built his fortune through metals assets acquired during...”.
- Avoid “visionary”, “iconic”, “renowned”, “legendary”, and other puffery.
- Avoid moral judgment and speculation about motives or personality.
- Omit current net worth unless it is essential to distinguish the person.
- Omit the yacht unless it materially resolves identity or the user requests it.
- Do not include citations inside the biography; keep them in the dossier.

## HTML

Store exactly one CKEditor paragraph:

```html
<p>Biography text.</p>
```

The JSON string must end with `\r\n` after `</p>`. Escape `&`, `<`, and `>` in
the HTML while preserving ordinary punctuation in `plain_text`.

## Shahid Khan calibration

Preferred:

> Shahid “Shad” Khan is a Pakistani-born American industrialist who built his
> fortune in automotive manufacturing. After moving to Illinois as a teenager
> and studying engineering, he developed a one-piece truck bumper, founded
> Bumper Works and later bought his former employer, Flex-N-Gate, expanding it
> into a global supplier. He subsequently moved into sport as owner of the
> Jacksonville Jaguars and Fulham F.C., and as a backer of All Elite Wrestling.

Why it works:

- leads with identity rather than net worth;
- describes the mechanism behind the fortune;
- gives a short career arc;
- treats sports ownership as the later chapter;
- stays factual, compact, and unembellished.

Avoid:

> Shahid Khan is a $15 billion billionaire and one of the world’s richest
> sports owners, ranked by Forbes...

That version is stat-heavy and does not explain where the position came from.
