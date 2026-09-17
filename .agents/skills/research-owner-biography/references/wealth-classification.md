# Wealth classification

## Purpose

Describe four separate aspects of an owner's wealth:

- `wealth_creation_industry`: the economic sector principally responsible for
  creating the original fortune;
- `primary_industry`: the economic sector that principally underpins the
  person's current identifiable private wealth;
- `wealth_origin`: how the person acquired or gained access to that wealth;
- `wealth_relationship`: the person's principal relationship to the
  wealth-producing assets.

Assess the industries separately, then use the origin-sector fallback below if
current interests cannot be classified. A technology founder who now principally
manages a diversified investment portfolio can have `Technology` as a wealth
creation industry, `Finance & Investments` as a primary industry, `Self-made`
as an origin, and `Family office principal` as a relationship.

## Output shape

Every dossier must contain all four objects:

```json
{
  "wealth_creation_industry": {
    "classification": "food_beverage",
    "label": "Food & Beverage",
    "summary": "The family fortune was created through a confectionery and pet-care company.",
    "confidence": {
      "score": 96,
      "band": "very_high",
      "reason": "The company history and a current Forbes profile identify the businesses that created the family fortune."
    },
    "source_ids": ["S1", "S2"]
  },
  "primary_industry": {
    "classification": "food_beverage",
    "label": "Food & Beverage",
    "summary": "The inherited stake is in a confectionery and pet-care company.",
    "confidence": {
      "score": 96,
      "band": "very_high",
      "reason": "The company and a current Forbes profile identify the businesses."
    },
    "source_ids": ["S1", "S2"]
  },
  "wealth_origin": {
    "classification": "inherited",
    "label": "Inherited",
    "summary": "She inherited her family-company stake from her father.",
    "confidence": {
      "score": 96,
      "band": "very_high",
      "reason": "The inheritance and resulting stake are directly documented."
    },
    "source_ids": ["S1"]
  },
  "wealth_relationship": {
    "classification": "heir_family_shareholder",
    "label": "Heir / family shareholder",
    "summary": "She is a family shareholder and board member rather than the day-to-day operator.",
    "confidence": {
      "score": 95,
      "band": "very_high",
      "reason": "Current sources document both the shareholding and board role."
    },
    "source_ids": ["S1", "S2"]
  }
}
```

`classification` is the stable machine value. `label` is the exact value to
show to reviewers and, when the corresponding website field exists, write to
the select control. The validator requires the two to match.

Use a non-`unknown` classification only at confidence 70 or higher. Below that
threshold, emit `unknown`, explain what could and could not be established, and
put any plausible alternative in `candidates_requiring_review`.

## Shared industry values

Both `wealth_creation_industry` and `primary_industry` use this dictionary.
The core values follow the Forbes wealth-list industry taxonomy. Five
yacht-owner-relevant extensions make maritime, aviation, hospitality, and
agricultural fortunes more informative than a broad fallback, while
cryptocurrency distinguishes crypto-created wealth from traditional finance.

| Classification | Label |
| --- | --- |
| `automotive` | Automotive |
| `construction_engineering` | Construction & Engineering |
| `cryptocurrency` | Cryptocurrency |
| `diversified` | Diversified |
| `energy` | Energy |
| `fashion_retail` | Fashion & Retail |
| `finance_investments` | Finance & Investments |
| `food_beverage` | Food & Beverage |
| `gambling_casinos` | Gambling & Casinos |
| `healthcare` | Healthcare |
| `logistics` | Logistics |
| `manufacturing` | Manufacturing |
| `media_entertainment` | Media & Entertainment |
| `metals_mining` | Metals & Mining |
| `real_estate` | Real Estate |
| `service` | Service |
| `sports` | Sports |
| `technology` | Technology |
| `telecom` | Telecom |
| `shipping_maritime` | Shipping & Maritime |
| `aviation_aerospace` | Aviation & Aerospace |
| `hospitality` | Hospitality |
| `agriculture` | Agriculture |
| `unknown` | Unknown |

Apply these shared rules:

1. Classify evidenced private wealth, not a person's public office, yacht,
   hobby, first job, or unsupported reputation.
2. For inherited wealth, follow the underlying operating assets. Inheritance
   changes `wealth_origin`, not either industry classification.
3. Use `cryptocurrency` when cryptocurrency holdings or a crypto-native
   enterprise principally created the fortune or currently principally
   underpins it, according to the field being classified. Later crypto
   investment, advocacy, or participation does not by itself make
   `wealth_creation_industry` Cryptocurrency.
4. Use `diversified` only when several unrelated sectors make material
   contributions and no sector is demonstrably dominant. Do not use it merely
   because evidence is incomplete.
5. Prefer a specific extension over `service` when the evidence supports it.
   Use `shipping_maritime` for shipping lines and principally maritime
   businesses; `logistics` for broader freight, delivery, and supply-chain
   businesses; and `manufacturing` for shipbuilding.
6. Use `unknown` when the sector cannot be established reliably.

### Wealth creation industry

Classify the sector principally responsible for creating the original fortune:

1. Identify the business, asset, investment activity, or inherited operating
   assets that first produced the principal fortune. This is not necessarily
   the person's first employment or earliest commercial activity.
2. Keep the classification durable when proceeds are sold, reinvested, or
   diversified. Change it only when stronger evidence corrects the origin
   story.
3. For inherited or transferred wealth, classify the sector that created the
   transferred family fortune or principally underpinned the received assets.
4. Use `cryptocurrency` only when reliable evidence establishes that
   cryptocurrency appreciation or a crypto-native enterprise principally
   created the fortune. The biography may state the evidenced mechanism, such
   as early Bitcoin investment or founding an exchange; the classification
   remains the broad Cryptocurrency label.

### Primary industry

Classify the sector that currently best describes the person's principal
identifiable private business or wealth-producing interests:

1. Use the largest identifiable share of current private wealth, not merely
   the person's occupation or best-known former company.
2. Reassess this field as of the research date because dominant holdings and
   operating interests can change.
3. It may differ from `wealth_creation_industry` after a sale, reinvestment,
   or diversification.
4. If the current principal sector remains unknown after research but
   `wealth_creation_industry` is known, use that same sector and label for
   `primary_industry`. This is a reporting fallback, not evidence that the
   original business or industry still dominates current private wealth.
   Explain the missing current evidence and the fallback explicitly in the
   primary summary and confidence reason. Cite the origin-sector sources,
   score the fallback conservatively (at least 70 and no higher than the
   origin-sector score), and leave `wealth_origin` and `wealth_relationship`
   to their separately evidenced classifications. If the origin sector is
   also unknown, retain `primary_industry=unknown`; never turn a known
   `wealth_origin` mechanism such as inheritance into an industry label.

## Wealth-origin values

| Classification | Label | Definition |
| --- | --- | --- |
| `self_made` | Self-made | Founded, built, bought, or earned the principal fortune without inheriting the core wealth-producing assets, but reliable evidence does not distinguish the person's starting position more precisely. |
| `self_made_independent` | Self-made — independent start | Built the principal fortune without inheriting the core assets and without a substantial family-wealth or family-business platform materially enabling the launch. This does not require poverty or exclude education, employment experience, ordinary family support, or commercial finance obtained on ordinary terms. |
| `self_made_advantaged` | Self-made — advantaged start | Built and owns the principal wealth-producing asset without inheriting it, but began with a substantial advantage from family wealth, status, industry access, business experience, networks, mentoring, financial security, or a comparable platform. |
| `inherited` | Inherited | Inherited the principal stake or assets and has not demonstrably transformed their scale through personal operating activity. |
| `inherited_and_expanded` | Inherited and expanded | Inherited the core assets and subsequently made a well-documented, material contribution to expanding or transforming them. Passive appreciation is not enough. |
| `dynastic_royal` | Dynastic / royal | Access to the relevant personal or family wealth principally follows royal or ruling-family lineage. |
| `marriage_family_transfer` | Marriage / family transfer | Received the principal assets through marriage, divorce settlement, inter vivos family transfer, or a comparable family mechanism other than inheritance. |
| `mixed` | Mixed | Two or more materially important origin mechanisms apply and none adequately describes the fortune alone. |
| `unknown` | Unknown | Reliable public evidence does not establish how the wealth arose. |

Describe the mechanism in `summary`: for example, founded company, inherited
stake, property development, investment career, resource concession, marriage
settlement, or royal-family allocation. Never substitute a net-worth estimate
for the mechanism.

### Self-made starting position

The self-made classifications answer two questions together: whether the
person created the principal wealth-producing asset, and what starting
platform materially shaped that achievement. They are not moral rankings.
`Self-made — advantaged start` recognises a separately built success while
making its formative context visible.

Apply these rules:

1. Use `self_made_independent` only when strong evidence supports both the
   founder-built mechanism and a materially independent launch. Do not treat
   personally earned education, employment experience, savings, or ordinary
   commercial borrowing as inherited advantage.
2. Use `self_made_advantaged` when a wealthy, prominent, or industry-connected
   family supplied a material head start through relevant exposure, mentoring,
   networks, security, reputation, access, or opportunity. Direct seed capital
   is not required when the wider platform is well established.
3. Use the broader `self_made` value when the core asset was demonstrably
   created by the person but reliable sources do not establish the starting
   position well enough to choose either subtype. Do not infer an independent
   start merely because no inheritance was found.
4. Do not use `self_made_advantaged` to conceal a material transfer of the
   principal stake, assets, or launch capital. Use `marriage_family_transfer`,
   `mixed`, `inherited`, or `inherited_and_expanded` when the transferred
   component is itself a principal origin mechanism.
5. State the advantage neutrally in the summary and preserve the person's own
   achievement. A useful formulation distinguishes the family platform from
   the separately founded or acquired asset.

## Wealth-relationship values

Choose the relationship that best describes how the person currently relates
to the principal wealth-producing assets.

| Classification | Label | Definition |
| --- | --- | --- |
| `founder` | Founder | Created the core enterprise or platform that produced the wealth. |
| `operator` | Operator | Currently or materially ran the core business but did not found it; this includes active successors. |
| `investor` | Investor | Principally creates or manages wealth through allocation of investment capital. |
| `heir_family_shareholder` | Heir / family shareholder | Holds an inherited or family stake without being the principal day-to-day operator. A board seat alone does not make the person an operator. |
| `family_office_principal` | Family office principal | Directs or represents a family investment office or holding structure rather than an operating company. |
| `royal_beneficiary` | Royal beneficiary | Receives or controls personal benefits or assets principally through royal-family position, without a better evidenced operating relationship. |
| `trustee_custodian` | Trustee or custodian | Oversees assets for a trust, crown, nation, or others and does not personally own them in the ordinary sense. |
| `passive_asset_owner` | Passive asset owner | Owns the principal assets but has no evidenced active management role and is not better described as an heir. |
| `unknown` | Unknown | Reliable public evidence does not establish the person's relationship to the assets. |

Use the primary relationship only. Mention other material roles in the summary
or biography. For example, a founder who later became an investor remains
`Founder` when the founded company is still the principal source of wealth.

## Royal and dynastic wealth

Do not label a ruler `Energy` merely because the state produces oil or gas.
Separate personal and family assets from state, sovereign-wealth-fund, crown,
and office-held assets:

1. Classify only assets that strong evidence identifies as personally or
   privately held by the person or family.
2. Do not treat assets controlled in an official, custodial, or sovereign
   capacity as personal property.
3. Use `dynastic_royal` for the origin when lineage or ruling-family position
   principally explains access to the relevant wealth.
4. Use the evidenced private sector for each industry field, such as
   `real_estate`, `hospitality`, `finance_investments`, or `diversified`.
   `wealth_creation_industry` requires evidence for the sector that created
   the relevant private family fortune. For `primary_industry`, use evidence
   of current private interests when available; otherwise use that verified
   private origin sector as the disclosed fallback.
5. Use `energy` only when private oil, gas, power, or related holdings
   demonstrably underpin the person's private wealth.
6. When no private sector can be separated reliably from state or royal
   assets, use `unknown` for both industries and explain the opacity. Do not
   substitute `diversified` or `energy` as a guess.
7. Use `trustee_custodian` when the evidence establishes stewardship without
   personal ownership; use `royal_beneficiary` when personal benefit follows
   royal status and no better operating relationship is supported.

## Examples

| Case | Wealth creation industry | Primary industry | Wealth origin | Wealth relationship |
| --- | --- | --- | --- | --- |
| Marijke Mars | Food & Beverage | Food & Beverage | Inherited | Heir / family shareholder |
| Manufacturer whose original fortune is documented but whose current private holdings cannot be ranked; disclose the primary fallback in its reasoning | Manufacturing | Manufacturing | Self-made | Unknown |
| Early Bitcoin investor whose current holdings span unrelated sectors and whose starting position is unclear | Cryptocurrency | Diversified | Self-made | Investor |
| Traditional financier who later becomes active in crypto and built the career without a material family platform | Finance & Investments | Cryptocurrency or Finance & Investments, according to current evidence | Self-made — independent start | Investor |
| Shahid Khan, who built an automotive supplier after arriving in the United States as a student | Automotive | Automotive | Self-made — independent start | Founder |
| Founder of a separate property company who grew up in a billionaire property-development family | Real Estate | Real Estate | Self-made — advantaged start | Founder |
| Technology founder now principally directing an investment office | Technology | Finance & Investments | Self-made | Family office principal |
| Active successor who substantially expands an inherited property company | Real Estate | Real Estate | Inherited and expanded | Operator |
| Royal with documented private hotels and no larger private sector holding | Hospitality or Unknown, according to origin evidence | Hospitality | Dynastic / royal | Royal beneficiary or Operator, according to the evidence |
| Royal whose only apparent connection to oil is governing an oil-producing state | Unknown | Unknown | Dynastic / royal | Royal beneficiary or Unknown |
| Monarch overseeing crown assets that cannot be personally sold | Unknown | Unknown | Dynastic / royal | Trustee or custodian |

## Mapping to owner details

Always populate the four dossier objects, even if the website does not yet
expose equivalent editable fields.

When `wealth_creation_industry`, `primary_industry`, `wealth_origin`, or
`wealth_relationship` exists in the source owner's `details`:

- propose the exact `label`, never the machine `classification`;
- use `action=fill_missing` when the field is blank;
- use `action=correct_existing` only when strong evidence demonstrates the
  existing value is wrong and include `existing_value`;
- use the same confidence and source IDs as the corresponding classification;
- do not propose `Unknown` as a website value unless the website explicitly
  supports it and the reviewer wants unknowns stored.

If a field is not present in the source owner document, do not invent a
`proposed_details` entry. The compiled `ai_research` metadata will retain the
classification until the system field becomes available.
