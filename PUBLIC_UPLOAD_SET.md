# Public Upload Set

Use this file as the practical upload guide for the first public version of
`ai-equity-research-system`.

## Green

Safe to upload directly in the first public version:

- `README.md`
- `.gitignore`
- `.env.example`
- `requirements.txt`
- `PUBLIC_RELEASE_CHECKLIST.md`
- `00_PROJECT_CHARTER.md`
- `01_AGENT_ORG.md`
- `02_CORE_PRINCIPLES.md`
- `03_RESEARCH_WORKFLOW.md`
- `04_REPORT_DEPTH_LEVELS.md`
- `05_DATA_POLICY.md`
- `06_ROADMAP.md`
- `07_LIVE_PROJECT_MAP.md`
- `08_RESEARCH_MANAGER_PROTOCOL.md`
- `09_MVP_RUNBOOK.md`
- `10_INVESTMENT_JUDGMENT_FRAMEWORK.md`
- `11_RATING_MODEL.md`
- `12_WEB_RESEARCH_PROTOCOL.md`
- `13_INPUT_OUTPUT_CONTRACT.md`
- `src/`
- `scripts/`
- `templates/`
- `skills/`
- `diagrams/`
- `knowledge_packs/01_valuation_engine/`
- `knowledge_packs/02_triggers_engine/`
- `knowledge_packs/03_thesis_quality/`
- `knowledge_packs/04_source_registry/`

## Yellow

Upload only after a manual review, because these files are more case-specific
even if they currently look abstract:

- `knowledge_packs/05_sany_case_study/`
- `knowledge_packs/10_curated_examples/`

Review rule:

- Keep them only if they describe logic, examples, and failure modes in your
  own words.
- Remove them if they reproduce third-party report language too closely or rely
  on proprietary snippets, titles, or target-price details.

## Red

Do not upload in the first public version:

- `inputs/`
- `outputs/`
- `institutional_examples_raw/`
- `knowledge_packs/09_institutional_examples_raw/`
- `.venv/`
- any local `.env` file

Reason:

- These folders contain personal working materials, generated test artifacts,
  or references to licensed third-party research content.

## Recommended First Public Repo

If you want the cleanest first version, upload exactly this shape:

- core docs: `00_` through `13_`
- project entry files: `README.md`, `.gitignore`, `.env.example`, `requirements.txt`, `PUBLIC_RELEASE_CHECKLIST.md`
- implementation: `src/`, `scripts/`, `templates/`, `skills/`, `diagrams/`
- abstract research packs only: `knowledge_packs/01_valuation_engine/`, `02_triggers_engine/`, `03_thesis_quality/`, `04_source_registry/`

## Recommended Holdback

Keep local for now:

- all real input packages
- all generated memo outputs
- all raw institutional examples
- the full institutional example inventory layer
- case-study packs until you finish a manual review

## Simple Upload Rule

If a file helps explain your system design, judgment framework, or code logic,
it is usually publishable.

If a file contains real research materials, third-party report traces, private
working context, or generated test artifacts, keep it local.
