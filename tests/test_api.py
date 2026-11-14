import json
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from emotion_painting.api import app, get_http_client, get_settings, lifespan
from emotion_painting.config import Settings
from emotion_painting.constants import (
    BASE_VERSION,
    ENTRY_MAX_CHARS,
    EXTERNAL_SERVICE_TIMEOUT_SECONDS,
)
from fake_services import PAINTING_BYTES, FakeServices

pytestmark = pytest.mark.anyio

ENTRY = "早上去了灯塔。\nThe harbour was quiet."


@pytest.fixture
def services() -> FakeServices:
    return FakeServices()


@pytest.fixture
def outputs_dir(tmp_path: Path) -> Path:
    return tmp_path / "outputs"


@pytest.fixture
async def api(
    services: FakeServices, outputs_dir: Path
) -> AsyncGenerator[httpx.AsyncClient]:
    """The app, called in process, with its two outside edges replaced: the settings and the HTTP transport."""

    async def fake_http_client() -> AsyncGenerator[httpx.AsyncClient]:
        async with services.client() as client:
            yield client

    app.dependency_overrides[get_settings] = lambda: Settings(
        hf_token=SecretStr("a-token"), outputs_dir=outputs_dir
    )
    app.dependency_overrides[get_http_client] = fake_http_client
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://emotion-painting.test"
    ) as api_client:
        yield api_client
    app.dependency_overrides.clear()


def snapshot_names(outputs_dir: Path) -> list[str]:
    if not outputs_dir.exists():
        return []
    return sorted(path.name for path in outputs_dir.iterdir())


async def test_the_response_is_the_image(api: httpx.AsyncClient) -> None:
    response = await api.post("/generate", json={"text": ENTRY})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == PAINTING_BYTES


async def test_a_call_leaves_a_snapshot_under_the_base_version(
    api: httpx.AsyncClient, outputs_dir: Path
) -> None:
    await api.post("/generate", json={"text": ENTRY})

    image_name, metadata_name = snapshot_names(outputs_dir)
    assert image_name.startswith(f"v{BASE_VERSION}_")
    assert image_name.endswith(".jpg")
    assert metadata_name == image_name.removesuffix(".jpg") + "_meta.json"
    assert (outputs_dir / image_name).read_bytes() == PAINTING_BYTES
    metadata = json.loads((outputs_dir / metadata_name).read_text("utf-8"))
    assert metadata["version"] == BASE_VERSION
    assert metadata["text"] == ENTRY
    assert metadata["image_file"] == image_name


async def test_the_request_can_name_its_version(
    api: httpx.AsyncClient, outputs_dir: Path
) -> None:
    await api.post("/generate", json={"text": ENTRY, "version": "0.2-warm-palette"})

    names = snapshot_names(outputs_dir)
    assert len(names) == 2
    assert all(name.startswith("v0.2-warm-palette_") for name in names)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"text": ""},
        {"text": "x" * (ENTRY_MAX_CHARS + 1)},
        {"text": ENTRY, "version": "../elsewhere"},
        {"text": ENTRY, "version": "has space"},
        {"text": ENTRY, "version": ""},
    ],
)
async def test_a_malformed_request_is_refused_before_any_work(
    api: httpx.AsyncClient,
    services: FakeServices,
    outputs_dir: Path,
    body: dict[str, str],
) -> None:
    response = await api.post("/generate", json=body)

    assert response.status_code == 422
    assert services.requests == []
    assert snapshot_names(outputs_dir) == []


async def test_an_entry_with_nothing_to_paint_is_refused(
    api: httpx.AsyncClient, outputs_dir: Path
) -> None:
    response = await api.post(
        "/generate", json={"text": " \n https://example.com/only-a-link "}
    )

    assert response.status_code == 422
    assert "no text left to paint" in response.json()["detail"]
    assert snapshot_names(outputs_dir) == []


async def test_a_failing_service_is_a_bad_gateway_that_says_why(
    api: httpx.AsyncClient, services: FakeServices, outputs_dir: Path
) -> None:
    services.hugging_face_response = httpx.Response(
        402, json={"error": "Purchase pre-paid credits"}
    )

    response = await api.post("/generate", json={"text": ENTRY})

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Hugging Face answered 402")
    assert snapshot_names(outputs_dir) == []


async def test_the_docs_show_the_response_as_an_image(api: httpx.AsyncClient) -> None:
    openapi = (await api.get("/openapi.json")).json()

    responses = openapi["paths"]["/generate"]["post"]["responses"]
    assert set(responses["200"]["content"]) == {"image/jpeg", "image/png"}
    assert "502" in responses


async def test_outside_calls_get_the_long_timeout_and_follow_redirects() -> None:
    async for client in get_http_client():
        assert client.timeout == httpx.Timeout(EXTERNAL_SERVICE_TIMEOUT_SECONDS)
        assert client.follow_redirects


@pytest.fixture
def no_settings_in_reach(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither the developer's `.env` nor an earlier test's cached settings."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    get_settings.cache_clear()


@pytest.mark.usefixtures("no_settings_in_reach")
async def test_the_service_starts_with_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "a-token")

    async with lifespan(app):
        assert get_settings().hf_token.get_secret_value() == "a-token"
    get_settings.cache_clear()


@pytest.mark.usefixtures("no_settings_in_reach")
async def test_the_service_refuses_to_start_without_a_token() -> None:
    with pytest.raises(ValidationError, match="hf_token"):
        async with lifespan(app):
            pass
