"""Azure AI Foundry REST client (knowledge indexes)."""

from __future__ import annotations

import os
from typing import Any, Iterator

import httpx
from azure.identity import DefaultAzureCredential

API_VERSION = "2024-12-01-preview"
SCOPE = "https://ai.azure.com/.default"


class FoundryClient:
    def __init__(self, endpoint: str | None = None):
        self.endpoint = (endpoint or os.environ.get("FOUNDRY_ENDPOINT", "")).rstrip("/")
        if not self.endpoint:
            raise RuntimeError("FOUNDRY_ENDPOINT is not set")
        self._cred = DefaultAzureCredential()
        self._http = httpx.Client(timeout=60.0)
        self._token: str | None = None
        self._token_exp: float = 0.0

    def _headers(self) -> dict[str, str]:
        import time

        if not self._token or time.time() > self._token_exp - 60:
            tok = self._cred.get_token(SCOPE)
            self._token = tok.token
            self._token_exp = tok.expires_on
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.endpoint}{path}"
        merged = {"api-version": API_VERSION, **(params or {})}
        r = self._http.get(url, headers=self._headers(), params=merged)
        r.raise_for_status()
        return r.json()

    def paginate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        url: str | None = path
        first = True
        while url:
            data = self._get(url, params=params if first else None)
            first = False
            for item in data.get("value", []):
                yield item
            url = data.get("nextLink")

    # ----- API surface ------------------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        return list(self.paginate("/api/projects"))

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self._get(f"/api/projects/{project_id}")

    def list_indexes(self, project_id: str) -> list[dict[str, Any]]:
        return list(self.paginate(f"/api/projects/{project_id}/indexes"))

    def list_index_documents(
        self, project_id: str, index_id: str
    ) -> Iterator[dict[str, Any]]:
        yield from self.paginate(
            f"/api/projects/{project_id}/indexes/{index_id}/documents"
        )

    def close(self) -> None:
        self._http.close()
