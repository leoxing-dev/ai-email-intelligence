# Privacy-First AI Email Intelligence Platform

This project turns unstructured email into structured actions, deadlines,
events, registration and reply signals, and deterministic routing decisions.
It combines a read-only local Gmail pipeline with a synthetic evaluation system
for deterministic rules, structured-output language-model predictions, and a
frozen hybrid policy.

The strongest result from the final frozen experiment is straightforward:
**model-only-v1 generalized best on the blind V3 benchmark**. Hybrid-v1 was
strong on development data, but overfit and underperformed model-only-v1 on
blind V3. These are synthetic benchmark results, not claims about production
Gmail accuracy.

For the complete evidence, see:

- [Frozen V3 final comparison](evaluation/FROZEN_V3_FINAL_COMPARISON.md)
- [V3 benchmark construction audit](evaluation/BENCHMARK_AUDIT_V3.md)

## What the repository includes

- A local Gmail reader restricted to the `gmail.readonly` OAuth scope.
- MIME parsing, HTML sanitization, attachment exclusion, quoted-thread
  trimming, and transient body processing.
- Structured extraction of action, event, registration, deadline, reply, and
  route fields.
- Strict model-output schema and domain validation.
- Deterministic normalization and routing precedence that keeps semantic
  signals separate from presentation routing.
- Synthetic V1, adversarial V2, and blind V3 benchmarks with frozen artifacts.
- Offline tests for privacy controls, read-only Gmail behavior, parsing,
  classification, evaluation, and benchmark integrity.

## Three operating modes

### Live Gmail mode

The live application is local and read-only:

- OAuth scope is exactly `https://www.googleapis.com/auth/gmail.readonly`.
- Gmail operations are message list/get only; there are no Gmail writes.
- Attachments are not retrieved separately, and attachment-part data is
  discarded before parsing.
- Raw Gmail bodies are processed transiently and are not persisted.
- The in-memory cache holds derived summaries, not raw message bodies.
- Current live Gmail semantic processing remains local and deterministic.

The application does not send or reply, mark messages read, modify labels,
archive or delete messages, create calendar events, or transmit live Gmail data
to the model benchmark pipeline.

### AI benchmark mode

The model evaluation path is separate from live Gmail:

- Inputs are committed synthetic fixtures only.
- The frozen provider configuration uses OpenAI `gpt-5.6-terra` with structured
  outputs and medium reasoning.
- Outputs pass strict schema validation, domain validation, and deterministic
  normalization.
- Provider requests use `store=false`.
- No live Gmail data enters this path.

The OpenAI Responses integration uses `httpx` directly, so the OpenAI Python
SDK is not required.

### Public demo mode

The public demo is upcoming and is not implemented yet. Its intended boundary
is synthetic data and precomputed predictions only, with no Gmail login and no
frontend API key.

## Architecture

```text
LIVE GMAIL (read-only)                 SYNTHETIC BENCHMARKS
          |                                      |
          v                                      v
list/get MIME payloads                 deterministic / model-only
          |                                      |
          v                                      v
local parser + LocalSummarizer          schema + domain validation
          |                                      |
          v                                      v
derived EmailSummary objects            deterministic normalization
          |                                      |
          v                                      v
local CLI / localhost API               frozen metrics and snapshots
```

The semantic dimensions—action kind, reply need, event presence, registration
state, and deadlines—are independent. A deterministic policy maps those fields
to one primary presentation route without treating valid multi-signal messages
as contradictions.

## Frozen blind V3 results

`synthetic-email-benchmark-v3-blind` contains 312 cases across 52 isolated
scenario families. Hard and adversarial cases account for 216/312 (69.2%). It
was frozen before evaluation and has no tuning split.

| Metric | deterministic-rules-v2 | model-only-v1 | hybrid-v1 |
| --- | ---: | ---: | ---: |
| Required-action F1 | 0.731 | **0.961** | 0.768 |
| Event F1 | 0.927 | **0.964** | 0.937 |
| Upcoming-event F1 | 0.952 | **0.992** | 0.969 |
| Deadline F1 | **0.828** | 0.816 | **0.828** |
| Route accuracy | 0.532 | **0.849** | 0.679 |

These are **synthetic blind benchmark results**, not production Gmail accuracy.
Model-only-v1 was the best overall generalizing architecture and had the best
aggregate protected-error profile. Hybrid-v1 improved deadline F1 slightly over
model-only-v1 but worsened required-action safety, routing, and accepted-case
errors, repeating the overfitting pattern first exposed on V2.

### Experimental progression

```text
deterministic baseline
    -> adversarial V2
    -> model-only-v1
    -> hybrid-v1
    -> V2 exposed hybrid overfitting
    -> blind V3 confirmed a model-first architecture
```

The model is not uniformly better. Deadline false negatives remain significant,
reply recall remains weak, and the model may abstain. Synthetic evaluation does
not establish safety, fairness, policy compliance, or real-mailbox performance.

## Privacy and security boundary

> Never commit `credentials.json`, `token.json`, `.env`, API keys, OAuth tokens,
> or exported email data.

- API responses use `Cache-Control: no-store`.
- Logs are designed to exclude message content and redact credential-like data.
- Result snapshots contain case IDs, predictions, diagnostics, aggregate
  metrics, latency, and token accounting—not raw subjects, bodies, senders,
  evidence text, rationales, API keys, or authorization headers.
- Synthetic sender domains use the reserved `.example` namespace.
- Gmail credentials and tokens remain local and ignored by Git.

Software controls do not by themselves establish organizational, legal, or
institutional approval. Review the applicable rules before using any mailbox,
especially one containing regulated or protected data.

## Requirements and installation

- Python 3.12 or newer
- A trusted local computer for live Gmail use
- For live Gmail only: an authorized Google Cloud project, Gmail API enabled,
  and an OAuth Desktop application credential

Gmail dependencies are explicitly declared in `requirements.txt`. The model
provider uses the same declared `httpx` dependency directly.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No dependency upgrade or lockfile is implied by these instructions.

## Local Gmail setup and use

Follow Google's official Gmail Python quickstart to enable the API and create a
Desktop OAuth client. Configure only this scope:

```text
https://www.googleapis.com/auth/gmail.readonly
```

Save the downloaded client file as `credentials.json` in the repository root
and confirm it is ignored:

```powershell
git check-ignore -v credentials.json
```

Generate a local digest:

```powershell
python -m app.cli digest
python -m app.cli digest --json
```

The first Gmail-dependent command opens the local OAuth flow and stores the
result in ignored `token.json`. Digest output contains derived mailbox
information and should still be treated as sensitive.

Run the development API on loopback only:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Available endpoints are `GET /health`, `GET /unread`,
`GET /digest/unread`, and `POST /sync`. Do not expose this unauthenticated local
development API through a public interface, proxy, or tunnel.

## Evaluation and reproducibility

The committed benchmarks are fully synthetic. Offline deterministic evaluation
does not authenticate to Gmail or call OpenAI:

```powershell
python -m evaluation.run --dataset v2 --split all
python -m evaluation.run --dataset v2 --split v2_test
python -m evaluation.run --dataset v2 --split challenge
```

V3 was a one-time blind evaluation. Its construction, freeze rules, composition,
and leakage audit are documented in
[`evaluation/BENCHMARK_AUDIT_V3.md`](evaluation/BENCHMARK_AUDIT_V3.md). The final
comparison and limitations are in
[`evaluation/FROZEN_V3_FINAL_COMPARISON.md`](evaluation/FROZEN_V3_FINAL_COMPARISON.md).

The repository tracks only the privacy-safe result snapshots referenced by
`evaluation/FROZEN_V3_FINAL_RESULT_MANIFEST.json`; other generated runs remain
ignored. Verify dataset and artifact integrity with the tests before relying on
the reported numbers.

## Tests

Tests are offline, use synthetic content, and mock Gmail operations. They need
no Google account, Gmail credentials, OpenAI key, or network access.

```powershell
python -m pytest -q
```

Coverage includes MIME and HTML handling, attachment exclusion, date/time and
timezone behavior, semantic validation, routing precedence, provider-contract
handling with mocked responses, privacy-safe logging, read-only Gmail access,
evaluation metrics, and frozen V3 integrity.

## Pre-commit privacy check

Inspect both filenames and staged contents before every public commit:

```powershell
git status --short
git diff --cached --name-only
git diff --cached
git ls-files
git check-ignore -v credentials.json token.json .env
```

If a secret was ever committed, removing the current file is not enough: revoke
or rotate it and treat the Git history as exposed.

## License

Licensed under the [MIT License](LICENSE).
