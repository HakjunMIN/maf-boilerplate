import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class AzureRagSettings:
    azure_openai_endpoint: str
    azure_openai_api_version: str
    azure_openai_chat_deployment: str
    azure_openai_embedding_deployment: str
    azure_openai_vision_deployment: str
    azure_search_endpoint: str
    azure_search_index_name: str
    use_developer_credentials: bool = False
    managed_identity_client_id: str | None = None
    search_top: int = 5
    extraction_version: str = "v1"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AzureRagSettings":
        values = os.environ if env is None else env
        missing = [name for name in _REQUIRED_ENV_VARS if not _read_required(values, name)]
        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(f"Missing required Azure RAG settings: {joined}")

        return cls(
            azure_openai_endpoint=_read_required(values, "AZURE_OPENAI_ENDPOINT"),
            azure_openai_api_version=_read_required(values, "AZURE_OPENAI_API_VERSION"),
            azure_openai_chat_deployment=_read_required(values, "AZURE_OPENAI_CHAT_DEPLOYMENT"),
            azure_openai_embedding_deployment=_read_required(
                values,
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            ),
            azure_openai_vision_deployment=_read_required(
                values,
                "AZURE_OPENAI_VISION_DEPLOYMENT",
            ),
            azure_search_endpoint=_read_required(values, "AZURE_SEARCH_ENDPOINT"),
            azure_search_index_name=_read_required(values, "AZURE_SEARCH_INDEX_NAME"),
            use_developer_credentials=_read_bool(
                values,
                "USE_DEVELOPER_CREDENTIALS",
                default=False,
            ),
            managed_identity_client_id=_read_optional(values, "MANAGED_IDENTITY_CLIENT_ID"),
            search_top=_read_int(values, "SEARCH_TOP", default=5),
            extraction_version=_read_optional(values, "EXTRACTION_VERSION") or "v1",
        )


_REQUIRED_ENV_VARS = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_CHAT_DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "AZURE_OPENAI_VISION_DEPLOYMENT",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_INDEX_NAME",
)

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _read_required(values: Mapping[str, str], name: str) -> str:
    value = _read_optional(values, name)
    return value or ""


def _read_optional(values: Mapping[str, str], name: str) -> str | None:
    value = values.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _read_bool(values: Mapping[str, str], name: str, *, default: bool) -> bool:
    value = _read_optional(values, name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean for {name}: {value}")


def _read_int(values: Mapping[str, str], name: str, *, default: int) -> int:
    value = _read_optional(values, name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"Invalid integer for {name}: {value}") from error
