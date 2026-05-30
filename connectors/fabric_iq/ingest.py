"""Fabric IQ ingest loop.

For every workspace in FABRIC_WORKSPACE_IDS:
  - dump workspace metadata
  - list every item; for each lakehouse/warehouse, dump table schemas
  - for each semantic model, dump relationships → ontology document
  - run extraction over every document and persist memories.
"""

from __future__ import annotations

import json
import os
from typing import Any

from rich.console import Console

from company_brain.extraction import extract_facts
from company_brain.store import Memory, MemoryStore

from .client import FabricClient
from .ontology import extract_relationships, render_ontology


def _facts_to_memories(
    facts, *, container_tag: str, source_ref: str, document_id: str | None = None
) -> list[Memory]:
    return [
        Memory(
            content=f.fact,
            container_tag=container_tag,
            source="fabric",
            source_ref=source_ref,
            confidence=f.confidence,
            temporal_validity=f.temporal_validity,
            fact_type=f.type,
            metadata={"document_id": document_id} if document_id else {},
        )
        for f in facts
    ]


def _ingest_workspace(
    client: FabricClient,
    store: MemoryStore,
    workspace_id: str,
    *,
    console: Console,
) -> dict[str, int]:
    counts = {"items": 0, "tables": 0, "ontologies": 0, "memories": 0}

    workspace = client.get_workspace(workspace_id)
    ws_tag_root = f"fabric:{workspace_id}"

    # Workspace overview document.
    overview = json.dumps(workspace, indent=2, default=str)
    overview_doc_id = store.add_document(
        container_tag=ws_tag_root,
        source="fabric",
        source_ref=f"workspace/{workspace_id}",
        title=f"Workspace: {workspace.get('displayName', workspace_id)}",
        body=overview,
        metadata={"kind": "workspace"},
    )
    facts = extract_facts(overview, context=f"Microsoft Fabric workspace {workspace_id}")
    if facts:
        store.add(
            _facts_to_memories(
                facts,
                container_tag=ws_tag_root,
                source_ref=f"workspace/{workspace_id}",
                document_id=overview_doc_id,
            )
        )
        counts["memories"] += len(facts)

    items = client.list_items(workspace_id)
    counts["items"] = len(items)

    for item in items:
        item_id = item.get("id")
        item_type = (item.get("type") or "").lower()
        item_name = item.get("displayName") or item_id
        container_tag = f"{ws_tag_root}:{item_id}"

        if item_type in ("lakehouse", "warehouse"):
            try:
                tables = client.list_lakehouse_tables(workspace_id, item_id)
            except Exception as e:
                console.print(f"[yellow]! tables fetch failed for {item_name}: {e}[/yellow]")
                tables = []
            counts["tables"] += len(tables)
            body = json.dumps({"item": item, "tables": tables}, indent=2, default=str)
            doc_id = store.add_document(
                container_tag=container_tag,
                source="fabric",
                source_ref=f"item/{item_id}",
                title=f"{item_type}: {item_name}",
                body=body,
                metadata={"kind": item_type, "table_count": len(tables)},
            )
            facts = extract_facts(
                body, context=f"Fabric {item_type} '{item_name}' table inventory"
            )
            if facts:
                store.add(
                    _facts_to_memories(
                        facts,
                        container_tag=container_tag,
                        source_ref=f"item/{item_id}",
                        document_id=doc_id,
                    )
                )
                counts["memories"] += len(facts)

        elif item_type == "semanticmodel":
            try:
                definition = client.get_semantic_model_definition(workspace_id, item_id)
                rels = extract_relationships(definition)
                ontology = render_ontology(workspace, rels)
                doc_id = store.add_document(
                    container_tag=container_tag,
                    source="fabric",
                    source_ref=f"semanticmodel/{item_id}",
                    title=f"Ontology: {item_name}",
                    body=ontology,
                    metadata={"kind": "ontology", "relationship_count": len(rels)},
                )
                counts["ontologies"] += 1
                facts = extract_facts(
                    ontology,
                    context=f"Semantic model '{item_name}' join graph",
                )
                if facts:
                    store.add(
                        _facts_to_memories(
                            facts,
                            container_tag=container_tag,
                            source_ref=f"semanticmodel/{item_id}",
                            document_id=doc_id,
                        )
                    )
                    counts["memories"] += len(facts)
            except Exception as e:
                console.print(
                    f"[yellow]! semantic model {item_name} skipped: {e}[/yellow]"
                )

    return counts


def run(store: MemoryStore, *, console: Console | None = None) -> dict[str, Any]:
    console = console or Console()
    raw = os.environ.get("FABRIC_WORKSPACE_IDS", "").strip()
    if not raw:
        console.print("[yellow]FABRIC_WORKSPACE_IDS not set — skipping Fabric ingest.[/yellow]")
        return {}

    workspace_ids = [w.strip() for w in raw.split(",") if w.strip()]
    client = FabricClient()
    totals: dict[str, int] = {"items": 0, "tables": 0, "ontologies": 0, "memories": 0}
    try:
        for ws_id in workspace_ids:
            console.print(f"[bold cyan]→ fabric workspace {ws_id}[/bold cyan]")
            c = _ingest_workspace(client, store, ws_id, console=console)
            for k, v in c.items():
                totals[k] = totals.get(k, 0) + v
    finally:
        client.close()

    console.print(
        f"[green]✓ fabric_iq:[/green] {len(workspace_ids)} workspaces, "
        f"{totals['items']} items, {totals['tables']} tables, "
        f"{totals['ontologies']} ontologies, {totals['memories']} memories"
    )
    return totals
