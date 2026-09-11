import asyncio
import signal
import time
from sqlalchemy import or_, select
from .config import settings
from .db import Session, Task, migrate
from .runtime import run_task


async def main():
    settings().validate_runtime()
    migrate()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    redis = None
    if settings().redis_url:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings().redis_url, socket_timeout=3)
    while not stop.is_set():
        # DB is the durable queue/outbox. Redis only reduces wake-up latency.
        with Session() as db:
            ids = list(
                db.scalars(
                    select(Task.id)
                    .where(or_(Task.status == "queued", (Task.status == "running") & (Task.lease_until < time.time())))
                    .order_by(Task.created)
                    .limit(8)
                )
            )
        for task_id in ids:
            if stop.is_set():
                break
            await run_task(task_id)
        if not ids:
            if redis:
                try:
                    await redis.blpop("autoagent:queue", timeout=2)
                except Exception:
                    await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)
    if redis:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
