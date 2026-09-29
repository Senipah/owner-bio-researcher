# Yacht Owner Biography Researcher plugin

The maintained ChatGPT/Codex distribution for one-off name-and-context owner research. The old GPT editor/Knowledge workflow is retired; its files are preserved in [the archive](../../archive/owner-biography-gpt/ARCHIVED.md). This plugin does not access or update the live owner website.

## End-user experience

Select the installed plugin and enter a name, with optional identifying context:

> Mark Zuckerberg

> Mark Zucherberg, Facebook founder

The plugin returns the complete human-readable profile by default. Copyable values
come first in owner-page order, followed by evidence, confidence, classification
reasoning, gaps and source links. A verified Forbes result always contains a
`Forbes` row with the exact profile URL in Social Media Profiles. Other Forbes
statuses do not invent a link. A JSON dossier is produced only on request.

Web search and page reading are needed for fresh public-source verification. File creation is optional; requested JSON can be returned as a fenced code block. If tools are unavailable, state the limitations without claiming unsupported verification. End users need no repository checkout, Python, owner export or local validation scripts.

## Installation

Use the individual ZIP built by the repository maintainer. Create it through Plugin Creator in a supported host, or update the existing plugin using its verified plugin identity. Do not create a duplicate when an installed plugin already exists. Installation, hosted creation and sharing are separate steps; this source migration performs none of them.

Start a fresh conversation with the installed version and run [VALIDATION.md](VALIDATION.md), including explicit selection and ordinary matching requests. Available tools depend on the host. See [OpenAI's plugin workflow](https://learn.chatgpt.com/docs/build-plugins).

## Routine use

A name alone is enough when public evidence resolves the person. The plugin searches first and asks one focused question only when multiple plausible identities remain. It returns supported details, biographies and links, using the active catalogue as a closed-world whitelist. It never creates taxonomy candidates or writes to the owner website.

All original starters remain usable:

1. `Mark Zuckerberg`
2. `Shahid Khan, Flex-N-Gate owner`
3. `Research this owner and return verified social links, personal details and both biographies.`
4. `Check whether this owner name represents a person or an institution, then complete the appropriate research.`

The first three appear in the manifest interface, which allows at most three starter prompts.

## Updating the package

The canonical portable metadata is [plugin.json](plugin.json). Edit the manual workflow in [SKILL.md](skills/research-owner-biography/SKILL.md). Canonical research/editorial rules remain in the repository skill's references, tag policy in docs/ai/OWNER_TAG_GOVERNANCE.md, and the full lifecycle registry in config/owner-tags.json. The compiler copies only active assignable tags into the plugin. The manual-dossier example is maintained with the repository skill's references and copied into the plugin.

From the repository root:

```powershell
.\venv\Scripts\python.exe tools/build_plugin.py
.\venv\Scripts\python.exe tools/build_plugin.py --check
.\venv\Scripts\python.exe -m pytest -q tests/test_plugin_bundle.py tests/test_tag_backfill.py
.\venv\Scripts\python.exe tools/build_plugin.py --package
```

Generation refreshes the bundled guide, active tag catalogue and manual JSON example. `--check` writes nothing. `--package` refuses stale references and produces a deterministic `dist/yacht-owner-biography-researcher-<version>.zip` and SHA-256 checksum. The archive includes exactly the root manifest, skill and three references; no owner exports, credentials, dossiers, archive files or repository scripts are included. The installed package is self-contained.

Bump the manifest version for a release, rebuild and test. Before a hosted update, inspect the current plugin/release and preserve its identity, integrations and sharing settings; a local package version alone does not establish the hosted state. The old `build_gpt_knowledge.py` command exits with a deprecation message and writes nothing.

The root manifest follows [Agent Plugins packaging guidance](https://developers.openai.com/plugins/build/plugins). GPT Instructions limits and separate Knowledge uploads no longer apply to this workflow.
