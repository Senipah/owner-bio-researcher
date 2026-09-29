# Custom GPT setup: Yacht Owner Biography Researcher

This directory packages the canonical `research-owner-biography` workflow for
one-off, name-and-context research in a Custom GPT. It is a distribution of the
existing skill, not a second source of truth.

## End-user experience

The person using the finished GPT does not run repository commands, read these
files, or configure a dossier. They enter an owner name:

> Mark Zuckerberg

or add optional identity context:

> Mark Zucherberg, Facebook founder

The GPT corrects an obvious spelling variation when the context is
unambiguous, resolves the identity, researches public sources, and returns an
`Owner page fields` block first. It contains only supported copyable values in
the site's order: Details, Birth, Biography, Wealth, Long Biography, Tags, and
Social Media Profiles. A separate `Research context` section then returns:

- supported personal details such as date of birth, birthplace, nationality,
  residence, gender, mortality status, and a concise known-for title;
- an explicit Forbes result;
- wealth-creation industry, current primary industry, wealth origin, and
  wealth relationship;
- verified personal social profiles and relevant official websites;
- the 50–55 word short biography and 90–190 word two-paragraph profile;
- confidence, sources, unresolved questions, and limitations; and
- a minimal set of approved active canonical tags; and
- optional schema-v8 JSON when explicitly requested.

When the Forbes check is `verified`, Social Media Profiles always contains a
`Forbes` row with the exact profile URL. The later context still states the
verification result. `not_found`, `ambiguous`, and `unavailable` produce a
context status but no invented social link.

Only genuinely ambiguous names require a focused follow-up question.
Ordinary responses never discuss repository scripts, schema resources, or
internal validation requirements.

OpenAI recommends putting behaviour and workflow in GPT Instructions and using
uploaded Knowledge for reference material. The package follows that split:

- paste [`instructions.md`](instructions.md) into the GPT's Instructions;
- upload [`owner-biography-knowledge.md`](owner-biography-knowledge.md) and
  [`tag-catalogue.json`](tag-catalogue.json) as its two Knowledge files; and
- use [`preview-tests.md`](preview-tests.md) before sharing or relying on an
  updated version.

## Builder configuration

Configure the GPT directly in the web GPT editor.

- **Name:** `Yacht Owner Biography Researcher`
- **Description:** `Researches one yacht owner from public sources and returns supported personal details, verified links, wealth classifications, complementary biographies, confidence and sources.`
- **Recommended model:** choose the strongest web-search-capable model
  available in the workspace; do not pin a model name in this repository.
- **Web Search:** on
- **Code Interpreter & Data Analysis:** optional; useful for downloadable JSON
  when requested, but not required for normal research
- **Image generation:** off
- **Canvas:** off
- **Apps:** off
- **Actions:** none
- **Sharing:** private or restricted to the intended workspace

Add these conversation starters:

1. `Mark Zuckerberg`
2. `Shahid Khan, Flex-N-Gate owner`
3. `Research this owner and return verified social links, personal details and both biographies.`
4. `Check whether this owner name represents a person or an institution, then complete the appropriate research.`

## One-time GPT creator setup

These steps are performed once by the person creating or updating the Custom
GPT. End users do not perform them.

1. Open the GPT editor in ChatGPT on the web.
2. Copy the complete contents of `instructions.md` into **Instructions**.
3. Upload the already generated `owner-biography-knowledge.md` and
   `tag-catalogue.json` under **Knowledge**.
4. Apply the configuration above.
5. Run every required scenario in `preview-tests.md`.
6. Keep the GPT private or workspace-restricted unless a separate public
   publishing review is completed.

Do not upload owner exports, generated dossiers, credentials, authenticated
cookies, or other owner-specific working data as persistent Knowledge. Supply
the owner's name and identity context in the individual conversation.

## Routine use

Open the finished GPT and enter the owner's name. Additional context is
optional:

```text
Mark Zuckerberg
```

```text
Mark Zucherberg, Facebook founder
```

```text
Shahid Khan, Flex-N-Gate owner
```

The GPT searches first and proceeds automatically when one identity is strongly
supported. It asks for company, role, geography, family context, or another
disambiguator only when multiple plausible people remain.

The GPT returns the complete human-readable profile by default. Copyable values
come first in owner-page order; confidence, reasoning, verification context,
uncertainties, and sources come afterwards. The user does not need to ask
separately for personal details, social links, classifications, or biographies.
It creates a schema-v8 manual dossier only when the user explicitly
asks for JSON or a dossier. That optional dossier is not owner-input-validated
or compilation-ready.

The uploaded active catalogue is a closed-world whitelist for literal
assignments. The GPT resolves approved aliases to canonical active IDs and
assigns no tag when none fits. It never invents a tag, emits a formal candidate
or requests catalogue creation during ordinary owner research. Important
unrepresented facts remain in biography or research context; an optional
plain-language gap observation is not a taxonomy proposal.

The example in [`manual-dossier.example.json`](manual-dossier.example.json)
is maintainer documentation for that optional contract; do not upload it as
Knowledge. A maintainer may validate a downloaded dossier locally without
`--owner-input`:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  PATH_TO_DOSSIER `
  --strict-editorial
```

Passing this command proves structural and editorial validity only. It does not
compare the dossier with an owner export.

## Updating the package

This section is for repository maintainers, not GPT users. The canonical
governance policy, four supporting reference files and
`config/owner-tags.json` remain authoritative. After a globally approved
catalogue change, deduplicate it against every lifecycle state, add or promote
the canonical repo tag with its human approval reference,
rebuild both GPT Knowledge files and run:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\build_gpt_knowledge.py `
  --check

.\venv\Scripts\python.exe -m pytest -q tests\test_gpt_bundle.py
```

Then update the GPT draft, replace the Knowledge upload, rerun Preview tests,
and use GPT version history to retain a rollback point.

## Privacy and retention

Custom GPT Knowledge files remain associated with the GPT until it is deleted.
For consumer plans, whether conversations and uploaded content may be used to
improve models depends on the account's Data Controls. Business, Enterprise,
and Edu workspaces have different defaults and may impose additional sharing
or capability restrictions. Review the current official OpenAI guidance before
adding non-public material:

- [Creating and editing GPTs](https://help.openai.com/en/articles/8554397-creating-a-gpt)
- [GPTs in ChatGPT](https://help.openai.com/en/articles/8554407-gpts-faq)
- [Chat and file retention policies](https://help.openai.com/en/articles/8983778/chat-and-file-retention-policies-in-chatgpt)
- [Troubleshooting GPTs](https://help.openai.com/en/articles/11325361-troubleshooting-gpts)
