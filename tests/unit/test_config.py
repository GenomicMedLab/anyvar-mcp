"""Check application configuration defaults and user override precedence."""

import os
from pathlib import Path
from traceback import format_exception

import pytest
from pydantic import ValidationError

from anyvar_mcp import config
from anyvar_mcp.clients.anyvar import AnyVarClient


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ignore host configuration and run outside the source tree."""
    for key in (
        "ANYVAR_API_URL",
        "ANYVAR_API_TIMEOUT",
        "ANYVAR_MAX_SEARCH_SPAN",
        "ANYVAR_MAX_RESPONSE_BYTES",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


def test_defaults_without_env_file() -> None:
    """Use application defaults when no user configuration is present."""
    settings = AnyVarClient().settings

    assert settings.anyvar_api_url == "http://localhost:8000"
    assert settings.anyvar_api_timeout == 10.0
    assert settings.anyvar_max_search_span == 1_000_000
    assert settings.anyvar_max_response_bytes == 65_536


@pytest.mark.parametrize(
    "value",
    ["0", "nan", "secret-config-token"],
)
def test_invalid_settings(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Reject invalid timeouts and identify the affected configuration field."""
    monkeypatch.setenv("ANYVAR_API_TIMEOUT", value)

    with pytest.raises(ValidationError) as caught:
        config.Settings()

    assert caught.value.errors()[0]["loc"] == ("ANYVAR_API_TIMEOUT",)
    assert "secret-config-token" not in "".join(format_exception(caught.value))


def test_configuration_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer explicit fields, then environment, then .env, then defaults."""
    Path(".env").write_text(
        "ANYVAR_API_URL=invalid\n"
        "ANYVAR_API_TIMEOUT=invalid\n"
        "ANYVAR_MAX_SEARCH_SPAN=200\n"
    )
    monkeypatch.setenv("ANYVAR_API_URL", "https://environment.example/api")
    monkeypatch.setenv("ANYVAR_API_TIMEOUT", "invalid")
    original_environment = dict(os.environ)

    settings = config.Settings(anyvar_api_timeout=3)

    assert settings.anyvar_api_url == "https://environment.example/api"
    assert settings.anyvar_api_timeout == 3.0
    assert settings.anyvar_max_search_span == 200
    assert settings.anyvar_max_response_bytes == 65_536
    assert dict(os.environ) == original_environment


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("anyvar_max_search_span", True),
        ("anyvar_max_response_bytes", 1.5),
    ],
    ids=["boolean", "fractional"],
)
def test_invalid_explicit_resource_limit_type(argument: str, value: object) -> None:
    """Reject boolean and fractional limits instead of coercing them to integers."""
    with pytest.raises(
        ValidationError, match="Resource limits must be positive integers"
    ):
        config.Settings(**{argument: value})


def test_client_reuses_supplied_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use supplied settings without reloading a subsequently changed environment."""
    settings = config.Settings(anyvar_api_timeout=3)
    monkeypatch.setenv("ANYVAR_API_TIMEOUT", "invalid")

    client = AnyVarClient(settings=settings)

    assert client.settings is settings
    assert client.settings.anyvar_api_timeout == 3.0


def test_settings_reject_assignment() -> None:
    """Keep validated settings unchanged after construction."""
    settings = config.Settings(anyvar_api_timeout=3)

    with pytest.raises(ValidationError) as caught:
        settings.anyvar_api_timeout = 5

    assert caught.value.errors()[0]["type"] == "frozen_instance"
    assert settings.anyvar_api_timeout == 3.0
