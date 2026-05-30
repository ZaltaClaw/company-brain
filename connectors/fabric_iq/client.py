"""Microsoft Fabric REST API client.

Auth: client-credentials flow against Entra ID using
AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET.
Scope: https://api.fabric.microsoft.com/.default
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterator

import httpx
import msal

FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
SCOPE = ["https://api.fabric.microsoft.com/.default"]


class FabricClient:
    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.tenant_id = tenant_id or os.environ["AZURE_TENANT_ID"]
        self.client_id = client_id or os.environ["AZURE_CLIENT_ID"]
        self.client_secret = client_secret or os.environ.get("AZURE_CLIENT_SECRET", "")
        self._token: str | None = None
        self._token_exp: float = 0.0
        self._http = httpx.Client(timeout=60.0)

    # ----- auth -------------------------------------------------------------

    def _acquire_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        if not self.client_secret:
            raise RuntimeError(
                "Fabric connector requires AZURE_CLIENT_SECRET (client-credentials flow). "
                "Device-code flow against Fabric REST is not supported."
            )
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=SCOPE)
        if "access_token" not in result:
            raise RuntimeError(f"Fabric auth failed: {result.get('error_description')}")
        self._token = result["access_token"]
        self._token_exp = time.time() + int(result.get("expires_in", 3000))
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._acquire_token()}"}

    # ----- HTTP -------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{FABRIC_BASE}{path}"
        r = self._http.get(url, headers=self._headers(), params=params)
        r.raise_for_status()
        return r.json()

    def _paginate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        url: str | None = path
        while url:
            data = self._get(url, params=params if url == path else None)
            for item in data.get("value", []):
                yield item
            url = data.get("continuationUri") or data.get("nextLink")

    # ----- API surface ------------------------------------------------------

    def list_workspaces(self) -> list[dict[str, Any]]:
        return list(self._paginate("/workspaces"))

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        return self._get(f"/workspaces/{workspace_id}")

    def list_items(self, workspace_id: str) -> list[dict[str, Any]]:
        return list(self._paginate(f"/workspaces/{workspace_id}/items"))

    def list_lakehouse_tables(
        self, workspace_id: str, lakehouse_id: str
    ) -> list[dict[str, Any]]:
        return list(
            self._paginate(f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables")
        )

    def get_semantic_model(self, workspace_id: str, model_id: str) -> dict[str, Any]:
        return self._get(f"/workspaces/{workspace_id}/semanticModels/{model_id}")

    def get_semantic_model_definition(
        self, workspace_id: str, model_id: str
    ) -> dict[str, Any]:
        # POST endpoint that returns parts of the TMDL definition.
        url = f"{FABRIC_BASE}/workspaces/{workspace_id}/semanticModels/{model_id}/getDefinition"
        r = self._http.post(url, headers=self._headers())
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()
