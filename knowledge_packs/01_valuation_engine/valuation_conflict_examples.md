# Valuation Conflict Examples

## Sany Failure Case

Bad output:

```text
Buy / Overweight because P/FCF 8.0x looks attractive.
```

Problem:

```text
The memo also calculates observed P/FCF at 4.1x from current price and FCF/share. The two values conflict, so valuation is not clean enough for High confidence.
```

Better output:

```text
Buy / Overweight, Medium confidence. Cash-flow valuation appears attractive, but confidence is capped because source-file P/FCF and price/FCF-share implied P/FCF conflict. Refresh live price, share count, FCF definition, and fiscal year before increasing conviction.
```

Decision rule:
- Do not hide the conflict.
- Do not average the two multiples.
- Use the conflict to lower confidence and define the next required reconciliation step.
