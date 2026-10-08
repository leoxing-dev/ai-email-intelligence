# hybrid-v1 policy

`hybrid-v1-policy-1` is an offline, field-level fusion policy over two frozen
inputs: `deterministic-rules-v2` and `model-only-v1`. It never reads benchmark
labels at runtime. Ground truth is used only by the evaluator after predictions
have been produced.

## Risk policy

- Required action, registration-required, and deadlines are high risk.
  Definite deterministic positives are retained. A model-only positive must be
  confident and corroborated by another high-risk semantic signal; unresolved
  disagreements route to `manual_review`.
- A message where both systems agree that a reply is needed is not promoted to
  a required action solely because the model chose `required`. Reply remains an
  independent semantic dimension.
- Definite deterministic reply decisions take precedence. The model may resolve
  deterministic reply uncertainty.
- Registration availability, requirement, and completion remain independent.
  Completion has precedence over a registration requirement. Uncertainty is
  not converted to false merely to simplify routing.
- Deterministic deadlines are preserved. Model dates fill a gap only when their
  semantic role is corroborated by a resolved action, registration, or event.
- A confident model may resolve an uncertain event status when both semantics
  support a real event.

## Routing precedence

1. unresolved high-risk conflict -> `manual_review`
2. urgent deterministic required action -> `urgent`
3. required action -> `needs_action`
4. reply needed -> `needs_reply`
5. upcoming/ongoing event -> `upcoming_events`
6. agreed newsletter/promotional semantics -> `low_priority`
7. informational fallback -> `informational`

`digest` is deliberately excluded from the low-value shortcut: a container can
carry important or ordinary informational content and is not promotional by
type alone.

Every hybrid result records deterministic route, model route, final route,
field-level source, disagreement fields, and generic policy decision codes.
No raw message body, rationale, or evidence text is persisted.
