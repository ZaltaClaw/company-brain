"""Microsoft Graph auth.

Two modes:
  - client-credentials (service principal) when AZURE_CLIENT_SECRET is set
  - device-code flow otherwise (token cached to disk)

Run `python -m connectors.work_iq.auth login` to seed the device-code cache.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import msal

GRAPH_SCOPE_DEFAULT = ["https://graph.microsoft.com/.default"]
GRAPH_SCOPES_DEVICE = [
    "Mail.Read",
    "Files.Read.All",
    "Chat.Read",
    "ChannelMessage.Read",
    "Calendars.Read",
    "Sites.Read.All",
    "User.Read",
]

CACHE_PATH = Path.home() / ".config" / "company-brain" / "work-iq-token.json"


def _ensure_cache_dir() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        cache.deserialize(CACHE_PATH.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        _ensure_cache_dir()
        CACHE_PATH.write_text(cache.serialize())


def get_token() -> str:
    tenant = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["AZURE_CLIENT_ID"]
    secret = os.environ.get("AZURE_CLIENT_SECRET", "")
    authority = f"https://login.microsoftonline.com/{tenant}"

    if secret:
        app = msal.ConfidentialClientApplication(
            client_id, authority=authority, client_credential=secret
        )
        r = app.acquire_token_for_client(scopes=GRAPH_SCOPE_DEFAULT)
        if "access_token" not in r:
            raise RuntimeError(f"Graph auth failed: {r.get('error_description')}")
        return r["access_token"]

    # Device-code path
    cache = _load_cache()
    app = msal.PublicClientApplication(client_id, authority=authority, token_cache=cache)
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPES_DEVICE, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPES_DEVICE)
        if "user_code" not in flow:
            raise RuntimeError(f"device-flow init failed: {flow}")
        print(flow["message"], flush=True)
        result = app.acquire_token_by_device_flow(flow)
    _save_cache(cache)
    if "access_token" not in result:
        raise RuntimeError(f"Graph auth failed: {result.get('error_description')}")
    return result["access_token"]


def login() -> None:
    """CLI entrypoint: forces a fresh device-code login."""
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
    token = get_token()
    print(f"✓ token acquired ({len(token)} chars). cached at {CACHE_PATH}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        login()
    else:
        token = get_token()
        print(json.dumps({"len": len(token), "expires_at": int(time.time()) + 3000}))
