"""Configuration and shared fixtures for test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ignore host configuration and run outside the source tree."""
    for key in (
        "ANYVAR_API_URL",
        "ANYVAR_API_TIMEOUT",
        "ANYVAR_MAX_SEARCH_SPAN",
        "ANYVAR_MAX_RESPONSE_BYTES",
        "ANYVAR_SEARCH_PAGE_SIZE",
        "ANYVAR_ENABLE_REGISTRATION",
        "ANYVAR_MAX_CALLS_PER_MINUTE",
        "ANYVAR_MAX_CALLS_PER_HOUR",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


def pytest_addoption(parser):
    """Add custom commands to pytest invocation.

    See https://docs.pytest.org/en/8.1.x/reference/reference.html#parser
    """
    parser.addoption(
        "--verbose-logs",
        action="store_true",
        default=False,
        help="show noisy module logs",
    )


def pytest_configure(config):
    """Configure pytest setup."""
    # add noisy logging libraries.
    if not config.getoption("--verbose-logs"):
        pass
