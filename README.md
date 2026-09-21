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

Enable Corepack so the console uses the pinned pnpm version:

```bash
corepack enable
```

## Local setup

The participant inbox is **not** in this repository. Point `VERIFY_DATA_DIR` at the unzipped hackathon bundle.

```bash
git clone https://github.com/ubturja/VeriFY.git
cd VeriFY
cp .env.example .env
```

Edit `.env`:

- `VERIFY_DATA_DIR` should resolve to `sdoc-hackathon-bundle` (from this folder that is `../../sdoc-hackathon-bundle` if the repo lives at `Dev/VeriFY`).
- Put `GEMINI_API_KEY` and `GROQ_API_KEY` in `.env` only. Never commit them.
- Set `IMAP_USERNAME=wesuffertogether22@gmail.com` and add a Gmail app password when you want live mail.

Install Python 3.12 (uv downloads it) and dependencies:

```bash
cd backend
uv python install 3.12
uv sync
cd ..
```

The console uses Node 22. Enable Corepack if you can (`corepack enable`), then `pnpm install`. If Corepack cannot write to `/usr/bin`, use npm:

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

## Process the sample inbox

```bash
make eval
```

This reads every email under `VERIFY_DATA_DIR`, writes `artifacts/submission.json` in the required scoreboard shape, and, if `VERIFY_GROUND_TRUTH` is set, prints a local score. Ground truth is never committed.

You can also drop a new email into the console with **Submit email**. Organizers can test with messages this repository has never seen.

On a case page, **Confirm** accepts the current verdict. It does not change category, status, or defect fields. **Retry** re-runs the pipeline and clears that stamp. Both actions are written to the Audit log. **Poll mailbox** on the queue reads `wesuffertogether22@gmail.com` over IMAP once `IMAP_APP_PASSWORD` is set.

## Cloud (no Azure credits)

Azure for Students and many personal accounts cannot grant the credits this demo would need. Host the same Docker API on Render's free tier and the console on Cloudflare Pages or a Render static site. Terraform under `infra/` remains the Averis production mapping.

See [docs/cloud.md](docs/cloud.md). `render.yaml` is the Render Blueprint.

Demo mailbox: `wesuffertogether22@gmail.com` (IMAP). Put a Gmail app password in `IMAP_APP_PASSWORD` locally or in the host's secret env. Never commit it.

## Configuration

Every runtime setting is an environment variable. See `.env.example`. In the hackathon cloud they are Render or Cloudflare secrets. In Azure the same names are populated from Key Vault. The application refuses to start if a required secret is empty in a non-local environment.

## Security

- Secrets live in `.env` locally, host env vars on Render, and Key Vault in Azure.
- Email bodies are treated as untrusted input and are never interpolated into system prompts as instructions.
- The dataset and `ground_truth.json` are git-ignored.
- CORS is restricted to `VERIFY_CORS_ORIGINS`.

## License

Proprietary to the We Suffer Together hackathon team unless otherwise agreed.
