"""24-case evaluator. Fixture execution is deterministic; live runs require credentials.

Run from backend: python -m evaluation.run [--live]
Never use fixture results as live agent accuracy evidence.
"""

import argparse
import asyncio
import io
import json
import os
import platform
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

parser = argparse.ArgumentParser()
parser.add_argument("--live", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
if args.live:
    load_dotenv(root / ".env", override=False)
out = root / "evaluation"
out.mkdir(exist_ok=True)
temp = Path(tempfile.mkdtemp(prefix="autoagent-eval-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (temp / "eval.db").as_posix()
os.environ["STORAGE_ROOT"] = str(temp / "files")
os.environ["REDIS_URL"] = ""
os.environ["RATE_LIMIT_WRITES"] = "1000"  # Isolated benchmark client; production quotas remain unchanged.
os.environ["MODE"] = "live" if args.live else "demo"

from fastapi.testclient import TestClient  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app, identity  # noqa: E402
from app.runtime import run_task  # noqa: E402


def pdf_fixture():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(60, 780, "Launch review: October rollout; measure conversion against a control.")
    c.save()
    return buffer.getvalue()


csv = b"category,revenue\nBooks,20\nGames,5\nFood,12\nClothes,40\n"
cases = []
for topic in ["retail", "supply chains", "education", "open source", "energy", "productivity"]:
    cases.append(
        {
            "id": f"research-{topic.replace(' ', '-')}",
            "goal": f"Research {topic} and create a cited report.",
            "status": "completed",
            "sources": True,
            "files": ["report.md", "report.pdf"],
        }
    )
for label, content, expected in [
    ("baseline", csv, 5),
    ("negatives", b"category,revenue\nA,-5\nB,0\nC,2\nD,10\n", -5),
    ("zeros", b"category,revenue\nA,0\nB,0\nC,1\n", 0),
    ("duplicates", b"category,revenue\nA,2\nA,3\nB,7\n", 5),
    ("missing", b"category,revenue\nA,\nB,7\nC,2\n", 2),
    ("unicode", "category,revenue\nCafé,2\nBooks,3\n".encode(), 2),
]:
    cases.append(
        {
            "id": "csv-" + label,
            "goal": "Analyze this CSV and create a chart, spreadsheet, and report. Rank lowest total revenue first.",
            "upload": content,
            "name": "sales.csv",
            "status": "completed",
            "files": ["category-analysis.xlsx", "category-revenue.svg", "report.pdf"],
            "first_value": expected,
        }
    )
for label, goal in [
    ("flagship", "Analyze sales CSV, research market context, generate report with charts and experiments."),
    ("comparison", "Analyze sales CSV and research retail benchmarks. Separate facts and hypotheses in a report."),
    ("experiments", "Analyze CSV, research category context and report testable experiments."),
    ("brief", "Analyze sales CSV and research market context for a concise cited report."),
]:
    cases.append(
        {
            "id": "combined-" + label,
            "goal": goal,
            "upload": csv,
            "name": "sales.csv",
            "status": "completed",
            "sources": True,
            "files": ["report.md", "report.pdf", "category-analysis.xlsx", "category-revenue.svg"],
        }
    )
cases += [
    {
        "id": "text-notes",
        "goal": "Summarize this text as a report.",
        "upload": b"October rollout; compare conversion against a control.",
        "name": "notes.txt",
        "status": "completed",
        "files": ["report.md", "report.pdf"],
    },
    {
        "id": "markdown-notes",
        "goal": "Summarize this document as a report.",
        "upload": b"# Review\nLaunch in October.",
        "name": "notes.md",
        "status": "completed",
        "files": ["report.pdf"],
    },
    {
        "id": "pdf-ingestion",
        "goal": "Read this PDF and create a report.",
        "upload": pdf_fixture(),
        "name": "notes.pdf",
        "status": "completed",
        "files": ["report.pdf"],
    },
    {
        "id": "browser-extraction",
        "goal": "Browse https://example.com and extract its purpose in a report.",
        "status": "completed",
        "sources": True,
        "files": ["report.md", "report.pdf"],
    },
    {
        "id": "browser-research",
        "goal": "Browse https://example.com and research example domains, then report sources.",
        "status": "completed",
        "sources": True,
        "files": ["report.pdf"],
    },
    {"id": "malformed-csv", "goal": "Analyze this CSV.", "upload": b"category,revenue\nA,2,extra\n", "name": "bad.csv", "status": "failed", "files": []},
    {
        "id": "missing-column",
        "goal": "Analyze revenue by category in this CSV.",
        "upload": b"category,amount\nA,2\n",
        "name": "bad.csv",
        "status": "failed",
        "files": [],
    },
    {"id": "nonnumeric-csv", "goal": "Analyze this CSV.", "upload": b"category,revenue\nA,invalid\n", "name": "bad.csv", "status": "failed", "files": []},
]
rubric = {
    "behavior": "1 if terminal status matches expected success or controlled failure",
    "artifact_validity": "1 if all requested names exist and every generated PDF/XLSX parses",
    "content": "1 if specified numeric first row is correct; report hypotheses and fixture labels preserved where applicable",
    "citation_traceability": "1 if research sources have HTTP(S) URLs and exact excerpts appear in report; this does NOT measure factual support of model synthesis",
}
(out / "cases.json").write_text(json.dumps({"rubric": rubric, "cases": [{k: v for k, v in case.items() if k != "upload"} for case in cases]}, indent=2))
metadata = {
    "date": datetime.now(timezone.utc).isoformat(),
    "mode": "live" if args.live else "fixture",
    "provider": settings().llm_base_url if args.live else "none",
    "model": settings().llm_model if args.live else "deterministic fixture planner",
    "python": platform.python_version(),
    "limits": {"steps": settings().max_steps, "tokens": settings().max_tokens, "seconds": settings().max_seconds, "estimated_cost": settings().max_cost},
    "rubric": rubric,
}
try:
    settings().validate_runtime()
except ValueError as exc:
    (out / "live-results.json").write_text(json.dumps({**metadata, "status": "blocked", "reason": str(exc), "results": []}, indent=2))
    raise SystemExit("Live evaluation blocked: configure provider and authentication secrets; see evaluation/live-results.json")
app.dependency_overrides[identity] = lambda: "evaluation-runner"
results = []
with TestClient(app) as client:
    for case in cases:
        started = time.monotonic()
        file_ids = []
        if "upload" in case:
            response = client.post("/api/uploads", files={"file": (case["name"], case["upload"])})
            response.raise_for_status()
            file_ids.append(response.json()["id"])
        response = client.post("/api/tasks", json={"goal": case["goal"], "file_ids": file_ids})
        response.raise_for_status()
        task_id = response.json()["id"]
        asyncio.run(run_task(task_id))
        task = client.get("/api/tasks/" + task_id).json()
        artifacts = [f for f in task["files"] if f["kind"] == "artifact"]
        validity = set(case["files"]).issubset({f["name"] for f in artifacts})
        content_ok = True
        markdown = ""
        for f in artifacts:
            data = client.get("/api/files/" + f["id"]).content
            try:
                if f["name"].endswith(".pdf"):
                    validity &= len(PdfReader(io.BytesIO(data)).pages) > 0
                elif f["name"].endswith(".xlsx"):
                    book = load_workbook(io.BytesIO(data))
                    if "first_value" in case:
                        content_ok &= book.active["B3"].value == case["first_value"]
                elif f["name"].endswith(".md"):
                    markdown = data.decode()
                    content_ok &= "Hypotheses" in markdown
                    if not args.live:
                        content_ok &= "DEMO" in markdown
            except Exception:
                validity = False
        # A report need not cite every search hit. Check the sources it actually uses.
        cited_sources = [s for s in task["sources"] if f"[{s['id']}]" in markdown]
        citations = (
            not case.get("sources")
            or bool(cited_sources)
            and all(s["url"].startswith(("http://", "https://")) and s["excerpt"] in markdown for s in cited_sources)
        )
        checks = {
            "behavior": task["status"] == case["status"] and not (task.get("error") or "").startswith("Model provider HTTP"),
            "artifact_validity": bool(validity),
            "content": bool(content_ok),
            "citation_traceability": bool(citations),
        }
        results.append(
            {
                "id": case["id"],
                "status": task["status"],
                "checks": checks,
                "score": sum(checks.values()),
                "max_score": 4,
                "seconds": round(time.monotonic() - started, 3),
                "usage": task["usage"],
                "failure_category": task.get("error"),
            }
        )
        print(case["id"], results[-1]["score"], task["status"], flush=True)
app.dependency_overrides.clear()
report = {
    **metadata,
    "status": "finished",
    "results": results,
    "passed": sum(all(r["checks"].values()) for r in results),
    "total": len(results),
    "expected_controlled_failures": 3,
    "live_semantic_citation_review": "not evaluated; human source-support review required",
}
(out / ("live-results.json" if args.live else "fixture-results.json")).write_text(json.dumps(report, indent=2))
print(f"{report['passed']}/{report['total']} cases met their rubric. See evaluation results; fixtures do not measure live model performance.")
