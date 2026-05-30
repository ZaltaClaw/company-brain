"""Work IQ ingest loop."""

from __future__ import annotations

import os
from typing import Any

from rich.console import Console

from company_brain.extraction import extract_facts
from company_brain.store import Memory, MemoryStore

from .client import GraphClient


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _to_memories(facts, *, container_tag, source_ref, document_id=None) -> list[Memory]:
    return [
        Memory(
            content=f.fact,
            container_tag=container_tag,
            source="work",
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
    days = int(os.environ.get("WORK_IQ_DAYS_BACK", "30"))
    client = GraphClient()
    counts = {"mails": 0, "teams_messages": 0, "drive_items": 0, "events": 0, "memories": 0}

    try:
        me = client.me()
        user_id = me.get("id", "me")
        tag = f"work:{user_id}"

        # ----- Mail
        console.print(f"[cyan]→ outlook (last {days}d)[/cyan]")
        for m in client.list_messages(days_back=days):
            counts["mails"] += 1
            body = _strip_html((m.get("body") or {}).get("content") or m.get("bodyPreview", ""))
            title = m.get("subject") or "(no subject)"
            doc_id = store.add_document(
                container_tag=tag,
                source="work",
                source_ref=f"mail/{m['id']}",
                title=title,
                body=body,
                metadata={
                    "kind": "mail",
                    "from": (m.get("from") or {}).get("emailAddress", {}),
                    "received": m.get("receivedDateTime"),
                    "webLink": m.get("webLink"),
                },
            )
            facts = extract_facts(f"Subject: {title}\n\n{body}", context="Outlook email")
            if facts:
                store.add(_to_memories(facts, container_tag=tag,
                                       source_ref=f"mail/{m['id']}", document_id=doc_id))
                counts["memories"] += len(facts)

        # ----- Teams
        console.print("[cyan]→ teams[/cyan]")
        for team in client.list_joined_teams():
            try:
                channels = client.list_channels(team["id"])
            except Exception as e:
                console.print(f"[yellow]! channels for {team.get('displayName')}: {e}[/yellow]")
                continue
            for ch in channels:
                try:
                    messages = list(client.list_channel_messages(team["id"], ch["id"]))
                except Exception as e:
                    console.print(f"[yellow]! channel msgs {ch.get('displayName')}: {e}[/yellow]")
                    continue
                counts["teams_messages"] += len(messages)
                if not messages:
                    continue
                # Aggregate channel into one document.
                aggregated = "\n\n".join(
                    _strip_html((mm.get("body") or {}).get("content", ""))
                    for mm in messages
                    if mm.get("body")
                )
                if not aggregated.strip():
                    continue
                doc_id = store.add_document(
                    container_tag=tag,
                    source="work",
                    source_ref=f"team/{team['id']}/channel/{ch['id']}",
                    title=f"Teams: {team.get('displayName')} / {ch.get('displayName')}",
                    body=aggregated[:50000],
                    metadata={"kind": "teams_channel"},
                )
                facts = extract_facts(
                    aggregated[:20000],
                    context=f"Teams channel {team.get('displayName')}/{ch.get('displayName')}",
                )
                if facts:
                    store.add(_to_memories(
                        facts, container_tag=tag,
                        source_ref=f"team/{team['id']}/channel/{ch['id']}",
                        document_id=doc_id,
                    ))
                    counts["memories"] += len(facts)

        # ----- OneDrive recent
        console.print("[cyan]→ onedrive recent[/cyan]")
        for item in client.list_recent_drive_items():
            counts["drive_items"] += 1
            store.add_document(
                container_tag=tag,
                source="work",
                source_ref=f"drive/{item.get('id')}",
                title=item.get("name") or "(unnamed)",
                body=item.get("webUrl") or "",
                metadata={"kind": "drive_item", "size": item.get("size"),
                          "lastModified": item.get("lastModifiedDateTime")},
            )

        # ----- Calendar
        console.print(f"[cyan]→ calendar (±{days}d)[/cyan]")
        for ev in client.list_calendar_events(days_back=days):
            counts["events"] += 1
            body = _strip_html((ev.get("body") or {}).get("content", ""))
            title = ev.get("subject") or "(no subject)"
            doc_id = store.add_document(
                container_tag=tag,
                source="work",
                source_ref=f"event/{ev['id']}",
                title=title,
                body=body,
                metadata={
                    "kind": "calendar_event",
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "attendees": [a.get("emailAddress", {}) for a in ev.get("attendees", [])],
                },
            )
            attendees = ", ".join(
                a.get("emailAddress", {}).get("name", "") for a in ev.get("attendees", [])
            )
            facts = extract_facts(
                f"Meeting: {title}\nAttendees: {attendees}\nNotes: {body}",
                context="Calendar event",
            )
            if facts:
                store.add(_to_memories(
                    facts, container_tag=tag,
                    source_ref=f"event/{ev['id']}", document_id=doc_id,
                ))
                counts["memories"] += len(facts)

    finally:
        client.close()

    console.print(
        f"[green]✓ work_iq:[/green] {counts['mails']} mails, "
        f"{counts['teams_messages']} teams messages, "
        f"{counts['drive_items']} drive items, {counts['events']} events, "
        f"{counts['memories']} memories"
    )
    return counts
