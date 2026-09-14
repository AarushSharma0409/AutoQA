# Browse the application database

Prisma Studio connects directly to the existing Docker PostgreSQL database. No Prisma migrations or backend ORM changes are needed.

Start Docker Desktop, then run from the project directory:

```powershell
docker compose up -d postgres
docker compose -f compose.yaml -f compose.studio.yaml up -d --no-deps studio
```

Open http://127.0.0.1:5555. The first launch downloads Prisma CLI, so it may take a few minutes.

Studio can edit and delete real application records. It is an administrator tool, bound only to this computer, and must not be forwarded through ngrok. Supabase authentication users are managed separately in Supabase.

Stop the browser service:

```powershell
docker compose -f compose.yaml -f compose.studio.yaml stop studio
```

The connection in compose.studio.yaml matches the development PostgreSQL credentials in compose.yaml. Update both if those credentials change.
