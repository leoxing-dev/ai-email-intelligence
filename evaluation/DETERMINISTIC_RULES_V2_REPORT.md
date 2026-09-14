# deterministic-rules-v2

This was one bounded deterministic improvement pass. Development used only the
V2 development split. After production logic was frozen, V2 held-out test and
challenge were each evaluated exactly once. No classifier change was made from
those results.

**Synthetic benchmark performance is not equivalent to real-world accuracy.**

## Generalizable changes

- Date roles now use clause-local evidence instead of allowing one global cue to
  label every date. Publication, historical, deadline, registration-deadline,
  event, promotional, and referenced roles retain distinct precedence.
- Deadline grammar handles inflected action verbs, before/cutoff language, and
  consequence-linked dates without treating every apply/register/submit date as
  a universal obligation.
- Required actions can arise from the combination of operational context, user
  applicability, adverse consequence, and a consequence link. Promotional
  urgency alone remains optional.
- Registration availability, access-gate requirements, completion, and optional
  walk-in language are independent signals. Completion and explicit optionality
  override stale required wording.
- Event evidence includes more general scheduled-gathering language and separates
  future scheduling from recaps, archives, photos, and recordings.
- Hour-only times are normalized to minute zero rather than inheriting the
  message-received minute. “This weekday” and “next weekday” use a documented
  calendar-week distinction.

These are reusable concepts and invariants. No real organization, inbox subject,
sender-domain blacklist, live date, or benchmark-case exception was added.

## Development result

V2 dev contains 100 previously exposed synthetic cases.

| Metric | Before | deterministic-rules-v2 |
| --- | ---: | ---: |
| Required action P/R/F1 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Contains event P/R/F1 | 0.976 / 1.000 / 0.988 | 0.976 / 1.000 / 0.988 |
| Upcoming event P/R/F1 | 1.000 / 0.973 / 0.986 | 1.000 / 0.973 / 0.986 |
| Registration required P/R/F1 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Registration completed P/R/F1 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Deadline P/R/F1 | 1.000 / 0.750 / 0.857 | 1.000 / 1.000 / 1.000 |
| Needs reply P/R/F1 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| Route accuracy | 0.940 | 0.960 |
| Coverage | 0.970 | 0.990 |
| Date exact match | 0.929 | 0.986 |
| Time ±15 minutes | 0.545 | 0.909 |

Final protected dev counts: 0 false required actions, 0 required-action false
negatives, 0 deadline false negatives, and 1 upcoming-event false negative.

## Frozen V2 held-out comparison

| Metric | Original deterministic | deterministic-rules-v2 |
| --- | ---: | ---: |
| Required action P/R/F1 | 0.000 / 0.000 / 0.000 | 0.700 / 0.538 / 0.609 |
| Contains event P/R/F1 | 0.867 / 0.542 / 0.667 | 0.900 / 0.750 / 0.818 |
| Upcoming event P/R/F1 | 0.800 / 0.364 / 0.500 | 0.900 / 0.409 / 0.563 |
| Registration required P/R/F1 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| Registration completed P/R/F1 | n/a / 0.000 / n/a | 1.000 / 0.500 / 0.667 |
| Deadline P/R/F1 | 0.333 / 0.083 / 0.133 | 0.733 / 0.917 / 0.815 |
| Needs reply P/R/F1 | 1.000 / 0.400 / 0.571 | 1.000 / 0.400 / 0.571 |
| Route accuracy | 0.288 | 0.519 |
| Coverage | 0.500 | 0.654 |
| Accepted-route error rate | 0.500 | 0.265 |

Protected held-out counts changed as follows:

| Error | Original | deterministic-rules-v2 |
| --- | ---: | ---: |
| False required actions | 3 | 3 |
| Required-action false negatives | 13 | 6 |
| Deadline false negatives | 11 | 1 |
| Upcoming-event false negatives | 14 | 13 |

## Frozen challenge comparison

| Metric | Original deterministic | deterministic-rules-v2 |
| --- | ---: | ---: |
| Required action P/R/F1 | 0.200 / 0.059 / 0.091 | 0.706 / 0.706 / 0.706 |
| Contains event P/R/F1 | 0.800 / 0.485 / 0.604 | 0.857 / 0.727 / 0.787 |
| Upcoming event P/R/F1 | 0.818 / 0.391 / 0.529 | 0.875 / 0.609 / 0.718 |
| Registration required P/R/F1 | n/a / 0.000 / n/a | n/a / 0.000 / n/a |
| Registration completed P/R/F1 | n/a / 0.000 / n/a | 1.000 / 0.167 / 0.286 |
| Deadline P/R/F1 | 0.333 / 0.118 / 0.174 | 0.750 / 0.706 / 0.727 |
| Needs reply P/R/F1 | 0.750 / 0.429 / 0.545 | 0.750 / 0.429 / 0.545 |
| Route accuracy | 0.303 | 0.515 |
| Coverage | 0.500 | 0.712 |
| Accepted-route error rate | 0.576 | 0.383 |

Protected challenge counts changed from 4 to 5 false required actions, 16 to 5
required-action false negatives, 15 to 5 deadline false negatives, and 14 to 9
upcoming-event false negatives. The extra false required action is important:
recall improved substantially, but deterministic consequence logic still cannot
reliably resolve every applicability or promotional ambiguity.

## Three-generation summary

- `deterministic-baseline-v1` on benchmark V1 remains the historical high-score
  regression snapshot; its small, similar held-out fixtures are not a credible
  real-world estimate.
- The original deterministic classifier on benchmark V2 exposed major failures
  in implicit obligations, registration state, multi-role dates, event routing,
  and ambiguity.
- `deterministic-rules-v2` materially improves obligations, deadlines, event
  detection, time normalization, completion state, routing, and coverage, while
  retaining strong dev required-action precision.

## Remaining deterministic limitations

The final held-out/challenge outputs were not used for another tuning pass.
Aggregate error categories show the largest remaining problems in event routing,
trigger-word hard negatives, multi-date relationships, registration and
registration completion, relative dates, reply inference, ambiguous messages,
and date-role semantics. Required-registration recall remains zero in both frozen
sets, and held-out upcoming-event recall remains only 0.409.

Rules fundamentally struggle when obligation depends on missing conversational
context, discourse-level scope, exceptions spanning several clauses, tentative
plans, or whether a generic instruction actually applies to the recipient. They
also struggle to distinguish a direct request from quoted/container content when
structure is malformed, and to associate several dates/events across long mixed
sections without a richer semantic representation. These limitations should be
measured on a future blind V3 rather than addressed by tuning against the now
observed V2 test/challenge.

## Reproducibility and privacy

Snapshots:

- `evaluation/baselines/deterministic-rules-v2-dev.json`
- `evaluation/baselines/deterministic-rules-v2-test.json`
- `evaluation/baselines/deterministic-rules-v2-challenge.json`

The snapshots contain derived labels, predictions, counts, IDs, and tags—not
subjects, bodies, or senders. The experiment used synthetic local data only. It
did not access Gmail, make network calls, process attachments, persist raw Gmail
bodies, add external AI, or alter OAuth/Gmail permissions.

