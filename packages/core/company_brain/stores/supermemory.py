"""Supermemory adapter (https://api.supermemory.ai).

Stub — env-gated. Set MEMORY_STORE=supermemory and SUPERMEMORY_API_KEY to use.
The shape mirrors PostgresStore so connectors are agnostic.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from company_brain.store import Memory, MemoryStore, SearchResult

BASE = "https://api.supermemory.ai/v3"


class SupermemoryStore(MemoryStore):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    @classmethod
    def from_env(cls) -> "SupermemoryStore":
        key = os.environ.get("SUPERMEMORY_API_KEY")
        if not key:
            raise RuntimeError("SUPERMEMORY_API_KEY not set")
        return cls(key)

    # NOTE: these are scaffolds — fill in once Roey decides to enable Supermemory.
    def add(self, memories: list[Memory]) -> list[str]:
        ids: list[str] = []
        for m in memories:
            r = self.client.post(
                f"{BASE}/memories",
                json={
                    "content": m.content,
                    "containerTag": m.container_tag,
                    "metadata": {**(m.metadata or {}), "source": m.source},
                },
            )
            r.raise_for_status()
            ids.append(r.json().get("id", ""))
        return ids

    def search(self, query, *, container_tag=None, limit=10) -> list[SearchResult]:
        params: dict[str, Any] = {"q": query, "limit": limit}
        if container_tag:
            params["containerTag"] = container_tag
        r = self.client.get(f"{BASE}/search", params=params)
        r.raise_for_status()
        out: list[SearchResult] = []
        for hit in r.json().get("results", []):
            out.append(
                SearchResult(
                    memory=Memory(
                        id=hit.get("id"),
                        content=hit.get("content", ""),
                        container_tag=hit.get("containerTag", ""),
                        source=(hit.get("metadata") or {}).get("source", ""),
                        metadata=hit.get("metadata") or {},
                    ),
                    score=float(hit.get("score", 0.0)),
                )
            )
        return out

    def profile(self, *, container_tag=None) -> dict[str, Any]:
        raise NotImplementedError("Supermemory adapter: profile() not wired yet")

    def list_documents(self, *, container_tag=None, limit=100) -> list[dict[str, Any]]:
        raise NotImplementedError("Supermemory adapter: list_documents() not wired yet")

    def add_document(self, **kwargs) -> str:
        raise NotImplementedError("Supermemory adapter: add_document() not wired yet")

    def close(self) -> None:
        self.client.close()
