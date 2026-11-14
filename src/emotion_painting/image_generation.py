"""Step 4 — the painting, from a free image service."""

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote

import httpx

from emotion_painting.constants import (
    IMAGE_MEDIA_TYPE_PREFIX,
    POLLINATIONS,
    POLLINATIONS_QUERY,
    POLLINATIONS_URL_TEMPLATE,
)
from emotion_painting.external_service import (
    ExternalServiceError,
    send_to_external_service,
)


class ImageChannel(StrEnum):
    """The service that produced an image. A fallback channel is pending (design/overall-design.md)."""

    POLLINATIONS = "pollinations"


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    media_type: str
    channel: ImageChannel


async def generate_image(prompt: str, client: httpx.AsyncClient) -> GeneratedImage:
    """The prompt painted by Pollinations: a GET with the prompt in the path answers with the image."""
    request = client.build_request(
        "GET",
        POLLINATIONS_URL_TEMPLATE.format(prompt=quote(prompt, safe="")),
        params=POLLINATIONS_QUERY,
    )
    response = await send_to_external_service(client, POLLINATIONS, request)
    media_type = response.headers.get("content-type", "").split(";")[0].strip()
    if not media_type.startswith(IMAGE_MEDIA_TYPE_PREFIX):
        raise ExternalServiceError(
            f"{POLLINATIONS} answered with {media_type or 'no content type'} instead of an image"
        )
    return GeneratedImage(
        content=response.content,
        media_type=media_type,
        channel=ImageChannel.POLLINATIONS,
    )
