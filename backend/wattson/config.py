"""Typed application settings. Secrets are read only from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env"),
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    wattson_api_token: str = Field(default="", alias="WATTSON_API_TOKEN")
    wattson_database_url: str = Field(
        default="sqlite:///./.data/wattson.db", alias="WATTSON_DATABASE_URL"
    )
    wattson_kill_switch: bool = Field(default=False, alias="WATTSON_KILL_SWITCH")
    wattson_provider: str = Field(default="simulator", alias="WATTSON_PROVIDER")
    wattson_temporal_host: str = Field(default="localhost:7233", alias="WATTSON_TEMPORAL_HOST")
    wattson_temporal_namespace: str = Field(default="default", alias="WATTSON_TEMPORAL_NAMESPACE")
    wattson_temporal_task_queue: str = Field(default="wattson", alias="WATTSON_TEMPORAL_TASK_QUEUE")
    wattson_approval_timeout_seconds: int = Field(
        default=900, ge=10, alias="WATTSON_APPROVAL_TIMEOUT_SECONDS"
    )
    wattson_api_url: str = Field(default="http://localhost:8000", alias="WATTSON_API_URL")
    wattson_cors_origins: str = Field(
        default="http://localhost:3000", alias="WATTSON_CORS_ORIGINS"
    )
    wattson_report_dir: Path = Field(default=ROOT / ".data" / "reports", alias="WATTSON_REPORT_DIR")
    wattson_assumptions_path: Path = Field(
        default=ROOT / "simulator_assumptions.yaml", alias="WATTSON_ASSUMPTIONS_PATH"
    )

    wattson_ai_provider: str = Field(default="none", alias="WATTSON_AI_PROVIDER")
    gemma_model: str = Field(default="", alias="GEMMA_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    hosted_gemma_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        alias="HOSTED_GEMMA_BASE_URL",
    )
    hosted_gemma_api_key: str = Field(default="", alias="HOSTED_GEMMA_API_KEY")

    jl_api_key: str = Field(default="", alias="JL_API_KEY")

    wattson_kepler_prometheus_url: str = Field(
        default="", alias="WATTSON_KEPLER_PROMETHEUS_URL"
    )
    wattson_kepler_pod_label: str = Field(default="", alias="WATTSON_KEPLER_POD_LABEL")

    @field_validator("wattson_provider")
    @classmethod
    def _provider(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"simulator", "jarvislabs"}:
            raise ValueError("WATTSON_PROVIDER must be simulator or jarvislabs")
        return value

    @field_validator("wattson_ai_provider")
    @classmethod
    def _ai(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"none", "ollama", "hosted"}:
            raise ValueError("WATTSON_AI_PROVIDER must be none, ollama or hosted")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.wattson_cors_origins.split(",") if item.strip()]

    @property
    def ai_configured(self) -> bool:
        if self.wattson_ai_provider == "none":
            return False
        if not self.gemma_model:
            return False
        return not (
            self.wattson_ai_provider == "hosted" and not self.hosted_gemma_api_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
