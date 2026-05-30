-- Company Brain — schema for Postgres + pgvector.
-- Idempotent. Run via `company-brain init-db` or scripts/init-db.sh.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Raw documents pulled from a connector. One row per mail / SharePoint file /
-- Fabric table-schema dump / Foundry doc.
CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    container_tag TEXT NOT NULL,
    source        TEXT NOT NULL,         -- fabric | work | foundry
    source_ref    TEXT NOT NULL,         -- upstream id (mail id, table path...)
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_ref)
);

CREATE INDEX IF NOT EXISTS documents_container_tag_idx ON documents (container_tag);
CREATE INDEX IF NOT EXISTS documents_source_idx ON documents (source);

-- Chunks of a document (used for RAG retrieval over long docs).
CREATE TABLE IF NOT EXISTS chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index  INT NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(1536),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (document_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Atomic memories (extracted facts). These are what an agent normally retrieves.
CREATE TABLE IF NOT EXISTS memories (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id        UUID REFERENCES documents (id) ON DELETE SET NULL,
    container_tag      TEXT NOT NULL,
    source             TEXT NOT NULL,
    source_ref         TEXT,
    content            TEXT NOT NULL,
    embedding          vector(1536),
    confidence         REAL NOT NULL DEFAULT 1.0,
    temporal_validity  TEXT,
    fact_type          TEXT,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memories_container_tag_idx ON memories (container_tag);
CREATE INDEX IF NOT EXISTS memories_source_idx ON memories (source);
CREATE INDEX IF NOT EXISTS memories_fact_type_idx ON memories (fact_type);
CREATE INDEX IF NOT EXISTS memories_embedding_idx
    ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Aggregate per-container profile (lightweight cache; rebuilt on `profile`).
CREATE TABLE IF NOT EXISTS profiles (
    container_tag  TEXT PRIMARY KEY,
    summary        TEXT NOT NULL,
    stats          JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
