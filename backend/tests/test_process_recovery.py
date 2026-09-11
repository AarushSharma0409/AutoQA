import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from sqlalchemy import select
from app.db import Event, Session, Task
from app.runtime import run_task
from test_workflows import create


def test_killed_worker_replays_checkpoint(client):
    task_id = create(client, "Research retail and generate a report")
    helper = Path(__file__).with_name("worker_to_kill.py")
    process = subprocess.Popen(
        [sys.executable, str(helper), task_id], env={**os.environ, "PYTHONPATH": str(Path.cwd())}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        deadline = time.monotonic() + 10
        pending = False
        while time.monotonic() < deadline:
            with Session() as db:
                pending = bool(db.get(Task, task_id).checkpoint.get("pending"))
            if pending:
                break
            time.sleep(0.05)
        assert pending, "Worker did not reach persisted dispatch checkpoint"
        process.kill()
        process.wait(timeout=5)
        with Session.begin() as db:
            task = db.get(Task, task_id)
            assert task.status == "running"
            task.lease_until = time.time() - 1  # advance expiry rather than wait 30 seconds
        asyncio.run(run_task(task_id))
        task = client.get("/api/tasks/" + task_id).json()
        assert task["status"] == "completed"
        assert len([f for f in task["files"] if f["kind"] == "artifact"]) == 2
        with Session() as db:
            assert any(e.kind == "recovery" for e in db.scalars(select(Event).where(Event.task_id == task_id)))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
