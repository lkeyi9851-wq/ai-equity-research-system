# AI Equity Research System

`ai-equity-research-system` is an experimental AI-assisted equity research
workflow for educational and research purposes.

It is not a stock recommendation engine, financial advisor, trading system, or
production investment platform. The project focuses on research process quality:
source handling, evidence evaluation, company understanding, industry signal
interpretation, valuation reasoning, thesis formation, risk review, and
post-mortem learning.

The current public version is a prototype. It is shared to document system
design and invite feedback on research workflow, agent architecture, and
viewpoint-quality evaluation. It should not be used as the sole basis for
investment decisions.

The MVP is intentionally narrow: it turns a small local source package into an
English Standard-depth research memo with explicit thesis, confidence,
valuation bridge, triggers, and self-checks.

The project is not trying to be a full investment platform yet. It does not
do portfolio construction, dashboards, trading workflows, cloud deployment, or
full DCF modeling in the current MVP.

## What The MVP Does

Current path:

```text
local source package -> evidence extraction -> root driver -> valuation bridge -> research memo
```

Current scope:

- Local-first single-stock research
- English-only Standard memo
- Official filings, spreadsheets, notes, and compact web briefs as inputs
- Rating / confidence / trigger discipline
- Limited web augmentation when explicitly enabled

Out of scope for now:

- Portfolio and screening workflows
- Complex DCF / Excel model generation
- Dashboard UI
- Cloud deployment
- Fully autonomous web crawling

## Why This Is An Agent

The point is not just to generate prose. The system behaves like a constrained
research agent:

- It reads a source package and classifies evidence.
- It decides what is strong enough to enter the core thesis.
- It refuses to treat weak or missing transmission as an investable thesis.
- It tracks what evidence is still missing before rating confidence should rise.
- It can add a compact web brief, but it also distinguishes true research
  evidence from quote-only fallback.

In other words, the agent is defined by workflow discipline and judgment gates,
not by having a chat interface.

## Quick Start

Put your local research materials in `inputs/`.

Supported source types in the MVP:

- `.pdf`
- `.txt`
- `.md`
- `.json`
- `.csv`
- `.xlsx`

Run the Standard memo flow with your own local source package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp.ps1 -InputFile .\inputs -Company "Company Name" -Ticker TICKER
```

Or use a natural-language request:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp.ps1 -Request "Analyze Example Industrial Co. using inputs, concise memo"
```

Each run writes:

```text
[ticker-or-company]-source-notes.md
[ticker-or-company]-research-memo.md
[ticker-or-company]-summary.json
[ticker-or-company]-quality-score.json
```

`summary.json` is the structured artifact for downstream use. The memo is the
compressed external output. Internal self-checks should stay in the supporting
artifacts rather than being copied into the final memo.

## Web Research

Web context is optional and tightly scoped. The system does not scrape the web
by default. When web mode is enabled, it tries to produce a compact reviewed
web brief rather than dumping raw search output into the memo.

Generate an offline search log:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_web_research_brief.ps1 -Company "Example Industrial Co." -Ticker EXAMPLE -Market US
```

Attempt an online brief:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_web_research_brief.ps1 -Company "Example Industrial Co." -Ticker EXAMPLE -Market US -Online -ResearchProvider llm
```

Recommended local test provider: OpenRouter. It is OpenAI-compatible and can
be used with web-enabled model variants or a web plugin.

```powershell
$env:AI_EQUITY_WEB_PROVIDER = "llm"
$env:AI_EQUITY_WEB_LLM_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
$env:AI_EQUITY_WEB_LLM_API_KEY = "your_openrouter_key"
$env:AI_EQUITY_WEB_LLM_MODEL = "openai/gpt-oss-20b:free:online"
$env:AI_EQUITY_WEB_LLM_WEB_PLUGIN = "1"
$env:AI_EQUITY_WEB_LLM_WEB_ENGINE = "exa"
```

The LLM provider receives only company, ticker, market, evidence gaps, allowed
sources, and output schema. It does not receive local source files, file paths,
private notes, uploaded reports, memo drafts, or portfolio holdings.

## Runtime

Install dependencies in your target Python environment:

```powershell
python -m pip install -r requirements.txt
```

If needed, point the scripts at a specific interpreter:

```powershell
$env:AI_EQUITY_PYTHON = "C:\path\to\python.exe"
```

or:

```powershell
-PythonPath "C:\path\to\python.exe"
```

`.env.example` shows the expected environment variables for local testing.

## GitHub Notes

This repository is set up so that local runtime files, generated outputs,
private API configuration, and working input packages do not get committed by
default.

Ignored by `.gitignore`:

- `.venv/`
- `outputs/`
- local working files in `inputs/`
- raw reference files in `institutional_examples_raw/`
- local `.env` files

That keeps the public repo focused on the system logic rather than personal
research materials or test artifacts.

## Public Safety

The public repository should contain only framework, code, templates, and
synthetic or abstract examples. Do not commit private research notes, paid
research excerpts, raw institutional reports, real API keys, personal input
packages, generated outputs, or live investment theses.

## Core Docs

If you want the full design and judgment framework, start here:

- `PUBLIC_SAFETY.md`
- `ROADMAP_PUBLIC.md`
- `07_LIVE_PROJECT_MAP.md`
- `00_PROJECT_CHARTER.md`
- `03_RESEARCH_WORKFLOW.md`
- `09_MVP_RUNBOOK.md`
- `10_INVESTMENT_JUDGMENT_FRAMEWORK.md`
- `11_RATING_MODEL.md`
- `12_WEB_RESEARCH_PROTOCOL.md`
- `13_INPUT_OUTPUT_CONTRACT.md`
