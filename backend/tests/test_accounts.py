import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app import auth
from app.config import settings

URL = "https://testproject.supabase.co"


@pytest.fixture
def account_tokens(monkeypatch):
    cfg = settings()
    monkeypatch.setattr(cfg, "auth_provider", "supabase")
    monkeypatch.setattr(cfg, "supabase_url", URL)
    monkeypatch.setattr(cfg, "supabase_publishable_key", "sb_publishable_test")
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth, "signing_keys", lambda url: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key()),
    ))

    def issue(user=None, **overrides):
        claims = {"sub": user or str(uuid4()), "exp": int(time.time()) + 600,
                  "iat": int(time.time()), "iss": URL + "/auth/v1",
                  "aud": "authenticated", "role": "authenticated"}
        claims.update(overrides)
        return {"Authorization": "Bearer " + jwt.encode(claims, private, algorithm="ES256", headers={"kid": "test"})}
    return issue


def test_public_config_does_not_require_login(client, account_tokens):
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    assert response.json() == {"provider": "supabase", "url": URL, "publishableKey": "sb_publishable_test"}
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/tasks").status_code == 401


@pytest.mark.parametrize("claims", [
    {"exp": 1}, {"iss": "https://another.supabase.co/auth/v1"},
    {"aud": "service_role"}, {"role": "service_role"},
    {"sub": "not-a-user-id"}, {"is_anonymous": True},
])
def test_invalid_account_tokens_are_rejected(client, account_tokens, claims):
    assert client.get("/api/tasks", headers=account_tokens(**claims)).status_code == 401


def test_account_history_persists_and_other_users_cannot_access(client, account_tokens):
    user = str(uuid4())
    first = account_tokens(user)
    stranger = account_tokens()
    created = client.post("/api/tasks", headers=first, json={"goal": "Analyze my document", "file_ids": []})
    assert created.status_code == 201
    task_id = created.json()["id"]
    # A fresh session for the same account recovers persisted history.
    assert client.get("/api/tasks", headers=account_tokens(user)).json()[0]["id"] == task_id
    assert client.get("/api/tasks", headers=stranger).json() == []
    for path in [f"/api/tasks/{task_id}", f"/api/tasks/{task_id}/events"]:
        assert client.get(path, headers=stranger).status_code == 404
    for action in ["messages", "cancel", "resume"]:
        assert client.post(f"/api/tasks/{task_id}/{action}", headers=stranger,
                           json={"goal": "Change the document", "file_ids": []}).status_code == 404


def test_local_signed_token_cannot_impersonate_supabase_account(client, account_tokens):
    token = jwt.encode({"sub": str(uuid4()), "exp": time.time() + 600}, "a" * 32, algorithm="HS256")
    assert client.get("/api/tasks", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_bad_signature_rejected(client, account_tokens):
    private = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode({"sub": str(uuid4()), "exp": time.time() + 600}, private, algorithm="ES256")
    assert client.get("/api/tasks", headers={"Authorization": "Bearer " + token}).status_code == 401
