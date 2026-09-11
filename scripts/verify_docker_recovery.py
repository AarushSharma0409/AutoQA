"""Kill only this project's worker during a fixture action; verify durable recovery.

Run from the repository root with the demo Compose stack already running.
"""
import json
from pathlib import Path
import subprocess
import time
import uuid
from datetime import datetime, timezone
import httpx

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    return subprocess.check_output(["docker", "compose", *args], cwd=ROOT, text=True, timeout=30).strip()


with httpx.Client(base_url="http://127.0.0.1:8000", timeout=20) as client:
    assert client.get("/api/config").json()["mode"] == "demo"
    csv = b"category,revenue\n" + b"Books,20\nGames,5\nFood,12\nClothes,40\n" * 20000
    upload = client.post("/api/uploads", files={"file": ("recovery-sales.csv", csv)})
    upload.raise_for_status()
    created = client.post("/api/tasks", json={"goal": "Analyze CSV, research context and generate a report with charts", "file_ids": [upload.json()["id"]]})
    created.raise_for_status()
    task_id = str(uuid.UUID(created.json()["id"]))
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        pending = compose("exec", "-T", "postgres", "psql", "-U", "autoagent", "-d", "autoagent", "-Atc", f"SELECT checkpoint::jsonb ? 'pending' FROM tasks WHERE id='{task_id}'")
        if pending == "t":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Did not observe an in-flight persisted action; recovery was not tested")
    started = time.monotonic()
    try:
        compose("kill", "-s", "SIGKILL", "worker")
        assert client.get(f"/api/tasks/{task_id}").json()["status"] == "running"
    finally:
        compose("start", "worker")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        task = client.get(f"/api/tasks/{task_id}").json()
        if task["status"] not in {"queued", "running"}:
            break
        time.sleep(0.5)
    assert task["status"] == "completed", task
    assert "recovery" in client.get(f"/api/tasks/{task_id}/events").text
    files = [f for f in task["files"] if f["kind"] == "artifact"]
    assert len(files) == 4 and len({f["name"] for f in files}) == 4
    for file in files:
        assert client.get(f"/api/files/{file['id']}").status_code == 200
    result = {"date": datetime.now(timezone.utc).isoformat(), "status": "passed", "mode": "fixture on PostgreSQL/Redis/Docker", "task_id": task_id, "action": "SIGKILL worker during a persisted pending action, restart, await lease recovery", "seconds_after_kill": round(time.monotonic() - started, 3), "artifacts": len(files)}
    (ROOT / "evaluation/docker-recovery-result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
