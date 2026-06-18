---
name: financial-long-document-reader
description: Use when reading long financial documents for equity research, including annual reports, 10-K/20-F filings, analyst reports, prospectuses, investor presentations, industry reports, and long PDF source packs. Focus on fast source mapping, decision-relevant extraction, evidence quality, and concise reusable notes.
---

# Financial Long Document Reader

## Principle

Map first. Read selectively. Compress only after the investment question is clear.

Do not summarize a long document linearly. The goal is to locate the evidence that can change rating, thesis, valuation, risk, or confidence.

## Safety

- For GitHub or web references, inspect metadata and text first. Do not clone, download archives, install packages, or run unknown code unless the user approves and the source is checked.
- Treat user files as private. Do not upload, quote large passages, or expose raw document text in final output.
- Prefer local parsing of user-provided files.

## First Pass: Source Map

For each file, identify:

- source type: official filing, annual report, financial Excel, analyst report, industry report, reference sample, or supplement
- date, reporting period, company/ticker if visible
- page count or sheet list
- useful sections/pages
- extraction quality: clean, partial, table-heavy, scanned/OCR-needed, or noisy

Stop the first pass with a compact map, not a memo.

Web research brief:

- treat as a source map for current market context
- identify current price, market cap, fact date, source URL/publisher, recent events, and what each item could change
- keep only facts that can affect rating, thesis conditions, valuation bridge, risk, or confidence
- do not let web commentary override official filings or provided institutional data

## Reading Order By Source

Annual report or filing:

1. business and segment structure
2. revenue, margin, profit, cash flow
3. balance sheet and liquidity
4. management discussion and outlook
5. capital allocation
6. risk factors only if thesis-relevant
7. accounting/legal issues only if they can change valuation or risk

Financial Excel:

1. historical actuals
2. forecast years
3. revenue growth, gross margin, operating margin, EPS
4. operating cash flow, capex, FCF, working capital
5. price, shares, market cap, EV, multiples
6. scenario or sensitivity assumptions if present

Analyst report:

1. rating, target price, time horizon
2. estimate changes
3. valuation method and assumptions
4. thesis drivers
5. risks and downgrade triggers
6. evidence that should be verified in official sources

Industry report:

1. demand driver
2. supply/pricing/capacity
3. cycle indicator
4. regulation or policy
5. peer positioning
6. what this changes for the stock thesis

Web research brief:

1. current price and market cap
2. latest official results or announcement
3. material recent news
4. valuation or estimate changes
5. source reliability and freshness
6. direct decision impact

## Web Search Pattern

For stock research, treat web search as a separate public-data worker:

```text
query plan -> quote/news/search leads -> reviewed brief -> source package -> memo
```

Do not let the memo engine browse freely while reading private files. The web worker should not have local private-file access, and the memo engine should not trust unreviewed snippets as evidence.

Use mature finance/data projects as design references:

- OpenBB: reusable data layer.
- yfinance / AKShare: provider adapters with source and rights labels.
- EdgarTools: filings as typed structured objects before analysis.
- Qlib: data-health checks, offline/online modes, workflow separation.
- FinGPT: retrieval and task labels for finance NLP.

Ignore one-shot GitHub stock-agent demos unless they contribute a concrete, auditable pattern.

## Evidence Extraction

Extract in this shape:

```text
Claim:
Metric:
Period / unit / currency:
Source / page:
Reliability:
Thesis use:
Failure trigger:
```

Only keep evidence that affects:

- growth durability
- margin direction
- cash conversion
- balance sheet risk
- valuation range
- catalyst timing
- rating change

## Noise Filter

Remove or down-rank:

- legal disclaimers
- analyst biographies and distribution lists
- repeated headers/footers
- tables of contents unless used as a map
- generic strategy slogans
- marketing language without numbers
- risk boilerplate that does not connect to the thesis
- copied sell-side opinion without underlying evidence

## Conflict Handling

Use this hierarchy:

1. user-provided institutional exports
2. official filings and company releases
3. exchange/regulator sources
4. reputable financial data providers
5. analyst reports
6. news and secondary commentary
7. unverified web content

Do not average conflicts silently. Keep the number that best matches the decision and label the conflict.

## Output

For source notes, use:

```text
Source Map
Key Data
Decision Evidence
External Thesis Samples
Missing / Next
```

For final memo, do not show the reading process. Only show the compressed judgement.

## Stop Rule

Stop reading when the selected depth can answer:

```text
rating -> thesis -> conditions -> valuation bridge -> rating-change triggers
```

Continue only when the missing section could change one of those outputs.
