# AI-assisted owner duplicate audit

This component creates a manual-review report of possible duplicate owner
records. It is intentionally separate from the owner update workflow:

- it has no `--apply` option;
- it never imports `src.browser_update` or either update entrypoint;
- live SYN access is limited to authenticated GET requests;
- it writes only new files beneath its output directory;
- it never sends biographies, long biographies, or internal notes to the AI;
- OpenAI Responses are requested with `store: false`.

The audit is evidence, not authority to merge or delete records.

## Install the one additional dependency

From the repository root:

```powershell
.\venv\Scripts\python.exe -m pip install -r .\duplicate_audit\requirements.txt
```

The implementation uses the repository's existing `requests` dependency for
the OpenAI API and NumPy for bounded all-to-all embedding similarity.

## Run a fresh live audit

Set the API key in the current PowerShell process. Do not put it in a report or
commit it to the repository.

```powershell
$env:OPENAI_API_KEY = "your-api-key"

.\venv\Scripts\python.exe .\audit_owner_duplicates.py `
  --live `
  --headless `
  --allow-ai-upload
```

`--allow-ai-upload` is mandatory. It acknowledges that the allow-listed owner
identity fields will be sent to the OpenAI API for embeddings and model
judgments. The flag does not authorize any SYN write.

The default run performs these stages:

1. Export the complete live owner list into a new timestamped directory.
2. Create separate name and identity embeddings.
3. Retrieve nearest-neighbour candidate pairs plus pairs linked by strong
   record evidence such as a shared social URL.
4. Re-read live details and social profiles only for candidate records.
5. Ask a conservative model to classify every pair.
6. Independently verify every `probable_duplicate` judgment.
7. Write checkpointed JSON and a self-contained HTML review report.

The embedding retrieval and structured judgments use the documented OpenAI
[embeddings](https://developers.openai.com/api/reference/resources/embeddings/methods/create)
and [Responses structured-output](https://developers.openai.com/api/docs/guides/structured-outputs)
interfaces. Defaults are configurable CLI options rather than hidden constants.

## Smoke test

Use a new explicit output directory and limit both the live pages and paid
judgments:

```powershell
.\venv\Scripts\python.exe .\audit_owner_duplicates.py `
  --live `
  --headless `
  --allow-ai-upload `
  --max-pages 2 `
  --limit 10 `
  --output-dir output\duplicate-audit\smoke
```

A page-limited run is not a complete audit and is labelled as such in its live
snapshot warnings.

## Resume an interrupted run

Repeat the same configuration with the same explicit directory and add
`--resume`:

```powershell
.\venv\Scripts\python.exe .\audit_owner_duplicates.py `
  --live `
  --headless `
  --allow-ai-upload `
  --output-dir output\duplicate-audit\20260830T120000Z `
  --resume
```

Source hashes, model settings, dimensions, and person-ID order are validated
before embedding or candidate checkpoints are reused.

## Audit an existing owner file

This mode is useful for offline testing. It copies the supplied input into the
new run directory and never overwrites the input:

```powershell
.\venv\Scripts\python.exe .\audit_owner_duplicates.py `
  --input output\owners-list.vessel-enriched.enriched.json `
  --allow-ai-upload
```

Add `--enrich-candidates-live` if candidate details and socials should be
re-read from live SYN. A truly live whole-system audit should use `--live`.

## Exhaustive evidence mode

The default candidate-first flow minimizes load on SYN. For maximum recall,
the following option reads details and socials for every owner before embedding
retrieval:

```powershell
--exhaustive-live-enrichment
```

This performs roughly two live detail requests per owner and should be used
deliberately. It remains read-only and checkpoints every record.

## Output

Each run writes a new directory containing:

- `live-owners.json` or `source-owners.json`: immutable audit source snapshot;
- `embeddings.npz` and metadata: local resumable embedding cache;
- `candidates.json`: every retrieved pair and its retrieval evidence;
- `candidate-evidence.live.json`: candidate-only live details/social snapshot;
- `duplicate-audit.json`: structured judgments and API provenance;
- `duplicate-review.html`: filterable side-by-side manual-review report.

Manual decisions entered in the HTML report stay in that browser's local
storage. Use **Export manual decisions** to download a portable JSON review.
The report has no controls that call SYN.

## Judgment meanings

- `probable_duplicate`: strong match evidence and an agreeing skeptical pass;
- `possible_duplicate`: plausible, but not strong enough to treat as probable;
- `needs_manual_review`: a probable primary result lacking verifier agreement;
- `probably_distinct`: evidence favours two different people;
- `insufficient_evidence`: the available fields cannot support a conclusion.

Deterministic normalization and exact-field signals only improve candidate
recall. They never determine any of these classifications.
