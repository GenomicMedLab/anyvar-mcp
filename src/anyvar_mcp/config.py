"""Load AnyVar configuration from .env files and environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_NAME = "AnyVar"
SERVER_INSTRUCTIONS = "MCP server for AnyVar."


class Settings(BaseSettings):
    """Validate configuration loaded from .env files and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
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
    anyvar_max_response_bytes: int = Field(
        default=65_536, alias="ANYVAR_MAX_RESPONSE_BYTES", gt=0
    )


settings = Settings()
