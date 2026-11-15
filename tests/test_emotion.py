import json

import httpx
import pytest

from emotion_painting.chunking import Chunk
from emotion_painting.constants import EMOTION_MODEL_URL
from emotion_painting.emotion import (
    ChunkEmotions,
    HuggingFaceEmotionScorer,
    combine_chunk_emotions,
    find_dominant_emotion,
    parse_scores,
)
from emotion_painting.external_service import ExternalServiceError
from emotion_painting.vocabulary import Emotion

pytestmark = pytest.mark.anyio

SUNNY = Chunk(index=0, text="今天阳光很好！")
RAINY = Chunk(index=1, text="The rain never stopped...")
SCORE_BY_TEXT = {SUNNY.text: 0.9, RAINY.text: 0.1}


def answer_with_scores(request: httpx.Request) -> httpx.Response:
    """Hugging Face's zero-shot answer: a label and a score per candidate label."""
    payload = json.loads(request.content)
    return httpx.Response(
        200,
        json=[
            {"label": label, "score": SCORE_BY_TEXT[payload["inputs"]]}
            for label in payload["parameters"]["candidate_labels"]
        ],
    )


async def test_each_chunk_is_scored_in_order() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(answer_with_scores)
    ) as client:
        chunk_emotions = await HuggingFaceEmotionScorer(client, "a-token").score_chunks(
            [SUNNY, RAINY]
        )

    assert chunk_emotions == [
        ChunkEmotions(chunk=SUNNY, scores={Emotion.HAPPY: 0.9}),
        ChunkEmotions(chunk=RAINY, scores={Emotion.HAPPY: 0.1}),
    ]


async def test_the_request_carries_the_token_the_whole_vocabulary_and_multi_label() -> (
    None
):
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return answer_with_scores(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(record)) as client:
        await HuggingFaceEmotionScorer(client, "a-token").score_chunks([SUNNY])

    (request,) = requests
    assert request.method == "POST"
    assert str(request.url) == EMOTION_MODEL_URL
    assert request.headers["authorization"] == "Bearer a-token"
    assert request.headers["x-wait-for-model"] == "true"
    assert json.loads(request.content) == {
        "inputs": SUNNY.text,
        "parameters": {
            "candidate_labels": [emotion.value for emotion in Emotion],
            "multi_label": True,
        },
    }


async def test_a_refused_call_fails_the_step_with_what_hugging_face_said() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(402, json={"error": "Purchase pre-paid credits"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(
            ExternalServiceError, match=r"Hugging Face answered 402.*credits"
        ):
            await HuggingFaceEmotionScorer(client, "a-token").score_chunks([SUNNY])


def test_an_answer_in_another_shape_is_an_error() -> None:
    with pytest.raises(ExternalServiceError, match="unexpected shape"):
        parse_scores(b'{"labels": ["\xe5\xbc\x80\xe5\xbf\x83"], "scores": [0.9]}')


def test_an_answer_missing_an_emotion_is_an_error() -> None:
    with pytest.raises(
        ExternalServiceError, match="The emotion model left out a score for: 开心"
    ):
        parse_scores(b"[]")


def test_the_entry_distribution_weights_each_chunk_by_its_length() -> None:
    short_chunk = Chunk(index=0, text="x" * 10)
    long_chunk = Chunk(index=1, text="x" * 30)

    entry_emotions = combine_chunk_emotions(
        [
            ChunkEmotions(chunk=short_chunk, scores={Emotion.HAPPY: 1.0}),
            ChunkEmotions(chunk=long_chunk, scores={Emotion.HAPPY: 0.2}),
        ]
    )

    assert entry_emotions == {Emotion.HAPPY: pytest.approx(0.4)}


def test_the_dominant_emotion_has_the_highest_score() -> None:
    assert find_dominant_emotion({Emotion.HAPPY: 0.3}) is Emotion.HAPPY
