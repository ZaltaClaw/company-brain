# Work IQ connector

Pulls personal/team knowledge from Microsoft 365 via Microsoft Graph.

## Sources

| Source | Endpoint | Default window |
|---|---|---|
| Outlook mail | `/me/messages` | last `WORK_IQ_DAYS_BACK` days |
| Teams chats / channel msgs | `/me/joinedTeams` → `/teams/{id}/channels/{cid}/messages` | last 30 days |
| SharePoint / OneDrive docs | `/me/drive/root/children` | recent only |
| Calendar events | `/me/calendar/events` | last `WORK_IQ_DAYS_BACK` days |

## Required permissions

In your Entra app registration, add (delegated **or** application):

- `Mail.Read`
- `Files.Read.All`
- `Chat.Read` and `ChannelMessage.Read.All`
- `Calendars.Read`
- `Sites.Read.All`
- `User.Read`

Then **Grant admin consent**.

## Auth modes

- **Service principal** (recommended for org Mac): set
  `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` and the connector
  uses client-credentials flow.
- **Device code** (no admin needed): leave `AZURE_CLIENT_SECRET` empty, run
  `uv run python -m connectors.work_iq.auth login`. Token caches to
  `~/.config/company-brain/work-iq-token.json`.
