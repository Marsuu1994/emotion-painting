"""The local POC's one endpoint: an entry's text in, its painting out."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from http import HTTPStatus
from typing import Annotated, assert_never

import httpx
from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from emotion_painting.config import Settings, load_settings
from emotion_painting.constants import (
    BASE_VERSION,
    ENTRY_MAX_CHARS,
    EXTERNAL_SERVICE_TIMEOUT_SECONDS,
    NOTHING_TO_PAINT_DETAIL,
    VERSION_MAX_CHARS,
    VERSION_PATTERN,
)
from emotion_painting.emotion import (
    EmotionBackend,
    EmotionScorer,
    HuggingFaceEmotionScorer,
)
from emotion_painting.external_service import ExternalServiceError
from emotion_painting.pipeline import EmptyEntryError, paint_entry
from emotion_painting.snapshot import save_snapshot


class GenerateRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=ENTRY_MAX_CHARS,
        description="The diary entry, as plain text.",
    )
    version: str = Field(
        default=BASE_VERSION,
        pattern=VERSION_PATTERN,
        max_length=VERSION_MAX_CHARS,
        description="The experiment version stamped on this run's snapshot.",
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=EXTERNAL_SERVICE_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        yield client


@lru_cache
def get_local_emotion_scorer() -> EmotionScorer:
    """The model on this machine, loaded once. Imported here: it needs the `local-model` extra."""
    from emotion_painting.local_emotion_model import load_local_emotion_scorer

    return load_local_emotion_scorer()


def get_emotion_scorer(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> EmotionScorer:
    match settings.emotion_backend:
        case EmotionBackend.LOCAL:
            return get_local_emotion_scorer()
        case EmotionBackend.HUGGING_FACE:
            return HuggingFaceEmotionScorer(
                client=client, hf_token=settings.require_hf_token()
            )
        case _:
            assert_never(settings.emotion_backend)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Bad settings, a missing extra or a model that won't load stop the service at startup,
    # not at the first request — which would otherwise also pay for loading the model.
    settings = get_settings()
    if settings.emotion_backend is EmotionBackend.LOCAL:
        await asyncio.to_thread(get_local_emotion_scorer)
    yield


app = FastAPI(title="Emotion Painting", lifespan=lifespan)


@app.post(
    "/generate",
    response_class=Response,
    responses={
        HTTPStatus.OK: {
            "description": "The painting. The same call saves it, with its metadata, to the outputs directory.",
            "content": {"image/jpeg": {}, "image/png": {}},
        },
        HTTPStatus.BAD_GATEWAY: {
            "description": "An outside service failed a step; the detail says which, and what it answered."
        },
    },
)
async def generate(
    request: GenerateRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    emotion_scorer: Annotated[EmotionScorer, Depends(get_emotion_scorer)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> Response:
    """Paints a diary entry: chunking, emotion and imagery, a prompt, then the image."""
    try:
        painting = await paint_entry(request.text, emotion_scorer, client)
    except EmptyEntryError as error:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY, detail=NOTHING_TO_PAINT_DETAIL
        ) from error
    except ExternalServiceError as error:
        raise HTTPException(HTTPStatus.BAD_GATEWAY, detail=str(error)) from error
    save_snapshot(
        painting, request.version, datetime.now().astimezone(), settings.outputs_dir
    )
    return Response(
        content=painting.image.content, media_type=painting.image.media_type
    )
