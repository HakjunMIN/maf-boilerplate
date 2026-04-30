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
        managed_identity_client_id="ignored-client-id",
    )

    assert isinstance(credential, FakeDefaultAzureCredential)
    assert calls == [("default", None)]


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
        managed_identity_client_id="client-id",
    )
    implicit_credential = build_azure_credential(
        use_developer_credentials=False,
        managed_identity_client_id=None,
    )

    assert isinstance(explicit_credential, FakeManagedIdentityCredential)
    assert isinstance(implicit_credential, FakeManagedIdentityCredential)
    assert explicit_credential.client_id == "client-id"
    assert implicit_credential.client_id is None
    assert calls == [("managed", "client-id"), ("managed", None)]
