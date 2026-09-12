"""Small live acceptance check. Uses real model quota; writes only audit-owned tasks."""
import json
from pathlib import Path
import time
import uuid
import httpx
import jwt
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
cfg = dotenv_values(root / ".env")
owner = "live-audit-" + uuid.uuid4().hex
token = jwt.encode({"sub": owner, "iss": cfg.get("AUTH_ISSUER", "autoagent"), "aud": cfg.get("AUTH_AUDIENCE", "autoagent-api"), "exp": int(time.time()) + 900}, cfg["AUTH_SECRET"], algorithm="HS256")
records = []
with httpx.Client(base_url="http://127.0.0.1:8000", headers={"Authorization": "Bearer " + token}, timeout=15) as client:
    response = client.post("/api/tasks", json={"goal": "Browse https://docs.python.org/3/tutorial/ and create a brief report with one qualitative finding for beginners, citing its source ID inline. Use only retrieved evidence. Finish after the report. Do not execute Python code."})
    response.raise_for_status()
    task_id = response.json()["id"]
    for turn in range(2):
        deadline = time.monotonic() + 240
        while True:
            response = client.get("/api/tasks/" + task_id)
            response.raise_for_status()
            task = response.json()
            if task["status"] in {"completed", "failed", "canceled", "awaiting_approval"}:
                break
            if time.monotonic() > deadline:
                client.post(f"/api/tasks/{task_id}/cancel").raise_for_status()
                task["status"], task["error"] = "canceled", "Audit timeout; partial files retained"
                break
            time.sleep(2)
        records.append({"turn": turn + 1, "status": task["status"], "error": task.get("error"), "usage": task.get("usage"), "sources": task.get("sources", [])})
        current = task.get("current_file_ids")
        reports = [f for f in task["files"] if f["mime"] == "text/markdown" and (current is None or f["id"] in current)]
        if reports:
            content = client.get("/api/files/" + reports[-1]["id"])
            content.raise_for_status()
            (root / "evaluation" / f"live-audit-turn-{turn + 1}.md").write_text(content.text, encoding="utf-8")
        print(json.dumps({"turn": turn + 1, "status": task["status"], "error": task.get("error")}), flush=True)
        if task["status"] != "completed" or turn == 1:
            break
        client.post(f"/api/tasks/{task_id}/messages", json={"goal": "Revise the report into three short beginner tips using the same retrieved document. Cite source IDs inline and distinguish advice from source facts. No new web search is needed."}).raise_for_status()
result = {"task_id": task_id, "owner": owner, "status": "passed" if len(records) == 2 and all(r["status"] == "completed" for r in records) else "failed", "turns": records}
(root / "evaluation" / "live-security-smoke.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("Live research and follow-up:", result["status"])
