from urllib.parse import unquote

import httpx
import pytest

from emotion_painting.emotion import EmotionBackend, HuggingFaceEmotionScorer
from emotion_painting.external_service import ExternalServiceError
from emotion_painting.image_generation import ImageChannel
from emotion_painting.pipeline import EmptyEntryError, paint_entry
from emotion_painting.vocabulary import Emotion
from fake_services import (
    HAPPY_SCORE,
    HUGGING_FACE_HOST,
    PAINTING_BYTES,
    POLLINATIONS_HOST,
    FakeServices,
)

pytestmark = pytest.mark.anyio

ENTRY = "早上去了灯塔。\nThe harbour was quiet, the harbour was mine."


async def test_an_entry_becomes_a_painting_with_everything_that_led_to_it() -> None:
    services = FakeServices()
    async with services.client() as client:
        painting = await paint_entry(
            ENTRY, HuggingFaceEmotionScorer(client, "a-token"), client
        )

    assert painting.text == ENTRY
    assert painting.emotion_backend is EmotionBackend.HUGGING_FACE
    assert [emotions.chunk.text for emotions in painting.chunk_emotions] == ENTRY.split(
        "\n"
    )
    assert painting.entry_emotions == {Emotion.HAPPY: pytest.approx(HAPPY_SCORE)}
    assert painting.dominant_emotion is Emotion.HAPPY
    assert {"灯塔", "harbour"} <= set(painting.imagery_words)
    assert painting.prompt.startswith("A painting of ")
    assert painting.prompt.endswith(", in a joyful mood.")
    assert painting.image.content == PAINTING_BYTES
    assert painting.image.channel is ImageChannel.POLLINATIONS


async def test_each_chunk_is_scored_and_the_prompt_is_what_gets_painted() -> None:
    services = FakeServices()
    async with services.client() as client:
        painting = await paint_entry(
            ENTRY, HuggingFaceEmotionScorer(client, "a-token"), client
        )

    assert len(services.requests_to(HUGGING_FACE_HOST)) == 2
    (image_request,) = services.requests_to(POLLINATIONS_HOST)
    assert unquote(image_request.url.path) == f"/prompt/{painting.prompt}"


async def test_an_entry_with_nothing_to_paint_calls_no_service() -> None:
    services = FakeServices()
    async with services.client() as client:
        with pytest.raises(EmptyEntryError):
            await paint_entry(
                "  \nhttps://example.com/only-a-link\n",
                HuggingFaceEmotionScorer(client, "a-token"),
                client,
            )

    assert services.requests == []


async def test_a_failed_emotion_step_stops_before_the_image() -> None:
    services = FakeServices(
        hugging_face_response=httpx.Response(
            402, json={"error": "Purchase pre-paid credits"}
        )
    )
    async with services.client() as client:
        with pytest.raises(ExternalServiceError, match="Hugging Face answered 402"):
            await paint_entry(
                ENTRY, HuggingFaceEmotionScorer(client, "a-token"), client
            )

    assert services.requests_to(POLLINATIONS_HOST) == []
