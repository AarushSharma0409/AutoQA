"""Real broker integration; requires the running Compose sandbox service."""
import asyncio
import os
import subprocess
import pytest
from app.runtime import run_task
from app.schemas import Decision
from test_workflows import create

pytestmark = pytest.mark.skipif(os.getenv("AUTOAGENT_COMPOSE_TESTS") != "1", reason="Requires the running Compose broker")


def test_approved_python_generates_chart_through_broker(client, monkeypatch):
    code = "import numpy as np\nimport matplotlib.pyplot as plt\nvalues=np.array([2,3,5])\nprint(int(values.sum()))\nplt.bar(['A','B','C'],values)\nplt.savefig('/output/verified-chart.png')"

    def planner(goal, checkpoint, files):
        if any(r["tool"] == "python" and "error" not in r["output"] for r in checkpoint.get("results", [])):
            return Decision(tool="finish", arguments={"summary": "Verified isolated chart."}, summary="Finish")
        return Decision(tool="python", arguments={"code": code, "file_ids": []}, summary="Calculate and chart in an isolated container")

    monkeypatch.setattr("app.runtime.demo_decision", planner)
    task_id = create(client, "Compute values using Python and save a PNG")
    asyncio.run(run_task(task_id))
    pending = client.get(f"/api/tasks/{task_id}").json()
    assert pending["status"] == "awaiting_approval"
    assert pending["files"] == []
    approval = client.post(f"/api/tasks/{task_id}/approve", json={"digest": pending["approval"]["digest"], "approved": True})
    assert approval.status_code == 200
    asyncio.run(run_task(task_id))
    task = client.get(f"/api/tasks/{task_id}").json()
    assert task["status"] == "completed", task
    chart = next(f for f in task["files"] if f["name"] == "verified-chart.png")
    assert client.get(f"/api/files/{chart['id']}").content.startswith(b"\x89PNG\r\n\x1a\n")
    assert '10' in client.get(f"/api/tasks/{task_id}/events").text


def test_task_cancellation_removes_running_container(client, monkeypatch):
    def containers():
        return set(subprocess.check_output(["docker", "ps", "--filter", "name=autoagent-job-", "--format", "{{.ID}}"], text=True).split())

    decision = Decision(tool="python", arguments={"code": "import time; time.sleep(30)", "file_ids": []}, summary="Wait in isolated Python for cancellation verification")
    monkeypatch.setattr("app.runtime.demo_decision", lambda *args: decision)
    task_id = create(client, "Verify Python cancellation")
    asyncio.run(run_task(task_id))
    approval = client.get(f"/api/tasks/{task_id}").json()["approval"]
    assert client.post(f"/api/tasks/{task_id}/approve", json={"digest": approval["digest"], "approved": True}).status_code == 200
    before = containers()

    async def scenario():
        execution = asyncio.create_task(run_task(task_id))
        try:
            running = set()
            for _ in range(40):
                running = await asyncio.to_thread(containers) - before
                if running:
                    break
                await asyncio.sleep(0.1)
            assert running, "Approved code did not reach a running container"
            assert client.post(f"/api/tasks/{task_id}/cancel").status_code == 200
            await asyncio.wait_for(execution, 5)
            for _ in range(40):
                if not (await asyncio.to_thread(containers) & running):
                    break
                await asyncio.sleep(0.1)
            assert not (await asyncio.to_thread(containers) & running), "Canceled task left its container running"
        finally:
            if not execution.done():
                client.post(f"/api/tasks/{task_id}/cancel")
                execution.cancel()
                await asyncio.gather(execution, return_exceptions=True)

    asyncio.run(scenario())
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "canceled"
