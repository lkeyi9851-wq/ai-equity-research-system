# Public Release Checklist

Use this checklist before pushing the repository to GitHub or sharing it with
external reviewers.

## Safe To Publish

- Core project docs that define scope, workflow, judgment rules, and MVP boundaries
- Source code in `src/`
- Local runner scripts in `scripts/`
- Reusable templates in `templates/`
- Public-facing README and environment template
- Abstract knowledge packs that describe research logic without reproducing third-party content

## Do Not Publish

- Local API keys or any real `.env` file
- Local input packages in `inputs/`
- Generated outputs in `outputs/`
- Raw institutional or sell-side materials in `institutional_examples_raw/`
- Inventory or training-pack files that reproduce proprietary report titles, snippets, target prices, or extracts
- Any local notebook, note, or scratch file containing private research context

## Current Repo Notes

- `.gitignore` excludes `.venv/`, `inputs/`, `outputs/`, local `.env` files, root `institutional_examples_raw/`, and `knowledge_packs/09_institutional_examples_raw/`.
- `knowledge_packs/09_institutional_examples_raw/` should remain private because it references third-party research files and extracted snippets.
- `README.md` is already rewritten into a GitHub-facing project overview.

## Recommended First Public Version

Publish:

- `README.md`
- `requirements.txt`
- `.env.example`
- `src/`
- `scripts/`
- `templates/`
- design and framework docs such as `00_` to `13_`
- selected abstract knowledge packs that do not reproduce proprietary content

Keep local-only:

- full test outputs
- working input folders
- raw institutional example repositories
- private or licensed research artifacts

## Final Pre-Push Check

1. Confirm `git status --short` does not show local inputs, outputs, or secrets.
2. Search the repo for institution names plus target-price language if you want a stricter public version.
3. Remove or rewrite any file that quotes or closely paraphrases licensed research content.
4. Keep public examples structural and abstract rather than source-specific.
