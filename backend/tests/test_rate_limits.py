import asyncio
import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError
from app.config import settings
from app.rate_limit import RequestLimiter


def test_request_limits_separate_users_reads_and_writes(client, monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_writes", 2)
    path = '/api/tasks/missing/resume'
    assert client.post(path).status_code == 404
    assert client.post(path).status_code == 404
    rejected = client.post(path)
    assert rejected.status_code == 429
    assert int(rejected.headers['retry-after']) >= 1
    assert client.get('/api/tasks').status_code == 200
    assert client.post('/api/tasks/missing/cancel').status_code == 404


def test_limit_expiry_and_identity_isolation(monkeypatch):
    async def run():
        limiter = RequestLimiter('')
        monkeypatch.setattr('app.rate_limit.time.monotonic', lambda: 10)
        await limiter.check('alice', 'writes', 1, 60)
        with pytest.raises(HTTPException) as error:
            await limiter.check('alice', 'writes', 1, 60)
        assert error.value.status_code == 429
        await limiter.check('bob', 'writes', 1, 60)
        monkeypatch.setattr('app.rate_limit.time.monotonic', lambda: 71)
        await limiter.check('alice', 'writes', 1, 60)
    asyncio.run(run())


def test_redis_outage_fails_closed():
    class BrokenRedis:
        async def eval(self, *args):
            raise ConnectionError('private connection details')
    async def run():
        limiter = RequestLimiter('')
        limiter.redis = BrokenRedis()
        with pytest.raises(HTTPException) as error:
            await limiter.check('alice', 'writes', 1, 60)
        assert error.value.status_code == 503
        assert 'private' not in error.value.detail
    asyncio.run(run())
