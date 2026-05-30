# Fabric IQ connector

Pulls structural knowledge out of Microsoft Fabric workspaces:

- Workspace metadata
- Lakehouses, warehouses, KQL DBs
- Table schemas + sample rows
- Semantic-model relationships (FK graph) → emitted as a structured "ontology
  document" so an agent can reason about how tables join

## Required permissions

The principal (service principal **or** user) used must be:

- A **Member** or **Admin** on every workspace in `FABRIC_WORKSPACE_IDS`
- The Fabric capacity backing those workspaces must be **Active**

App-registration scopes (Entra ID → API permissions → Power BI Service):

- `Workspace.Read.All`
- `Item.Read.All`
- `Lakehouse.Read.All` (preview)
- `SemanticModel.Read.All`

Then **Grant admin consent**.

## Endpoints used

- `GET https://api.fabric.microsoft.com/v1/workspaces`
- `GET https://api.fabric.microsoft.com/v1/workspaces/{wsId}/items`
- `GET https://api.fabric.microsoft.com/v1/workspaces/{wsId}/lakehouses/{lhId}/tables`
- `GET https://api.fabric.microsoft.com/v1/workspaces/{wsId}/semanticModels/{smId}`
