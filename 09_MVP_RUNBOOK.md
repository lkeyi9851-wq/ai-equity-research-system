# MVP Runbook

## Purpose

Build the Standard-depth MVP:

```text
local source package -> evidence -> root drivers -> valuation bridge -> rating-backed English memo
```

The MVP should prove that a local single-stock research system can produce a
useful investment memo with evidence, limitations, valuation discipline, rating,
confidence, and observable triggers.

## Product Boundary

Do:

- accept one company source package,
- read local files first,
- support English-only single-stock memo output,
- classify source quality,
- build a source map before extracting long documents,
- identify two to three root economic drivers,
- quantify materiality against company and industry context,
- build a multiple-based pre-DCF valuation bridge,
- produce Buy / Neutral / Sell / No Rating when evidence allows,
- produce source notes, summary JSON, and quality score,
- hide internal self-checks from the memo.

Do not:

- build a dashboard,
- run portfolio analysis,
- automate trading,
- create a full Excel / DCF model inside Standard,
- scrape the web by default,
- publish loose evidence lists,
- copy sell-side conclusions as system conclusions,
- use reference samples as evidence.

## Research Depths

The product has three planned depths:

| Depth | Role | Current status |
| --- | --- | --- |
| Quick | Triage memo with potential long/short space and balanced positives/negatives. No full valuation required. | Planned path |
| Standard | MVP investment memo with rating, root drivers, multiple bridge, triggers, and self-check. | Current focus |
| Deep | Full company research with detailed business analysis, peer work, and DCF / APV when appropriate. | Future phase |

All current rules and code should optimize Standard first.

## Input Contract

Use:

```text
inputs/
```

Accepted files:

- annual report PDF or text,
- official filing PDF,
- company IR / presentation,
- CSV/XLSX financial supplement,
- Markdown/JSON reviewed web research brief,
- user-provided institutional report,
- `evidence_patch.json` with verified values.

Standard request fields:

```text
company
ticker
market
source_files
optional_user_request
web_mode: off / auto / online
output_depth: standard
language: EN
holding_horizon: default 6-12 months
```

## Source Hierarchy

| Level | Use |
| --- | --- |
| A: official filings, annual reports, exchange/regulator filings | factual base |
| B: company IR, earnings release, transcript | company framing and official updates |
| C: Bloomberg/Wind/FactSet/Capital IQ/user spreadsheet | structured financial and market data |
| D: institutional reports | market framing and assumptions to test |
| E: reputable news / market data sites | recent events and quote context |
| F: social/community platforms | sentiment/noise only, not thesis evidence |

## Market Scope

Current source rules support US and China A-share research.

US preferred sources:

- SEC EDGAR,
- company investor relations,
- earnings releases,
- user-provided financial exports,
- reputable quote providers for market context.

China A-share preferred sources:

- cninfo,
- SSE / SZSE / BSE,
- company investor relations,
- Wind/Bloomberg/Choice exports if user provides them,
- Eastmoney/Snowball only as quote, sentiment, or lead context.

## Standard Flow

```text
1. Request Intake
2. Source Intake
3. Source Classification
4. Source Map
5. Evidence Extraction
6. Financial Snapshot
7. Industry / Cycle Calibration
8. Company Fundamental Read
9. Root Driver Identification
10. Market Expectation Gap
11. Multiple-Based Valuation Bridge
12. Rating and Confidence
13. Catalyst / Trigger Design
14. Risk Check
15. Internal Self-Check
16. Memo Compression
```

## Required Evidence Package

For Standard, seek the smallest reliable package that can support:

- current or latest available price,
- market cap if available,
- recent stock direction,
- business model,
- segment/product mix,
- revenue, profit, margin, cash-flow direction,
- balance sheet risk,
- industry/cycle context,
- upstream/downstream context when thesis-relevant,
- recent news or material events,
- market or institutional view,
- valuation inputs: EPS, EBITDA, FCF, P/E, EV/EBITDA, P/FCF, peer/history range,
- key risks and triggers.

Do not write all of this into the memo. Publish only what changes the decision.

## Root Driver Standard

Standard should normally publish two to three root economic drivers. A driver is
material when it can move group-level EPS, FCF, or fair value by roughly 10% or
more, calibrated by industry.

Driver test:

```text
size -> profitability -> cash conversion -> sustainability -> company specificity
-> market mispricing -> valuation impact -> observable failure
```

## Valuation Standard

Standard uses a multiple-based valuation bridge, not full DCF.

Steps:

```text
select valuation metric
normalize EPS / EBITDA / FCF
anchor to current, historical, peer, or external market-view multiple
adjust for growth, margin, FCF, ROIC, capital intensity, cyclicality, risk
build bear/base/bull range when inputs are clean
compare current price
set rating and confidence
```

Bear/Base/Bull cases require:

```text
root driver assumption
financial estimate
justified multiple
implied return
```

If inputs are missing or conflicting, show the data gap instead of inventing a
range.

## Standard Memo Shape

```text
# [Company] Research Memo

## Rating

## Bottom Line

## Core Thesis

## Thesis Conditions

## Market Expectation Gap

## Pre-DCF Valuation

## Catalysts / Rating Triggers

## Key Risks

## What To Verify Next
```

## Stop Rule

Stop when the selected depth can be written honestly:

```text
Can we state the root thesis?
Can we quantify why the drivers matter?
Can we support the thesis with reliable evidence?
Can we explain the expectation gap?
Can we build a disciplined valuation bridge or name the data gap?
Can we name what would change rating or confidence?
```

If not, produce a focused evidence request rather than manufacturing conviction.

## Output Rule

```text
If a sentence does not change rating, confidence, valuation range, trigger
design, downside risk, or next evidence request, remove it.
```
