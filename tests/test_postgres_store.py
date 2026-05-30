"""Smoke tests for PostgresStore. Skipped if no Postgres reachable."""

from __future__ import annotations

import os

import pytest


def _pg_available() -> bool:
    try:
        import psycopg

        with psycopg.connect(
            os.environ.get(
                "POSTGRES_DSN",
                "postgresql://brain:brain@localhost:5433/company_brain",
            ),
            connect_timeout=2,
        ):
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _pg_available(), reason="local postgres not reachable")
@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")
def test_postgres_store_roundtrip():
    from company_brain.store import Memory
    from company_brain.stores.postgres import PostgresStore

    store = PostgresStore.from_env()
    store.init_schema()

    ids = store.add([
        Memory(content="Roey works on Company Brain.", container_tag="test:smoke",
               source="test", fact_type="knowledge"),
    ])
    assert ids and len(ids) == 1

    results = store.search("who works on Company Brain", container_tag="test:")
    assert any("Roey" in r.memory.content for r in results)
    store.close()
