# CLAUDE.md — Handoff instructions for Claude Code

> Read this top-to-bottom before touching anything. This is the contract between
> the scaffolding agent (Hermes) and you (Claude Code) running on Roey's org Mac.

## What this project is

Company Brain is a local-first memory engine that pulls Microsoft Fabric, Microsoft
365 (Graph) and Azure AI Foundry into one Postgres+pgvector database, then exposes
a small HTTP API for agents. Everything runs on the dev machine — no SaaS, no
external memory provider, no data leaves the laptop except calls to the source
APIs and to OpenAI for embeddings + extraction.

## How to set up on this Mac

```bash
# 1. Tools
brew install uv docker gh
open -a Docker        # make sure Docker Desktop is running

# 2. Project deps
cd ~/projects/company-brain   # or wherever you cloned it
uv sync                        # resolves and installs Python deps

# 3. Configure
cp .env.example .env
$EDITOR .env                   # fill in the values below
```

### Required env vars (in `.env`)

| Var | Where to get it |
|---|---|
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys — used for embeddings + fact extraction |
| `AZURE_TENANT_ID` | Azure Portal → Microsoft Entra ID → Overview |
| `AZURE_CLIENT_ID` | App registration created for this brain (Entra ID → App registrations → New) |
| `AZURE_CLIENT_SECRET` | Same app registration → Certificates & secrets. Optional if using device-code flow. |
| `FABRIC_WORKSPACE_IDS` | Comma-separated workspace GUIDs from https://app.fabric.microsoft.com (admin → workspaces) |
| `FOUNDRY_PROJECT_IDS` | Comma-separated project IDs from https://ai.azure.com |
| `WORK_IQ_DAYS_BACK` | How many days of mail/Teams to backfill (default 30) |
| `POSTGRES_DSN` | Pre-filled — points at the local docker-compose Postgres on 5433 |

### Microsoft Graph permissions (Work IQ)

In your Entra app registration, under **API permissions**, add these
**delegated** scopes (or **application** scopes if using service principal):

- `Mail.Read`
- `Files.Read.All`
- `Chat.Read`
- `Calendars.Read`
- `Sites.Read.All`
- `User.Read`

Then click **Grant admin consent** (you need a tenant admin to do this once).

If you're not a tenant admin and can't get a service principal, use device-code
flow:

```bash
uv run python -m connectors.work_iq.auth login
```

This pops a device-code URL, you sign in as yourself, and the token caches to
`~/.config/company-brain/work-iq-token.json`.

### Fabric permissions

The service principal (or your user) must be a **Member** or **Admin** on each
workspace listed in `FABRIC_WORKSPACE_IDS`, and the Fabric capacity backing
those workspaces must be **Active** (not paused).

### Foundry permissions

`Cognitive Services User` role on the Foundry resource group is enough for
read-only knowledge index ingest. We use `DefaultAzureCredential` so `az login`
works locally too.

## How to start the brain

```bash
./scripts/init-db.sh           # docker compose up -d + applies schema.sql
uv run company-brain status    # sanity check — should connect, show 0 rows
```

## How to ingest

```bash
uv run company-brain ingest fabric    # ~minutes; pulls table schemas + samples
# expected: "fabric_iq: 12 workspaces, 47 lakehouses, 312 tables ingested"

uv run company-brain ingest work      # ~minutes; pulls last N days of M365
# expected: "work_iq: 421 mails, 89 teams messages, 17 calendar events"

uv run company-brain ingest foundry   # ~seconds-minutes
# expected: "foundry_iq: 3 projects, 8 indexes, 1,204 chunks"

# or all in sequence
uv run company-brain ingest all
```

## How to query

```bash
uv run company-brain search "what did I work on with Michal last week"
uv run company-brain search "fact tables in the sales lakehouse" --container-tag fabric:
uv run company-brain profile --container-tag work:
```

Or start the API and hit it from any agent:

```bash
uv run uvicorn apps.api.main:app --port 8088
curl -X POST http://localhost:8088/v1/search \
  -H 'content-type: application/json' \
  -d '{"query":"sales pipeline architecture","limit":5}'
```

## Architecture in 60 seconds

```
Fabric IQ ─┐
Work IQ   ─┼─► connectors/* ─► extraction.py ─► MemoryStore (pgvector) ─► FastAPI ─► agents
Foundry   ─┘                       │                    ▲
                                   ▼                    │
                              embeddings.py ────────────┘
```

Every memory row carries a `container_tag` like `fabric:<workspaceId>:<lakehouseId>`,
`work:<userId>` or `foundry:<projectId>`, so you can scope searches per source.

## Common pitfalls

- **Graph admin consent**: delegated permissions DO NOT WORK until a tenant admin
  clicks "Grant admin consent" in the app registration. Symptoms: `AADSTS65001`.
- **Fabric capacity paused**: Fabric REST returns 403 with `CapacityNotActive` if
  the F-SKU backing your workspace is paused. Resume it in the Azure portal.
- **OpenAI rate limits on first ingest**: a cold ingest can issue thousands of
  embedding calls; we batch 100 inputs per request and back off on 429, but if
  you're on a free tier you'll hit TPM limits — set `OPENAI_RPM_LIMIT` in `.env`.
- **pgvector dimension mismatch**: schema is hard-coded to 1536 (text-embedding-3-small).
  If you switch to `text-embedding-3-large` you must redo the schema with `vector(3072)`.
- **Token cache stale**: if Graph starts returning 401, delete
  `~/.config/company-brain/work-iq-token.json` and re-run the device-code login.
