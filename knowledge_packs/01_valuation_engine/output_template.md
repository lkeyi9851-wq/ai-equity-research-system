# Valuation Output Template

Use compact rows:

```text
Case | Input anchor | Formula | Implied value | Rating impact | Confidence limit
Bear | [real downside driver] | [formula] | [price/upside] | [action] | [why capped]
Base | [current market anchor] | [formula] | [price/upside] | [action] | [why capped]
Bull | [real upside driver] | [formula] | [price/upside] | [action] | [why capped]
```

Required note when inputs conflict:

```text
Valuation confidence is capped because [input A] and [input B] do not reconcile. The rating can only be High after [specific reconciliation].
```

Forbidden:
- Multiple-only Bear/Base/Bull with no business mechanism.
- External target price treated as truth.
- Upside shown without current price date.
