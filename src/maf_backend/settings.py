from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MAF Analysis Backend"
    api_bearer_token: str = Field(..., alias="API_BEARER_TOKEN")

    model_provider: Literal["azure_openai", "openai", "foundry_local"] = Field(
        default="azure_openai", alias="MODEL_PROVIDER"
    )

    azure_openai_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_model: str | None = Field(default=None, alias="AZURE_OPENAI_MODEL")

    openai_model: str | None = Field(default=None, alias="OPENAI_MODEL")

    foundry_local_model: str | None = Field(default=None, alias="FOUNDRY_LOCAL_MODEL")

    sandbox_image: str = Field(default="maf-analysis-sandbox:latest", alias="SANDBOX_IMAGE")
    sandbox_timeout_seconds: int = Field(default=45, alias="SANDBOX_TIMEOUT_SECONDS")
    sandbox_memory: str = Field(default="512m", alias="SANDBOX_MEMORY")
    sandbox_cpus: str = Field(default="1.0", alias="SANDBOX_CPUS")
    sandbox_user: str = Field(default="65532:65532", alias="SANDBOX_USER")
    sandbox_output_limit_bytes: int = Field(default=65536, alias="SANDBOX_OUTPUT_LIMIT_BYTES")
    sandbox_data_root: Path = Field(default=Path("data"), alias="SANDBOX_DATA_ROOT")

    @property
    def resolved_data_root(self) -> Path:
        return self.sandbox_data_root.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
