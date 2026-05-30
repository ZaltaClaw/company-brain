# Company Brain API

Minimal FastAPI server that exposes the MemoryStore so any agent can call:

- `POST /v1/add` — append memories
- `POST /v1/search` — vector search
- `GET  /v1/profile` — aggregate stats
- `GET  /v1/documents` — list documents
- `GET  /healthz` — liveness

## Run

```bash
uv run uvicorn apps.api.main:app --port 8088 --reload
```

## Example

```bash
curl -s http://localhost:8088/v1/search \
  -H 'content-type: application/json' \
  -d '{"query":"sales pipeline","limit":5}' | jq
```
