# Acceptance evidence

This file distinguishes implemented source, executed verification, and external blockers. The project is not declared complete.

| # | Criterion | Evidence / status |
|---|---|---|
| 1 | Fresh checkout startup | Documented local and Compose commands; local startup exercised. Fresh Compose build/startup PASSED on 2026-09-11. |
| 2 | Configuration and migrations | `.env.example`; idempotent version-1 migration in `backend/app/db.py`; Compose migration job before services. |
| 3 | Submission/uploads/history | API workflow tests and desktop/mobile E2E. |
| 4 | Real model-driven tool selection | Adapter and mock HTTP contract tests implemented. Live execution BLOCKED: no credentials. |
| 5 | All tool families | Fixture ingestion/analysis/artifacts verified; real public browser extraction PASSED (`evaluation/public-browser-result.json`); real Docker Python PASSED; live search BLOCKED on credentials. |
| 6 | Three combined workflows | Research→report; CSV→chart/XLSX; CSV+research→cited report/chart pass fixture workflow tests and benchmarks. Live versions unverified. |
| 7 | Streaming/reconnection | Persisted SSE IDs/replay tests; actual UI timeline/history reload in E2E. |
| 8 | Worker interruption | Expired lease test plus a real subprocess-kill test; PostgreSQL tests and actual worker-container SIGKILL/recovery PASSED. |
| 9 | Cancellation/budgets/approval | Guard cancellation, step/token/cost preflight, wrong-digest denial, uncertain Python reapproval tests. Actual running Python-container cancellation PASSED. |
| 10 | Security negative tests | Ownership, authentication, traversal, malformed uploads, formula injection, private DNS and redirects tested. All five real sandbox negative tests PASSED with Docker. |
| 11 | Artifact validity | PDFs opened by pypdf; XLSX opened by openpyxl with values/chart checks. PDF page rendered with Poppler for visual review. Native Excel UI not available. |
| 12 | Quality checks | Backend pytest/Ruff, frontend lint/typecheck/build, desktop/mobile Playwright. Final counts recorded below. |
| 13 | Benchmarks | 24 cases, four-part explicit rubric, actual fixture timing/usage/failure results; live result file says blocked. |
| 14 | No unresolved P0/P1 | NOT SATISFIED: P1 external verification blockers in ISSUES.md. |
| 15 | Engineering README | Setup, architecture, tools, permissions, durability and limits documented. |
| 16 | Demo and architecture | `DEMO.md`; Mermaid diagram in README. |
| 17 | Honest resume bullets | Measured fixture claim and explicit live/kernel placeholders in DEMO.md. |

## Executed commands

Run backend commands from `backend/`, frontend commands from `frontend/`:

```text
python -m pytest -q
python -m evaluation.run
python -m evaluation.run --live
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

Ruff from root: `python -m ruff check backend sandbox`.

Earlier local evidence on 2026-09-10 (superseded for container checks by the results below):

- `python -m pytest -q`: **32 passed, 5 skipped**, 26.30 seconds. Skips are actual Docker isolation tests. Two upstream test-client deprecation warnings remain; no test failures.
- `python -m ruff check backend sandbox scripts`: **passed**.
- `python -m evaluation.run`: **24/24 cases met rubric**, 21 completed tasks and 3 expected controlled failures. Median 2.734 seconds; sum 65.625 seconds. Zero model tokens/cost in fixture mode. Actual per-case results are in `evaluation/fixture-results.json`.
- `python -m evaluation.run --live`: **blocked** by missing live configuration. No live completion metrics were invented.
- `python -m evaluation.public_browser`: **passed**, real Chromium extraction of `https://example.com`, no fixture or model call. Result saved in `evaluation/public-browser-result.json`.
- `npm run lint`, `npm run typecheck`, `npm run build`: **passed** with Next.js 16.3.4.
- `npm run test:e2e`: **8 passed**, 21.4 seconds, desktop and mobile. Covers real task submission/upload, worker results, download, citations, reload/history, template/settings controls and horizontal overflow.
- `pip-audit -r backend/requirements.txt`: **zero known vulnerabilities** after upgrades; `evaluation/dependency-audit.json`.
- `npm audit`: **zero known vulnerabilities** after ESLint update; `evaluation/frontend-audit.json`. Formatter installation was also audited clean.
- PDF opened and rendered with Poppler; rendered page visually inspected without clipping/overlap. XLSX reopened, numeric cells and native chart object checked with openpyxl. Sample outputs are in `evaluation/samples/`; native Excel is unverified.
- `python scripts/smoke_demo.py`: **passed** against the final running API/worker with `examples/sales.csv`. Confirmed Beauty 10,000, Games 14,600 and Books 21,000. Five steps, 3.313 seconds worker time, zero model tokens. Evidence: `evaluation/demo-result.json`.

No test was weakened or removed to hide a failure. A configuration-string-only sandbox check was removed because it did not prove isolation; real container tests remain explicitly skipped.

## Scope of results

No reported fixture score measures real LLM quality. Citation checks establish saved-source traceability, not semantic support. Sandbox command configuration does not prove kernel isolation. The PostgreSQL suite and Docker/Redis integration have now passed. Live model/search and semantic source-support results remain necessary before closing full project acceptance.

## Redesign verification

The eight E2E checks ran against `npm run build` + `npm start` (the standalone production server), with the real local API and worker. They cover sample upload, combined CSV/research execution, chart and inline report, PDF download, Markdown preview, citations, event history, reload restoration, unavailable saved-task recovery, history search, keyboard settings and unauthorized state. Axe WCAG 2 A/AA and 2.1 AA checks reported no violations on the tested home/report/settings views at both viewport sizes; this is automated coverage, not a blanket accessibility certification.

Screenshots: `frontend/test-results/workspace-desktop.png`, `workspace-mobile.png`, `report-desktop.png`, `report-mobile.png`. Revised PDF: `evaluation/samples/report-page-1.png`. Fixed container packaging for public assets and non-root Chromium lookup. `.github/workflows/verify.yml` automates Linux/Compose checks but has not run remotely in this workspace.

## Docker acceptance — 2026-09-11

**PASSED.** Fresh Docker build/startup, successful migration, PostgreSQL 17.4, Redis PONG, API/worker/web and broker running. Docker Desktop 4.84.0 / Engine 29.6.2 / Compose v5.3.1, Linux amd64 through WSL2.

- PostgreSQL + real Docker suite: **39 passed, 0 skipped, 0 failures**, 28.59 seconds. Includes all ownership/budget/approval/recovery tests, five kernel negative tests, approved NumPy/Matplotlib PNG generation and actual running-container cancellation. Two upstream test-client deprecation warnings remain.
- Browser UI against Compose: **8 passed**, 22.9 seconds; includes accessibility checks, sample uploads, reports/downloads, citations and reload.
- Real public Chromium extraction from the non-root worker: **passed** for example.com; no model and no browser fixture.
- Worker container SIGKILL while an action was persisted as pending: **passed**, 35.609 seconds to recovered completion, four unique artifacts, downloads intact.
- Flagship Compose smoke: **passed**, Beauty/Games/Books verified in the XLSX, five steps, 4.709 seconds worker time; PDF parses successfully.
- Ruff: **passed** after adding test/recovery helpers.
- Live evaluation attempted again: **blocked**, missing LLM_API_KEY, LLM_MODEL and SEARCH_API_KEY. Auth/broker secrets now exist locally.

Evidence: `evaluation/docker-verification.json`, `evaluation/docker-tests.xml`, `evaluation/docker-recovery-result.json`, `evaluation/demo-result.json`, `evaluation/live-results.json`. Reproduction: README and `.github/workflows/verify.yml`. CI source is updated; remote CI has not run.
