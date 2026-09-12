import asyncio

from app import runtime
from app.schemas import Decision


def repeating_report(goal, checkpoint, files):
    return Decision(tool="report", summary="Generate report", arguments={
        "title": "Report", "findings": "A summary.", "hypotheses": "",
        "source_ids": [],
    })


def test_repeated_reports_finish_once_and_follow_up_can_revise(client, monkeypatch):
    monkeypatch.setattr(runtime, "demo_decision", repeating_report)
    task = client.post("/api/tasks", json={"goal": "Create a report"}).json()
    for turn in range(2):
        if turn:
            client.post(f"/api/tasks/{task['id']}/messages", json={"goal": "Revise the report"})
        asyncio.run(runtime.run_task(task["id"]))
        result = client.get(f"/api/tasks/{task['id']}").json()
        assert result["status"] == "completed"
        assert sum(f["mime"] == "application/pdf" for f in result["files"]) == turn + 1
        assert sum(f["mime"] == "text/markdown" for f in result["files"]) == turn + 1


def test_failed_report_can_retry_without_duplicate_outputs(client, monkeypatch):
    monkeypatch.setattr(runtime, "demo_decision", repeating_report)
    original = runtime.execute
    attempts = 0

    async def execute(*args):
        nonlocal attempts
        if args[1] == "report":
            attempts += 1
            if attempts == 1:
                raise ValueError("Invalid citation")
        return await original(*args)

    monkeypatch.setattr(runtime, "execute", execute)
    task = client.post("/api/tasks", json={"goal": "Create a report"}).json()
    asyncio.run(runtime.run_task(task["id"]))
    result = client.get(f"/api/tasks/{task['id']}").json()
    assert result["status"] == "completed"
    assert attempts == 2
    assert len(result["files"]) == 3


def test_duplicate_report_does_not_bypass_required_research(client, monkeypatch):
    monkeypatch.setattr(runtime, "demo_decision", repeating_report)
    task = client.post("/api/tasks", json={"goal": "Research and create a report"}).json()
    asyncio.run(runtime.run_task(task["id"]))
    result = client.get(f"/api/tasks/{task['id']}").json()
    assert result["status"] == "failed"
    assert "search" in result["error"]
    assert len(result["files"]) == 3
