import httpx
import pytest

from emotion_painting.external_service import ExternalServiceError
from emotion_painting.image_generation import (
    GeneratedImage,
    ImageChannel,
    generate_image,
)

pytestmark = pytest.mark.anyio

JPEG_BYTES = b"\xff\xd8\xff\xe0 not really a painting"


async def test_the_prompt_goes_in_the_path_and_the_image_comes_back() -> None:
    requests: list[httpx.Request] = []

    def paint(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, content=JPEG_BYTES, headers={"content-type": "image/jpeg"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(paint)) as client:
        image = await generate_image(
            "A painting of 公园, a/b?, in a joyful mood.", client
        )

    assert image == GeneratedImage(
        content=JPEG_BYTES, media_type="image/jpeg", channel=ImageChannel.POLLINATIONS
    )
    (request,) = requests
    assert request.method == "GET"
    assert request.url.host == "image.pollinations.ai"
    assert request.url.raw_path.split(b"?")[0] == (
        b"/prompt/A%20painting%20of%20%E5%85%AC%E5%9B%AD%2C%20a%2Fb%3F%2C%20in%20a%20joyful%20mood."
    )
    assert dict(request.url.params) == {
        "model": "flux",
        "private": "true",
    }


async def test_the_media_type_drops_its_parameters() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=JPEG_BYTES,
            headers={"content-type": "image/png; charset=binary"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        image = await generate_image("a prompt", client)

    assert image.media_type == "image/png"


async def test_an_answer_that_is_not_an_image_is_an_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"queued": True})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(
            ExternalServiceError,
            match="Pollinations answered with application/json instead of an image",
        ):
            await generate_image("a prompt", client)


async def test_a_failed_call_fails_the_step() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(502, text="Bad Gateway")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(
            ExternalServiceError, match="Pollinations answered 502: Bad Gateway"
        ):
            await generate_image("a prompt", client)
