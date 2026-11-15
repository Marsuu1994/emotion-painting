import json
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from emotion_painting import api as api_module
from emotion_painting.api import app, get_http_client, get_settings, lifespan
from emotion_painting.config import Settings
from emotion_painting.constants import (
    BASE_VERSION,
    ENTRY_MAX_CHARS,
    EXTERNAL_SERVICE_TIMEOUT_SECONDS,
)
from emotion_painting.emotion import EmotionBackend, EmotionScorer
from emotion_painting.local_emotion_model import LocalEmotionScorer
from emotion_painting.vocabulary import Emotion
from fake_services import HAPPY_SCORE, HUGGING_FACE_HOST, PAINTING_BYTES, FakeServices

if TYPE_CHECKING:
    from transformers import ZeroShotResult

pytestmark = pytest.mark.anyio

ENTRY = "早上去了灯塔。\nThe harbour was quiet."


LOCAL_SCORE = 0.6


def local_scorer_answering(score: float) -> LocalEmotionScorer:
    """The real local scorer, with transformers' pipeline — its outside edge — answering `score` for every label."""

    def classify(
        sequences: list[str], *, candidate_labels: list[str], multi_label: bool
    ) -> "list[ZeroShotResult]":
        return [
            {
                "sequence": text,
                "labels": candidate_labels,
                "scores": [score] * len(candidate_labels),
            }
            for text in sequences
        ]

    return LocalEmotionScorer(classifier=classify)


@pytest.fixture
def services() -> FakeServices:
    return FakeServices()


@pytest.fixture(params=list(EmotionBackend))
def emotion_backend(request: pytest.FixtureRequest) -> EmotionBackend:
    """Every endpoint test runs once with the model on this machine and once behind the Hugging Face API."""
    return request.param


@pytest.fixture
def fake_local_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        api_module,
        "get_local_emotion_scorer",
        lambda: local_scorer_answering(LOCAL_SCORE),
    )
    yield


@pytest.fixture
def outputs_dir(tmp_path: Path) -> Path:
    return tmp_path / "outputs"


@pytest.fixture
async def api(
    services: FakeServices,
    outputs_dir: Path,
    emotion_backend: EmotionBackend,
    fake_local_model: None,
) -> AsyncGenerator[httpx.AsyncClient]:
    """The app, called in process, with its outside edges replaced: the settings, the HTTP transport and the model."""

    async def fake_http_client() -> AsyncGenerator[httpx.AsyncClient]:
        async with services.client() as client:
            yield client

    app.dependency_overrides[get_settings] = lambda: Settings(
        emotion_backend=emotion_backend,
        hf_token=SecretStr("a-token"),
        outputs_dir=outputs_dir,
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


async def test_the_snapshot_records_where_the_emotion_model_ran(
    api: httpx.AsyncClient,
    services: FakeServices,
    outputs_dir: Path,
    emotion_backend: EmotionBackend,
) -> None:
    await api.post("/generate", json={"text": ENTRY})

    (metadata_name,) = [
        name for name in snapshot_names(outputs_dir) if name.endswith(".json")
    ]
    metadata = json.loads((outputs_dir / metadata_name).read_text("utf-8"))
    assert metadata["emotion_backend"] == emotion_backend.value
    expected_score = (
        LOCAL_SCORE if emotion_backend is EmotionBackend.LOCAL else HAPPY_SCORE
    )
    assert metadata["entry_emotions"] == {
        Emotion.HAPPY.value: pytest.approx(expected_score)
    }
    called_hugging_face = bool(services.requests_to(HUGGING_FACE_HOST))
    assert called_hugging_face is (emotion_backend is EmotionBackend.HUGGING_FACE)


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


@pytest.mark.parametrize("emotion_backend", [EmotionBackend.HUGGING_FACE])
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
def no_settings_in_reach(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Neither the developer's `.env` and variables nor an earlier test's cached settings."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("EMOTION_BACKEND", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("no_settings_in_reach")
async def test_the_local_model_is_loaded_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loads: list[EmotionScorer] = []

    def load_once() -> EmotionScorer:
        scorer = local_scorer_answering(HAPPY_SCORE)
        loads.append(scorer)
        return scorer

    monkeypatch.setattr(api_module, "get_local_emotion_scorer", load_once)

    async with lifespan(app):
        assert len(loads) == 1


@pytest.mark.usefixtures("no_settings_in_reach")
async def test_the_hugging_face_backend_starts_with_a_token_and_loads_no_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMOTION_BACKEND", "hugging_face")
    monkeypatch.setenv("HF_TOKEN", "a-token")
    monkeypatch.setattr(api_module, "get_local_emotion_scorer", fail_if_called)

    async with lifespan(app):
        assert get_settings().require_hf_token() == "a-token"


@pytest.mark.usefixtures("no_settings_in_reach")
async def test_the_hugging_face_backend_refuses_to_start_without_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMOTION_BACKEND", "hugging_face")

    with pytest.raises(ValidationError, match="needs HF_TOKEN"):
        async with lifespan(app):
            pass


def fail_if_called() -> EmotionScorer:
    raise AssertionError("The local model was loaded")
