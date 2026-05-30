"""Microsoft Graph REST client (thin)."""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from .auth import get_token

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphClient:
    def __init__(self):
        self._http = httpx.Client(timeout=60.0)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {get_token()}"}

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{GRAPH_BASE}{path}"
        r = self._http.get(url, headers=self._headers(), params=params)
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
            url = data.get("@odata.nextLink")

    # ----- mail -------------------------------------------------------------

    def list_messages(self, *, days_back: int, top: int = 50) -> Iterator[dict]:
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        params = {
            "$filter": f"receivedDateTime ge {since}",
            "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,body,webLink",
            "$top": str(top),
            "$orderby": "receivedDateTime desc",
        }
        yield from self.paginate("/me/messages", params=params)

    # ----- teams ------------------------------------------------------------

    def list_joined_teams(self) -> list[dict]:
        return list(self.paginate("/me/joinedTeams"))

    def list_channels(self, team_id: str) -> list[dict]:
        return list(self.paginate(f"/teams/{team_id}/channels"))

    def list_channel_messages(self, team_id: str, channel_id: str) -> Iterator[dict]:
        yield from self.paginate(f"/teams/{team_id}/channels/{channel_id}/messages")

    # ----- onedrive / sharepoint -------------------------------------------

    def list_recent_drive_items(self, top: int = 50) -> Iterator[dict]:
        yield from self.paginate("/me/drive/recent", params={"$top": str(top)})

    # ----- calendar ---------------------------------------------------------

    def list_calendar_events(self, *, days_back: int, top: int = 100) -> Iterator[dict]:
        from datetime import datetime, timedelta, timezone

        start = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=days_back)).isoformat()
        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$top": str(top),
            "$select": "id,subject,start,end,attendees,bodyPreview,body,organizer,webLink",
        }
        yield from self.paginate("/me/calendarView", params=params)

    def me(self) -> dict:
        return self._get("/me")

    def close(self) -> None:
        self._http.close()
