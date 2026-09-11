# Recruiter walkthrough (about 5 minutes)

1. Start API, worker and UI using README. Point out **Demo mode** before running anything. Explain that research is fixture-backed, while calculations and artifact generation operate on the upload.
2. Click **Load example** to attach the sample CSV and fill the flagship goal, then click **Run task** (or Ctrl+Enter).
3. Read the generated chart and report in Overview. Open Activity to inspect ingestion, calculation, fixture search and report events; expand Action details for a structured result. Explain that these are observable actions, not private chain-of-thought.
4. Confirm the metric: ascending **sum of revenue**, not profit or growth. Expected totals: Beauty 10,000; Games 14,600; Books 21,000; Apparel 26,100; Outdoor 32,800; Home 43,900. The weakest three are Beauty, Games and Books.
5. Preview the chart; download/open the XLSX and PDF. Inspect external source excerpts, clearly labeled fictional market context, and experimental hypotheses.
6. Reload the page: the same saved task opens automatically. Return to Workspace or use All tasks to search previous work; on mobile, open the navigation drawer. Events and artifacts remain available.
7. Run a malformed CSV from an evaluation case. Show the bounded failure and retained partial result; it never becomes a successful analysis.
8. Show the architecture diagram in README and the real process-kill recovery test. Explain leases, Redis notifications with DB reconciliation, and uncertain-action reapproval.

For a live demo, first configure credentials and validate the Docker profile. Use a small search query. Ask for a Python calculation, review the exact approval payload, and demonstrate denial. Do not present a fixture screen as live behavior.

An executable fixture smoke demonstration is also included: run `.venv/Scripts/python.exe scripts/smoke_demo.py` on Windows (or `.venv/bin/python scripts/smoke_demo.py` on Unix) while API and worker are running. It checks Beauty/Games/Books against the actual workbook and saves the generated artifacts in `evaluation/samples/`. The Docker smoke run passed in 4.709 seconds of recorded worker time, using five tool steps and zero model tokens.

## Portfolio claims

Safe measured template:

> Built a Next.js/FastAPI agent workspace with persisted execution events, task ownership, bounded tool calls, and downloadable PDF/XLSX artifacts; validated 24 deterministic benchmark cases, including three expected failure cases.

Use only after completing live evaluation:

> Implemented a model-driven tool runtime achieving **[measured N/M live task completions]**, with **[measured median latency]** and **[measured estimated cost]** on **[provider/model/date]**.

Measured container claim (2026-09-11):

> Validated Docker-isolated Python with five kernel boundary checks and PostgreSQL-backed approval/cancellation workflows; all 39 backend tests passed on Docker Engine 29.6.2, including a real generated chart. Recovered an interrupted worker container in 35.6 seconds without duplicate artifacts.

Never convert fixture success into an autonomous-agent accuracy claim. Do not claim exactly-once side effects.
