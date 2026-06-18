# Triggers Engine Rules

A trigger is not a risk sentence.

Rules:
- A trigger must be observable.
- Every trigger must include metric, threshold, direction, source, linked thesis condition, and rating action.
- No generic trigger is allowed.
- A trigger must say what changes the rating or confidence.
- If the source is unavailable, write the data gap.

Bad generic trigger:

```text
Demand weakens.
```

Good trigger:

```text
Downgrade to Neutral if FY26/FY27 revenue growth falls below high-single-digit level or consensus EPS revisions turn negative, because the Buy thesis depends on double-digit growth sustaining margin expansion.
```
