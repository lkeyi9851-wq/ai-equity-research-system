# Web Research Protocol

## Purpose

Use web research only when it can change:

- current price or market cap,
- latest reported financials,
- recent company events,
- valuation bridge,
- thesis condition probability,
- rating-change triggers.

Do not browse to make the report look fuller.

## MVP Boundary

Do:

- collect a compact web research brief,
- record source URL, publisher, retrieval date, and fact date,
- separate fact, estimate, and opinion,
- prefer official/company/exchange/regulator sources,
- use financial data providers for current quote and market context when available.

Do not:

- scrape sites by default,
- bypass paywalls or anti-bot systems,
- download or run unknown files,
- store raw web pages,
- let web commentary override official filings.

## Source Priority

1. Company investor relations, exchange, regulator.
2. Official earnings releases and filings.
3. Reputable market data providers.
4. Established financial news.
5. Analyst reports supplied by the user.
6. Social platforms and forums only as sentiment/noise checks, not evidence.

## Market-Specific Source Whitelist

### US

Primary:

- SEC EDGAR / `data.sec.gov` for filings, XBRL facts, 10-K, 10-Q, 8-K.
- Company investor relations for releases, presentations, and guidance.

Secondary:

- Reputable quote and market data providers for price, market cap, multiples.
- Established financial news for material event leads only.

### China A-share

Primary:

- 宸ㄦ疆璧勮 / `cninfo.com.cn` for official company announcements.
- 涓婁氦鎵€ / `sse.com.cn`, 娣变氦鎵€ / `szse.cn`, 鍖椾氦鎵€ / `bse.cn` for exchange disclosures and supervision.
- Company investor relations and official releases.

Secondary:

- 涓滄柟璐㈠瘜銆佹柊娴储缁忋€丄KShare-style adapters for quote, valuation, and market snapshot only.
- Treat third-party琛屾儏 and浼板€?as helper data, not as official evidence.

Do not default to Yahoo Finance for A-share research. If used at all, label it as secondary quote context.

### Hong Kong

Primary:

- `hkexnews.hk` for official announcements and reports.
- Company investor relations for releases and presentations.

Secondary:

- Reputable quote providers for price and market cap.
- Established financial news for material event leads only.

### Other Markets

Use:

- local exchange,
- local regulator,
- company investor relations,
- reputable market data providers,
- established financial news only for event leads.

## Provider Adapter Candidates

Selection rule:

```text
official source or high-adoption project > clear data rights > stable API > market fit > ease of use
```

Do not install or run any provider package before a separate safety review.

| Provider / project | Best use | Market fit | Status | Safety note |
| --- | --- | --- | --- | --- |
| OpenBB | unified data layer and future provider router | global | preferred architecture reference | high adoption; still label upstream provider and terms |
| yfinance | quote, market snapshot, Yahoo search/news, sector/screener | US/global, secondary for A-share | candidate adapter | unofficial Yahoo API; personal/research use only; not official evidence |
| AKShare | China market quote, indicators, valuation helpers | China A-share | candidate adapter | many upstream sources; label source and data risk |
| EdgarTools | SEC filings, XBRL facts, 10-K/10-Q/8-K structured objects | US | candidate filing adapter | official SEC data; requires identity/rate-limit discipline |
| SEC EDGAR APIs | official filings and company facts | US | primary source | official; use direct APIs where simple |
| Yahooquery | broader Yahoo Finance endpoint coverage | US/global | watchlist, not first choice | lower adoption than yfinance; unofficial; avoid premium/login/Selenium path |
| Polygon / Finnhub / Alpha Vantage / IEX | paid or key-based market data | mainly US/global | future optional adapters | only with user-provided API key and terms review |
| Finviz wrappers | screens and valuation snapshots | US | avoid for MVP | often page-scrape style; fragile and terms-sensitive |

Current MVP decision:

- Build provider interface and compact web brief first.
- Do not auto-install provider libraries.
- For A-share, do not default to Yahoo.
- For US filings, prefer SEC/EdgarTools pattern over generic web search.
- For prices, treat every non-exchange quote as market context, not official evidence.

## Web Research Brief

Every web search pass should first be compressed into one Markdown or JSON file in `outputs/` for review. Move it into `inputs/` only after the sources are acceptable:

```text
# Web Research Brief

Company:
Ticker:
Retrieved at:
Search scope:

## Market Snapshot
- Current price:
- Market cap:
- Source:
- Fact date:

## Recent Events
- Fact:
  Source:
  Fact date:
  Why it matters:
  Could change:

## Valuation / Estimate Updates
- Fact:
  Source:
  Fact date:
  Why it matters:
  Could change:

## Noise Removed
- Items ignored:
- Reason:
```

The MVP parser classifies files with `web`, `search`, `news`, `quote`, `market`, `source_url`, `retrieved_at`, or `Web Research Brief` as `web_research`.

Generated briefs are not evidence until reviewed and moved into the source package.
Search logs and query lists are audit/debug artifacts only. They do not enter the main memo workflow.

## LLM Web Research Provider

The MVP may use an external LLM provider as a public web research assistant, but
only behind a privacy gate.

Allowed payload:

```text
company
ticker
market
evidence gaps
allowed sources
output schema
```

Forbidden payload:

```text
local file contents
local file paths
private user notes
uploaded report text
memo drafts
portfolio holdings
```

The LLM provider must return evidence cards, not ratings:

```text
claim
source_url
publisher
source_tier
fact_date
label
why_it_matters
could_change
confidence
query_or_gap
```

The local memo engine decides whether a card can affect rating, confidence,
valuation bridge, trigger design, or next evidence request.

## Source Gate

LLM-provided source tiers are advisory only. The local system re-checks each
evidence card by URL domain:

- official domains may support facts,
- secondary market-data domains may support quote, market cap, and valuation
  context,
- news domains may support recent-event leads,
- social/forums/commentary are rejected unless explicitly used as sentiment
  noise,
- `source_url=not_found` with `label=data_gap` is preserved as a data gap, not
  evidence.

Rejected sources and data gaps must appear in the brief audit section and must
not strengthen rating or confidence.

## Mainline Integration Gate

The web branch can enter the main memo workflow only when all conditions pass:

- Output is a compact brief in `outputs/`, not raw web pages.
- Every item has source URL or publisher, retrieved date, and decision impact.
- Provider safety status is visible in the brief.
- Search leads are filtered by market whitelist.
- Non-whitelisted, social, forum, and copied-commentary sources are rejected.
- The brief does not contain local private file content.
- The user or operator explicitly moves the reviewed brief into `inputs/`.

Until then, web output is context only and must not affect rating or thesis.

## Search Query Set

For one stock, use the smallest useful set:

```text
[ticker company] current price market cap
[company] investor relations latest results
[company] latest earnings release
[company] guidance latest
[company] latest news material event
[company] valuation PE PFCF EV EBITDA
```

For the English-only MVP, keep A-share search terms in English and rely on
official-domain constraints first:

```text
[ticker company] latest announcement / annual report
[company] investor relations / latest results
[ticker company] share price / market cap
[company] consensus estimate / valuation / PE
```

Localized Chinese queries can be added in a later multilingual phase.

## Decision Rule

Web evidence enters the memo only if it updates one of these:

```text
rating -> thesis condition probability -> valuation bridge -> trigger
```

Otherwise it stays in source notes or is discarded.

## High-Quality GitHub Reference Scan

Use high-signal, widely adopted finance/data projects as inspiration. Do not learn from small demo agents unless they solve a specific problem better.

Read-only references:

- `OpenBB-finance/OpenBB`: data should be connected once and reused across Python, APIs, Excel, dashboards, and agents.
- `ranaroussi/yfinance`: quote/news/sector/screener access is useful, but provider terms and data freshness must be explicit.
- `akfamily/akshare`: China-market data needs dedicated adapters and source-risk labels.
- `dgunning/edgartools`: filings should become typed, structured objects before analysis; SEC access needs identity, rate limits, and clean text for RAG.
- `microsoft/qlib`: serious financial research separates data, features, model workflow, backtest, report, offline/online modes, and data-health checks.
- `AI4Finance-Foundation/FinGPT`: finance NLP is data-centric; real-time data, retrieval, task labels, and benchmark discipline matter more than generic LLM prose.
- `AI4Finance-Foundation/FinRL`: trading/research systems need decoupled data, environment, model, backtest, and risk-control layers.

Adopt:

- provider adapters, not ad hoc scraping,
- explicit source, date, freshness, rights, and rate-limit labels,
- offline-first local private-file analysis,
- public web worker isolated from private files,
- reviewed web briefs as the only bridge into memo generation,
- data-health checks before model or memo confidence,
- cache raw market data separately from LLM analysis,
- every web item declares the decision it could change.

Reject:

- one-shot stock-agent demos,
- social sentiment as evidence,
- LLM conclusions based only on search snippets,
- silently mixing private files and public browsing,
- web search that changes rating without source trail,
- backtests or predictions without data provenance and leakage checks.

## Safety Rule

Before using GitHub or web code:

- inspect repository metadata, README, and file list first,
- do not clone, install, or execute without explicit approval,
- prefer reading docs through trusted interfaces,
- never upload private user files to third-party services.
- default generated briefs to `outputs/`, not `inputs/`, so unreviewed web results do not affect a memo.

External-code rule:

- Default to zero third-party runtime dependencies.
- Any future provider package must pass a separate safety review before use.
- Review includes: package source, maintainer reputation, license, dependency tree, install scripts, network calls, telemetry, file access, credential handling, and terms of service.
- Provider adapters must not read `inputs/` or any private local file.
- Provider adapters may return public market context only; they must not upload user prompts, reports, spreadsheets, or generated memos.
