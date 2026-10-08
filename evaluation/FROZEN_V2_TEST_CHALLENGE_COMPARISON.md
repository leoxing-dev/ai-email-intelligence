# Frozen V2 held-out and challenge comparison

This is the one-time evaluation of `deterministic-rules-v2`, `model-only-v1`,
and `hybrid-v1-policy-1`. No policy or model configuration was changed after
the development freeze. Cells below are precision / recall / F1.

## V2 held-out test (52 cases)

| Metric | Deterministic | Model-only | Hybrid |
|---|---:|---:|---:|
| Required action | .700 / .538 / .609 | .846 / .846 / .846 | .769 / .769 / .769 |
| Event | .900 / .750 / .818 | 1.000 / 1.000 / 1.000 | .917 / .917 / .917 |
| Upcoming event | .900 / .409 / .563 | 1.000 / 1.000 / 1.000 | .952 / .909 / .930 |
| Registration required | .000 / .000 / .000 | 1.000 / .667 / .800 | .500 / .333 / .400 |
| Registration completed | 1.000 / .500 / .667 | 1.000 / .833 / .909 | 1.000 / .833 / .909 |
| Deadline | .733 / .917 / .815 | 1.000 / 1.000 / 1.000 | .750 / 1.000 / .857 |
| Needs reply | 1.000 / .400 / .571 | .714 / 1.000 / .833 | .667 / .800 / .727 |

| Operational metric | Deterministic | Model-only | Hybrid |
|---|---:|---:|---:|
| Route accuracy | .519 | .846 | .846 |
| Coverage | .654 | .962 | .904 |
| Accepted-case error rate | .265 | .160 | .128 |
| Abstention rate | .346 | .038 | .096 |
| False required actions | 3 | 2 | 3 |
| Required false negatives | 6 | 2 | 3 |
| Deadline false negatives | 1 | 0 | 0 |
| Upcoming-event false negatives | 13 | 0 | 2 |

## V2 challenge (66 cases)

| Metric | Deterministic | Model-only | Hybrid |
|---|---:|---:|---:|
| Required action | .706 / .706 / .706 | .941 / .941 / .941 | .722 / .765 / .743 |
| Event | .857 / .727 / .787 | .929 / .788 / .852 | .848 / .848 / .848 |
| Upcoming event | .875 / .609 / .718 | .875 / .913 / .894 | .808 / .913 / .857 |
| Registration required | n/a / .000 / n/a | 1.000 / .500 / .667 | n/a / .000 / n/a |
| Registration completed | 1.000 / .167 / .286 | .800 / .667 / .727 | .800 / .667 / .727 |
| Deadline | .750 / .706 / .727 | .895 / 1.000 / .944 | .778 / .824 / .800 |
| Needs reply | .750 / .429 / .545 | .857 / .857 / .857 | .750 / .857 / .800 |

| Operational metric | Deterministic | Model-only | Hybrid |
|---|---:|---:|---:|
| Route accuracy | .515 | .864 | .758 |
| Coverage | .712 | .864 | .788 |
| Accepted-case error rate | .383 | .123 | .135 |
| Abstention rate | .288 | .136 | .212 |
| False required actions | 5 | 1 | 5 |
| Required false negatives | 5 | 1 | 4 |
| Deadline false negatives | 5 | 0 | 3 |
| Upcoming-event false negatives | 9 | 2 | 2 |

## Hybrid decision provenance

| Measure | Held-out | Challenge |
|---|---:|---:|
| Total field decisions | 520 | 660 |
| Agreements | 246 | 298 |
| Deterministic selected | 141 | 220 |
| Model selected | 74 | 71 |
| Policy-derived | 57 | 62 |
| Cases with model-selected fields | 32 | 35 |
| Cases with deterministic-selected fields | 51 | 63 |
| Hybrid abstentions | 5 | 14 |

Held-out hybrid routes versus deterministic: 23 changed, 19 improved, 2
worsened, and 2 remained incorrect. Versus model-only: 10 changed, 5
improved, and 5 worsened.

Challenge hybrid routes versus deterministic: 22 changed, 16 improved, none
worsened, and 6 remained incorrect. Versus model-only: 16 changed, 4
improved, 11 worsened, and 1 remained incorrect.

The leading disagreement categories were email type, dates, registration
completion, action kind, route, reply state, and the other registration fields.

## Generalization result

Development performance was materially over-optimistic. Hybrid route accuracy
fell from .980 on development to .846 held-out and .758 challenge. Required
action F1 fell from 1.000 to .769 and .743. Protected errors reappeared: false
required actions were 3 and 5; required-action false negatives were 3 and 4;
deadline false negatives were 0 and 3; upcoming-event false negatives were 2
on both target splits.

The hybrid did generalize relative to deterministic routing, improving route
accuracy substantially on both target splits. It did not generalize relative
to model-only quality: held-out route accuracy tied model-only while most
semantic fields were worse, and challenge route accuracy and protected metrics
were materially worse. No post-evaluation tuning was performed.

## New model usage

- Requests/billable responses: 118 / 118
- Retries: 0
- Input tokens: 114,305
- Output tokens: 21,422
- Total tokens: 135,727
- Usage-priced cost: $0.485674
- Average cost/message: $0.00411588
- Estimated cost per 1,000 comparable messages: $4.11588
- Average latency: 3.241 s
- p50 latency: 3.020 s
- p95 latency: 4.530 s
- Hybrid incremental API cost: $0

All 118 API responses passed structured-output and domain validation. The model
produced 2 intentional abstentions on held-out and 9 on challenge. There were no
provider failures, schema failures, normalization failures, or retries.
