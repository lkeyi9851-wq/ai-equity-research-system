# AI Equity Research System Charter

## Purpose

Build a lean AI research organization that can collect market and company data, analyze it with discipline, and produce clear equity research reports or portfolio ideas.

The system should help a user move from a small prompt to a high-quality investment memo:

> Analyze a stock or stock group, choose a research depth, identify what matters, show evidence, expose risk, and produce a report that is useful without being bloated.

## North Star

Less is more, but only after truth survives compression.

The goal is not to create many agents, many dashboards, or many pages. The goal is to compress complex financial reality into a few well-supported judgments.

## What This System Is

- A research workflow for public equities.
- A coordinated set of AI agents with clearly bounded roles.
- A living project map that can be updated as the system changes.
- A report-generation engine with selectable depth.
- A quality-control layer for evidence, assumptions, and risks.

## What This System Is Not

- It is not a black-box stock picker.
- It is not a financial advisor.
- It is not allowed to fabricate data.
- It is not designed to maximize agent count.
- It is not designed to produce long reports by default.

## Ideal User Experience

The user should be able to give a short, natural request:

```text
Analyze AMD, standard depth, 6-12 month horizon, medium risk.
```

The system should infer the research plan, gather or request missing data, analyze the business and valuation, surface risk, and produce a concise report.

## Operating Belief

High-quality investment work comes from:

- clean data,
- clear assumptions,
- independent risk review,
- disciplined compression,
- and a final answer that knows what would make it wrong.

## First Build Target

Create a working MVP that supports single-stock research before expanding into screening, portfolio construction, automated monitoring, and backtesting.

Initial scope:

- market: US equities,
- output format: Markdown,
- language: match the user's input unless explicitly specified,
- research style: institutional-quality depth compressed into the smallest useful report.
