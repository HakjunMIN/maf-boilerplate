from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import AzureCliCredential, DefaultAzureCredential, ManagedIdentityCredential


def build_azure_credential(
    *,
    use_developer_credentials: bool,
    azure_tenant_id: str | None = None,
    managed_identity_client_id: str | None = None,
) -> AsyncTokenCredential:
    if use_developer_credentials:
        if azure_tenant_id:
            return AzureCliCredential(tenant_id=azure_tenant_id)
        return DefaultAzureCredential()
    if managed_identity_client_id:
        return ManagedIdentityCredential(client_id=managed_identity_client_id)
    return ManagedIdentityCredential()
