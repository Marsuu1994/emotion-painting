from pathlib import Path

import pytest
from pydantic import ValidationError

from emotion_painting.config import load_settings
from emotion_painting.emotion import EmotionBackend


@pytest.fixture(autouse=True)
def empty_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No `.env` of the developer's, and none of their variables, leak into these tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("EMOTION_BACKEND", raising=False)


def test_the_model_runs_locally_by_default_and_needs_no_token() -> None:
    settings = load_settings()

    assert settings.emotion_backend is EmotionBackend.LOCAL
    assert settings.hf_token is None


def test_the_backend_and_token_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMOTION_BACKEND", "hugging_face")
    monkeypatch.setenv("HF_TOKEN", "from-the-environment")

    settings = load_settings()

    assert settings.emotion_backend is EmotionBackend.HUGGING_FACE
    assert settings.require_hf_token() == "from-the-environment"


def test_the_token_comes_from_a_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "EMOTION_BACKEND=hugging_face\nHF_TOKEN=from-the-file\n"
    )

    assert load_settings().require_hf_token() == "from-the-file"


def test_the_token_never_shows_when_settings_are_printed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_TOKEN", "a-secret")

    assert "a-secret" not in repr(load_settings())


def test_the_hugging_face_backend_without_a_token_stops_the_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMOTION_BACKEND", "hugging_face")

    with pytest.raises(ValidationError, match="needs HF_TOKEN"):
        load_settings()


def test_an_unknown_backend_stops_the_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMOTION_BACKEND", "somewhere_else")

    with pytest.raises(ValidationError, match="emotion_backend"):
        load_settings()
