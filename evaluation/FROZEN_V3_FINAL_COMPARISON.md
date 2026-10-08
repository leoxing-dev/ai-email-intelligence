# Frozen V3 final blind comparison

This is the first and only evaluation of the frozen deterministic-rules-v2, model-only-v1, and hybrid-v1 systems on synthetic-email-benchmark-v3-blind. No semantic configuration was changed and no V3 result was used for tuning.

## Technical reliability and usage

The integrity gate passed before predictions. The initial sandboxed test transport produced 186 local network failures, no API responses, and no billable usage. One bounded batch retry was then authorized. Final runs received 312/312 API responses: 281 valid predictions and 31 intentional abstentions, with zero provider, refusal, structured-output, domain-validation, or normalization failures.

Usage was 364,413 input tokens (0 cached), 71,768 output tokens, and 436,181 total tokens. Usage-priced cost was $1.590042, or $0.005096 per message and $5.096 per 1,000. Billable latency averaged 3379.5 ms (p50 3276.4, p95 4564.3). Hybrid incremental API cost was $0.

## V3 test

| Measure | Deterministic | Model-only | Hybrid |
| --- | ---: | ---: | ---: |
| Required action P/R/F1 | 0.974/0.881/0.925 | 0.977/1.000/0.988 | 0.974/0.881/0.925 |
| Event P/R/F1 | 0.823/0.940/0.878 | 1.000/0.964/0.982 | 0.828/0.976/0.896 |
| Upcoming event P/R/F1 | 1.000/0.923/0.960 | 1.000/0.974/0.987 | 1.000/0.974/0.987 |
| Registration required P/R/F1 | n/a/0.000/n/a | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| Registration completed P/R/F1 | n/a/0.000/n/a | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| Deadline P/R/F1 | 0.875/0.875/0.875 | 1.000/0.875/0.933 | 0.875/0.875/0.875 |
| Needs reply P/R/F1 | n/a/0.000/n/a | 1.000/0.167/0.286 | 1.000/0.167/0.286 |
| Route accuracy | 0.634 | 0.860 | 0.774 |
| Coverage | 0.742 | 0.892 | 0.930 |
| Accepted error rate | 0.174 | 0.072 | 0.191 |
| Abstention rate | 0.258 | 0.108 | 0.070 |
| False required actions | 1 | 1 | 1 |
| Required false negatives | 5 | 0 | 5 |
| Deadline false negatives | 6 | 6 | 6 |
| Upcoming false negatives | 6 | 2 | 2 |

## V3 challenge

| Measure | Deterministic | Model-only | Hybrid |
| --- | ---: | ---: | ---: |
| Required action P/R/F1 | 0.400/0.500/0.444 | 1.000/0.833/0.909 | 0.471/0.667/0.552 |
| Event P/R/F1 | 1.000/1.000/1.000 | 1.000/0.883/0.938 | 1.000/1.000/1.000 |
| Upcoming event P/R/F1 | 0.889/1.000/0.941 | 1.000/1.000/1.000 | 0.889/1.000/0.941 |
| Registration required P/R/F1 | n/a/0.000/n/a | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| Registration completed P/R/F1 | n/a/0.000/n/a | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| Deadline P/R/F1 | 0.833/0.714/0.769 | 1.000/0.476/0.645 | 0.833/0.714/0.769 |
| Needs reply P/R/F1 | 0.000/0.000/0.000 | n/a/0.000/n/a | 0.000/0.000/0.000 |
| Route accuracy | 0.381 | 0.833 | 0.540 |
| Coverage | 0.698 | 0.825 | 0.865 |
| Accepted error rate | 0.568 | 0.163 | 0.468 |
| Abstention rate | 0.302 | 0.175 | 0.135 |
| False required actions | 18 | 0 | 18 |
| Required false negatives | 12 | 4 | 8 |
| Deadline false negatives | 12 | 22 | 12 |
| Upcoming false negatives | 0 | 0 | 0 |

## V3 combined

| Measure | Deterministic | Model-only | Hybrid |
| --- | ---: | ---: | ---: |
| Required action P/R/F1 | 0.721/0.742/0.731 | 0.984/0.939/0.961 | 0.736/0.803/0.768 |
| Event P/R/F1 | 0.891/0.965/0.927 | 1.000/0.931/0.964 | 0.893/0.986/0.937 |
| Upcoming event P/R/F1 | 0.952/0.952/0.952 | 1.000/0.984/0.992 | 0.954/0.984/0.969 |
| Registration required P/R/F1 | n/a/0.000/n/a | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| Registration completed P/R/F1 | n/a/0.000/n/a | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| Deadline P/R/F1 | 0.857/0.800/0.828 | 1.000/0.689/0.816 | 0.857/0.800/0.828 |
| Needs reply P/R/F1 | 0.000/0.000/0.000 | 1.000/0.111/0.200 | 0.400/0.111/0.174 |
| Route accuracy | 0.532 | 0.849 | 0.679 |
| Coverage | 0.724 | 0.865 | 0.904 |
| Accepted error rate | 0.327 | 0.107 | 0.298 |
| Abstention rate | 0.276 | 0.135 | 0.096 |
| False required actions | 19 | 1 | 19 |
| Required false negatives | 17 | 4 | 13 |
| Deadline false negatives | 18 | 28 | 18 |
| Upcoming false negatives | 6 | 2 | 2 |

## Date/time results

| Scope/system | Precision | Recall | Exact normalized | Time tolerance | Role errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| v3_test / deterministic-rules-v2 | 0.988 | 0.977 | 0.977 | 0.941 | 201 |
| v3_test / model-only-v1 | 0.962 | 0.977 | 0.977 | 0.941 | 32 |
| v3_test / hybrid-v1 | 0.981 | 0.977 | 0.977 | 0.941 | 199 |
| v3_challenge / deterministic-rules-v2 | 1.000 | 1.000 | 1.000 | 1.000 | 144 |
| v3_challenge / model-only-v1 | 1.000 | 0.859 | 0.859 | 0.909 | 80 |
| v3_challenge / hybrid-v1 | 1.000 | 1.000 | 1.000 | 1.000 | 144 |
| combined / deterministic-rules-v2 | 0.993 | 0.987 | 0.987 | 0.964 | 345 |
| combined / model-only-v1 | 0.977 | 0.925 | 0.925 | 0.929 | 112 |
| combined / hybrid-v1 | 0.989 | 0.987 | 0.987 | 0.964 | 343 |

## Difficulty

| Tier/system | Cases | Mean defined binary F1 | Route accuracy | Semantic errors |
| --- | ---: | ---: | ---: | ---: |
| easy / deterministic-rules-v2 | 30 | 0.944 | 0.533 | 10 |
| easy / model-only-v1 | 30 | 1.000 | 0.967 | 0 |
| easy / hybrid-v1 | 30 | 0.944 | 0.800 | 10 |
| medium / deterministic-rules-v2 | 66 | 0.885 | 0.576 | 49 |
| medium / model-only-v1 | 66 | 0.809 | 0.667 | 28 |
| medium / hybrid-v1 | 66 | 0.804 | 0.682 | 33 |
| hard / deterministic-rules-v2 | 126 | 0.907 | 0.651 | 77 |
| hard / model-only-v1 | 126 | 0.965 | 0.897 | 30 |
| hard / hybrid-v1 | 126 | 0.936 | 0.738 | 46 |
| adversarial / deterministic-rules-v2 | 90 | 0.760 | 0.333 | 60 |
| adversarial / model-only-v1 | 90 | 0.926 | 0.878 | 19 |
| adversarial / hybrid-v1 | 90 | 0.871 | 0.556 | 38 |

## Hybrid generalization

Across 3089 field decisions, sources were {'agreement': 1532, 'model': 332, 'policy': 305, 'deterministic': 920}. Hybrid routes versus deterministic changed 79, improved 51, and worsened 5. Versus model-only they changed 76, improved 4, and worsened 57. Hybrid produced 30 manual-review routes, including 10 policy conflict abstentions.

Hybrid beat deterministic on required-action, event, upcoming-event,
registration-required, registration-completed, and needs-reply F1, while tying
deadline F1. Against model-only it improved only deadline F1 (0.828 versus
0.816), tied both registration fields, and hurt required-action, event,
upcoming-event, needs-reply, route accuracy, and accepted-case error rate. The
frozen hybrid therefore repeats the V2 overfitting pattern and is not justified
as the default architecture.

## Major weaknesses

Model-only's largest weakness is reply detection: combined needs-reply recall
was 0.111, with recurring errors in the actual `reply`, `conditional`, and
direct-question families. It also missed 28 applicable deadlines, concentrated
in challenge cases and abstentions. Its most affected families included
`silent_access_revocation`, `conditional_travel_preference`,
`mentor_choice_question`, `policy_revision_question`, and
`question_without_reply_word`.

Deterministic and hybrid errors were broader. Both retained major weaknesses in
`required_action`, `implicit_obligation`, `registration`, `reply`,
`quoted_content`, multilingual/encoding, and adversarial promotion cases. The
hybrid inherited 19 false required actions and 13 required-action false
negatives; deterministic had 19 and 17 respectively. Full tag and family
counts use only committed V3 tag names and are stored in the JSON artifact.

## V2 to V3 generalization

Model-only route accuracy was stable from 0.856 on combined unseen V2 to 0.849
on V3. Its required, event, upcoming-event, and registration F1 values were
stable or better, but deadline F1 fell by 0.151, needs-reply F1 fell by 0.646,
and coverage fell from 0.907 to 0.865. Its protected profile remained strongest
overall, although deadline false negatives rose from 0 to 28.

Deterministic route accuracy remained low (0.517 to 0.532). Hybrid route
accuracy materially deteriorated from 0.797 to 0.679 despite higher coverage,
while false required actions rose from 8 to 19. The prior conclusion survives:
model-only generalizes best, deterministic rules generalize poorly on semantic
scope, and hybrid-v1 does not preserve model-only quality on unseen data.

## Evidence-based conclusion

Model-only-v1 is the best overall generalizing architecture and has the safest
aggregate protected-error profile: 1 false required action, 4 required-action
false negatives, 2 upcoming-event false negatives, and 28 deadline false
negatives, versus protected-error totals of 60 for deterministic and 52 for
hybrid. It is not uniformly safest: deterministic and hybrid each had 18
deadline false negatives, so deadline recall and reply recall remain major
limitations. Hybrid-v1 is not justified as the default because it improved
only deadline F1 over model-only while substantially worsening routing,
required-action safety, and accepted-case errors.

The complete tag, family, disagreement, policy-decision, date-role, and V2-to-V3 delta tables are preserved in `FROZEN_V3_FINAL_RESULTS.json`.

## Privacy

No Gmail or Calendar access, real email data, Gmail writes, or raw body persistence occurred. Result snapshots contain no body, rationale, or evidence fields. The API key was not logged; every provider request used `store=false`; all fixtures remain synthetic.
