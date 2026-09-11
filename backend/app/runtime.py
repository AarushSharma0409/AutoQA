import asyncio
import hashlib
import json
import time
import uuid
from copy import deepcopy
from sqlalchemy import or_, select, update
from .config import settings
from .db import File, Session, Task, emit
from .provider import demo_decision, live_decision, prepare_call
from .schemas import Decision, TOOLS
from .tools import execute


def digest(decision):
    return hashlib.sha256(json.dumps({"tool": decision.tool, "arguments": decision.arguments}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def claim(task_id):
    lease = str(uuid.uuid4())
    with Session.begin() as db:
        result = db.execute(
            update(Task)
            .where(Task.id == task_id, or_(Task.status == "queued", (Task.status == "running") & (Task.lease_until < time.time())))
            .values(status="running", lease=lease, lease_until=time.time() + settings().lease_seconds)
        )
        if result.rowcount != 1:
            return None
        task = db.get(Task, task_id)
        emit(db, task, "status", status="running", summary="Worker acquired execution lease. Saved checkpoints will be reused.")
    return lease


def save(task_id, lease, checkpoint, kind, payload, status=None, error=None, artifacts=None):
    with Session.begin() as db:
        result = db.execute(
            update(Task)
            .where(Task.id == task_id, Task.lease == lease, Task.status == "running", Task.lease_until > time.time())
            .values(checkpoint=checkpoint, lease_until=time.time() + settings().lease_seconds)
        )
        if result.rowcount != 1:
            return False
        task = db.get(Task, task_id)
        if status:
            task.status = status
            task.lease = None
            task.lease_until = 0
        task.error = error
        for f in artifacts or []:
            stored = File(task_id=task_id, **f)
            db.add(stored)
            db.flush()
            if "current_file_ids" in checkpoint:
                checkpoint["current_file_ids"].append(stored.id)
        if "current_file_ids" in checkpoint:
            task.checkpoint = deepcopy(checkpoint)
        emit(db, task, kind, **payload)
    return True


async def guard(task_id, lease, start, elapsed, operation):
    """Keep lease alive; promptly cancel the active async tool when control changes."""
    future = asyncio.create_task(operation)
    try:
        while not future.done():
            await asyncio.wait({future}, timeout=0.25)
            if future.done():
                return await future
            with Session.begin() as db:
                result = db.execute(
                    update(Task)
                    .where(Task.id == task_id, Task.lease == lease, Task.status == "running", Task.lease_until > time.time())
                    .values(lease_until=time.time() + settings().lease_seconds)
                )
                if result.rowcount != 1:
                    raise asyncio.CancelledError()
            if elapsed + time.monotonic() - start > settings().max_seconds:
                raise TimeoutError("Task duration budget exhausted")
        return await future
    finally:
        if not future.done():
            future.cancel()
            try:
                await future
            except (asyncio.CancelledError, Exception):
                pass


async def run_task(task_id):
    lease = claim(task_id)
    if not lease:
        return
    started = time.monotonic()
    with Session() as db:
        task = db.get(Task, task_id)
        goal, mode = task.goal, task.mode
        cp = deepcopy(task.checkpoint)
        goal = cp.get("current_goal", goal)
        files = [{"id": f.id, "name": f.name} for f in db.scalars(select(File).where(File.task_id == task_id, File.kind == "upload"))]
    elapsed = cp.get("elapsed", 0)
    if cp.get("pending_started"):
        elapsed += max(0, time.time() - cp.pop("pending_started"))
        cp["elapsed"] = elapsed
    if cp.pop("provider_reservation", None):
        cp["accounting_note"] = "Interrupted provider call: reserved upper-bound tokens retained; actual billing is unknown."
    cp.setdefault("results", [])
    cp.setdefault("steps", 0)
    cp.setdefault("tokens", 0)
    cp.setdefault("cost", 0)
    cp.setdefault("failures", {})
    if cp.get("pending"):
        pending = Decision.model_validate(cp["pending"])
        if pending.tool == "python":
            # The container outcome is uncertain after worker death. Explicitly re-authorize.
            cp["approval"] = {
                "digest": digest(pending),
                "decision": pending.model_dump(),
                "approved": None,
                "reason": "Worker interrupted during Python execution; inspect partial outputs before retrying.",
            }
            cp.pop("pending", None)
            save(task_id, lease, cp, "approval", cp["approval"], status="awaiting_approval")
            return
        cp.pop("pending", None)
        save(task_id, lease, cp, "recovery", {"summary": "Interrupted read/derived-artifact action will be retried. Only committed artifacts are visible."})
    save(task_id, lease, cp, "plan", {"summary": "Inspect inputs → gather required evidence → calculate → generate deliverables → evaluate.", "mode": mode})
    try:
        while True:
            cp["elapsed"] = elapsed + time.monotonic() - started
            cfg = settings()
            if cp["steps"] >= cfg.max_steps or cp["tokens"] >= cfg.max_tokens or cp["cost"] >= cfg.max_cost or cp["elapsed"] >= cfg.max_seconds:
                raise ValueError("Execution budget exhausted. Partial results are available; start a narrower task.")
            approval = cp.get("approval")
            if approval and approval["approved"] is True:
                decision = Decision.model_validate(approval["decision"])
                if digest(decision) != approval["digest"]:
                    raise ValueError("Approval does not match the proposed action")
            else:
                if mode == "demo":
                    decision, tokens = demo_decision(goal, cp, files), 0
                else:
                    prepared = prepare_call(goal, cp, files)
                    reserve = prepared[1]
                    cp["tokens"] += reserve
                    cp["cost"] += reserve * cfg.token_price_per_million / 1_000_000
                    cp["provider_reservation"] = reserve
                    cp["pending_started"] = time.time()
                    if not save(task_id, lease, cp, "provider", {"summary": "Provider call budget reserved before dispatch."}):
                        return
                    decision, tokens = await guard(task_id, lease, started, elapsed, live_decision(goal, cp, files, prepared=prepared))
                    cp["tokens"] -= cp.pop("provider_reservation")
                    cp["cost"] -= reserve * cfg.token_price_per_million / 1_000_000
                    cp.pop("pending_started", None)
                cp["tokens"] += tokens
                cp["cost"] += tokens * cfg.token_price_per_million / 1_000_000
            # Schema validation precedes approval and execution.
            TOOLS[decision.tool].model_validate(decision.arguments)
            action_hash = digest(decision)
            if cp["failures"].get(action_hash, 0) >= 2:
                raise ValueError("Repeated identical action failed twice; revise the task or input before resuming")
            if decision.tool == "python" and not (approval and approval["approved"] is True and approval["digest"] == action_hash):
                cp["approval"] = {
                    "digest": action_hash,
                    "decision": decision.model_dump(),
                    "approved": None,
                    "reason": "Approve this exact code and input file set for isolated execution.",
                }
                save(task_id, lease, cp, "approval", cp["approval"], status="awaiting_approval")
                return
            cp.pop("approval", None)
            cp["steps"] += 1
            cp["pending"] = decision.model_dump()
            cp["pending_started"] = time.time()
            if not save(task_id, lease, cp, "action", {"tool": decision.tool, "summary": decision.summary, "step": cp["steps"]}):
                return
            try:
                output, artifacts = await guard(
                    task_id,
                    lease,
                    started,
                    elapsed,
                    asyncio.wait_for(execute(task_id, decision.tool, decision.arguments, cp, mode), timeout=min(90, cfg.max_seconds)),
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Never persist raw provider HTTP errors, request headers, or credentials.
                message = (
                    str(exc)[:400]
                    if isinstance(exc, (ValueError, TimeoutError))
                    else f"{type(exc).__name__}: tool failed; check service availability and input format"
                )
                output, artifacts = {"error": message}, []
                cp["failures"][action_hash] = cp["failures"].get(action_hash, 0) + 1
            cp.pop("pending", None)
            cp.pop("pending_started", None)
            cp["elapsed"] = elapsed + time.monotonic() - started
            cp["results"].append(
                {"tool": decision.tool, "arguments": decision.arguments if decision.tool != "python" else {"code_digest": action_hash}, "output": output}
            )
            completed = decision.tool == "finish" and "error" not in output
            if completed and (not cp["results"][:-1] or "error" in cp["results"][-2]["output"]):
                raise ValueError("Cannot complete after an unresolved tool failure")
            if completed:
                successful = {r["tool"] for r in cp["results"] if "error" not in r["output"]}
                requested = goal.lower()
                required = set()
                if any(word in requested for word in ["report", "pdf"]):
                    required.add("report")
                if any(word in requested for word in ["research", "market context"]):
                    required.add("search")
                if any(word in requested for word in ["browse", "navigate", "extract"]) and "http" in requested:
                    required.add("browse")
                if files:
                    required.add("ingest")
                if not required.issubset(successful):
                    raise ValueError("Required evidence or deliverables are missing: " + ", ".join(sorted(required - successful)))
                ingested_ids = {r.get("arguments", {}).get("file_id") for r in cp["results"] if r["tool"] == "ingest" and "error" not in r["output"]}
                if not {f["id"] for f in files}.issubset(ingested_ids):
                    raise ValueError("Some uploaded files have not been inspected")
                with Session() as db:
                    delivered = list(db.scalars(select(File).where(File.task_id == task_id, File.kind == "artifact")))
                if "spreadsheet" in requested and not any(f.name.endswith(".xlsx") for f in delivered):
                    raise ValueError("Requested spreadsheet has not been generated")
                if "chart" in requested and not any(f.mime in {"image/svg+xml", "image/png"} for f in delivered):
                    raise ValueError("Requested chart has not been generated")
            if not save(
                task_id,
                lease,
                cp,
                "result",
                {
                    "tool": decision.tool,
                    "output": output,
                    "artifacts": [f["id"] for f in artifacts],
                    "usage": {"steps": cp["steps"], "tokens": cp["tokens"], "cost": cp["cost"], "elapsed": cp["elapsed"]},
                },
                status="completed" if completed else None,
                artifacts=artifacts,
            ):
                return
            if completed:
                return
    except asyncio.CancelledError:
        # Cancellation state is persisted by the API; a dead worker loses its lease.
        return
    except Exception as exc:
        message = (
            str(exc)[:500]
            if isinstance(exc, (ValueError, TimeoutError))
            else f"{type(exc).__name__}: runtime stopped. Verify provider configuration and retry."
        )
        cp.pop("pending_started", None)
        if cp.get("provider_reservation"):
            cp["accounting_note"] = "Provider call failed: reserved upper-bound tokens retained; actual billing may be unknown."
        cp["elapsed"] = elapsed + time.monotonic() - started
        save(task_id, lease, cp, "error", {"summary": message}, status="failed", error=message)
