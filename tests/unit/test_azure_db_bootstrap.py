import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "azure_db_bootstrap.py"


def load_script():
    spec = importlib.util.spec_from_file_location("azure_db_bootstrap", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_admin_settings_ignore_fault_variables_in_shell(monkeypatch):
    # Reproduces the 2026-10-13 failure: leftover local fault settings in the shell environment
    monkeypatch.setenv("FAULTS_ENABLED", "true")
    monkeypatch.setenv("FAULT_ADMIN_TOKEN", "change-me-local-fault-token")
    monkeypatch.setenv("DB_PASSWORD", "local-dev-only-password")

    settings = load_script().admin_settings("srv.postgres.database.azure.com", "me@x.com", "orders")

    assert settings.faults_enabled is False
    assert settings.db_auth_mode == "entra"
    assert settings.db_user == "me@x.com"
    assert settings.db_host == "srv.postgres.database.azure.com"
    assert settings.db_sslmode == "require"
    assert settings.telemetry_connection_string is None
