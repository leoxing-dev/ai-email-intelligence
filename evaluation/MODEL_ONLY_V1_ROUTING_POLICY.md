# Model-only-v1 semantic and routing policy

Model extraction semantics and presentation routing are separate concerns.
The following fields remain independent and are evaluated independently:

- `action_kind`
- `needs_reply`
- `contains_event` and `event_status`
- registration availability, requirement, and completion
- normalized dates and deadline semantics

The model-proposed `route` is retained as `model_proposed_route`. A deterministic
normalizer chooses the single final `route` used by the UI. A disagreement is
observable and is not itself a domain-validation failure.

## Primary-route precedence

The first matching rule wins:

1. `abstain=true` -> `manual_review`
2. required action with model-proposed `urgent` -> `urgent`
3. any other required action -> `needs_action`
4. `needs_reply=true` without a required action -> `needs_reply`
5. upcoming or ongoing event without a higher-priority signal ->
   `upcoming_events`
6. model-proposed `manual_review` without a higher-priority signal ->
   `manual_review`
7. promotional email or model-proposed `low_priority` -> `low_priority`
8. otherwise -> `informational`

This means `action_kind=required` and `needs_reply=true` is valid. The reply flag
is retained, while the final primary route is normally `needs_action`.

## Domain validation

Route disagreement is presentation-policy disagreement, not semantic invalidity.
Domain validation therefore does not reject route/action, route/reply, or
route/event combinations. It retains the current contradiction that a
registration cannot simultaneously be marked both completed and currently
required. A completed registration may coexist with a different required action.

## Evaluation views

- Semantic fields are scored independently through existing binary/date metrics.
- `model_proposed_route_accuracy` measures the model's route extraction directly.
- `normalized_route_accuracy` measures deterministic routing-policy output.
- Legacy `route_accuracy` remains an alias of normalized final-route accuracy so
  historical consumers continue to load and behave consistently.
