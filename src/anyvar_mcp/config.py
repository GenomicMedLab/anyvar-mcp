"""Load AnyVar configuration from .env files and environment variables."""

from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_NAME = "AnyVar"
SERVER_INSTRUCTIONS = "MCP server for AnyVar."


class Settings(BaseSettings):
    """Resolve immutable settings from constructor values, environment, .env, and defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        populate_by_name=True,
        frozen=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    anyvar_api_url: str = Field(
        default="http://localhost:8000", alias="ANYVAR_API_URL", min_length=1
    )
    anyvar_api_timeout: float = Field(
        default=10.0, alias="ANYVAR_API_TIMEOUT", gt=0, allow_inf_nan=False
    )

    anyvar_max_search_span: int = Field(
        default=1_000_000, alias="ANYVAR_MAX_SEARCH_SPAN", gt=0
    )
    # Default result count controls context use; the byte cap also bounds reads
    # when individual variants contain large literal sequences.
    anyvar_search_page_size: int = Field(
        default=100, alias="ANYVAR_SEARCH_PAGE_SIZE", gt=0, le=10_000
    )
    anyvar_max_response_bytes: int = Field(
        default=1_048_576, alias="ANYVAR_MAX_RESPONSE_BYTES", gt=0
    )

    @field_validator("anyvar_api_url")
    @classmethod
    def validate_api_url(cls, value: str) -> str:
        """Require an HTTP(S) service URL without credentials, query, or fragment.

        :param value: Resolved service URL.
        :return: Valid service URL, preserving any path prefix.
        :raises ValueError: If the URL is invalid or includes prohibited components.
        """
        error_message = (
            "AnyVar API URL must be HTTP(S) without credentials, query, or fragment."
        )
        try:
            parsed_url = urlsplit(value)
        except ValueError:
            raise ValueError(error_message) from None

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise ValueError(error_message)
        return value

    @field_validator(
        "anyvar_max_search_span",
        "anyvar_max_response_bytes",
        "anyvar_search_page_size",
        mode="before",
    )
    @classmethod
    def validate_resource_limit_type(cls, value: object) -> object:
        """Accept integer limits and strings loaded from configuration sources.

        :param value: Resource limit before settings type conversion.
        :return: Value for integer parsing and positive-value validation.
        :raises ValueError: If a limit is neither an integer nor a string.
        """
        if type(value) is not int and not isinstance(value, str):
            error_message = "Resource limits must be positive integers."
            raise ValueError(error_message)
        return value
