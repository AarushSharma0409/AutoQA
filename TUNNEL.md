# Share AutoQA for a demo

The tunnel forwards the Docker web gateway to your free ngrok HTTPS domain. Your computer and Docker must stay running. This is temporary sharing, not independent hosting.

## One-time configuration

Create a free HTTPS-tunnel account at https://dashboard.ngrok.com/signup. In the ignored root `.env`, add your own values:

```dotenv
NGROK_AUTHTOKEN=your-private-ngrok-authtoken
NGROK_URL=https://your-assigned-domain.ngrok-free.app
```

Use the exact free domain assigned in the dashboard; its suffix may differ from the example. Never put the auth token in source control or chat. The tunnel container receives only its ngrok token, not the model/database credentials. Agent HTTP introspection is disabled, and no inspector port is published.

Before sharing:

1. Confirm `/api/auth/config` reports `supabase` and unauthenticated `/api/tasks` returns 401. Never expose the local demo identity mode.
2. Append the exact `NGROK_URL` origin to `ALLOWED_ORIGINS`, retaining your existing local origins. Recreate the API containers so they load the change.
3. Add `NGROK_URL/` to Supabase's allowed redirect URLs, and set the Site URL to that address if using it as your main demo URL. This configuration change must be confirmed in the dashboard workflow.
4. Supabase's default sender is restricted to team addresses. Configure SMTP for other users. PKCE email links should be opened in the same browser that initiated signup/reset; a public URL alone does not remove that requirement.

## Start and stop

From the project directory, start AutoQA first:

```powershell
docker compose --profile live up -d --scale api=2 --scale worker=2
docker compose -f compose.yaml -f compose.tunnel.yaml up -d --no-deps tunnel
```

Stop public sharing without stopping AutoQA or deleting data:

```powershell
docker compose -f compose.yaml -f compose.tunnel.yaml stop tunnel
```

The tunnel intentionally does not automatically restart when Docker restarts. Start it explicitly when you want to share. Free-plan request/bandwidth limits and a visitor interstitial may apply. No raw API, database, Redis, broker or Docker socket ports are forwarded.

## Verification before sharing the link

- Load the public HTTPS page and confirm the account screen.
- Confirm anonymous requests cannot list tasks or download files.
- Sign in, create one small task, verify event updates and download its output.
- Verify logout and returning to saved work, and that another account cannot see it.

Only share with trusted testers initially. The existing Python broker has host Docker access; this tunnel does not turn that setup into hardened public multi-tenant infrastructure.

Official setup: https://ngrok.com/docs/using-ngrok-with/docker
