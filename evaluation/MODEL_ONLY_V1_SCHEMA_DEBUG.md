# Model-only-v1 local schema debugging

This pass is offline. It does not call OpenAI, Gmail, held-out V2 test, or the
challenge split, and it does not change benchmark fixtures or the model prompt.

## Historical controlled-20 failures

The existing snapshot identifies these four failed cases:

| Case | Last proven stage | Historical field/value diagnostic | Stages not reached |
| --- | --- | --- | --- |
| `act_dev_011` | `ModelStructuredPrediction.model_validate_json` raised | Not retained by the old adapter | normalization, evaluation |
| `evt_dev_010` | `ModelStructuredPrediction.model_validate_json` raised | Not retained by the old adapter | normalization, evaluation |
| `news_dev_004` | `ModelStructuredPrediction.model_validate_json` raised | Not retained by the old adapter | normalization, evaluation |
| `rep_dev_002` | `ModelStructuredPrediction.model_validate_json` raised | Not retained by the old adapter | normalization, evaluation |

For each case, the old code proves that the HTTP response was successful, the
Responses payload status was `completed`, and an output-text item existed. The
old adapter then caught `ValidationError`, replaced it with the single code
`schema_validation`, discarded `ValidationError.errors()`, discarded the
structured object, and captured usage only after validation. Consequently, the
exact historical field, received value, expected value, and validator cannot be
recovered from this privacy-minimized snapshot. Because `store=false` was used,
there is intentionally no retrievable server-side response artifact.

The evidence excludes normalization failure and evaluator-schema mismatch for
the historical four. It does not permit a defensible case-by-case distinction
between an upstream Structured Outputs violation and a local runtime-only
constraint. A paid rerun would be required to produce new per-case diagnostics;
this pass deliberately does not do that.

## Contract drift found locally

`ModelStructuredPrediction.model_json_schema()` was the schema sent to OpenAI
and the same Pydantic model was used for runtime parsing. However, the model also
contained constraints that were absent from its generated JSON Schema:

- three cross-field rules implemented by a Pydantic `model_validator`;
- a 240-character limit for each top-level evidence item implemented only by a
  `field_validator`.

This meant an object could satisfy the actual OpenAI JSON Schema and still fail
the local call to `model_validate_json`. The adapter mislabeled both this domain
contract mismatch and a genuine structural failure as `schema_validation`.
All four historical failures were required-action cases for which alternative
routes such as `needs_reply` or `upcoming_events` are plausible outputs, so the
runtime-only required-action/route rule is a strong hypothesis. It is not
reported as historical fact because the old adapter destroyed the evidence.

The fixed architecture is:

1. `ModelStructuredPrediction` is the canonical strict structural contract.
2. Its generated JSON Schema is sent to OpenAI and the same model parses output.
3. JSON-Schema-expressible constraints, including evidence-item length, are
   represented directly in that canonical model.
4. Cross-field rules run in an explicit domain-validation stage.
5. Normalization into `CasePrediction` is a separately classified stage.
6. Privacy-safe validation issues retain field, type, bounded safe value,
   expectation, and error code. Free-text rationale/evidence values are never
   retained in diagnostics.

## Outcome taxonomy

Every execution now records one detailed outcome:

- `provider_failure`
- `provider_refusal`
- `structured_output_failure`
- `domain_validation_failure`
- `normalization_failure`
- `model_abstention`
- `valid_prediction`

The older coarse status remains only as a compatibility view for hybrid and
snapshot consumers.

## Usage and cost policy

Usage is captured immediately after a parseable provider response, before
structured-output or domain validation. A response with reported usage remains
billable even when it is unusable. Totals, averages, and cost per 1,000 use all
billable attempts. `cost_accounting_complete` is true only when every attempt
with reported usage also has a measured cost.

## Metric policy

- **Technical reliability** reports request success, structured-output success,
  domain-validation success, and end-to-end usable-prediction rates with their
  explicit denominators.
- **Semantic quality** is computed on usable predictions only and stored as
  `usable_report`.
- **End-to-end quality** remains in `report`; unusable outcomes become the
  existing conservative `manual_review` prediction and therefore count against
  full-sample metrics according to the established evaluation policy.

These two quality views are intentionally separate and neither is substituted
silently for the other.
