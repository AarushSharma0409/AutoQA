"""Internal broker. Only this service has Docker access; never expose its port."""

import asyncio
import json
import secrets
import uuid
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from .config import settings

app = FastAPI(title="Isolated execution broker")
slots = asyncio.Semaphore(2)


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(max_length=16000)
    files: dict[str, str]


async def remove_container(name):
    proc = await asyncio.create_subprocess_exec("docker", "rm", "-f", name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()


@app.post("/execute")
async def execute(job: Job, request: Request, authorization: str = Header(default="")):
    if len(settings().sandbox_secret) < 32 or not secrets.compare_digest(authorization, "Bearer " + settings().sandbox_secret):
        raise HTTPException(401, "Broker authentication required")
    if len(job.files) > 5 or sum(len(v) for v in job.files.values()) > 16_000_000:
        raise HTTPException(413, "Input limit exceeded")
    for name in job.files:
        try:
            uuid.UUID(name)
        except ValueError:
            raise HTTPException(422, "Invalid file ID") from None
    async with slots:
        name = "autoagent-job-" + str(uuid.uuid4())
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "48",
            "--memory",
            "256m",
            "--memory-swap",
            "256m",
            "--cpus",
            "1",
            "--ulimit",
            "nofile=128:128",
            "--tmpfs",
            "/input:rw,noexec,nosuid,size=12m,uid=10001",
            "--tmpfs",
            "/output:rw,noexec,nosuid,size=16m,uid=10001",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=32m,uid=10001",
            "autoagent-python:local",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        async def collect():
            proc.stdin.write(job.model_dump_json().encode())
            await proc.stdin.drain()
            proc.stdin.close()
            data = bytearray()
            while chunk := await proc.stdout.read(65536):
                data.extend(chunk)
                if len(data) > 7_000_000:
                    raise ValueError("Output limit exceeded")
            await proc.wait()
            if proc.returncode:
                raise ValueError("Container failed, reached a resource limit, or image is unavailable")
            return json.loads(data)

        task = asyncio.create_task(collect())
        try:
            for _ in range(220):
                done, _ = await asyncio.wait({task}, timeout=0.25)
                if done:
                    return await task
                if await request.is_disconnected():
                    raise asyncio.CancelledError()
            raise TimeoutError("Sandbox wall-clock limit exceeded")
        except (ValueError, TimeoutError):
            raise HTTPException(422, "Sandbox failed or exceeded resource limits") from None
        finally:
            await remove_container(name)
            if not task.done():
                task.cancel()
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
