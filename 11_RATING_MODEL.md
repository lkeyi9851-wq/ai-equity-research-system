# Rating Model v0.3

Purpose: produce a realistic Buy / Neutral / Sell / No Rating view from source
files without pretending that stocks can be reduced to a fixed formula.

## Core Logic

```text
Rating = expected return asymmetry adjusted by evidence reliability and valuation confidence.
```

The model asks:

1. What does the current valuation imply?
2. What are the two to three root economic drivers that can move fair value?
3. Are those drivers material at group level?
4. Are they profitable, cash-generative, and sustainable?
5. What does the market already price?
6. What is the justified multiple range?
7. What is the bear/base/bull asymmetry?
8. Are the data reliable enough for a rating?

## Root Driver Standard

A driver is material only if a change in its assumption can move group EPS, FCF,
or fair value by roughly 10% or more over the investment horizon, subject to
industry calibration.

Use this internal test:

```text
1. Is the driver large enough at group level?
2. Is it profitable, not just growing?
3. Is it cash-generative, not just accounting earnings?
4. Is it sustainable beyond one reporting period?
5. Is it company-specific rather than industry beta?
6. Is the market underpricing or overpricing it?
7. Can it justify a different multiple?
8. Can failure be observed?
```

Only drivers that pass this test may support Buy/Sell conviction.

## Valuation Method Selection

Select the valuation metric before judging the stock:

| Company type | Preferred Standard metric |
| --- | --- |
| Stable earnings | P/E |
| Capital-intensive / industrial | EV/EBITDA and P/E cross-check |
| Cash-generative | P/FCF and FCF yield |
| Financials | P/B with ROE / capital quality |
| Early growth | EV/Sales only with explicit caution |
| Cyclical | Mid-cycle P/E or EV/EBITDA |
| Resource / asset-heavy | EV/EBITDA, NAV, cost curve |

The MVP can use any available clean multiple, but it must label data gaps and
avoid false precision.

## Justified Multiple

Standard valuation is not "take peer average." It is:

```text
current multiple
-> peer/history anchor
-> quality and risk adjustments
-> justified range
```

Adjust the deserved multiple using evidence, not adjectives:

| Evidence | Multiple effect |
| --- | --- |
| Higher durable growth | premium |
| Structural margin quality | premium |
| Better FCF conversion | premium |
| Lower capital intensity | premium |
| Higher ROIC / value-accretive reinvestment | premium |
| Lower cyclicality or risk | premium |
| Stronger balance sheet | premium |
| Weak governance, disclosure, liquidity, or cyclicality | discount |
| Stale or conflicting valuation data | confidence cap |

Approximate adjustment discipline:

| Evidence strength | Multiple adjustment |
| --- | --- |
| Weak or unproven thesis | 0-10% |
| One core quality metric improves | 10-20% |
| Multiple quality metrics improve and persist | 20-35% |
| Company attribute changes | 35%+ only with very strong evidence |

Calibrate by industry. A small P/B move can be large for banks; software
multiples can move more; cyclical stocks should not get peak multiples on peak
earnings.

## Bear / Base / Bull

Every case must include:

```text
root driver assumption
financial estimate
justified multiple
implied return
```

Case rules:

| Case | Driver | Financial estimate | Multiple |
| --- | --- | --- | --- |
| Bear | Root driver fails | EPS/FCF below base by a driver-linked amount | lower peer/history range or de-rating |
| Base | Most likely evidence-backed path | current best estimate | fair mid-range |
| Bull | Root driver proves structural | EPS/FCF above base by a driver-linked amount | upper justified range |

Default sensitivity when no model exists:

- Stable businesses: narrower EPS/FCF sensitivity, often 5-15%.
- Industrials/cyclicals: 10-25% EPS/FCF sensitivity.
- High-growth or expectation-sensitive stocks: wider multiple sensitivity.

Do not publish bear/base/bull cases if the inputs are not clean enough. Show a
valuation data gap instead.

## Rating Rules

| Rating | Rule |
| --- | --- |
| Buy / Overweight | Root-driver thesis is medium-high or high, valuation gap is meaningful, valuation inputs are reliable, downside is manageable, and triggers are observable. |
| Neutral | Thesis is plausible but valuation gap, timing, evidence reliability, or downside asymmetry is not strong enough. |
| Sell / Underweight | Negative asymmetry or overvaluation is meaningful and supported by reliable evidence. |
| No Rating | Valuation or forecast inputs are too weak or conflicting to make a decision. |

## Confidence Rules

```text
Thesis probability scores business truth.
Rating confidence scores investable stock-call reliability.
```

Hard caps:

- valuation conflict: confidence cannot exceed Medium,
- stale price without large margin of safety: confidence cannot exceed Medium,
- no market expectation gap: Buy confidence cannot exceed Medium,
- no observable triggers: confidence cannot exceed Medium-high,
- missing EPS/FCF anchor: rating should usually be No Rating or Low confidence.

## DCF Readiness

DCF is not part of the Standard MVP output. It is a next step only when:

- price, share count, EPS/FCF, fiscal year, and source definitions are clean,
- valuation conflict is resolved,
- root-driver thesis passes,
- expectation gap is meaningful,
- a model would change rating or position sizing.

Until then, the MVP stays with a disciplined multiple-based valuation bridge.
