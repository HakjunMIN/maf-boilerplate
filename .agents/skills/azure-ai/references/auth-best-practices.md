# Azure Authentication Best Practices

> Source: [Microsoft — Passwordless connections for Azure services](https://learn.microsoft.com/azure/developer/intro/passwordless-overview) and [Azure Identity client libraries for Python](https://learn.microsoft.com/python/api/overview/azure/identity-readme).

This reference is Python-only.

## Golden Rule

Use **managed identities** and **Azure RBAC** in production. Reserve `DefaultAzureCredential` for **local development only**.

## Authentication by Environment

| Environment | Recommended Credential | Why |
|---|---|---|
| **Production (Azure-hosted)** | `ManagedIdentityCredential` (system- or user-assigned) | No secrets to manage; auto-rotated by Azure |
| **Production (on-premises)** | `ClientCertificateCredential` or `WorkloadIdentityCredential` | Deterministic; no fallback chain overhead |
| **CI/CD pipelines** | `AzurePipelinesCredential` / `WorkloadIdentityCredential` | Scoped to pipeline identity |
| **Local development** | `DefaultAzureCredential` | Chains CLI, PowerShell, and VS Code credentials for convenience |

## Why Not `DefaultAzureCredential` in Production?

1. **Unpredictable fallback chain** — walks through multiple credential types, adding latency and making failures harder to diagnose.
2. **Broad surface area** — checks environment variables, CLI tokens, and other sources that should not exist in production.
3. **Non-deterministic** — which credential actually authenticates depends on the environment, making behavior inconsistent across deployments.
4. **Performance** — each failed credential attempt adds network round-trips before falling back to the next.

## Production Patterns

### Python

```python
import os
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

credential = (
    DefaultAzureCredential()                              # local dev — uses CLI/VS credentials
    if os.getenv("AZURE_FUNCTIONS_ENVIRONMENT") == "Development"
    else ManagedIdentityCredential()                      # production — deterministic, no fallback chain
)
# For user-assigned identity: ManagedIdentityCredential(client_id="<client-id>")
```

## Local Development Setup

`DefaultAzureCredential` is ideal for local dev because it automatically picks up credentials from developer tools:

1. **Azure CLI** — `az login`
2. **Azure Developer CLI** — `azd auth login`
3. **Azure PowerShell** — `Connect-AzAccount`
4. **Visual Studio / VS Code** — sign in via Azure extension

```python
from azure.identity import DefaultAzureCredential

# Local development only — uses CLI/VS Code credentials
credential = DefaultAzureCredential()
```

## Environment-Aware Pattern

Detect the runtime environment and select the appropriate credential. The key principle is to use `DefaultAzureCredential` only when running locally, and a specific credential in production.

> **Tip:** Azure Functions sets `AZURE_FUNCTIONS_ENVIRONMENT` to `"Development"` when running locally. For App Service or containers, use any environment variable you control.

```python
import os

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

def get_credential():
    if os.getenv("AZURE_FUNCTIONS_ENVIRONMENT") == "Development":
        return DefaultAzureCredential()
    if os.getenv("AZURE_CLIENT_ID"):
        return ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"])
    return ManagedIdentityCredential()
```

## Security Checklist

- [ ] Use managed identity for all Azure-hosted apps
- [ ] Never hardcode credentials, connection strings, or keys
- [ ] Apply least-privilege RBAC roles at the narrowest scope
- [ ] Use `ManagedIdentityCredential` (not `DefaultAzureCredential`) in production
- [ ] Store any required secrets in Azure Key Vault
- [ ] Rotate secrets and certificates on a schedule
- [ ] Enable Microsoft Defender for Cloud on production resources

## Further Reading

- [Passwordless connections overview](https://learn.microsoft.com/azure/developer/intro/passwordless-overview)
- [Managed identities overview](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview)
- [Azure RBAC overview](https://learn.microsoft.com/azure/role-based-access-control/overview)
- [Python identity library](https://learn.microsoft.com/python/api/overview/azure/identity-readme)
