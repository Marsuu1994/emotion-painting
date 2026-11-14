"""Step 2, track A — each chunk's emotion distribution, from a zero-shot model on Hugging Face."""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from emotion_painting.chunking import Chunk
from emotion_painting.constants import (
    EMOTION_MODEL_URL,
    HUGGING_FACE,
    HUGGING_FACE_WAIT_FOR_MODEL_HEADER,
)
from emotion_painting.external_service import (
    ExternalServiceError,
    send_to_external_service,
)
from emotion_painting.vocabulary import Emotion


@dataclass(frozen=True)
class ChunkEmotions:
    """One chunk's score for every emotion in the vocabulary, each scored on its own (multi-label)."""

    chunk: Chunk
    scores: Mapping[Emotion, float]


class LabelScore(BaseModel):
    """One item of the model's answer."""

    label: Emotion
    score: float


LABEL_SCORES = TypeAdapter(list[LabelScore])


async def score_chunks(
    chunks: Sequence[Chunk], client: httpx.AsyncClient, hf_token: str
) -> list[ChunkEmotions]:
    """Every chunk's emotion distribution, in the chunks' order: one call per chunk, sent concurrently."""
    return list(
        await asyncio.gather(
            *(score_chunk(chunk, client, hf_token) for chunk in chunks)
        )
    )


async def score_chunk(
    chunk: Chunk, client: httpx.AsyncClient, hf_token: str
) -> ChunkEmotions:
    request = client.build_request(
        "POST",
        EMOTION_MODEL_URL,
        headers={
            "Authorization": f"Bearer {hf_token}",
            HUGGING_FACE_WAIT_FOR_MODEL_HEADER: "true",
        },
        json={
            "inputs": chunk.text,
            "parameters": {
                "candidate_labels": [emotion.value for emotion in Emotion],
                "multi_label": True,
            },
        },
    )
    response = await send_to_external_service(client, HUGGING_FACE, request)
    return ChunkEmotions(chunk=chunk, scores=parse_scores(response.content))


def parse_scores(response_body: bytes) -> dict[Emotion, float]:
    """The model's answer — a list of label and score — as a score for every emotion."""
    try:
        label_scores = LABEL_SCORES.validate_json(response_body)
    except ValidationError as error:
        raise ExternalServiceError(
            f"{HUGGING_FACE} answered in an unexpected shape: {error}"
        ) from error
    scores = {label_score.label: label_score.score for label_score in label_scores}
    missing_emotions = set(Emotion) - set(scores)
    if missing_emotions:
        raise ExternalServiceError(
            f"{HUGGING_FACE} left out a score for: {', '.join(sorted(missing_emotions))}"
        )
    return scores


def combine_chunk_emotions(
    chunk_emotions: Sequence[ChunkEmotions],
) -> dict[Emotion, float]:
    """The entry's distribution: the chunks' scores averaged, each weighted by its chunk's length.

    Takes at least one chunk; a chunk is never empty.
    """
    total_chars = sum(emotions.chunk.char_count for emotions in chunk_emotions)
    return {
        emotion: sum(
            emotions.scores[emotion] * emotions.chunk.char_count
            for emotions in chunk_emotions
        )
        / total_chars
        for emotion in Emotion
    }


def find_dominant_emotion(entry_emotions: Mapping[Emotion, float]) -> Emotion:
    return max(Emotion, key=lambda emotion: entry_emotions[emotion])
