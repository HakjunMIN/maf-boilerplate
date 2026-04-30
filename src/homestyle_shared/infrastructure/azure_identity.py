from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential


def build_azure_credential(
    *,
    use_developer_credentials: bool,
    managed_identity_client_id: str | None = None,
) -> AsyncTokenCredential:
    if use_developer_credentials:
        return DefaultAzureCredential()
    if managed_identity_client_id:
        return ManagedIdentityCredential(client_id=managed_identity_client_id)
    return ManagedIdentityCredential()
