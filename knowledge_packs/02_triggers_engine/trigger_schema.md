# Trigger Schema

```text
trigger_id
rating_action: upgrade / maintain / downgrade / no-rating / watch
linked_thesis_condition
metric
threshold
direction
source
frequency
why_it_matters
confidence
data_gap_if_unavailable
```

Minimum trigger:
- one metric
- one threshold
- one rating action
- one linked thesis condition

If no threshold exists, it is a risk note, not a trigger.
