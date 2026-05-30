# Company Brain

A local-first, self-hosted memory engine that ingests three Microsoft IQ sources
(**Fabric IQ**, **Work IQ**, **Foundry IQ**) into a single Postgres+pgvector store
and exposes one HTTP API any agent (Hermes, Claude Code, Cursor, custom bots) can
hit for memory + RAG.

## Why

Microsoft's "IQ" surfaces are siloed: Fabric IQ knows your data warehouse, Work IQ
(Copilot/Graph) knows your email + Teams + SharePoint, Foundry IQ knows your AI
project knowledge bases. None of them talk to each other and none of them give
**you** raw access to embeddings or facts. This project unifies all three behind
a small, opinionated `MemoryStore` interface so your agents have one brain, not
three.

## 30-second quickstart

```bash
brew install uv
git clone git@github.com:roy2392/company-brain.git
cd company-brain
uv sync
cp .env.example .env          # then fill in the values (see CLAUDE.md)
./scripts/init-db.sh          # boots postgres+pgvector on :5433 and applies schema
uv run company-brain status   # should print empty container tags
uv run company-brain ingest all
uv run company-brain search "what did I work on with Michal last week"
```

The full handoff doc for setting this up on a fresh Mac (with all the env vars
explained) lives in [CLAUDE.md](./CLAUDE.md).

## Architecture

```
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │  Fabric IQ   │    │   Work IQ    │    │  Foundry IQ  │
  │ (warehouse,  │    │ (mail, teams,│    │ (AI project  │
  │  lakehouses) │    │  sharepoint) │    │  knowledge)  │
  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
         │                   │                   │
   connectors/fabric_iq  connectors/work_iq  connectors/foundry_iq
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                   ┌──────────────────┐
                   │   MemoryStore    │   packages/core
                   │  (Postgres +     │
                   │    pgvector)     │
                   └────────┬─────────┘
                            │
                   ┌────────▼─────────┐
                   │   FastAPI        │   apps/api
                   │  /v1/add /search │
                   │     /profile     │
                   └────────┬─────────┘
                            │
                   ┌────────▼─────────┐
                   │  Agents (Hermes, │
                   │  Claude Code, …) │
                   └──────────────────┘
```

## License

Internal / private. Not for redistribution.
