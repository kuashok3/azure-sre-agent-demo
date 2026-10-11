"""orders-api settings. See docs/CONFIGURATION.md for every variable."""

from typing import Literal

from pydantic import Field, SecretStr, model_validator

from app.common.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    otel_service_name: str = "orders-api"

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "orders"
    db_user: str = "orders"
    db_password: SecretStr | None = None
    db_sslmode: Literal["disable", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    # "password" locally; "entra" in Azure (managed identity token, no stored password)
    db_auth_mode: Literal["password", "entra"] = "password"
    db_connect_timeout_seconds: int = Field(3, ge=1, le=30)
    db_statement_timeout_ms: int = Field(5000, ge=100, le=60000)
    db_pool_min_size: int = Field(1, ge=0, le=20)
    db_pool_max_size: int = Field(5, ge=1, le=50)

    # Client ID of the user-assigned managed identity (Azure only)
    azure_client_id: str | None = None

    # Downstream payment service
    payment_base_url: str = "http://localhost:8001"
    payment_timeout_seconds: float = Field(2.0, gt=0, le=30)

    @model_validator(mode="after")
    def _validate_db(self) -> "Settings":
        if self.db_auth_mode == "password" and not (
            self.db_password and self.db_password.get_secret_value()
        ):
            raise ValueError("DB_AUTH_MODE=password requires DB_PASSWORD")
        if self.db_pool_min_size > self.db_pool_max_size:
            raise ValueError("DB_POOL_MIN_SIZE cannot exceed DB_POOL_MAX_SIZE")
        return self
