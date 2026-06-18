# Reconciliation Checks

Before issuing rating:

1. Recalculate P/E from price and EPS.
2. Recalculate P/FCF from price and FCF/share.
3. Recalculate equity P/FCF from market cap and FCF.
4. Compare recalculated multiples against source-file multiples.
5. Flag mismatch over 15%.

Possible mismatch explanations:

```text
stale price
currency mismatch
share count mismatch
fiscal year mismatch
FCF definition mismatch
per-share vs total-value mismatch
A-share vs H-share mismatch
analyst-report extraction error
spreadsheet formula error
```

Hard rule:

```text
If valuation conflict is unresolved, rating confidence cannot be High.
```

Confidence rule:
- If mismatch is unresolved but downside remains limited in the conservative case, allow Medium confidence.
- If mismatch drives the rating conclusion, cap at Low or No Rating.
