"""Shared atomic request quotas; fail closed when configured Redis is unavailable."""
import asyncio
import hashlib
import time

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


class RequestLimiter:
    def __init__(self, url):
        self.redis = Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1) if url else None
        self.local = {}
        self.lock = asyncio.Lock()

    async def close(self):
        if self.redis:
            await self.redis.aclose()

    async def check(self, owner, bucket, limit, window):
        key = "autoagent:requests:" + hashlib.sha256(f"{owner}:{bucket}".encode()).hexdigest()
        if self.redis:
            try:
                count, remaining = await self.redis.eval(SCRIPT, 1, key, window)
            except RedisError:
                raise HTTPException(503, "Request quota service unavailable; retry shortly", headers={"Retry-After": "5"}) from None
        else:
            # Single-process local development only. Production replicas share Redis.
            async with self.lock:
                now = time.monotonic()
                self.local = {k: v for k, v in self.local.items() if v[1] > now}
                count, expiry = self.local.get(key, (0, now + window))
                if len(self.local) >= 10000 and key not in self.local:
                    raise HTTPException(503, "Local quota capacity reached")
                count += 1
                self.local[key] = (count, expiry)
                remaining = max(1, int(expiry - now + 1))
        if count > limit:
            raise HTTPException(429, "Too many workspace requests; retry shortly", headers={"Retry-After": str(max(1, remaining))})
