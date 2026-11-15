"""What the service reads from its environment."""

from pathlib import Path
from typing import Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from emotion_painting.emotion import EmotionBackend


class Settings(BaseSettings):
    """Read from environment variables, or from a `.env` file in the working directory."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where the emotion model runs: EMOTION_BACKEND, `local` (the default) or `hugging_face`.
    emotion_backend: EmotionBackend = EmotionBackend.LOCAL
    # The Hugging Face access token, needed only when the model runs behind its API: HF_TOKEN.
    hf_token: SecretStr | None = None
    # Where each run's snapshot is written: OUTPUTS_DIR.
    outputs_dir: Path = Path("outputs")

    @model_validator(mode="after")
    def check_token_for_hugging_face(self) -> Self:
        if self.emotion_backend is EmotionBackend.HUGGING_FACE:
            self.require_hf_token()
        return self

    def require_hf_token(self) -> str:
        if self.hf_token is None:
            raise ValueError("EMOTION_BACKEND=hugging_face needs HF_TOKEN")
        return self.hf_token.get_secret_value()


def load_settings() -> Settings:
    # Workaround (pydantic-settings): `Settings()` is what its docs show, but a type checker
    # reads that call as missing every required field — it can't see the environment fill
    # them in. Validating an empty mapping loads from the environment the same way.
    return Settings.model_validate({})
