"""Run inside a Compose API container. Uses an isolated audit identity and fixture tasks."""
import asyncio
from collections import Counter
import json
import socket
import time
import uuid

import httpx
import jwt
from sqlalchemy import select
from app.config import settings
from app.db import Session, Task, Event, File


async def main():
    cfg = settings()
    assert cfg.mode == "live", "Ownership verification requires live authentication"
    owner = "scaling-audit-" + uuid.uuid4().hex
    token = jwt.encode({"sub": owner, "iss": cfg.auth_issuer, "aud": cfg.auth_audience, "exp": int(time.time()) + 900}, cfg.auth_secret, algorithm="HS256")
    peers = sorted({row[4][0] for row in socket.getaddrinfo("api", 8000, type=socket.SOCK_STREAM)})
    assert len(peers) >= 2, "Start at least two API replicas"
    task_ids = []
    async with httpx.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=15) as client:
        writes = []
        for index in range(cfg.rate_limit_writes + 3):
            response = await client.post(f"http://{peers[index % len(peers)]}:8000/api/tasks/missing/resume")
            writes.append(response.status_code)
            if response.status_code == 429:
                assert int(response.headers["retry-after"]) > 0
        assert writes.count(404) == cfg.rate_limit_writes and writes.count(429) == 3, writes
        semaphore = asyncio.Semaphore(12)
        async def read():
            async with semaphore:
                started = time.monotonic()
                response = await client.get("http://gateway:8081/api/config")
                assert response.status_code == 200, response.status_code
                return time.monotonic() - started
        started = time.monotonic()
        latencies = sorted(await asyncio.gather(*(read() for _ in range(120))))
        load_seconds = time.monotonic() - started
        assert (await client.get("http://gateway:8081/api/config", headers={"Authorization": "Bearer invalid"})).status_code == 401
        with Session.begin() as db:
            for _ in range(6):
                task = Task(owner=owner, goal="Generate a small fixture report for scaling verification", mode="demo", checkpoint={})
                db.add(task)
                db.flush()
                task_ids.append(task.id)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            with Session() as db:
                states = [db.get(Task, task_id).status for task_id in task_ids]
            if all(state == "completed" for state in states):
                break
            await asyncio.sleep(1)
        assert all(state == "completed" for state in states), states
        with Session() as db:
            artifacts = list(db.scalars(select(File).where(File.task_id.in_(task_ids))))
            counts = Counter(f.task_id for f in artifacts)
            assert all(counts[task_id] == 2 for task_id in task_ids), counts
            events = list(db.scalars(select(Event).where(Event.task_id.in_(task_ids), Event.kind == "result")))
            finishes = Counter(e.task_id for e in events if e.payload.get("tool") == "finish")
            assert all(finishes[task_id] == 1 for task_id in task_ids), finishes
        for file in artifacts:
            assert (await client.get("http://gateway:8081/api/files/" + file.id)).status_code == 200
        print(json.dumps({"status": "passed", "api_replicas": len(peers), "shared_quota": dict(Counter(writes)), "read_requests": 120,
                          "concurrency": 12, "seconds": round(load_seconds, 3), "p95_ms": round(latencies[113] * 1000, 2),
                          "fixture_tasks_completed": len(task_ids), "duplicate_completions": 0, "artifacts_downloaded": len(artifacts),
                          "audit_owner": owner, "note": "API load and real worker dispatch; fixture planner, no live model calls"}, indent=2))


asyncio.run(main())
