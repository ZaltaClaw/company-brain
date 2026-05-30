# Foundry IQ connector

Pulls knowledge indexes from Azure AI Foundry projects.

## Auth

Uses `azure-identity.DefaultAzureCredential`, which transparently tries:

1. Environment variables (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`)
2. Managed identity (when running in Azure)
3. `az login` cached identity
4. VS Code / Azure CLI / IntelliJ credentials

So locally you can just `az login` and it works.

## Required role

`Cognitive Services User` (read) on the AI Foundry resource group.

## Endpoints

- `GET {FOUNDRY_ENDPOINT}/api/projects?api-version=2024-12-01-preview`
- `GET {FOUNDRY_ENDPOINT}/api/projects/{projectId}/indexes?api-version=2024-12-01-preview`
- `GET {FOUNDRY_ENDPOINT}/api/projects/{projectId}/indexes/{indexId}/documents?api-version=2024-12-01-preview`

`FOUNDRY_ENDPOINT` looks like `https://<your-foundry-resource>.services.ai.azure.com`.

> The Foundry surface is still moving. If a project uses the older "Azure AI
> Studio" surface (`https://<region>.api.azureml.ms/...`) the same OAuth token
> works; only the URL prefix changes.
