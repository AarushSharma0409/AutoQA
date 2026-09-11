import asyncio
import json
import re
from contextlib import asynccontextmanager
import jwt
from fastapi import Depends, FastAPI, File as UploadParameter, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from sqlalchemy import select, func
from .config import settings
from .db import Event, File, Session, Task, emit, migrate
from .schemas import Approval, CreateTask
from .storage import storage


@asynccontextmanager
async def lifespan(app):
    settings().validate_runtime()
    migrate()
    yield


app = FastAPI(title="AutoAgent", lifespan=lifespan)


@app.middleware("http")
async def ingress_limits(request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in settings().allowed_origins.split(","):
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    if request.method == "POST":
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        if request.headers.get("transfer-encoding") or (request.url.path == "/api/uploads" and length <= 0):
            return JSONResponse({"detail": "A bounded Content-Length is required"}, status_code=411)
        limit = settings().max_upload_bytes + 65536 if request.url.path == "/api/uploads" else 32768
        if length > limit:
            return JSONResponse({"detail": "Request exceeds size limit"}, status_code=413)
    return await call_next(request)


def identity(authorization: str | None = Header(default=None)):
    if settings().mode == "demo":
        return "local-demo"
    try:
        token = (authorization or "").removeprefix("Bearer ")
        data = jwt.decode(
            token,
            settings().auth_secret,
            algorithms=["HS256"],
            audience=settings().auth_audience,
            issuer=settings().auth_issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
        if not isinstance(data["sub"], str) or not 1 <= len(data["sub"]) <= 200:
            raise ValueError("Invalid subject")
        return data["sub"]
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Valid access token required") from None


def owned(db, task_id, owner):
    task = db.get(Task, task_id)
    if not task or task.owner != owner:
        raise HTTPException(404, "Task not found")
    return task


def file_json(f):
    return {"id": f.id, "name": f.name, "mime": f.mime, "size": f.size, "kind": f.kind}


def task_json(task, detailed=False):
    data = {"id": task.id, "goal": task.goal, "status": task.status, "mode": task.mode, "created": task.created, "updated": task.updated, "error": task.error}
    if detailed:
        cp = task.checkpoint
        data.update(
            usage={k: cp.get(k, 0) for k in ["steps", "tokens", "cost", "elapsed"]},
            accounting_note=cp.get("accounting_note"),
            approval=cp.get("approval"),
            sources=list({s["id"]: s for r in cp.get("context_results", []) + cp.get("results", []) for s in r["output"].get("sources", [])}.values()),
            turns=cp.get("turns", []),
            current_goal=cp.get("current_goal", task.goal),
            current_file_ids=cp.get("current_file_ids"),
        )
    return data


async def notify(task_id):
    if settings().redis_url:
        from redis.asyncio import Redis

        client = Redis.from_url(settings().redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            await client.lpush("autoagent:queue", task_id)
        except Exception:
            pass  # Durable DB scan will reconcile a lost queue notification.
        finally:
            await client.aclose()


@app.get("/health")
def health():
    with Session() as db:
        db.execute(select(1))
    return {"status": "ok", "mode": settings().mode}


@app.get("/api/config")
def config(owner=Depends(identity)):
    cfg = settings()
    return {
        "mode": cfg.mode,
        "model": cfg.llm_model if cfg.mode == "live" else "Fixture planner",
        "limits": {"steps": cfg.max_steps, "tokens": cfg.max_tokens, "seconds": cfg.max_seconds, "cost": cfg.max_cost, "upload_bytes": cfg.max_upload_bytes},
        "search_configured": cfg.search_provider == "tavily" or bool(cfg.search_api_key),
        "search_provider": cfg.search_provider,
    }


@app.post("/api/uploads", status_code=201)
async def upload(file: UploadFile = UploadParameter(...), owner=Depends(identity)):
    name = (file.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f]", "", name)[:180]
    extension = name.rsplit(".", 1)[-1].lower()
    types = {"csv": "text/csv", "txt": "text/plain", "md": "text/markdown", "pdf": "application/pdf"}
    if extension not in types:
        raise HTTPException(415, "Upload CSV, PDF, TXT or Markdown files")
    content = await file.read(settings().max_upload_bytes + 1)
    await file.close()
    if not content or len(content) > settings().max_upload_bytes:
        raise HTTPException(413, "File empty or exceeds upload limit")
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(422, "Invalid PDF signature")
    if extension != "pdf":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "Text uploads must use UTF-8") from None
    with Session.begin() as db:
        # Unattached upload gets an owner-scoped staging task, hidden from history.
        staging = Task(owner=owner, goal="Upload staging", mode=settings().mode, status="staging")
        db.add(staging)
        db.flush()
        f = File(task_id=staging.id, name=name, mime=types[extension], size=len(content), storage_key=storage.put(content), kind="upload")
        db.add(f)
        db.flush()
        result = file_json(f)
    return result


@app.post("/api/tasks", status_code=201)
async def create_task(body: CreateTask, owner=Depends(identity)):
    if len(body.goal.strip()) < 3:
        raise HTTPException(422, "Provide a goal with at least three characters")
    with Session.begin() as db:
        files = []
        for file_id in set(body.file_ids):
            f = db.scalar(select(File).where(File.id == file_id).with_for_update())
            if not f or owned(db, f.task_id, owner).status != "staging":
                raise HTTPException(422, "Upload is missing or already attached")
            files.append(f)
        task = Task(owner=owner, goal=body.goal.strip(), mode=settings().mode, checkpoint={})
        db.add(task)
        db.flush()
        for f in files:
            staging = db.get(Task, f.task_id)
            f.task_id = task.id
            db.delete(staging)
        emit(db, task, "status", status="queued", summary="Task saved and queued", mode=task.mode)
        result = task_json(task)
    await notify(result["id"])
    return result


@app.get("/api/tasks")
def history(owner=Depends(identity)):
    with Session() as db:
        count = select(func.count(File.id)).where(File.task_id == Task.id, File.kind == "artifact").correlate(Task).scalar_subquery()
        rows = db.execute(select(Task, count).where(Task.owner == owner, Task.status != "staging").order_by(Task.updated.desc()).limit(100))
        return [{**task_json(task), "artifact_count": artifact_count} for task, artifact_count in rows]


@app.get("/api/tasks/{task_id}")
def detail(task_id: str, owner=Depends(identity)):
    with Session() as db:
        task = owned(db, task_id, owner)
        return {**task_json(task, True), "files": [file_json(f) for f in db.scalars(select(File).where(File.task_id == task_id))]}


@app.post("/api/tasks/{task_id}/messages")
async def follow_up(task_id: str, body: CreateTask, owner=Depends(identity)):
    if len(body.goal.strip()) < 3:
        raise HTTPException(422, "Write a follow-up with at least three characters")
    with Session.begin() as db:
        task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task or task.owner != owner:
            raise HTTPException(404, "Task not found")
        if task.status not in {"completed", "failed", "canceled"}:
            raise HTTPException(409, "Wait for this turn to finish or cancel it before sending a follow-up")
        cp = task.checkpoint
        existing = list(db.scalars(select(File).where(File.task_id == task_id)))
        archived_ids = {i for turn in cp.get("turns", []) for i in turn["file_ids"]}
        turns = cp.get("turns", []) + [{
            "goal": cp.get("current_goal", task.goal), "status": task.status,
            "error": task.error, "created": task.updated,
            "summary": next((r["output"].get("summary", "") for r in reversed(cp.get("results", [])) if r["tool"] == "finish"), ""),
            "file_ids": [f.id for f in existing if f.kind == "artifact" and f.id not in archived_ids],
            "usage": {k: cp.get(k, 0) for k in ["steps", "tokens", "cost", "elapsed"]},
        }]
        if len(turns) > 100:
            raise HTTPException(409, "Conversation has reached 100 turns; start a new task")
        if sum(f.kind == "upload" for f in existing) + len(set(body.file_ids)) > 10:
            raise HTTPException(422, "Attach up to 10 documents per conversation")
        for file_id in sorted(set(body.file_ids)):
            f = db.scalar(select(File).where(File.id == file_id).with_for_update())
            if not f or owned(db, f.task_id, owner).status != "staging":
                raise HTTPException(422, "Upload is missing or already attached")
            staging = db.get(Task, f.task_id)
            f.task_id = task.id
            db.delete(staging)
        task.checkpoint = {
            "turns": turns, "current_goal": body.goal.strip(), "current_file_ids": [],
            "context_results": (cp.get("context_results", []) + cp.get("results", []))[-40:],
        }
        task.status, task.error, task.lease, task.lease_until = "queued", None, None, 0
        emit(db, task, "message", summary=body.goal.strip(), status="queued")
    await notify(task_id)
    return {"status": "queued"}


@app.get("/api/tasks/{task_id}/events")
async def events(task_id: str, request: Request, after: int = 0, owner=Depends(identity)):
    with Session() as db:
        owned(db, task_id, owner)
    try:
        cursor = max(after, int(request.headers.get("Last-Event-ID", "0")))
    except ValueError:
        raise HTTPException(422, "Invalid event cursor") from None

    async def stream():
        nonlocal cursor
        for _ in range(120):
            if await request.is_disconnected():
                break
            with Session() as db:
                task = owned(db, task_id, owner)
                rows = list(db.scalars(select(Event).where(Event.task_id == task_id, Event.id > cursor).order_by(Event.id).limit(100)))
                terminal = task.status in {"completed", "failed", "canceled", "awaiting_approval"}
                for row in rows:
                    cursor = row.id
                    yield f"id: {row.id}\ndata: {json.dumps({'id': row.id, 'kind': row.kind, 'payload': row.payload, 'created': row.created})}\n\n"
            if terminal and len(rows) < 100:
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/tasks/{task_id}/cancel")
def cancel(task_id: str, owner=Depends(identity)):
    with Session.begin() as db:
        task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task or task.owner != owner:
            raise HTTPException(404, "Task not found")
        if task.status not in {"queued", "running", "awaiting_approval"}:
            raise HTTPException(409, "Task cannot be canceled in its current state")
        task.status, task.lease, task.lease_until = "canceled", None, 0
        emit(db, task, "status", status="canceled", summary="Canceled. Active operations are being stopped; committed artifacts remain available.")
    return {"status": "canceled"}


@app.post("/api/tasks/{task_id}/resume")
async def resume(task_id: str, owner=Depends(identity)):
    with Session.begin() as db:
        task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task or task.owner != owner:
            raise HTTPException(404, "Task not found")
        if task.status not in {"canceled", "failed"}:
            raise HTTPException(409, "Only failed or canceled tasks can resume")
        if task.checkpoint.get("approval", {}).get("approved") is False:
            raise HTTPException(409, "Denied action cannot be resumed; create a revised task")
        task.status, task.error = "queued", None
        emit(db, task, "status", status="queued", summary="Resume requested. Existing usage limits and results are preserved.")
    await notify(task_id)
    return {"status": "queued"}


@app.post("/api/tasks/{task_id}/approve")
async def approve(task_id: str, body: Approval, owner=Depends(identity)):
    with Session.begin() as db:
        task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task or task.owner != owner:
            raise HTTPException(404, "Task not found")
        cp = dict(task.checkpoint)
        approval = cp.get("approval")
        if task.status != "awaiting_approval" or not approval or approval["digest"] != body.digest:
            raise HTTPException(409, "Approval is stale or does not match the proposed action")
        cp["approval"] = {**approval, "approved": body.approved}
        task.checkpoint = cp
        task.status = "queued" if body.approved else "canceled"
        emit(db, task, "status", status=task.status, summary="Exact action approved" if body.approved else "Action denied")
    if body.approved:
        await notify(task_id)
    return {"status": "queued" if body.approved else "canceled"}


@app.get("/api/files/{file_id}")
def download(file_id: str, owner=Depends(identity)):
    with Session() as db:
        f = db.get(File, file_id)
        if not f:
            raise HTTPException(404, "File not found")
        owned(db, f.task_id, owner)
        return FileResponse(
            storage.path(f.storage_key),
            media_type=f.mime,
            filename=f.name,
            headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'", "Cache-Control": "private, no-store"},
        )
