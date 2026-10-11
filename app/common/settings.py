"""Settings shared by both services, loaded from environment variables (and .env locally).

Validation runs at startup so a misconfigured service fails fast with a clear message instead of
failing later on the first request.
"""

from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_FAULT_TOKEN_LENGTH = 16


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["local", "test", "azure"] = "local"
    app_version: str = "0.1.0-dev"
    git_sha: str = "unknown"
    build_time: str = "unknown"
    deployment_region: str = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    otel_service_name: str = "service"

    # Empty locally; set in Azure. When empty, telemetry export is disabled.
    applicationinsights_connection_string: SecretStr | None = None

    # Demo-only failure injection. Off unless explicitly enabled.
    faults_enabled: bool = False
    fault_admin_token: SecretStr | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _validate_faults(self) -> "BaseServiceSettings":
        if self.faults_enabled:
            token = self.fault_admin_token.get_secret_value() if self.fault_admin_token else ""
            if len(token) < MIN_FAULT_TOKEN_LENGTH:
                raise ValueError(
                    "FAULTS_ENABLED=true requires FAULT_ADMIN_TOKEN with at least "
                    f"{MIN_FAULT_TOKEN_LENGTH} characters"
                )
            if self.environment == "azure" and token.startswith("change-me"):
                raise ValueError("Replace the placeholder FAULT_ADMIN_TOKEN before using Azure")
        return self

    @property
    def telemetry_connection_string(self) -> str | None:
        if self.applicationinsights_connection_string is None:
            return None
        return self.applicationinsights_connection_string.get_secret_value() or None

    @property
    def fault_token_value(self) -> str:
        return self.fault_admin_token.get_secret_value() if self.fault_admin_token else ""
