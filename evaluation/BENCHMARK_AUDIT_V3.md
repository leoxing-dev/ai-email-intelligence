# Synthetic Email Benchmark V3 construction audit

`synthetic-email-benchmark-v3-blind` is a fresh, fully synthetic blind
benchmark. It contains no tuning split and was constructed without running any
classifier, language model, hybrid policy, Gmail integration, or network
service. Synthetic benchmark performance is not equivalent to real-world
mailbox accuracy.

## Frozen composition

| Split | Cases | Scenario families | Purpose |
| --- | ---: | ---: | --- |
| `v3_test` | 186 | 31 | Broad blind generalization |
| `v3_challenge` | 126 | 21 | Adversarial and boundary behavior |
| **Total** | **312** | **52** | No tuning cases |

Each family contributes six variants and belongs to exactly one split. No
family is shared between test and challenge. The combined dataset fingerprint
is `4f8b557fffce59a4b51ccdefb3b29d7bf1f01d82c14c26e0d82eaacbb98f97b5`.

## Class balance

The table counts a positive only when the corresponding semantic field is
affirmatively true (or `action_kind=required`). Deadlines include both ordinary
and registration deadlines.

| Target | Test + / - | Challenge + / - | Total + / - |
| --- | ---: | ---: | ---: |
| Required action | 42 / 144 | 24 / 102 | 66 / 246 |
| Event | 84 / 102 | 60 / 66 | 144 / 168 |
| Upcoming event | 78 / 108 | 48 / 78 | 126 / 186 |
| Registration required | 18 / 168 | 12 / 114 | 30 / 282 |
| Registration completed | 12 / 174 | 12 / 114 | 24 / 288 |
| Deadline | 48 / 138 | 42 / 84 | 90 / 222 |
| Needs reply | 24 / 162 | 12 / 114 | 36 / 276 |

Route counts are: informational 84, low priority 12, manual review 30,
needs action 60, needs reply 30, upcoming events 90, and urgent 6. Rare but
important states remain deliberately less common; none of the reported binary
targets relies on only one or two positives.

## Difficulty and structural coverage

Difficulty is intentionally weighted toward difficult material: 30 easy, 66
medium, 126 hard, and 90 adversarial cases. Hard plus adversarial cases are
216/312 (69.2%). Challenge contains 36 hard and 90 adversarial cases; it has no
easy or medium cases.

Measured structural coverage includes:

- 48 long-form cases; average body length 745.8 characters and 97.9 tokens as
  measured by the audit's lexical tokenizer.
- 144 multi-date and 18 structurally multi-event cases.
- 12 digest/container, 30 HTML/noise, and 30 ambiguous/manual-review cases.
- 30 timezone/DST and 18 multilingual/encoding cases.
- Explicit hard negatives for imperative advertising, quoted obligations,
  historical deadlines, voluntary registration, past events, no-reply mail,
  forwarded closed work, and digest child content.
- Implicit positives for obligations, replies, structured events, assigned
  registration, and multi-signal routing.

The complete tag distribution and per-family mapping are machine-readable in
`data/v3_audit.json` and `data/v3_family_mapping.json`.

## Leakage and duplicate audit

The audit found:

- zero normalized exact duplicates;
- zero cross-split pairs at token-set Jaccard similarity >= 0.55;
- zero different-family pairs within a split at similarity >= 0.75; and
- zero V3-to-V1/V2 pairs at similarity >= 0.45.

Six variants within a family intentionally share a scenario template. This is
not cross-split leakage because all variants and their family remain in one
split. Thresholds and top-match arrays are recorded in `data/v3_audit.json` so
the limitation of a lexical similarity audit is explicit.

## Labels, provenance, and privacy

Every case has authored ground truth, tags, a scenario family, a difficulty,
and a separate concise rationale. Every sender uses the reserved `.example`
domain and every case carries the `X-Synthetic-Benchmark` marker. No real
message, person, account, credential, Gmail identifier, or mailbox data is
present.

The construction script imports only evaluation schemas for validation. The
audit imports only schemas and dataset-loading utilities. Neither script
imports or executes the deterministic classifier, model provider, model-only
pipeline, hybrid policy, Gmail client, or any network client.

## Freeze and historical integrity

`data/FROZEN_V3_SHA256.json` is the authority for the frozen case files,
metadata, family mapping, audit artifacts, construction/audit scripts, this
report, the blind-evaluation instructions, and the V3 integrity tests. It also
records reference hashes for the already frozen V2 policy and dataset
artifacts. V1/V2 fixtures, historical result snapshots, deterministic rules,
model prompt/configuration, hybrid policy, and routing policy were not changed
as part of V3 construction.

The benchmark is frozen before any system is evaluated on it. Any future
result must first verify the freeze manifest and follow
`V3_BLIND_EVALUATION_INSTRUCTIONS.md`.
