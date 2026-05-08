from homestyle_shared.infrastructure.azure_identity import build_azure_credential


def test_build_azure_credential_uses_default_credential_for_developer_flow(
    monkeypatch,
) -> None:
    calls: list[tuple[str, object | None]] = []

    class FakeDefaultAzureCredential:
        def __init__(self) -> None:
            calls.append(("default", None))

    class FakeManagedIdentityCredential:
        def __init__(self, *, client_id: str | None = None) -> None:
            calls.append(("managed", client_id))

    monkeypatch.setattr(
        "homestyle_shared.infrastructure.azure_identity.DefaultAzureCredential",
        FakeDefaultAzureCredential,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.azure_identity.ManagedIdentityCredential",
        FakeManagedIdentityCredential,
    )

    credential = build_azure_credential(
        use_developer_credentials=True,
        azure_tenant_id=None,
        managed_identity_client_id="ignored-client-id",
    )

    assert isinstance(credential, FakeDefaultAzureCredential)
    assert calls == [("default", None)]


def test_build_azure_credential_uses_cli_credential_with_explicit_tenant(
    monkeypatch,
) -> None:
    calls: list[tuple[str, object | None]] = []

    class FakeDefaultAzureCredential:
        def __init__(self) -> None:
            calls.append(("default", None))

    class FakeAzureCliCredential:
        def __init__(self, *, tenant_id: str) -> None:
            self.tenant_id = tenant_id
            calls.append(("cli", tenant_id))

    class FakeManagedIdentityCredential:
        def __init__(self, *, client_id: str | None = None) -> None:
            calls.append(("managed", client_id))

    monkeypatch.setattr(
        "homestyle_shared.infrastructure.azure_identity.DefaultAzureCredential",
        FakeDefaultAzureCredential,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.azure_identity.AzureCliCredential",
        FakeAzureCliCredential,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.azure_identity.ManagedIdentityCredential",
        FakeManagedIdentityCredential,
    )

    credential = build_azure_credential(
        use_developer_credentials=True,
        azure_tenant_id="tenant-id",
        managed_identity_client_id="ignored-client-id",
    )

    assert isinstance(credential, FakeAzureCliCredential)
    assert credential.tenant_id == "tenant-id"
    assert calls == [("cli", "tenant-id")]


def test_build_azure_credential_uses_managed_identity_with_optional_client_id(
    monkeypatch,
) -> None:
    calls: list[tuple[str, object | None]] = []

    class FakeDefaultAzureCredential:
        def __init__(self) -> None:
            calls.append(("default", None))

    class FakeManagedIdentityCredential:
        def __init__(self, *, client_id: str | None = None) -> None:
            self.client_id = client_id
            calls.append(("managed", client_id))

    monkeypatch.setattr(
        "homestyle_shared.infrastructure.azure_identity.DefaultAzureCredential",
        FakeDefaultAzureCredential,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.azure_identity.ManagedIdentityCredential",
        FakeManagedIdentityCredential,
    )

    explicit_credential = build_azure_credential(
        use_developer_credentials=False,
        azure_tenant_id="ignored-tenant-id",
        managed_identity_client_id="client-id",
    )
    implicit_credential = build_azure_credential(
        use_developer_credentials=False,
        azure_tenant_id=None,
        managed_identity_client_id=None,
    )

    assert isinstance(explicit_credential, FakeManagedIdentityCredential)
    assert isinstance(implicit_credential, FakeManagedIdentityCredential)
    assert explicit_credential.client_id == "client-id"
    assert implicit_credential.client_id is None
    assert calls == [("managed", "client-id"), ("managed", None)]
