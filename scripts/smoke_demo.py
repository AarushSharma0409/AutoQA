"""Exercise the running fixture stack and save the flagship example's artifacts."""

import io
import json
import time
from pathlib import Path
import httpx
from openpyxl import load_workbook
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1]
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=15) as client:
    assert client.get("/api/config").json()["mode"] == "demo", (
        "This script only runs in fixture mode"
    )
    upload = client.post(
        "/api/uploads",
        files={"file": ("sales.csv", (root / "examples/sales.csv").read_bytes())},
    )
    upload.raise_for_status()
    response = client.post(
        "/api/tasks",
        json={
            "goal": "Analyze this sales CSV, identify the three weakest-performing categories, research market context, and generate a report with charts and suggested experiments.",
            "file_ids": [upload.json()["id"]],
        },
    )
    response.raise_for_status()
    task_id = response.json()["id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        task = client.get("/api/tasks/" + task_id).json()
        if task["status"] not in {"queued", "running"}:
            break
        time.sleep(0.5)
    assert task["status"] == "completed", task
    output = root / "evaluation/samples"
    output.mkdir(exist_ok=True, parents=True)
    for file in task["files"]:
        if file["kind"] != "artifact":
            continue
        content = client.get("/api/files/" + file["id"]).content
        (output / file["name"]).write_bytes(content)
        if file["name"].endswith(".xlsx"):
            book = load_workbook(io.BytesIO(content))
            assert list(book.active.values)[2:5] == [
                ("Beauty", 10000),
                ("Games", 14600),
                ("Books", 21000),
            ]
        if file["name"].endswith(".pdf"):
            assert len(PdfReader(io.BytesIO(content)).pages) >= 1
    result = {
        "status": "passed",
        "mode": "fixture",
        "task_id": task_id,
        "weakest": ["Beauty", "Games", "Books"],
        "usage": task["usage"],
    }
    (root / "evaluation/demo-result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
