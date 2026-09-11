# Findings and limitations

## Latest live verification — 2026-09-11

Model credentials are configured and Tavily keyless REST search is verified in Docker. The live 24-case benchmark ran with Groq openai/gpt-oss-20b: two research tasks completed, one passed all checks, and 22 cases stopped on provider HTTP 429. The education report failed citation traceability. Provider failures are no longer counted as expected invalid-input passes. See evaluation/live-results.json. Next: rerun with pacing matched to provider quota, investigate citation selection, and review factual support. The earlier missing-credentials notes below are historical and superseded.

## Open / external verification

- **P1 verification blocker — live model/search credentials absent.** The provider adapter has structured-request unit coverage, but real model selection, Brave research and combined live workflows remain unverified. Configure the `.env.example` values and rerun `python -m evaluation.run --live`. `evaluation/live-results.json` records the blocked run.
- **P2 — citation support evaluation.** Source IDs/excerpts are traceable and unknown IDs are rejected. The benchmark does not establish that every generated interpretation follows from those excerpts. Live human source-support scoring is still required.
- **P2 — uncertain side-effect recovery.** Python interruption requires renewed exact-action approval. Outputs from an uncommitted execution may be lost, and unreferenced local files may remain. Exactly-once execution is not promised.
- **P2 — output-language limits.** PDF standard fonts do not cover every Unicode script. OCR and multilingual shaping are unsupported. UTF-8 file ingestion is supported.
- **P2 — development identity.** Demo intentionally shares one local identity; live uses server-issued short-lived JWTs. Public signup/login, TLS termination, backups, quotas per identity, storage garbage collection and an external identity provider are deployment work, not claimed as implemented.
- **P3 — browser scope.** Public extraction disables JavaScript and subresources; interactive websites and account actions are intentionally unsupported.

## Fixed during review

- Rebuilt the frontend around task submission, real history rows and inline reports; added file previews, sample loading and keyboard/mobile navigation.
- Corrected low-contrast secondary text; automated accessibility checks pass on the exercised workspace, report and settings screens.
- Added URL-based task recovery, unavailable-task feedback and guards against stale responses after switching sessions.
- Fixed missing public files in the production frontend image and Chromium installation lookup for the non-root backend image. Added a standalone production launcher and a Linux/Compose CI workflow; the workflow still needs an actual remote run.

- Replaced uncancellable fixed-tool threads with child processes so cancellation can terminate parsing/report work.
- Added conservative provider-budget reservation before dispatch, retaining reservations after uncertain outcomes.
- Added exact-action approval validation, denial/resume enforcement, and recovery approval for interrupted Python.
- Added row locking to upload attachment/control mutations for PostgreSQL concurrency.
- Added upload request-length and browser-origin checks.
- Added mobile saved-task navigation after UI review.
- Corrected the frontend Playwright peer dependency and upgraded audit-flagged Python/ESLint packages. Final audit evidence is in `evaluation/`.

There are no known remaining P0 defects in the locally exercised fixture paths. The remaining live-provider verification blocker above mean the overall execution contract is **not complete**.

## Verified and closed — 2026-09-11

Docker infrastructure is now available and verified. Fresh Compose build/startup, PostgreSQL, Redis, non-root Chromium, all five kernel negative tests, approved Python chart output, and real container cancellation passed. The complete PostgreSQL/Docker suite passed 39 tests without skips; eight frontend tests passed against Compose. SIGKILL worker recovery completed in 35.609 seconds with no duplicate artifacts. Evidence is in `evaluation/docker-verification.json` and `evaluation/docker-tests.xml`.

The live evaluator and operator token helper now load the root `.env`, preventing a configured root file from being overlooked when commands run from backend/. The three remaining missing configuration values are LLM_API_KEY, LLM_MODEL and SEARCH_API_KEY. No model/search success is claimed.
