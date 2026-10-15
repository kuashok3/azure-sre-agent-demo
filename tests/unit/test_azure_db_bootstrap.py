import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "azure_db_bootstrap.py"


def load_script():
    spec = importlib.util.spec_from_file_location("azure_db_bootstrap", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import pytest  # noqa: E402

OID = "769efb60-6847-4566-8b6b-d303fd562b8d"


def test_object_id_is_required():
    # Found 2026-10-15: granting by NAME fails once several environments in the tenant have an
    # identity called id-orders-api ("name isn't unique in the tenant"). Object IDs are unique.
    with pytest.raises(SystemExit):
        load_script().parse_args(["--server-fqdn", "s", "--admin-upn", "me@x.com"])


def test_object_id_must_be_a_guid():
    with pytest.raises(SystemExit):
        load_script().parse_args(
            ["--server-fqdn", "s", "--admin-upn", "me@x.com", "--app-object-id", "id-orders-api"]
        )


def test_principal_is_created_by_object_id():
    script = load_script()
    args = script.parse_args(
        ["--server-fqdn", "s", "--admin-upn", "me@x.com", "--app-object-id", OID]
    )
    query, params = script.create_principal_call(args.app_role, args.app_object_id)
    assert "pgaadauth_create_principal_with_oid" in query
    assert params == ("id-orders-api", OID, "service", False, False)


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
