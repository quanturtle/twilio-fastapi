from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # OpenAI settings
    model: str = "gpt-4.1-mini"
    instructions: str = (
        "You are a helpful assistant that can answer questions directly to the point and concisely."
    )
    temperature: float = 0.1
    max_output_tokens: int = 150

    # Message batching settings
    debounce_time: int = 0  # seconds


@lru_cache
def get_settings() -> Settings:
    """
    Create and cache a Settings instance.
    Using lru_cache ensures Settings is instantiated only once.
    """
    return Settings()
