# ruff: noqa: E402 -- test configuration must precede application imports
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

TEST_ROOT = Path(tempfile.mkdtemp(prefix="autoagent-tests-"))
test_database = os.getenv("AUTOAGENT_TEST_DATABASE_URL")
if test_database and not urlsplit(test_database).path.removeprefix("/").startswith("autoagent_verification_"):
    raise ValueError("Integration tests require a dedicated autoagent_verification_* database; application databases are never reset")
os.environ.update(DATABASE_URL=test_database or "sqlite:///" + (TEST_ROOT / "test.db").as_posix(), STORAGE_ROOT=str(TEST_ROOT / "files"), MODE="demo", REDIS_URL="")

import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
