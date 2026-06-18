# Data Policy

## Data Standard

No key investment conclusion should depend on unverified data without being labeled.

## Required Metadata

For important data points, track:

- source,
- date retrieved,
- reporting period,
- currency,
- unit,
- whether it is actual, estimate, or assumption.

## Source Preference

Prefer sources in this order:

1. User-provided authoritative exports from Bloomberg, Wind, FactSet, LSEG, Capital IQ, or similar institutional sources.
2. Company filings, annual reports, earnings releases, and investor relations materials.
3. Exchange or regulator sources.
4. Reputable financial data providers.
5. Established news sources.
6. Secondary commentary.
7. Unverified web content.

## Preferred MVP Data Path

The first version should favor user-provided authoritative files over fragile scraping.

Good inputs:

- annual reports,
- quarterly reports,
- Bloomberg or Wind exports,
- investor presentations,
- earnings transcripts,
- CSV or XLSX financial tables,
- PDF filings from official sources.

The system should analyze what is available and clearly state what is missing. Lack of proprietary internal data does not block useful public-equity research, but it should limit confidence when the missing data matters.

For the earliest MVP, annual reports are the most reliable default input because they are official, comprehensive, and widely available.

## Reusable Knowledge Policy

The system may accumulate reusable industry context over time, but it should do so compactly.

Store:

- short industry summaries,
- key metrics and definitions,
- source links or source file references,
- last-updated dates,
- known open questions,
- important changes since the prior version.

Do not store:

- large copied source text by default,
- unsourced claims,
- stale industry narratives without dates,
- duplicate notes that do not improve future decisions.

The goal is to make later reports faster and better without creating a memory pile that becomes harder to trust than the original sources.

## Staleness Rules

Flag data as stale when:

- price data is not current for a market-sensitive conclusion,
- financial data excludes the latest reported quarter,
- analyst estimates are older than the latest major company event,
- news/event data misses recent earnings, guidance, regulation, or litigation.

## Conflict Handling

When sources disagree:

- do not silently average,
- record the conflict,
- prefer primary sources,
- explain which number was used and why.

## Web Scraping Caution

Automated scraping should respect source terms, rate limits, and stability.

For MVP work, use a mix of manual upload, structured files, and approved APIs before building fragile scrapers.

## Web Research Briefs

When current market context is needed, compress web search into a Markdown or JSON brief before it enters the source package.

Required fields:

- source URL or publisher,
- retrieved date,
- fact date,
- fact / estimate / opinion label,
- why it matters,
- what decision it could change.

Web research may update price, recent events, and valuation context. It should not override official filings or user-provided institutional exports.

## Output Labels

Use these labels when needed:

- Verified
- Partially verified
- Unverified
- Assumption
- Estimate
- Stale
- Conflict detected
