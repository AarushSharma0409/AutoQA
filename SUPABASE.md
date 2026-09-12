# Account authentication

AutoQA uses Supabase Auth for email signup, confirmation, login, password recovery and session refresh. The client workspace uses the official Supabase JavaScript client with PKCE and persistent browser sessions. API authorization is independently verified by FastAPI against the project's public signing keys; a client-side session alone never authorizes access.

## Configuration

Set these in the ignored root `.env` file:

```dotenv
AUTH_PROVIDER=supabase
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

Use the publishable key, never a service-role/secret key. Configuration is served at `/api/auth/config` at runtime, so the frontend image contains no project credentials and needs no build-time environment variables. The Supabase project must use an asymmetric signing key (ES256 or RS256). The configured AutoQA project uses ES256.

After configuration, rebuild/restart the stack:

```powershell
docker compose --profile live up --build -d --scale api=2 --scale worker=2
```

`AUTH_PROVIDER=local` retains the developer token workflow. In Supabase mode account authorization also applies when `MODE=demo`; demo planning never bypasses account isolation. Local signed tokens are rejected in Supabase mode.

## Dashboard configuration

Project: AutoQA (`xwtfnzskmbvsezsifssg`), Singapore, free organization.

- Email signup enabled; email confirmation enabled; anonymous sign-in disabled.
- Site URL currently `http://localhost:3000`.
- Approved additional redirect `http://127.0.0.1:3000/` saved.
- Project created with automatic table exposure disabled and automatic RLS enabled for new public tables. No application tables or policies were migrated to Supabase.
- Custom SMTP is not configured. Supabase's default sender only delivers to organization team addresses, currently at 2 messages/hour. Configure a verified sender with an SMTP provider before public signup. See [official SMTP documentation](https://supabase.com/docs/guides/auth/auth-smtp).

For deployment, replace the Site URL and add exact HTTPS production redirects. Do not use broad wildcard redirects in production. Configure SMTP credentials directly in Supabase, not the frontend or chat. Open confirmation/recovery links in the same browser that initiated the request, as required by PKCE.

## Where data lives

| Data | Location |
|---|---|
| User identities, password hashes, auth sessions | Supabase Auth |
| Tasks, conversation turns, events, file metadata | Existing Docker PostgreSQL database `autoagent`, volume `autoqa_postgres` |
| Uploaded documents and generated artifacts | Existing Docker volume `autoqa_artifacts`, `/app/data/files` |
| Queue and shared account rate limits | Docker Redis |

Tasks are owned by the verified Supabase user UUID. Returning to the same account restores its history, including from another browser. All file, event, follow-up and control routes retain owner checks. Signing out clears the rendered workspace and the local session; it does not delete saved work. Previously issued access tokens remain valid until their expiry, as with JWT-based authorization generally; use short provider token lifetimes and appropriate revocation controls for sensitive deployments.

Existing tasks owned by `sharm`, `local-demo`, or audit identities remain preserved under those owners. They are **not** automatically assigned to the first signup. A deliberate administrator migration with a verified destination UUID is needed to transfer legacy history.

## Verification

- Backend: 57 passed, 7 skipped on the host. Includes 10 new account tests for issuer, audience, expiry, signatures, roles, anonymous rejection and persisted owner isolation. The skipped tests require running Docker/PostgreSQL.
- Browser: 6 passed across desktop/mobile for sign-in, reload persistence, expired-session renewal, sign-out, signup/reset feedback, accessibility, and continued conversations. Supabase/API responses were mocked; no real email was sent by these tests.
- Public project JWKS endpoint verified live: ES256 signing key available.
- Frontend production build, TypeScript, ESLint and backend Ruff checks passed.
- Desktop/mobile screenshots: `evaluation/account-desktop.png`, `evaluation/account-mobile.png`.
- Full real email signup/login/recovery and container rollout remain pending Docker engine recovery and a user-completed signup. Automated tests are not a claim that production email delivery works.

Docker Desktop currently fails while initializing its inference manager (`dockerInference` socket). A normal `docker desktop restart --timeout 60` also failed to stop its processes. No factory reset, volume deletion or database migration was performed. Restart Docker Desktop/Windows before rerunning the Compose command above.

The broader deployment requirements in `OPERATIONS.md` still apply: HTTPS, database credential hardening, backup/restore, monitoring and capacity planning. This change does not migrate task storage to the cloud or resolve model-provider quota limits.
