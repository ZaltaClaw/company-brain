"""mem0 self-hosted adapter (https://docs.mem0.ai).

Stub — env-gated. Set MEMORY_STORE=mem0 and MEM0_BASE_URL to use.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from company_brain.store import Memory, MemoryStore, SearchResult


class Mem0Store(MemoryStore):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)

    @classmethod
    def from_env(cls) -> "Mem0Store":
        return cls(os.environ.get("MEM0_BASE_URL", "http://localhost:8000"))

    def add(self, memories: list[Memory]) -> list[str]:
        ids: list[str] = []
        for m in memories:
            r = self.client.post(
                f"{self.base_url}/memories",
                json={
                    "data": m.content,
                    "user_id": m.container_tag,
                    "metadata": {**(m.metadata or {}), "source": m.source},
                },
            )
            r.raise_for_status()
            ids.append(r.json().get("id", ""))
        return ids

    def search(self, query, *, container_tag=None, limit=10) -> list[SearchResult]:
        r = self.client.post(
            f"{self.base_url}/search",
            json={"query": query, "user_id": container_tag, "limit": limit},
        )
        r.raise_for_status()
        out: list[SearchResult] = []
        for hit in r.json().get("results", []):
            out.append(
                SearchResult(
                    memory=Memory(
                        id=hit.get("id"),
                        content=hit.get("memory", ""),
                        container_tag=hit.get("user_id", ""),
                        source=(hit.get("metadata") or {}).get("source", ""),
                        metadata=hit.get("metadata") or {},
                    ),
                    score=float(hit.get("score", 0.0)),
                )
            )
        return out

    def profile(self, *, container_tag=None) -> dict[str, Any]:
        raise NotImplementedError("mem0 adapter: profile() not wired yet")

    def list_documents(self, *, container_tag=None, limit=100) -> list[dict[str, Any]]:
        raise NotImplementedError("mem0 adapter: list_documents() not wired yet")

    def add_document(self, **kwargs) -> str:
        raise NotImplementedError("mem0 adapter: add_document() not wired yet")

    def close(self) -> None:
        self.client.close()
