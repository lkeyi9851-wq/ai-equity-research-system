# Roadmap

## Phase 1: Living Architecture

Goal: Make the project visible and editable.

Deliverables:

- project charter,
- agent organization,
- core principles,
- research workflow,
- report depth levels,
- data policy,
- diagrams.

Status: started.

## Phase 2: Codex Research Skill

Goal: Create the first Codex skill that guides equity research work.

Deliverables:

- `equity-research-agent/SKILL.md`,
- default report workflow,
- depth selection rules,
- risk disclosure rules.

## Phase 3: Single-Stock MVP

Goal: Generate a useful standard-depth report for one stock.

Inputs:

- ticker,
- depth,
- horizon,
- risk preference.

Outputs:

- research memo,
- source table,
- key charts if data is available.

Initial constraints:

- US equities first,
- Markdown first,
- language follows user input unless specified,
- industry context included only where it affects the stock thesis.
- authoritative user-provided files preferred over fragile scraping.
- annual reports are the first default reliable data input.

## Phase 4: Visualization Layer

Goal: Make project structure and research outputs visual.

Deliverables:

- agent org chart,
- workflow diagram,
- report map,
- stock summary dashboard.

## Phase 4.5: Language Layer

Goal: Support user-selectable report language without bloating the report.

Planned modes:

- Chinese,
- English,
- bilingual Chinese-English.

Possible future agent:

- Language & Localization Agent.

This agent should only be added if language quality becomes a distinct failure mode. Until then, language behavior can remain part of the Report & Visualization Agent.

## Phase 5: Data Automation

Goal: Reduce manual data collection.

Possible paths:

- user-provided CSV/XLSX files,
- financial data API,
- company filings parser,
- carefully scoped web extraction.

## Phase 6: Multi-Stock And Portfolio Research

Goal: Compare stocks and produce portfolio ideas.

Modules:

- stock screening,
- peer comparison,
- portfolio weighting,
- correlation and concentration checks,
- risk-adjusted ranking.

## Phase 7: Monitoring And Updates

Goal: Track changes over time.

Modules:

- watchlists,
- earnings reminders,
- thesis change alerts,
- report refresh workflow.

## Future: Reusable Industry Memory

Goal: Let research become more efficient as more stocks are analyzed.

Approach:

- keep compact industry summaries,
- date every reusable note,
- link each summary to source files,
- update summaries only when new information changes the thesis,
- avoid storing large raw documents unless needed.

## Open Decisions

- Which authoritative data format should be supported first after annual reports: Bloomberg export, Wind export, IR PDF, or CSV/XLSX?
- How opinionated should the final rating be?
- When should industry analysis become its own agent instead of part of Company & Industry Analyst?
