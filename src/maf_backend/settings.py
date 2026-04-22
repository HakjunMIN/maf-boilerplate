from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    api_bearer_token: str = Field(default="change-me", validation_alias="API_BEARER_TOKEN")

    model_provider: str = Field(default="foundry_local", validation_alias="MODEL_PROVIDER")
    azure_openai_endpoint: str | None = Field(default=None, validation_alias="AZURE_OPENAI_ENDPOINT")
    azure_ai_project_endpoint: str | None = Field(default=None, validation_alias="AZURE_AI_PROJECT_ENDPOINT")
    azure_openai_model: str | None = Field(default=None, validation_alias="AZURE_OPENAI_MODEL")
    azure_openai_chat_deployment: str | None = Field(default=None, validation_alias="AZURE_OPENAI_CHAT_DEPLOYMENT")
    azure_openai_api_version: str | None = Field(default=None, validation_alias="AZURE_OPENAI_API_VERSION")
    openai_model: str | None = Field(default=None, validation_alias="OPENAI_MODEL")
    foundry_local_model: str | None = Field(default=None, validation_alias="FOUNDRY_LOCAL_MODEL")

    sandbox_image: str = Field(default="maf-analysis-sandbox:latest", validation_alias="SANDBOX_IMAGE")
    sandbox_timeout_seconds: int = Field(default=30, validation_alias="SANDBOX_TIMEOUT_SECONDS")
    sandbox_memory: str = Field(default="512m", validation_alias="SANDBOX_MEMORY")
    sandbox_cpus: str = Field(default="1", validation_alias="SANDBOX_CPUS")
    sandbox_user: str = Field(default="65534:65534", validation_alias="SANDBOX_USER")
    sandbox_output_limit_bytes: int = Field(default=65536, validation_alias="SANDBOX_OUTPUT_LIMIT_BYTES")
    sandbox_data_root: str = Field(default="data", validation_alias="SANDBOX_DATA_ROOT")

    web_search_max_results: int = Field(default=5)