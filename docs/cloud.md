# Cloud without Azure credits

Azure for Students and many personal Microsoft accounts do not grant the credits this prototype would need. The live demo still has to run in the cloud: a public URL, containerised API, env-based secrets, and a path that maps onto Averis's Azure estate.

## What to use now

| Concern | Hackathon host (no paid Azure) | Averis production (Terraform in `infra/`) |
| --- | --- | --- |
| API | [Render](https://render.com) free Web Service (Docker) | Azure Container Apps |
| Console | Render static site or [Cloudflare Pages](https://pages.cloudflare.com) | Azure Static Web Apps |
| Secrets | Render / Cloudflare environment variables | Key Vault |
| Postgres (optional) | [Neon](https://neon.tech) free project | Azure Database for PostgreSQL |
| Blobs | Local disk on the API container | Azure Blob Storage |
| Queue | File job queue with dead letters | Service Bus |
| LLM | Rules for the scoreboard. Gemini, then Groq, for live mail | Same interface, Azure OpenAI later |
| Mail | The Gmail account that signed in | Microsoft Graph |

Render's free Web Service does not require an Azure or AWS subscription. It runs the existing `backend/Dockerfile`, sleeps after idle time, and wakes on the first request. That is enough for judges to open a URL. Cloudflare Pages is the same idea for the React console and also has a no-card free tier.

Oracle Cloud Always Free and Fly.io need a payment card even when the bill is zero. Railway's trial credits expire. Those are backups, not the default.

## Deploy the API on Render

1. Push this repository to GitHub.
2. In Render, New Blueprint and select the repo. `render.yaml` defines `verify-api`.
3. Set these secret env vars in the Render dashboard (never commit them):
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY`
   - `IMAP_APP_PASSWORD` only if you want one mailbox registered at startup. Reviewers otherwise sign in with their own Gmail app password.
   - `VERIFY_CORS_ORIGINS` (the console URL, comma-separated)
4. `VERIFY_DATA_DIR` on a free instance will not contain the private hackathon bundle. Judges can **Submit email** with attached files. Local `make eval` is the scoring path, and it stays on the rules pipeline.

The free disk is ephemeral. Confirm and Correct actions survive a process restart on the same instance via `VERIFY_STATE_PATH` (JSON or SQLite). They are lost if Render recycles the filesystem. Replay the inbox, or attach Neon later, if a longer-lived demo is needed.

The API polls Gmail in the background when `IMAP_APP_PASSWORD` and `VERIFY_IMAP_AUTOPOLL=true` are set.

## Deploy the console

Build with the API origin baked in:

```bash
cd console
VITE_API_URL=https://YOUR-API.onrender.com npm run build
```

Point Cloudflare Pages or a Render static site at `console/`, build command `npm ci && npm run build`, publish directory `dist`. Set `VITE_API_URL` to the Render API origin (no trailing slash). CORS on the API must include that Pages origin.

## What this still proves

- The product is not a laptop-only script: it is a container with health checks, CORS, and secret injection.
- Compute, static hosting, and models are swappable. `infra/` is the Averis mapping; Render is the student mapping of the same interfaces.
- Human review (Confirm and Correct) is an API with an audit log, not a UI-only click.
