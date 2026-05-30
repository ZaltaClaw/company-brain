"""Microsoft Graph change notifications (webhooks).

This is a scaffolding stub showing the subscription pattern. To turn it on:

  1. Stand up a public HTTPS endpoint (e.g. via cloudflared or ngrok) that
     POSTs land at apps/api/main.py:/v1/graph/notifications.
  2. Call `subscribe(resource='me/messages', notification_url=<that_url>)`.
  3. Graph will validate the URL by sending a GET with ?validationToken=... —
     respond 200 with the raw token in the body.
  4. Real notifications POST a JSON body { 'value': [ { 'resource': '...' } ] }.

We deliberately leave the receiver unwired because exposing a public endpoint
is an org-policy decision, not a code decision.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx

from .auth import get_token

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def subscribe(*, resource: str, notification_url: str, expiration_hours: int = 1) -> dict:
    """Create a Graph change-notification subscription. Returns the sub object."""
    expires = (datetime.now(timezone.utc) + timedelta(hours=expiration_hours)).isoformat()
    body = {
        "changeType": "created,updated",
        "notificationUrl": notification_url,
        "resource": resource,
        "expirationDateTime": expires,
        "clientState": os.environ.get("WORK_IQ_WEBHOOK_SECRET", "company-brain"),
    }
    r = httpx.post(
        f"{GRAPH_BASE}/subscriptions",
        json=body,
        headers={"Authorization": f"Bearer {get_token()}"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def renew(subscription_id: str, expiration_hours: int = 1) -> dict:
    expires = (datetime.now(timezone.utc) + timedelta(hours=expiration_hours)).isoformat()
    r = httpx.patch(
        f"{GRAPH_BASE}/subscriptions/{subscription_id}",
        json={"expirationDateTime": expires},
        headers={"Authorization": f"Bearer {get_token()}"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()
