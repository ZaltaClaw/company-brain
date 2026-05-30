"""Extract foreign-key relationships from Fabric semantic models.

Emits a single 'ontology document' per workspace summarizing how tables join.
"""

from __future__ import annotations

import base64
import json
from typing import Any


def _decode_part(part: dict[str, Any]) -> str:
    payload = part.get("payload", "")
    encoding = part.get("payloadType", "InlineBase64")
    if encoding == "InlineBase64":
        try:
            return base64.b64decode(payload).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return payload or ""


def extract_relationships(definition: dict[str, Any]) -> list[dict[str, str]]:
    """Walk a semantic-model getDefinition response and pull relationships.

    The TMDL/JSON definition has a 'relationships' or 'parts' section depending
    on the export format. We support both.
    """
    rels: list[dict[str, str]] = []
    parts = definition.get("definition", {}).get("parts", [])
    for part in parts:
        text = _decode_part(part)
        # JSON model.bim format
        if text.lstrip().startswith("{"):
            try:
                doc = json.loads(text)
            except Exception:
                continue
            for r in doc.get("model", {}).get("relationships", []) or doc.get("relationships", []):
                rels.append(
                    {
                        "from_table": r.get("fromTable", ""),
                        "from_column": r.get("fromColumn", ""),
                        "to_table": r.get("toTable", ""),
                        "to_column": r.get("toColumn", ""),
                        "cardinality": r.get("crossFilteringBehavior", "manyToOne"),
                    }
                )
        else:
            # TMDL text — naive line scan; good enough for an ontology summary.
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("relationship "):
                    rels.append({"raw": s})
    return rels


def render_ontology(workspace: dict[str, Any], relationships: list[dict[str, str]]) -> str:
    lines = [
        f"# Ontology: {workspace.get('displayName', workspace.get('id'))}",
        f"workspace_id: {workspace.get('id')}",
        f"relationship_count: {len(relationships)}",
        "",
        "## Relationships",
    ]
    for r in relationships:
        if "raw" in r:
            lines.append(f"- {r['raw']}")
        else:
            lines.append(
                f"- {r['from_table']}.{r['from_column']} → "
                f"{r['to_table']}.{r['to_column']} ({r.get('cardinality', '?')})"
            )
    return "\n".join(lines)
