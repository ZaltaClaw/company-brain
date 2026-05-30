"""Abstract MemoryStore interface.

Concrete implementations live under company_brain.stores.*.
The default is PostgresStore (pgvector); supermemory.py and mem0.py are
adapters kept around so an org can swap backends with one env var.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Memory:
    """A single atomic memory row."""

    id: str | None = None
    content: str = ""
    container_tag: str = ""
    source: str = ""              # e.g. "fabric", "work", "foundry"
    source_ref: str | None = None  # e.g. mail message id, fabric table path
    confidence: float = 1.0
    temporal_validity: str | None = None  # ISO date or "ongoing"
    fact_type: str | None = None  # e.g. "schema", "relationship", "event"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass
class SearchResult:
    memory: Memory
    score: float


class MemoryStore(ABC):
    """Minimal contract every memory backend must satisfy."""

    @abstractmethod
    def add(self, memories: list[Memory]) -> list[str]:
        """Insert memories. Returns list of inserted IDs."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        container_tag: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Vector search. container_tag may be a prefix (e.g. 'fabric:')."""

    @abstractmethod
    def profile(self, *, container_tag: str | None = None) -> dict[str, Any]:
        """Return aggregate stats: counts by source, top fact types, etc."""

    @abstractmethod
    def list_documents(
        self,
        *,
        container_tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List ingested raw documents (parents of chunks/memories)."""

    def list_documents_with_memories(
        self,
        *,
        page: int = 1,
        limit: int = 500,
        container_tag: str | None = None,
        sort: str = "createdAt",
        order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Return (documents, total_count). Each document includes up to 10 of its memories.

        Used by the Supermemory-compatible /v3/documents/documents endpoint that the
        vendored memory-graph-playground talks to.
        """
        raise NotImplementedError

    @abstractmethod
    def add_document(
        self,
        *,
        container_tag: str,
        source: str,
        source_ref: str,
        title: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Insert a raw document. Returns document id."""

    def close(self) -> None:  # pragma: no cover - optional
        pass


def get_store() -> MemoryStore:
    """Factory honoring the MEMORY_STORE env var."""
    import os

    backend = os.getenv("MEMORY_STORE", "postgres").lower()
    if backend == "postgres":
        from company_brain.stores.postgres import PostgresStore

        return PostgresStore.from_env()
    if backend == "supermemory":
        from company_brain.stores.supermemory import SupermemoryStore

        return SupermemoryStore.from_env()
    if backend == "mem0":
        from company_brain.stores.mem0 import Mem0Store

        return Mem0Store.from_env()
    raise ValueError(f"Unknown MEMORY_STORE backend: {backend}")
