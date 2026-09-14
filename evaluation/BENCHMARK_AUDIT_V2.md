# Synthetic benchmark audit and v2 design

This report audits `synthetic-email-benchmark-v1` and records the construction
and first unchanged-classifier measurement of `synthetic-email-benchmark-v2`.
All records are synthetic. No Gmail account, credentials, tokens, mailbox data,
network service, or external AI was used.

**Synthetic benchmark performance is not equivalent to real-world accuracy.**

## Executive finding

V1 is useful as a small regression suite, but its high held-out scores are not a
credible estimate of mailbox accuracy. Its bodies average only about 72
characters, several important test positives number one or two, ambiguity is
almost absent, trigger words are unusually predictive, and at least 14 strong
lexical/template similarities cross the claimed dev/test boundary. V2 preserves
v1 unchanged for historical comparison, treats all v1 records as development
material, and adds family-isolated held-out and challenge sets. As expected, the
unchanged deterministic classifier scores much lower on v2.

## V1 composition

### Measured-task balance

| Task | Dev + | Dev - | Test + | Test - |
| --- | ---: | ---: | ---: | ---: |
| Required action | 18 | 47 | 10 | 25 |
| Contains event | 27 | 38 | 14 | 21 |
| Upcoming event | 24 | 41 | 13 | 22 |
| Registration required | 3 | 62 | 2 | 33 |
| Registration completed | 1 | 64 | 1 | 34 |
| Deadline detection | 13 | 52 | 7 | 28 |
| Needs reply | 3 | 62 | 1 | 34 |

Held-out registration-required (2), registration-completed (1), and
needs-reply (1) samples are too small for credible precision/recall/F1.
Urgent (3), low-priority (4), manual-review (1), and several email-type strata
are also too small for stable route conclusions. Even a single mistake moves a
one-case recall metric from 1.0 to 0.0.

### Email type and route counts

| Distribution | Dev (65) | Test (35) |
| --- | --- | --- |
| Email types | academic 5; administrative 9; digest 5; event 20; newsletter 5; personal 2; promotional 5; receipt 1; recruiting 4; security 6; unknown 3 | academic 3; administrative 4; automated 1; digest 2; event 11; newsletter 3; personal 1; promotional 3; recruiting 1; security 5; unknown 1 |
| Routes | urgent 4; needs action 14; needs reply 1; upcoming events 22; informational 16; low priority 7; manual review 1 | urgent 3; needs action 7; needs reply 1; upcoming events 11; informational 8; low priority 4; manual review 1 |

### Structure and length

| Measure | Dev | Test |
| --- | ---: | ---: |
| Average subject length (characters) | 28.0 | 27.2 |
| Average body length (characters) | 72.7 | 71.6 |
| Multiple-date cases | 5 | 3 |
| Multiple-event-time cases | 2 | 2 |
| HTML/noise cases | 4 | 2 |
| Digest/container cases | 5 | 2 |
| Conditional cases | 7 | 4 |
| Manual-review cases | 1 | 1 |

The intended mailbox use includes long newsletters, mixed sections, reply
history, forwards, MIME nesting, hidden preheaders, trackers, signatures, and
short context-dependent notes. V1 mostly contains one-sentence subject/body
pairs. It therefore tests isolated rules more than realistic email parsing and
semantic prioritization.

### Tag counts

Dev tags: academic 5, administrative 9, all-day 1, automated 1, boilerplate 2,
conditional 7, date 6, deadline 14, digest 5, emergency 2, event 28, financial 3,
historical-date 2, HTML-noise 3, informational 3, multiple-dates 5, newsletter 5,
personal 1, promotion 6, publication-date 2, recommended-action 1, recruiting 4,
registration 7, relative-date 6, reminder 1, reply 5, required-action 16,
security 7, survey 1, timezone 5, UTC-boundary 2.

Test tags: academic 3, administrative 4, automated 1, boilerplate 1,
conditional 4, date 1, deadline 8, digest 2, DST-boundary 1, emergency 2,
event 15, financial 1, historical-date 1, HTML-noise 2, multiple-dates 3,
newsletter 3, personal 1, promotion 3, recommended-action 1, recruiting 1,
registration 5, relative-date 4, reply 2, required-action 9, security 5,
survey 1, timezone 3, UTC-boundary 1.

## Dev/test similarity and leakage risk

There are no byte-identical cross-split subject/body pairs. That is insufficient:
after lowercasing, removing calendar tokens and common words, and calculating
token-set Jaccard similarity, 14 dev/test pairs score at least 0.35. Strong
candidates include:

| Similarity | Dev case | Test case | Likely shared family |
| ---: | --- | --- | --- |
| 0.625 | `evt_dev_010` | `news_test_003` | required RSVP / career fair |
| 0.545 | `act_dev_004` | `act_test_003` | missing verification document |
| 0.500 | `news_dev_004` | `news_test_003` | career newsletter / RSVP |
| 0.462 | `dig_dev_001` | `dig_test_001` | digest with RSVP/workshop child |
| 0.455 | `sec_dev_003` | `sec_test_003` | conditional sign-in alert |
| 0.429 | `evt_dev_011` | `evt_test_007` | public event / no registration |
| 0.400 | `act_dev_010` | `act_test_007` | mandatory evacuation |
| 0.400 | `news_dev_002` | `news_test_002` | event newsletter |
| 0.400 | `opt_dev_003` | `opt_test_002` | optional discount claim |
| 0.375 | `sec_dev_001` | `sec_test_001` | helmet/safety advisory |
| 0.364 | `opt_dev_010` | `opt_test_001` | optional application essay |
| 0.357 | `dig_dev_003` | `dig_test_002` | daily digest / embedded action |
| 0.353 | `html_dev_003` | `html_test_002` | browser-view boilerplate |

This is likely generator/template-family leakage, not necessarily intentional
label leakage. Nevertheless, it makes v1 test results optimistic because a
held-out record can be a date/name substitution or close paraphrase of a dev
record. V1 has no `family_id`, so its assignment policy cannot be mechanically
verified.

## Trigger-phrase audit

V1 does contain some hard negatives: “required” appears in 8 negative dev and 4
negative test cases; registration vocabulary appears in optional/completed
cases; and workshop/event terms occur in a few negatives or container cases.
However, the coverage is uneven:

- Every `must`, `mandatory`, and `due` occurrence is a required-action positive.
- Every deadline positive uses an overt cue such as “by,” “due,” “submit,” or
  “no later than”; there are no consequence-only cutoffs.
- Every required-registration positive contains RSVP/register/registration
  vocabulary. There are no access-gate formulations such as “only names on the
  roster may enter.”
- Required-action positives without the selected obvious cue list are only 2/18
  in dev and 2/10 in test. Event positives without obvious event nouns are only
  6/27 and 3/14.
- Missing adversaries include “You must see these discounts,” a genuinely
  scheduled gathering without an event noun, and an incomplete-document
  consequence stated without “required,” “must,” or “due.”

Thus v1 rewards keyword recognition more strongly than semantic discrimination.

## Minimal-pair audit

V1 has loose semantic contrasts: required versus optional documents, required
versus optional/completed registration, future events versus recaps, security
actions versus recognized sign-ins, and human reply requests versus no-reply
notifications. Most are different scenarios with different nouns and templates,
not controlled minimal pairs. Missing or weak pairs include:

- same document and date, consequence versus prize/incentive;
- same event, required roster versus open walk-in registration;
- same event title/date, future announcement versus historical recap;
- same application date, deadline versus opening/publication/reference date;
- same registration deadline/event date before and after completion;
- ambiguous conditional obligation versus confirmed obligation.

V2 places these controlled variants within a single family and a single split.

## Date/time difficulty audit

V1 covers Los Angeles as the configured timezone, a few UTC/local-day cases,
today, tomorrow, this Friday, yearless dates, all-day events, multiple dates,
publication versus event dates, historical dates, and registration deadlines
versus event dates. Coverage remains shallow.

Notably absent or too easy are next-Friday versus this-Friday contrasts, a true
fall-back repeated hour, a spring-forward nonexistent local time, explicit
ambiguity handling, quoted obsolete dates, forwarded current versus historical
dates, and long messages with several unrelated semantic roles. The one v1 DST
case is simply a valid time after the transition, not a DST ambiguity. Only four
held-out expected dates include times, so the reported 0.250 ±15-minute accuracy
is based on one success out of four and is unstable. V2 adds local-midnight,
this/next weekday, PST/PDT, fall/spring DST ambiguity, quoted dates, and
publication/deadline/registration/event/historical/promotion roles.

## Uncertainty and abstention

V1 has only one expected manual-review case per split. It labels most ancillary
fields definitively false even when a short message provides no evidence, so it
underrepresents epistemic uncertainty and can reward confident defaults. V2
adds vague requests, program-dependent obligations, tentative events, ambiguous
local times, malformed text, and context-free short messages. The expected
route is manual review when the primary routing decision cannot be made safely;
uncertain subfields can coexist with a known upcoming event.

## V2 construction and independence

V2 totals 218 cases:

| Split | Cases | Families | Purpose |
| --- | ---: | ---: | --- |
| `v2_dev` | 100 | 1 legacy family | all unchanged v1 fixtures; development/regression only |
| `v2_test` | 52 | 30 | newly authored held-out scenario families |
| `challenge` | 66 | 27 | adversarial pairs, noise, MIME, dates, and abstention |

All 100 v1 cases remain byte-for-byte in their original v1 files and the stored
`deterministic-baseline-v1.json` is unchanged. V2 copies them into its dev split
and adds `family_id` metadata. Every new family belongs to exactly one split;
the builder and tests reject a family spanning splits. The original v1 test is
therefore historical development material in v2, not reused as a new held-out
test.

V2 held-out has at least five positives for every measured task: required action
13, contains event 24, upcoming event 22, registration required 6, registration
completed 6, deadline 12, and needs reply 5. It contains 11 multi-date cases,
4 manual-review cases, 2 digest/container cases, and one HTML-noise case. The
challenge set contains 13 multi-date cases, 7 manual-review cases, 2 HTML cases,
2 digest cases, multipart/nested MIME, two malformed encodings, quoted and
forwarded content, and two long multi-section newsletters. Registration-required
challenge metrics still have only two positives and must be interpreted as a
targeted stress result, not a stable population estimate.

Average body length rises from 72 characters in v1 to 118 in v2 test and 115 in
challenge. This is materially more complex, but still much shorter and cleaner
than many real newsletters and institutional threads. V2 improves structural
coverage; it does not simulate a real-mail distribution.

## Unchanged deterministic classifier results

The v1 historical result was re-run and retained its original fingerprint
`18d873364fd9…` and metrics.

| Task | V1 held-out F1 | V2 all F1 | V2 test F1 | Challenge F1 |
| --- | ---: | ---: | ---: | ---: |
| Required action | 1.000 | 0.617 | 0.000 | 0.091 |
| Contains event | 0.966 | 0.800 | 0.667 | 0.604 |
| Upcoming event | 0.960 | 0.763 | 0.500 | 0.529 |
| Registration required | 1.000 | 0.500 | 0.000 | n/a (no positive predictions) |
| Registration completed | 1.000 | 0.250 | n/a (no positive predictions) | n/a (no positive predictions) |
| Deadline detection | 0.833 | 0.493 | 0.133 | 0.174 |
| Needs reply | 1.000 | 0.692 | 0.571 | 0.545 |

V2-all route accuracy is 0.592, coverage 0.716, and accepted-route error rate
0.224. V2-test route accuracy is 0.288; challenge route accuracy is 0.303.
Challenge has 4 false required actions, 16 required-action false negatives,
14 upcoming-event false negatives, and 15 deadline false negatives. Challenge
date extraction precision/recall is 0.862/0.735, exact normalized match is
0.676, and ±15-minute time accuracy is 0.667 (8/12).

Largest v1-to-v2-all F1 drops are completed registration (-0.750), required
registration (-0.500), required action (-0.383), deadline detection (-0.340),
needs reply (-0.308), and upcoming event (-0.197). The largest failure families
by aggregate evaluator error score are event, multiple dates, deadline,
registration, minimal pairs, implicit obligations, trigger-word hard negatives,
reply, and required action. These are diagnostic results, not tuning targets for
this task.

Machine-readable snapshots are stored in
`evaluation/baselines/unchanged-deterministic-v2.json` and
`evaluation/baselines/unchanged-deterministic-v2-challenge.json`. They contain
derived predictions, labels, counts, and case IDs/tags, but no synthetic body,
subject, or sender fields.

## Reproduction

```powershell
python -m evaluation.data.build_v2
python -m evaluation.run --dataset v1 --split test
python -m evaluation.run --dataset v2 --split all
python -m evaluation.run --dataset v2 --split v2_test
python -m evaluation.run --dataset v2 --split challenge
python -m pytest -q
```

The only production-code change associated with the evaluation harness remains
the earlier behavior-preserving extraction of digest routing into
`section_title_for_summary`. This v2 audit did not modify the parser,
summarizer/classifier, Gmail service, OAuth scopes, API behavior, or Gmail state.
