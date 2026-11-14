"""What the service reads from its environment."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from environment variables, or from a `.env` file in the working directory."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The Hugging Face access token the emotion step calls the model with: HF_TOKEN.
    hf_token: SecretStr


def load_settings() -> Settings:
    # Workaround (pydantic-settings): `Settings()` is what its docs show, but a type checker
    # reads that call as missing every required field — it can't see the environment fill
    # them in. Validating an empty mapping loads from the environment the same way.
    return Settings.model_validate({})
