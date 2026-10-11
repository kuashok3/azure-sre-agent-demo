import pytest
from pydantic import ValidationError

from app.orders.config import Settings
from tests.conftest import make_settings


def test_defaults_have_faults_disabled():
    settings = Settings(_env_file=None, db_password="x")
    assert settings.faults_enabled is False
    assert settings.telemetry_connection_string is None


def test_password_mode_requires_password():
    with pytest.raises(ValidationError, match="DB_PASSWORD"):
        Settings(_env_file=None, db_auth_mode="password")


def test_entra_mode_needs_no_password():
    assert Settings(_env_file=None, db_auth_mode="entra").db_password is None


def test_faults_require_long_token():
    with pytest.raises(ValidationError, match="FAULT_ADMIN_TOKEN"):
        make_settings(fault_admin_token="short")


def test_placeholder_token_rejected_in_azure():
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(environment="azure", fault_admin_token="change-me-local-fault-token")


def test_log_level_is_case_insensitive():
    assert make_settings(log_level="debug").log_level == "DEBUG"
