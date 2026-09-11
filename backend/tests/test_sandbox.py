import os
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.sandbox_service import app as broker


def test_broker_rejects_missing_secret():
    with TestClient(broker) as client:
        assert client.post("/execute", json={"code": "print(1)", "files": {}}).status_code == 401


@pytest.mark.skipif(
    os.getenv("AUTOAGENT_CONTAINER_TESTS") != "1", reason="Requires Docker and autoagent-python:local image; enable AUTOAGENT_CONTAINER_TESTS=1"
)
@pytest.mark.parametrize(
    "code,expected",
    [
        ("import os; print(os.getenv('LLM_API_KEY', 'NO_SECRET'))", "NO_SECRET"),
        ("from pathlib import Path; print(Path('/app/.env').exists()); print(Path('/var/run/docker.sock').exists())", "False"),
        (
            "import socket\ntry:\n socket.create_connection(('1.1.1.1',443), timeout=1)\n print('NETWORK_OPEN')\nexcept OSError:\n print('NETWORK_BLOCKED')",
            "NETWORK_BLOCKED",
        ),
        ("from pathlib import Path\ntry:\n Path('/outside').write_text('x')\n print('WRITE_OPEN')\nexcept OSError:\n print('WRITE_BLOCKED')", "WRITE_BLOCKED"),
    ],
)
def test_real_container_boundaries(monkeypatch, code, expected):
    monkeypatch.setattr(settings(), "sandbox_secret", "test-secret-" * 4)
    with TestClient(broker) as client:
        response = client.post("/execute", headers={"Authorization": "Bearer " + settings().sandbox_secret}, json={"code": code, "files": {}})
        assert response.status_code == 200, response.text
        assert expected in response.json()["stdout"]


@pytest.mark.skipif(os.getenv("AUTOAGENT_CONTAINER_TESTS") != "1", reason="Requires Docker and sandbox image")
def test_real_container_memory_limit(monkeypatch):
    monkeypatch.setattr(settings(), "sandbox_secret", "test-secret-" * 4)
    with TestClient(broker) as client:
        response = client.post(
            "/execute", headers={"Authorization": "Bearer " + settings().sandbox_secret}, json={"code": "x=bytearray(900*1024*1024)", "files": {}}
        )
        assert response.status_code == 422 or "error" in response.json()
