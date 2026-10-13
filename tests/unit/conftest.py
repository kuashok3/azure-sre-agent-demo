import pytest

from app.orders.config import Settings
from app.payment_stub.main import StubSettings

# Every environment variable the services read (field names, upper-cased by pydantic-settings).
_APP_ENV_VARS = {name.upper() for name in (*Settings.model_fields, *StubSettings.model_fields)}


@pytest.fixture(autouse=True)
def hermetic_environment(monkeypatch):
    """Unit tests must not depend on the shell or CI environment.

    Found 2026-10-13: CI sets DB_PASSWORD for the integration job, which leaked into unit tests that
    expect "no password configured". Same class of bug as leftover FAULT_* variables in a shell.
    Tests that need a variable set it themselves with monkeypatch.setenv.
    """
    for name in _APP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
