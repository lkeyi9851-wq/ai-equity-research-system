---
name: web-research-brief
description: Use when an equity research memo needs current public market context, including current price, market cap, latest official announcements, recent material events, consensus/valuation context, or rating-change triggers. This skill produces a compact reviewed web research brief for the main memo workflow, not a user-facing query plan.
---

# Web Research Brief

## Purpose

Add current public context to a single-stock research memo without exposing private local files.

This skill supports the main report only when web data can change:

```text
rating -> thesis condition probability -> valuation bridge -> rating-change trigger
```

## Safety Boundary

- Do not read `inputs/` or private local files inside the web worker.
- Do not upload user reports, spreadsheets, prompts, or generated memos.
- Do not clone, install, or run third-party packages unless separately reviewed and approved.
- Store generated web output in `outputs/` first.
- Only compact reviewed briefs may enter the memo source package.

## When To Use

Use this skill when the memo lacks one of:

- current price or market cap,
- latest official result or announcement,
- material recent event after the uploaded filings,
- valuation or consensus context,
- rating-change trigger that depends on recent public information.

Do not use it merely to make a report look fuller.

## Market Source Rules

US:

- Primary: SEC / data.sec.gov, company IR.
- Secondary: reputable quote providers and established financial news.

China A-share:

- Primary: cninfo, SSE, SZSE, BSE, company IR.
- Secondary: Eastmoney, Sina, AKShare-style adapters for market snapshot only.
- Do not use Yahoo as the default A-share source.

Hong Kong:

- Primary: HKEXnews, company IR.
- Secondary: reputable quote providers.

## Output Shape

The output should be a compact `Web Research Brief`:

```text
Market Snapshot
Recent Events
Valuation / Estimate Updates
Audit
```

Keep only facts that can change the memo. Do not include the search process unless needed for audit.

## Main Memo Handoff

The memo engine should use the brief as `web_research` evidence.

Map web facts into:

- `market_context` for price, market cap, trading context,
- `recent_events` for official announcements and material news,
- `valuation_context` for consensus, multiples, target price context,
- `current_price` for valuation bridge inputs.

Web facts can refresh valuation and triggers. They must not override official filings or user-provided institutional data.
