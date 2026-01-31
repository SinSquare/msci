"""Application and gunicorn configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings, env_prefix="MSCI_"):
    """App config model."""

    wiki_thread_count: int = Field(
        ge=1, default=200, description="Must have at least one worker"
    )
    wiki_api_url: str = "https://en.wikipedia.org/w/api.php"
    wiki_user_agent: str = "MSCI-test/1.0 (contact@example.com)"
    wiki_access_token: str | None = None
