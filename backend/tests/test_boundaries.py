import asyncio
import socket
import time
from unittest.mock import patch
import jwt
import pytest
from app.config import settings
from app.db import Session, Task
from app.main import app, identity
from app.runtime import claim, digest, run_task
from app.schemas import Decision
from app.security import public_address, fetch_public
from app.storage import storage
from app.tools import csv_rows, safe_cell, task_file
from test_workflows import create, CSV


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://169.254.169.254/latest",
        "http://10.0.0.1",
        "http://[::1]",
        "http://192.168.1.1",
        "file:///etc/passwd",
        "http://user:pass@example.com",
        "http://example.com:8000",
    ],
)
def test_ssrf_denied(url):
    with pytest.raises(ValueError):
        public_address(url)


def test_mixed_public_private_dns_denied():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("127.0.0.1", 443))]), pytest.raises(ValueError):
        public_address("https://public.example")


def test_redirect_revalidated():
    class Response:
        status = 302

        def getheader(self, *args):
            return "http://127.0.0.1/"

    class Connection:
        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    original = socket.getaddrinfo
    with (
        patch("app.security.PinnedTLS", return_value=Connection()),
        patch(
            "socket.getaddrinfo",
            side_effect=lambda host, *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))] if host == "public.example" else original(host, *a, **kw),
        ),
        pytest.raises(ValueError),
    ):
        fetch_public("https://public.example")


def test_ownership_all_surfaces(client):
    task_id = create(client, "Analyze sales", CSV)
    file_id = client.get("/api/tasks/" + task_id).json()["files"][0]["id"]
    app.dependency_overrides[identity] = lambda: "other-user"
    try:
        assert client.get("/api/tasks").json() == []
        for path in [f"/api/tasks/{task_id}", f"/api/tasks/{task_id}/events", f"/api/files/{file_id}"]:
            assert client.get(path).status_code == 404
        for action in ["cancel", "resume"]:
            assert client.post(f"/api/tasks/{task_id}/{action}").status_code == 404
        assert client.post(f"/api/tasks/{task_id}/approve", json={"digest": "x", "approved": True}).status_code == 404
    finally:
        app.dependency_overrides.clear()
    with pytest.raises(ValueError):
        task_file("another-task", file_id)


def test_upload_limits_and_names(client, monkeypatch):
    assert client.post("/api/uploads", files={"file": ("bad.exe", b"bad")}).status_code == 415
    assert client.post("/api/uploads", files={"file": ("bad.pdf", b"bad")}).status_code == 422
    monkeypatch.setattr(settings(), "max_upload_bytes", 4)
    assert client.post("/api/uploads", files={"file": ("big.txt", b"12345")}).status_code == 413
    response = client.post("/api/uploads", files={"file": ("../../secret.txt", b"ok")})
    assert response.json()["name"] == "secret.txt"
    with pytest.raises(ValueError):
        storage.path("../../secret")


def test_formula_injection_and_duplicate_headers():
    assert safe_cell('=HYPERLINK("bad")').startswith("'")
    with pytest.raises(ValueError):
        csv_rows(b"category,category\n1,2")


def test_auth_fail_closed(monkeypatch):
    monkeypatch.setattr(settings(), "mode", "live")
    monkeypatch.setattr(settings(), "auth_secret", "x" * 40)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        identity(None)
    token = jwt.encode({"sub": "alice", "iss": "autoagent", "aud": "autoagent-api", "exp": time.time() + 60}, "x" * 40, algorithm="HS256")
    assert identity("Bearer " + token) == "alice"


def test_step_budget(client, monkeypatch):
    monkeypatch.setattr(settings(), "max_steps", 1)
    task_id = create(client, "Research and report")
    asyncio.run(run_task(task_id))
    task = client.get("/api/tasks/" + task_id).json()
    assert task["status"] == "failed" and "budget" in task["error"]
    assert task["usage"]["steps"] == 1


def test_recovery_and_duplicate_lease(client):
    task_id = create(client, "Research a report")
    lease = claim(task_id)
    assert lease and claim(task_id) is None
    with Session.begin() as db:
        task = db.get(Task, task_id)
        task.lease_until = time.time() - 1
        task.checkpoint = {"pending": {"tool": "search", "arguments": {"query": "retail"}, "summary": "Search"}}
    asyncio.run(run_task(task_id))
    assert client.get("/api/tasks/" + task_id).json()["status"] == "completed"
    assert "recovery" in client.get(f"/api/tasks/{task_id}/events").text


def test_python_approval_exactness_and_denial(client, monkeypatch):
    decision = Decision(tool="python", arguments={"code": "print(1)", "file_ids": []}, summary="Calculate")
    monkeypatch.setattr("app.runtime.demo_decision", lambda *args: decision)
    task_id = create(client, "Compute with isolated Python")
    asyncio.run(run_task(task_id))
    task = client.get("/api/tasks/" + task_id).json()
    assert task["status"] == "awaiting_approval"
    assert task["usage"]["steps"] == 0
    assert client.post(f"/api/tasks/{task_id}/approve", json={"digest": "wrong", "approved": True}).status_code == 409
    response = client.post(f"/api/tasks/{task_id}/approve", json={"digest": digest(decision), "approved": False})
    assert response.json()["status"] == "canceled"
    assert client.post(f"/api/tasks/{task_id}/resume").status_code == 409


def test_cancel_propagates(client, monkeypatch):
    task_id = create(client, "Research a report")
    canceled = []

    async def slow(*args):
        try:
            await asyncio.sleep(10)
        finally:
            canceled.append(True)

    monkeypatch.setattr("app.runtime.execute", slow)

    async def scenario():
        execution = asyncio.create_task(run_task(task_id))
        await asyncio.sleep(0.1)
        assert client.post(f"/api/tasks/{task_id}/cancel").status_code == 200
        await asyncio.wait_for(execution, 2)

    asyncio.run(scenario())
    assert canceled
    assert client.get("/api/tasks/" + task_id).json()["status"] == "canceled"


def test_uncertain_python_requires_fresh_approval(client):
    task_id = create(client, "Python analysis")
    decision = Decision(tool="python", arguments={"code": "print(1)"}, summary="Calculate")
    with Session.begin() as db:
        task = db.get(Task, task_id)
        task.status = "running"
        task.lease_until = 0
        task.checkpoint = {"pending": decision.model_dump()}
    asyncio.run(run_task(task_id))
    result = client.get("/api/tasks/" + task_id).json()
    assert result["status"] == "awaiting_approval"
    assert "interrupted" in result["approval"]["reason"]


def test_untrusted_origin_and_large_body(client):
    assert client.post("/api/tasks", headers={"Origin": "https://attacker.example"}, json={"goal": "Research retail"}).status_code == 403
    assert client.post("/api/tasks", content="x" * 40000).status_code == 413


def test_duration_budget_cancels_active_tool(client, monkeypatch):
    task_id = create(client, "Research a report")
    monkeypatch.setattr(settings(), "max_seconds", 0.3)

    async def slow(*args):
        await asyncio.sleep(10)

    monkeypatch.setattr("app.runtime.execute", slow)
    asyncio.run(run_task(task_id))
    task = client.get("/api/tasks/" + task_id).json()
    assert task["status"] == "failed"
    assert "budget" in task["error"]
    assert task["usage"]["elapsed"] < 2
