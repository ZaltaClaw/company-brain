"""Foundry IQ ingest loop."""

from __future__ import annotations

import json
import os
from typing import Any

from rich.console import Console

from company_brain.extraction import extract_facts
from company_brain.store import Memory, MemoryStore

from .client import FoundryClient


def _to_memories(facts, *, container_tag, source_ref, document_id=None) -> list[Memory]:
    return [
        Memory(
            content=f.fact,
            container_tag=container_tag,
            source="foundry",
            source_ref=source_ref,
            confidence=f.confidence,
            temporal_validity=f.temporal_validity,
            fact_type=f.type,
            metadata={"document_id": document_id} if document_id else {},
        )
        for f in facts
    ]


def run(store: MemoryStore, *, console: Console | None = None) -> dict[str, Any]:
    console = console or Console()
    raw = os.environ.get("FOUNDRY_PROJECT_IDS", "").strip()
    if not raw:
        console.print("[yellow]FOUNDRY_PROJECT_IDS not set — skipping Foundry ingest.[/yellow]")
        return {}

    project_ids = [p.strip() for p in raw.split(",") if p.strip()]
    client = FoundryClient()
    counts = {"projects": 0, "indexes": 0, "chunks": 0, "memories": 0}

    try:
        for pid in project_ids:
            try:
                project = client.get_project(pid)
            except Exception as e:
                console.print(f"[yellow]! project {pid}: {e}[/yellow]")
                continue
            counts["projects"] += 1
            tag_root = f"foundry:{pid}"
            store.add_document(
                container_tag=tag_root,
                source="foundry",
                source_ref=f"project/{pid}",
                title=f"Foundry project: {project.get('name', pid)}",
                body=json.dumps(project, indent=2, default=str),
                metadata={"kind": "project"},
            )

            try:
                indexes = client.list_indexes(pid)
            except Exception as e:
                console.print(f"[yellow]! indexes for {pid}: {e}[/yellow]")
                continue
            for idx in indexes:
                counts["indexes"] += 1
                idx_id = idx.get("id") or idx.get("name")
                tag = f"{tag_root}:{idx_id}"
                try:
                    docs = list(client.list_index_documents(pid, idx_id))
                except Exception as e:
                    console.print(f"[yellow]! docs for index {idx_id}: {e}[/yellow]")
                    docs = []
                counts["chunks"] += len(docs)
                for d in docs:
                    body = (
                        d.get("content")
                        or d.get("text")
                        or json.dumps(d, default=str)
                    )
                    title = d.get("title") or d.get("name") or d.get("id", "doc")
                    doc_id = store.add_document(
                        container_tag=tag,
                        source="foundry",
                        source_ref=f"index/{idx_id}/doc/{d.get('id', title)}",
                        title=title,
                        body=body,
                        metadata={"kind": "knowledge_doc", "index": idx_id},
                    )
                    facts = extract_facts(
                        body[:20000],
                        context=f"Foundry knowledge index '{idx.get('name', idx_id)}'",
                    )
                    if facts:
                        store.add(_to_memories(
                            facts,
                            container_tag=tag,
                            source_ref=f"index/{idx_id}/doc/{d.get('id', title)}",
                            document_id=doc_id,
                        ))
                        counts["memories"] += len(facts)
    finally:
        client.close()

    console.print(
        f"[green]✓ foundry_iq:[/green] {counts['projects']} projects, "
        f"{counts['indexes']} indexes, {counts['chunks']} docs, "
        f"{counts['memories']} memories"
    )
    return counts
