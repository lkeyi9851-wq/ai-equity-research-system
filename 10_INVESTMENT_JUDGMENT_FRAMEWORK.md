# Investment Judgment Framework

Purpose: turn raw company and market sources into a concise, rating-backed
single-stock investment memo.

## Highest Standard

```text
Less is More means concise output, not shallow thinking.
```

The system should think deeply, test alternatives, and remove everything that
does not change rating, confidence, valuation range, trigger design, or the next
evidence request.

## Execution Rule

```text
No thesis without transmission.
```

Every final thesis claim must carry this chain:

```text
source evidence
-> observed fact
-> surface driver
-> root economic driver
-> financial line item
-> market expectation gap
-> valuation / rating impact
-> invalidation trigger
```

If the chain breaks, the point is an observation, not a thesis.

## MVP Scope

The current MVP is the Standard depth only:

```text
local-first English single-stock memo
pre-DCF
multiple-based valuation bridge
Buy / Neutral / Sell / No Rating
internal self-check hidden from final memo
```

Quick and Deep are product directions, but current implementation quality rules
serve Standard first.

## What Can Enter Core Thesis

A Core Thesis must be:

- Predictive: says what should happen over the investment horizon.
- Economic: affects revenue, margin, cash conversion, capital intensity, risk,
  or justified multiple.
- Material: can move group-level EPS, FCF, or fair value enough to matter.
- Rooted: identifies the underlying economic driver, not only the surface trend.
- Evidenced: has direct source support.
- Expectation-aware: says what the market may be mispricing.
- Valuation-linked: changes fair-value range or rating.
- Falsifiable: has observable failure triggers.

The final memo should usually have one Core Thesis and two to three supporting
conditions. More conditions are allowed only when each can independently change
fair value or rating.

## Observation vs Driver vs Root Driver

```text
Observation = what happened.
Surface driver = the visible cause.
Root economic driver = the company-specific mechanism that can change earnings
quality, cash flow, risk, or justified multiple.
```

Example:

```text
Observation: overseas revenue mix rose.
Surface driver: overseas sales grew faster than domestic sales.
Root driver: overseas expansion may be large, profitable, repeatable, and
cash-generative enough to change group earnings quality and the justified
multiple.
```

Do not stop at observed growth. Ask what makes it durable, profitable,
company-specific, and valuation-relevant.

## Materiality Test

Materiality is company-specific and industry-specific. Use quantitative
benchmarks, then calibrate them to the business model.

Starting rules:

- A driver is normally material if changing the assumption can move group EPS,
  FCF, or fair value by roughly 10% or more over the investment horizon.
- For stable or regulated businesses, 5-10% fair-value impact may be material.
- For cyclical or high-growth businesses, 15-20% may be needed to change rating.
- A small revenue line can be material if it has much higher margin, ROIC,
  repeatability, or multiple impact.
- A large revenue line may be non-core if it adds little incremental profit,
  consumes cash, or is already fully priced.

Assess each candidate driver with:

| Dimension | Question |
| --- | --- |
| Revenue weight | Is it large enough to affect group results? |
| Profit contribution | Can it drive more than 15-20% of incremental EBIT or net profit? |
| Growth contribution | Can it drive more than 25-30% of future growth? |
| Margin / FCF effect | Does it improve earnings quality, not only sales? |
| Capital intensity | Does growth require heavy reinvestment or working capital? |
| Sustainability | Is it structural or temporary? |
| Company specificity | Is it alpha, not just industry beta? |
| Market mispricing | Is it underappreciated or already priced? |
| Observability | Can failure be tracked with metrics? |
| Rating relevance | Would reversal change rating or confidence? |

## Industry Calibration

Before ranking drivers, identify how the industry is usually valued and which
variables matter most.

| Industry type | Typical root-driver metrics |
| --- | --- |
| Industrials / machinery | orders, backlog, utilization, overseas mix, gross margin, working capital, capex cycle |
| Software | ARR growth, NRR, churn, CAC payback, FCF margin, Rule of 40 |
| Consumer | same-store sales, pricing, volume, gross margin, inventory, channel mix |
| Banks | NIM, credit cost, deposit beta, CET1, loan growth, NPL ratio |
| Commodities | realized price, cost curve, volume, reserve life, sustaining capex, net debt |
| Semis | revenue cycle, gross margin, utilization, inventory, capex intensity, design wins |
| Pharma | pipeline probability, patent cliff, reimbursement, trial milestones, peak sales |
| Utilities | regulated return, capex base, allowed ROE, leverage, dividend sustainability |

The final driver should remain company-specific. Do not publish generic industry
factor lists.

## Driver Ranking

Rank candidate drivers by:

```text
financial magnitude
x differential profitability
x sustainability
x company specificity
x market mispricing
x observability
```

The best driver is the one that, if wrong, would make the rating wrong.

## Market Expectation Gap

A memo becomes stock research only when it explains the expectation gap:

```text
what the market seems to believe
what the system believes differently
why the gap exists
what evidence could close it
how it changes valuation or rating
```

Minimum pass:

- current valuation anchor,
- one market-view or consensus clue,
- one underappreciated root driver,
- one revision catalyst or trigger.

Without this, the correct rating is usually Neutral or No Rating.

## Catalyst vs Trigger

```text
Catalyst = what may cause the market to revise expectations.
Trigger = what makes the system change rating or confidence.
```

Good catalysts are time-bound and observable: earnings, guidance, order update,
margin inflection, FCF delivery, policy approval, product milestone, contract,
buyback/dividend change, or estimate revision.

Good triggers include metric, threshold, direction, source, linked thesis
condition, and rating action.

## Risks

Risks must be thesis-specific.

Do not publish generic risks such as macro uncertainty, competition, or execution
risk unless the memo explains:

```text
root risk
-> surface symptom
-> financial transmission
-> observable trigger
-> rating impact
```

Example:

```text
Root risk: overseas margin strength is cyclical rather than structural.
Surface symptom: overseas order growth slows and margin premium narrows.
Transmission: group margin expansion and EPS growth revert to domestic-cycle
economics.
Rating impact: multiple re-rating fails and confidence falls.
```

## Rating Standard

Rating is a stock call, not a company-quality score.

```text
Rating = expected return asymmetry adjusted by evidence reliability and valuation confidence.
```

Use:

| Rating | Standard |
| --- | --- |
| Buy / Overweight | Strong root-driver thesis, meaningful valuation gap, reliable inputs, manageable downside, observable triggers. |
| Neutral | Thesis is plausible but valuation gap, timing, evidence, or reliability is not strong enough. |
| Sell / Underweight | Downside or overvaluation is meaningful and supported by reliable evidence. |
| No Rating | Price, forecast, or valuation inputs are missing or conflicting enough to block an honest stock call. |

Hard rules:

- Good company does not equal Buy.
- Bad company does not equal Sell if the bad news is priced.
- No expectation gap means Buy confidence cannot be High.
- Valuation conflict means rating confidence cannot be High.
- No observable trigger means confidence must be capped.

## Confidence

Separate thesis probability from rating confidence.

```text
Thesis probability = likelihood that the business thesis is true.
Rating confidence = reliability of the stock call at current valuation.
```

High confidence requires direct current evidence, reconciled valuation inputs,
clear expectation gap, and observable triggers.

## Final Output Shape

Default Standard memo:

```text
Rating
Bottom Line
Core Thesis
Thesis Conditions
Market Expectation Gap
Pre-DCF Valuation
Catalysts / Rating Triggers
Key Risks
What To Verify Next
```

No process notes, no visible self-check, no loose evidence dump.
