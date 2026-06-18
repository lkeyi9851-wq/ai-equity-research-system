# Input / Output Contract

Purpose: keep the local Standard MVP easy to run now and wrap as a future API
without leaking local paths or private context.

## Request

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
optional evidence_patch.json
```

Rules:

- MVP output is English only.
- Current MVP is Standard depth.
- Chinese sources may inform analysis but do not change output language.
- Cloud requests should upload only required files and parameters, never local
  absolute paths.
- Web mode stays `off` or `auto` by default unless explicitly enabled.
- `auto` generates a targeted offline search log; it does not add web content to
  the memo.
- A compact reviewed web brief can enter the source package.
- Online research provider may be `search`, `llm`, or `auto`.
- `llm` provider receives only company, ticker, market, evidence gaps, allowed
  source list, and output schema. It must not receive local files, file paths,
  private notes, uploaded report text, memo drafts, or portfolio holdings.
- `evidence_patch.json` may provide verified current price, FCF/share, source
  P/FCF, share count, target price, EPS, source labels, and date labels.
- Evidence patches override only explicit fields and must be labeled.
- Sell-side reports are optional market-framing inputs, not final evidence by
  themselves.

## Artifacts

```text
research-memo.md
source-notes.md
summary.json
quality-score.json
```

`research-memo.md` is the concise external output.

`source-notes.md` is the audit layer for extracted evidence and source map.

`summary.json` contains:

- request contract snapshot,
- source file names,
- rating and confidence,
- root driver assessment,
- materiality and expectation-gap assessment,
- valuation reconciliation,
- pre-DCF valuation cases when available,
- autonomous research plan,
- evidence gaps and mode actions,
- source sufficiency gate,
- market expectation gap,
- DCF readiness gate,
- thesis / trigger gate results,
- internal self-check.

Do not show internal self-check in the final memo.

## LLM Web Research Provider

Optional environment variables:

```text
AI_EQUITY_WEB_PROVIDER=llm
AI_EQUITY_WEB_LLM_ENDPOINT=https://.../v1/chat/completions
AI_EQUITY_WEB_LLM_API_KEY=...
AI_EQUITY_WEB_LLM_MODEL=...
AI_EQUITY_WEB_LLM_WEB_PLUGIN=1
AI_EQUITY_WEB_LLM_WEB_ENGINE=exa
AI_EQUITY_WEB_LLM_WEB_MAX_RESULTS=5
```

The provider must return evidence cards, not a memo or rating:

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

The local memo engine remains responsible for source gating, thesis
transmission, valuation bridge, rating, confidence, and triggers.

LLM-reported source tiers are reclassified locally by URL domain. Rejected
sources and `data_gap` cards stay in the audit trail and do not strengthen the
memo.

`quality-score.json` contains deterministic gates:

- Less is More,
- thesis transmission,
- valuation discipline,
- trigger quality,
- research autonomy,
- next improvement target.

## Evidence Patch

Use `templates/evidence_patch.json`.

Purpose:

- feed verified missing values back into the pipeline,
- resolve valuation conflicts when the numbers reconcile,
- support multiple-based valuation cases,
- trigger DCF readiness only after inputs are clean.

The patch should not replace official filings or user-provided financial data.

## Future API Shape

```text
POST /research-memo
```

Input:

- multipart files or object-storage references,
- JSON request fields above.

Output:

- memo markdown,
- notes markdown,
- structured summary JSON,
- optional quality JSON.

Deployment target remains undecided. Design for a generic API service first.
