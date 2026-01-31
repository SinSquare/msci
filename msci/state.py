"""Application dependencies and state."""

import functools
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from msci.config import Config
from msci.wiki_word_frequency import WikiWordFrequency

log = logging.getLogger(__name__)


@functools.lru_cache()
def get_config() -> Config:
    """Return the config loaded from envvars."""
    return Config()


@functools.lru_cache()
def get_wiki() -> WikiWordFrequency:
    """Return the config loaded from envvars."""
    config = get_config()
    return WikiWordFrequency(
        max_workers=config.wiki_thread_count,
        api_url=config.wiki_api_url,
        user_agent=config.wiki_user_agent,
        access_token=config.wiki_access_token,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):  # pylint: disable=unused-argument
    """lifespan"""
    get_wiki()
    yield
