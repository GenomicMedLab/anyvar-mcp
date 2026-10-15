"""Check application configuration defaults and user override precedence."""

import os
from pathlib import Path
from traceback import format_exception

import pytest
from pydantic import ValidationError

from anyvar_mcp import config


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
    settings = config.Settings()

    assert settings.anyvar_api_url == "http://localhost:8000"
    assert settings.anyvar_api_timeout == 10.0
    assert settings.anyvar_max_search_span == 1_000_000
    assert settings.anyvar_max_response_bytes == 65_536


def test_env_file_and_environment_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer environment overrides without copying .env values into the process."""
    Path(".env").write_text(
        "ANYVAR_API_URL=https://anyvar.example/api\nANYVAR_API_TIMEOUT=30\n"
    )
    monkeypatch.setenv("ANYVAR_API_TIMEOUT", "60")
    original_environment = dict(os.environ)

    settings = config.Settings()

    assert settings.anyvar_api_url == "https://anyvar.example/api"
    assert settings.anyvar_api_timeout == 60.0
    assert dict(os.environ) == original_environment


@pytest.mark.parametrize(
    "value",
    ["0", "nan", "invalid", "inf", "secret-config-token"],
)
def test_invalid_settings(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Reject invalid timeouts and identify the affected configuration field."""
    monkeypatch.setenv("ANYVAR_API_TIMEOUT", value)

    with pytest.raises(ValidationError) as caught:
        config.Settings()

    assert caught.value.errors()[0]["loc"] == ("ANYVAR_API_TIMEOUT",)
    assert "secret-config-token" not in "".join(format_exception(caught.value))


@pytest.mark.parametrize(
    "setting",
    [
        "ANYVAR_MAX_SEARCH_SPAN",
        "ANYVAR_MAX_RESPONSE_BYTES",
    ],
)
def test_invalid_resource_limit(monkeypatch: pytest.MonkeyPatch, setting: str) -> None:
    """Reject nonpositive client resource limits."""

    monkeypatch.setenv(setting, "0")

    with pytest.raises(ValidationError) as caught:
        config.Settings()

    assert caught.value.errors()[0]["loc"] == (setting,)
