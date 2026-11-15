"""The whole endpoint against the real model and services. Not part of the default run or CI:

    uv run pytest -m live

The local run downloads the emotion model on first use (about 560 MB) and needs the
`local-model` extra. The Hugging Face run needs HF_TOKEN with inference credit, and spends
a little of it; without a token it is skipped.
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest

from emotion_painting.api import app, get_settings
from emotion_painting.config import load_settings
from emotion_painting.constants import BASE_VERSION, IMAGE_MEDIA_TYPE_PREFIX
from emotion_painting.emotion import EmotionBackend
from emotion_painting.snapshot import SnapshotMetadata
from emotion_painting.vocabulary import Emotion

pytestmark = [pytest.mark.live, pytest.mark.anyio]

ENTRY = (
    "今天终于放晴了！早上去公园跑步，湖边的柳树都发芽了。\n"
    "In the evening I walked down to the harbour and watched the lighthouse come on."
)


@pytest.fixture(params=list(EmotionBackend))
async def api(
    request: pytest.FixtureRequest, tmp_path: Path
) -> AsyncGenerator[httpx.AsyncClient]:
    """The app with its real settings, model and HTTP calls; only the backend and the snapshots' directory are set."""
    settings = load_settings().model_copy(
        update={"emotion_backend": request.param, "outputs_dir": tmp_path}
    )
    if request.param is EmotionBackend.HUGGING_FACE and settings.hf_token is None:
        pytest.skip("HF_TOKEN is not set")
    app.dependency_overrides[get_settings] = lambda: settings
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://emotion-painting.test"
    ) as api_client:
        yield api_client
    app.dependency_overrides.clear()


async def test_a_real_entry_comes_back_as_a_painting_with_its_snapshot(
    api: httpx.AsyncClient, tmp_path: Path
) -> None:
    response = await api.post("/generate", json={"text": ENTRY}, timeout=None)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(IMAGE_MEDIA_TYPE_PREFIX)
    (metadata_path,) = tmp_path.glob(f"v{BASE_VERSION}_*_meta.json")
    metadata = SnapshotMetadata.model_validate_json(metadata_path.read_bytes())
    assert (tmp_path / metadata.image_file).read_bytes() == response.content
    assert [chunk.text for chunk in metadata.chunks] == ENTRY.split("\n")
    assert all(0 <= chunk.emotions[Emotion.HAPPY] <= 1 for chunk in metadata.chunks)
    assert metadata.imagery_words
