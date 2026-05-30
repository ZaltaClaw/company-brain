"""Postgres + pgvector implementation of MemoryStore.

Uses psycopg 3 with a connection pool. All queries are parameterized.
Vector similarity uses cosine distance (`<=>`) — schema indexes match.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from company_brain.embeddings import embed_one
from company_brain.store import Memory, MemoryStore, SearchResult

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


class PostgresStore(MemoryStore):
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 8):
        self.dsn = dsn
        self.pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": False},
            configure=self._configure_conn,
            open=True,
        )

    @staticmethod
    def _configure_conn(conn: psycopg.Connection) -> None:
        # pgvector adapter must be registered per connection.
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        register_vector(conn)

    @classmethod
    def from_env(cls) -> "PostgresStore":
        dsn = os.environ.get(
            "POSTGRES_DSN",
            "postgresql://brain:brain@localhost:5433/company_brain",
        )
        return cls(dsn)

    # ------------------------------------------------------------------ admin

    def init_schema(self) -> None:
        sql = SCHEMA_PATH.read_text()
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()

    # ------------------------------------------------------------------ writes

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
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (container_tag, source, source_ref, title, body, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source, source_ref) DO UPDATE
                  SET title = EXCLUDED.title,
                      body = EXCLUDED.body,
                      metadata = EXCLUDED.metadata,
                      container_tag = EXCLUDED.container_tag
                RETURNING id
                """,
                (container_tag, source, source_ref, title, body, json.dumps(metadata or {})),
            )
            doc_id = cur.fetchone()[0]
            conn.commit()
            return str(doc_id)

    def add(self, memories: list[Memory]) -> list[str]:
        if not memories:
            return []
        # Embed all in one batch
        from company_brain.embeddings import embed

        vectors = embed([m.content for m in memories])
        ids: list[str] = []
        with self.pool.connection() as conn, conn.cursor() as cur:
            for mem, vec in zip(memories, vectors):
                cur.execute(
                    """
                    INSERT INTO memories
                      (container_tag, source, source_ref, content, embedding,
                       confidence, temporal_validity, fact_type, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        mem.container_tag,
                        mem.source,
                        mem.source_ref,
                        mem.content,
                        vec,
                        mem.confidence,
                        mem.temporal_validity,
                        mem.fact_type,
                        json.dumps(mem.metadata or {}),
                    ),
                )
                ids.append(str(cur.fetchone()[0]))
            conn.commit()
        return ids

    # ------------------------------------------------------------------ reads

    def search(
        self,
        query: str,
        *,
        container_tag: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        qvec = embed_one(query)
        sql = """
            SELECT id, container_tag, source, source_ref, content, confidence,
                   temporal_validity, fact_type, metadata, created_at,
                   1 - (embedding <=> %s) AS score
            FROM memories
            WHERE embedding IS NOT NULL
        """
        params: list[Any] = [qvec]
        if container_tag:
            sql += " AND container_tag LIKE %s"
            params.append(container_tag if container_tag.endswith("%") else container_tag + "%")
        sql += " ORDER BY embedding <=> %s ASC LIMIT %s"
        params.extend([qvec, limit])

        results: list[SearchResult] = []
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            for row in cur.fetchall():
                mem = Memory(
                    id=str(row[0]),
                    container_tag=row[1],
                    source=row[2],
                    source_ref=row[3],
                    content=row[4],
                    confidence=row[5],
                    temporal_validity=row[6],
                    fact_type=row[7],
                    metadata=row[8] if isinstance(row[8], dict) else json.loads(row[8] or "{}"),
                    created_at=row[9],
                )
                results.append(SearchResult(memory=mem, score=float(row[10])))
        return results

    def profile(self, *, container_tag: str | None = None) -> dict[str, Any]:
        where = ""
        params: list[Any] = []
        if container_tag:
            where = "WHERE container_tag LIKE %s"
            params.append(container_tag + "%")

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT container_tag, source, fact_type, COUNT(*)
                FROM memories {where}
                GROUP BY container_tag, source, fact_type
                ORDER BY 1, 2, 3
                """,
                params,
            )
            rows = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) FROM documents {where}", params)
            doc_count = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM memories {where}", params)
            mem_count = cur.fetchone()[0]

        breakdown: dict[str, Any] = {}
        for ct, source, ftype, n in rows:
            breakdown.setdefault(ct, {}).setdefault(source, {})[ftype or "unknown"] = n

        return {
            "container_tag": container_tag,
            "documents": doc_count,
            "memories": mem_count,
            "breakdown": breakdown,
        }

    def list_documents(
        self,
        *,
        container_tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if container_tag:
            where = "WHERE container_tag LIKE %s"
            params.append(container_tag + "%")
        params.append(limit)
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, container_tag, source, source_ref, title, created_at
                FROM documents
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            return [
                {
                    "id": str(r[0]),
                    "container_tag": r[1],
                    "source": r[2],
                    "source_ref": r[3],
                    "title": r[4],
                    "created_at": r[5].isoformat() if r[5] else None,
                }
                for r in cur.fetchall()
            ]

    def status_by_tag(self) -> list[tuple[str, int, int]]:
        """(container_tag, document_count, memory_count) — used by `status`."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  COALESCE(d.container_tag, m.container_tag) AS tag,
                  COALESCE(d.n, 0),
                  COALESCE(m.n, 0)
                FROM (SELECT container_tag, COUNT(*) AS n FROM documents GROUP BY 1) d
                FULL OUTER JOIN
                     (SELECT container_tag, COUNT(*) AS n FROM memories GROUP BY 1) m
                     ON d.container_tag = m.container_tag
                ORDER BY tag
                """
            )
            return [(r[0], r[1], r[2]) for r in cur.fetchall()]

    def close(self) -> None:
        self.pool.close()
