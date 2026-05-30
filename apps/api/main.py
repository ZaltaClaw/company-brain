"""FastAPI app — proxies requests to the configured MemoryStore."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from company_brain.store import Memory, MemoryStore, get_store

_store: MemoryStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = get_store()
    try:
        yield
    finally:
        if _store is not None:
            _store.close()


app = FastAPI(title="Company Brain API", version="0.1.0", lifespan=lifespan)


class AddItem(BaseModel):
    content: str
    container_tag: str
    source: str = "api"
    source_ref: str | None = None
    confidence: float = 1.0
    temporal_validity: str | None = None
    fact_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddRequest(BaseModel):
    memories: list[AddItem]


class SearchRequest(BaseModel):
    query: str
    container_tag: str | None = None
    limit: int = 10


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/add")
def add(req: AddRequest) -> dict[str, Any]:
    if _store is None:
        raise HTTPException(503, "store not initialized")
    mems = [Memory(**m.model_dump()) for m in req.memories]
    ids = _store.add(mems)
    return {"ids": ids, "count": len(ids)}


@app.post("/v1/search")
def search(req: SearchRequest) -> dict[str, Any]:
    if _store is None:
        raise HTTPException(503, "store not initialized")
    results = _store.search(req.query, container_tag=req.container_tag, limit=req.limit)
    return {
        "results": [
            {
                "score": r.score,
                "id": r.memory.id,
                "content": r.memory.content,
                "container_tag": r.memory.container_tag,
                "source": r.memory.source,
                "source_ref": r.memory.source_ref,
                "fact_type": r.memory.fact_type,
                "confidence": r.memory.confidence,
                "temporal_validity": r.memory.temporal_validity,
                "metadata": r.memory.metadata,
            }
            for r in results
        ]
    }


@app.get("/v1/profile")
def profile(container_tag: str | None = None) -> dict[str, Any]:
    if _store is None:
        raise HTTPException(503, "store not initialized")
    return _store.profile(container_tag=container_tag)


@app.get("/v1/documents")
def documents(container_tag: str | None = None, limit: int = 100) -> dict[str, Any]:
    if _store is None:
        raise HTTPException(503, "store not initialized")
    return {"documents": _store.list_documents(container_tag=container_tag, limit=limit)}
