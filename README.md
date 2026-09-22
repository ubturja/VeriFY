# VeriFY

VeriFY is a shipping-document verification service. It reads a documentation inbox, classifies each message, compares a Shipping Instruction against a draft Bill of Lading, and produces an evidence-linked discrepancy report. Uncertain cases are sent to a reviewer with the source documents and the reason they could not be decided.

Nothing in the product path is hardcoded against a particular inbox. New emails, languages, and layouts are handled by a Unicode-clean pipeline with a rules layer for high-confidence signals and an LLM layer for everything else.

## What it does

1. **Classify** incoming mail into `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL`, or `SPAM`.
2. **Extract** shipper, consignee, notify party, ports, container count, and gross weight from SI and BL attachments (txt, PDF, Word, Excel, and scans).
3. **Compare** those seven fields after synonym and Unicode normalisation, and report mismatches side by side.
4. **Escalate** when a document is the wrong type, missing, unreadable, or incomplete, instead of guessing.

## Repository layout

```
backend/          Python 3.12 API, workers, and verification pipeline
console/          React + TypeScript review console
infra/            Terraform for Azure (Southeast Asia)
docs/             Architecture and design decisions
docker-compose.yml
```

## Prerequisites

Install these on Linux, macOS, or Windows with WSL2.

| Tool | Why | Install |
| --- | --- | --- |
| Docker Engine + Compose plugin | Local Postgres, Azurite, API, worker | [Docker Engine](https://docs.docker.com/engine/install/) then the Compose plugin |
| [uv](https://docs.astral.sh/uv/) | Pins Python 3.12 for this repo. System Python 3.14 is not used. | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 22 | Console toolchain | [nodejs.org](https://nodejs.org/) or `nvm install 22` |
| Git | Version control | OS package manager |

Optional, installed when you deploy:

| Tool | Why | Install |
| --- | --- | --- |
| Terraform >= 1.7 | Azure infrastructure | [hashicorp.com/terraform](https://developer.hashicorp.com/terraform/install) |
| Azure CLI | `az login` and Key Vault | [learn.microsoft.com](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| GitHub CLI | PRs and secrets | [cli.github.com](https://cli.github.com/) |

Confirm:

```bash
docker compose version
uv --version
node --version   # v22 or newer
```

The console installs with npm. CI uses Node 22 and `npm ci`.

## Local setup

The participant inbox is **not** in this repository. Point `VERIFY_DATA_DIR` at the unzipped hackathon bundle.

```bash
git clone https://github.com/ubturja/VeriFY.git
cd VeriFY
cp .env.example .env
```

Edit `.env`:

- `VERIFY_DATA_DIR` should resolve to `sdoc-hackathon-bundle`. From this folder, next to the bundle, that is `../sdoc-hackathon-bundle`.
- Put `GEMINI_API_KEY` and `GROQ_API_KEY` in `.env` only. Never commit them. Those keys are for live mail. `make eval` does not call them.
- Leave `IMAP_USERNAME` and `IMAP_APP_PASSWORD` empty. Sign in from the console with any Gmail address and a Gmail app password. The API checks that password with IMAP and keeps the mailbox separate from every other sign-in.

Install Python 3.12 (uv downloads it) and dependencies:

```bash
cd backend
uv python install 3.12
uv sync
cd ..
```

The console uses Node 22 and npm:

```bash
cd console
npm install
npm run dev
```

Start supporting services:

```bash
docker compose up -d postgres azurite
```

Run the API and console in two terminals:

```bash
# terminal 1
make api

# terminal 2
make console
```

- API: http://localhost:8000/docs
- Console: http://localhost:5173

Sign in on the console. `/` is the welcome screen. The queue is at `/queue`. The mailbox owner is a supervisor and can switch the session to reviewer or auditor. An auditor can read. A reviewer can confirm, correct, and retry. A supervisor can also edit policy and open the webhook log and the dead-letter list.

## Process the sample inbox

```bash
make eval
```

This reads every email under `VERIFY_DATA_DIR` with the rules pipeline only. API keys in `.env` are ignored. It writes `artifacts/submission.json` in the required scoreboard shape, and, if `VERIFY_GROUND_TRUTH` is set, prints a local score. Ground truth is never committed.

Local scans need Tesseract with English, Chinese, and Malay:

```bash
brew install tesseract tesseract-lang
```

You can also drop a new email into the console with **Submit email**. Organizers can test with messages this repository has never seen.

On a case page, **Confirm** accepts the current verdict. It does not change category, status, or defect fields. **Correct** is the human override: it rewrites those scoreboard fields and sets `decided_by` to `human`. **Retry** re-runs the pipeline and clears that stamp. Each action is written to the Audit log. A correction also stores the party-name pair and refits a small local model for that mailbox. The model can suggest that two names are the same. It does not change a mismatch into a match. Only the exact stored correction does that.

**Poll mailbox** reads the signed-in Gmail account. The API also polls that mailbox in the background every `IMAP_POLL_SECONDS`. Ingest goes through a file-backed job queue. A job that still fails after its retries lands on the dead-letter page.

**Submit email** accepts uploaded files (base64) as well as paths under `VERIFY_DATA_DIR`, so organizers can test with mail this repository has never seen.

## Cloud (no Azure credits)

Azure for Students and many personal accounts cannot grant the credits this demo would need. Host the same Docker API on Render's free tier and the console on Cloudflare Pages or a Render static site. Terraform under `infra/` remains the Averis production mapping.

See [docs/cloud.md](docs/cloud.md). `render.yaml` is the Render Blueprint.

There is no built-in demo mailbox. Each reviewer signs in with their own Gmail address and app password. Never commit that password.

## Configuration

Every runtime setting is an environment variable. See `.env.example`. In the hackathon cloud they are Render or Cloudflare secrets. In Azure the same names are populated from Key Vault. The application refuses to start if a required secret is empty in a non-local environment.

## Security

- Secrets live in `.env` locally, host env vars on Render, and Key Vault in Azure.
- Email bodies are treated as untrusted input and are never interpolated into system prompts as instructions.
- The dataset and `ground_truth.json` are git-ignored.
- CORS is restricted to `VERIFY_CORS_ORIGINS`.

## License

Proprietary to the We Suffer Together hackathon team unless otherwise agreed.
