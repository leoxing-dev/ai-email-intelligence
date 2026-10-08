# V3 blind evaluation instructions

These instructions preserve `synthetic-email-benchmark-v3-blind` as a
one-time, no-tuning evaluation. They do not authorize an evaluation now.

## Before any prediction

1. Verify every path and SHA-256 digest in `data/FROZEN_V3_SHA256.json`.
2. Verify the combined and per-split dataset fingerprints and exact counts:
   186 `v3_test`, 126 `v3_challenge`, 312 total.
3. Verify there is no scenario-family overlap between splits and no case ID
   overlap with V1/V2.
4. Verify the frozen deterministic rules, model prompt/configuration,
   structured-output contract, route policy, and hybrid policy against their
   existing freeze manifests. Stop on any mismatch.
5. Record the evaluator code revision and a clean inventory of result paths.

## Blind execution protocol

- Treat both splits as held out. V3 has no development or tuning split.
- Generate predictions from `input` only. Ground truth, rationales, tags,
  difficulty, and family metadata must not enter any model prompt, classifier
  input, routing decision, retry decision, or abstention decision.
- Run each frozen system exactly once per case. Do not tune, patch, prompt-edit,
  relabel, filter, cherry-pick, or rerun semantically valid predictions after
  seeing any V3 result.
- If model calls are authorized in that future task, use only the separately
  frozen provider/model/reasoning/schema/store/privacy settings. Apply only the
  already documented bounded retry policy to technical transient failures.
- Never access Gmail or real email data. Keep `store=false`, do not log API
  keys, and do not persist raw bodies in result snapshots.
- Store predictions separately from fixtures. Result snapshots may contain
  case IDs, labels/predictions, metrics, failure taxonomy, usage, latency, and
  privacy-safe diagnostics, but no input body fields or rationale/evidence
  text.

## Reporting

Report `v3_test`, `v3_challenge`, and combined results separately for each
frozen system. Include precision/recall/F1 for required action, event, upcoming
event, registration required, registration completed, deadline, and needs
reply; route accuracy; coverage; abstention and accepted-case error rates; and
protected errors. Include by-family/tag/difficulty analysis without printing
message bodies.

For model-backed systems, account for every billable response and report
attempts, billable responses, usable predictions, retries, tokens, measured
cost, cost per message and per 1,000, and average/p50/p95 latency. Report hybrid
incremental cost separately when frozen model predictions are reused.

After the one-time evaluation, freeze result artifacts and stop. Do not modify
V3, tune any system from V3 outcomes, create a hidden tuning subset, or rerun to
select a better result. Any later system version requires a new independently
constructed benchmark version.
