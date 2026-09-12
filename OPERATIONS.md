# Operating AutoAgent

## Where the data lives

The active Docker installation uses PostgreSQL 17, database `autoagent`, service `postgres`, container `autoqa-postgres-1`. Tables store tasks, conversation checkpoints, events, file metadata and migration versions. The Docker volume is `autoqa_postgres`, mounted at `/var/lib/postgresql/data` in the container. Its Docker-internal path is `/var/lib/docker/volumes/autoqa_postgres/_data`; on Windows this is inside Docker Desktop's Linux VM, not a normal project folder. Use Docker Desktop → Volumes → autoqa_postgres to inspect its existence; use PostgreSQL tools to inspect records.

Uploads and generated report bytes are in `autoqa_artifacts`, mounted at `/app/data` in API/worker containers. Redis uses `autoqa_redis` for wake-up notifications and shared request quotas. PostgreSQL is the durable task queue; Redis is not the task-history database. Standalone development and isolated unit tests can use SQLite, which is separate from the active Docker database.

Inspect the database without publishing a network port:

```powershell
docker compose exec postgres psql -U autoagent -d autoagent
```

Inside psql, `\dt` lists tables and `\q` exits. Never use `docker compose down -v` to restart the app: `-v` removes persistent volumes.

## Scaling on this machine

```powershell
docker compose --profile live up --build -d --scale api=2 --scale worker=2
```

The Nginx gateway owns localhost ports 3000 and 8000. API/web replicas only expose internal ports. Docker DNS is refreshed every five seconds, and Nginx distributes API requests with least connections. Task leases prevent two workers from committing the same execution. API migrations use a PostgreSQL advisory lock; database pools are bounded per process. Streaming events release database connections before waiting for clients.

This is single-host horizontal scaling, not high availability across machines. The gateway, PostgreSQL, Redis and artifact volume remain single-host dependencies. Adding workers increases simultaneous model demand and can exhaust a free provider quota faster. Increase replicas only with matching model capacity. Do not scale SQLite or copy local artifact volumes between independent hosts.

## Request limits

- Authenticated reads: 600 per account per 60 seconds by default.
- Authenticated writes: 30 per account per 60 seconds, shared across API replicas.
- Cancellation bypasses account request limits so it remains available during overload.
- Exceeding a quota returns 429 with `Retry-After`.
- Configured Redis unavailable: quota-protected requests return 503; they do not silently bypass limits.
- Without Redis, the limiter is per-process and intended only for standalone development.
- Gateway connection/request limits provide a separate coarse limit before authentication.

Configure `RATE_LIMIT_READS`, `RATE_LIMIT_WRITES`, `RATE_LIMIT_WINDOW`, `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` in the ignored `.env`. Account request limits are separate from Groq/Tavily provider quotas and task token/cost budgets. Fixed windows permit boundary bursts; this is not a DDoS protection service.

Implementation references: [Redis atomic counter limits](https://redis.io/docs/latest/commands/incr/) and [Nginx upstream balancing and DNS resolution](https://nginx.org/en/docs/http/ngx_http_upstream_module.html).

## Before public deployment

The current app remains loopback-only. Public deployment still requires:

1. A domain and TLS termination, plus an explicit allowed-origin configuration.
2. Proper login/identity lifecycle, token revocation/rotation, and a secret manager.
3. Replace the development PostgreSQL password and separate the runtime DB role from the migration/admin role. Changing `POSTGRES_PASSWORD` alone does not rotate an existing database password.
4. Tested encrypted PostgreSQL and artifact backups with an off-host restore procedure. Backup both metadata and files; a database-only backup is incomplete.
5. Storage quotas/retention, task-admission quotas, monitoring, alerts and capacity planning.
6. Managed/replicated PostgreSQL and Redis, object storage and multiple gateway hosts if host-failure recovery is required.

The trusted Python broker retains access to the host Docker socket. Keep it private and isolate it onto dedicated infrastructure for public multi-tenant use. Passing local tests or dependency advisory checks is not a penetration test or a guarantee of security.

## Verification

`evaluation/security-scaling-tests.xml` records the real PostgreSQL/Docker suite. `scripts/verify_scaling.py` verifies shared limits, bounded concurrent reads and duplicate-free fixture completion across workers. It creates audit-owned tasks and retains their artifacts. `compose.verify.yaml`, used with project name `autoqa-verification`, isolates browser tests on port 3100 without model credentials or live task data. Stop that test stack after testing; keep its volumes unless deliberately discarding test data.
