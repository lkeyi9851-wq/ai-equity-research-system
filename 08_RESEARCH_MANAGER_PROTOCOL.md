# Research Manager Protocol

## Purpose

This file defines how the system decides:

- what information is needed first,
- when information is enough,
- what to request next,
- how much effort to spend,
- and when to stop.

Highest principle:

```text
Less is more.
```

That means: use the smallest reliable evidence package that can support a useful decision.

## Research Manager Role

Research Manager combines the first-version responsibilities of:

- Research Director,
- Data Steward,
- question-to-data mapping.

This avoids splitting early judgment across too many agents.

The Research Manager may later delegate work, but it owns the decision logic.

## First Pass: Minimum Useful Context

For any stock task, first identify:

- company or ticker,
- user intent,
- report depth,
- time horizon,
- available source files,
- output language,
- output form.

If missing, use defaults:

- depth: standard,
- horizon: 6-12 months,
- language: match user input,
- output: Markdown,
- source: annual report or official filing if available.

Ask the user only when the missing answer would materially change the work.

## Initial Evidence Package

Start with the smallest package that can support a standard single-stock view:

- business description,
- revenue trend,
- profit or margin trend,
- cash-flow direction,
- balance sheet risk,
- segment or product mix if disclosed,
- management outlook,
- top risks,
- industry context that affects the thesis,
- basic valuation reference if available,
- source and period for each key fact.

Annual reports and official filings are the default reliable base. Bloomberg, Wind, FactSet, LSEG, Capital IQ, or similar exports outrank public secondary sources when provided.

## Long Document Source Map

Before extracting from long PDFs or source packs, build a compact source map:

```text
file -> source type -> date/period -> pages or sheets -> useful sections -> extraction quality
```

This is an internal reading step. The final memo should not explain the reading process.

Use the source map to decide what to read next:

- annual reports: business, segment, financials, cash flow, liquidity, outlook, capital allocation, thesis-relevant risks
- financial Excel: actuals, forecasts, margins, EPS, FCF, price, multiples, valuation assumptions
- analyst reports: rating, target price, estimate changes, valuation assumptions, thesis drivers, risks to verify
- industry reports: demand, pricing, supply, cycle indicators, regulation, peer position

Skip long sections when they cannot change rating, thesis conditions, valuation bridge, downside risk, or confidence.

## Investment Judgment Gate

Before writing, convert facts into a thesis using this chain:

```text
Fact -> economic driver -> forecast implication -> evidence -> invalidation
```

Examples:

- revenue growth -> growth durability -> future sales can compound or mean-revert,
- mix shift -> margin quality -> profit can grow faster than revenue,
- working capital/capex -> cash conversion -> earnings quality is high or low,
- debt/liquidity -> downside risk -> equity value is more or less fragile,
- peer multiple/DCF assumption -> valuation -> market is paying for the right or wrong driver.

If the chain breaks, do not put the point in the thesis table.

## Rating Gate

When financial data or valuation data is available, the final memo must answer:

```text
Buy/Overweight, Neutral, Sell/Underweight, or No Rating?
```

Use this decision order:

1. Earnings direction: revenue, margin, EPS/net income.
2. Cash quality: operating cash flow, FCF, working capital, capex.
3. Valuation: P/E, EV/EBITDA, P/FCF, target price, peer range, or DCF.
4. Risk: balance sheet, cyclicality, execution, FX/geopolitics/regulation.

Positive business facts are not enough for Buy. They must translate into better earnings, better cash flow, or a valuation gap.

## Question Type Determines Data Need

Before requesting more data, classify the task:

| Question type | Data that matters most |
| --- | --- |
| Business quality | margins, cash conversion, revenue mix, competitive position |
| Growth durability | segment growth, demand drivers, guidance, leading indicators |
| Margin direction | gross margin, operating margin, cost drivers, pricing power |
| Valuation | price, market cap, net debt, earnings, cash flow, peers |
| Downside risk | debt, liquidity, cyclicality, concentration, risk factors |
| Turnaround | revenue stabilization, margin recovery, cash burn, restructuring |
| Cyclical stock | cycle indicators, inventory, backlog, utilization, leverage |
| Competitive position | share, differentiation, pricing power, switching costs |
| Capital allocation | capex, buybacks, dividends, M&A, dilution, debt use |
| Industry inflection | demand shift, regulation, supply, pricing, technology change |
| Catalyst | earnings, guidance, product, regulation, litigation, deal event |
| Portfolio fit | sector exposure, volatility, liquidity, concentration, role |

If a data request does not map to the question type, skip it.

## Depth Controls Evidence

### Quick

Enough if the system has:

- what the company does,
- latest key financial direction,
- one core risk,
- one valuation or market context point,
- and clear limitations.

Stop early. Do not build full financial history.

### Standard

Enough if the system can explain:

- business quality,
- financial direction,
- valuation logic,
- key risks,
- industry context,
- and confidence level.

This is the default target.

### Deep

Enough if the system has:

- 5-year financial trends,
- segment and margin drivers,
- cash-flow quality,
- balance sheet detail,
- peer or industry comparison,
- scenario assumptions,
- risk map,
- and source appendix.

If these are not available, downgrade to standard with disclosed limitations.

### Expert

Use only when the decision truly needs modeling, portfolio construction, or investment committee depth.

Requires:

- model-ready inputs,
- peer comps,
- scenario drivers,
- sensitivity assumptions,
- and preferably institutional or user-provided data.

Do not fake expert precision from weak public data.

## Information Sufficiency Test

Information is enough when the answer to all four questions is yes:

```text
1. Can we state the thesis?
2. Can we support it with reliable evidence?
3. Can we name what would make it wrong?
4. Would more data likely change the conclusion?
```

If 1-3 are yes and 4 is no, stop.

If 4 is yes, request only the missing data that could change the conclusion.

## Analyst Report Use

External reports are not evidence by themselves. Use them to identify:

- which driver the market cares about,
- which assumptions support the target price,
- what catalysts or risks professionals consider material,
- which facts should be verified in official sources.

Do not copy, audit, or summarize an external thesis as the final answer. The final answer must be the system's own supported judgement.

## Data Request Rule

Every extra data request must answer:

```text
What decision could this data change?
```

If the answer is unclear, do not request it.

Use this format:

```text
Requested data:
Decision it could change:
Expected value:
Effort/cost:
Can proceed without it:
Priority:
```

Priority:

- critical: cannot answer honestly without it,
- important: changes confidence or depth,
- optional: useful, but not worth delaying the report.

## Effort And Cost Budget

Research effort should scale with decision value.

Use this budget:

| Level | Effort budget | Stop rule |
| --- | --- | --- |
| Quick | one reliable source plus minimal market context | stop once a limited view is possible |
| Standard | annual report plus focused supplements | stop once thesis, risks, and confidence are supported |
| Deep | filings, transcripts, peers, industry context | stop when extra evidence refines but does not change thesis |
| Expert | model-ready data and institutional inputs | stop if data quality cannot support expert precision |

Cost includes:

- user time,
- Codex/OpenClaw compute,
- data access cost,
- context length,
- risk of stale or noisy data,
- complexity added to the system.

Prefer cheaper evidence when it is equally reliable.

## Annual Report Extraction Order

When using an annual report, extract only in this order until the selected depth is supported:

1. Business description.
2. Segment or product mix.
3. Revenue, operating income, net income.
4. Margin direction.
5. Operating cash flow and capex.
6. Cash, debt, liquidity.
7. Management discussion and outlook.
8. Capital allocation.
9. Risk factors.
10. Accounting or legal issues only if thesis-relevant.

Skip boilerplate unless it affects the thesis.

## Source Labels

For key facts, label:

- source,
- period,
- currency,
- unit,
- actual / estimate / assumption,
- verified / partial / stale / conflict.

No key conclusion should depend on unlabeled data.

For final memos, attach the source directly inside the thesis row. Avoid separate evidence dumps.

## When To Stop

Stop when:

- the selected depth is supported,
- missing data would not likely change the thesis,
- extra data is mostly decorative,
- cost is higher than decision value,
- or missing data should be disclosed instead of chased.

## When To Continue

Continue only when missing data could change:

- business quality,
- growth durability,
- margin direction,
- valuation range,
- downside risk,
- industry position,
- or final confidence.

## Output To Other Agents

Use this compact package:

```text
Research question:
Depth:
Sources used:
Core facts:
Key metrics:
Industry context:
Missing data:
Data conflicts:
Confidence impact:
Stop/continue decision:
Next request if any:
```

## Training Loop

After each real case, record only:

```text
Initial question type:
Data requested:
Data skipped:
What changed the conclusion:
What was unnecessary:
Stopping decision quality:
Rule to update:
```

Training means improving judgment, not accumulating more rules.
