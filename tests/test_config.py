from pathlib import Path

import pytest
from pydantic import ValidationError

from emotion_painting.config import load_settings


@pytest.fixture(autouse=True)
def empty_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No `.env` of the developer's leaks into these tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)


def test_the_token_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "from-the-environment")

    assert load_settings().hf_token.get_secret_value() == "from-the-environment"


def test_the_token_comes_from_a_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("HF_TOKEN=from-the-file\n")

    assert load_settings().hf_token.get_secret_value() == "from-the-file"


def test_the_token_never_shows_when_settings_are_printed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_TOKEN", "a-secret")

    assert "a-secret" not in repr(load_settings())


def test_a_missing_token_stops_the_load() -> None:
    with pytest.raises(ValidationError, match="hf_token"):
        load_settings()
