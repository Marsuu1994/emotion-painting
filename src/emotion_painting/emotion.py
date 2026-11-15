"""Step 2, track A — each chunk's emotion distribution, from a zero-shot model.

The model runs on this machine (`local_emotion_model.py`) or behind the Hugging Face API
(here); both score the same labels and answer the same shape.
"""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

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


class EmotionBackend(StrEnum):
    """Where the emotion model runs."""

    # On this machine: free, and the same pinned weights every run (Phase 1).
    LOCAL = "local"
    # Behind the Hugging Face API: needs HF_TOKEN and inference credit (Phase 2).
    HUGGING_FACE = "hugging_face"


class EmotionScorer(Protocol):
    """Wherever the model runs: every chunk's distribution, in the chunks' order."""

    @property
    def backend(self) -> EmotionBackend: ...

    async def score_chunks(self, chunks: Sequence[Chunk]) -> list[ChunkEmotions]: ...


class LabelScore(BaseModel):
    """One item of the model's answer."""

    label: Emotion
    score: float


LABEL_SCORES = TypeAdapter(list[LabelScore])


@dataclass(frozen=True)
class HuggingFaceEmotionScorer:
    """The model behind the Hugging Face API: one call per chunk, sent concurrently."""

    client: httpx.AsyncClient
    hf_token: str
    backend: EmotionBackend = EmotionBackend.HUGGING_FACE

    async def score_chunks(self, chunks: Sequence[Chunk]) -> list[ChunkEmotions]:
        return list(
            await asyncio.gather(*(self.score_chunk(chunk) for chunk in chunks))
        )

    async def score_chunk(self, chunk: Chunk) -> ChunkEmotions:
        request = self.client.build_request(
            "POST",
            EMOTION_MODEL_URL,
            headers={
                "Authorization": f"Bearer {self.hf_token}",
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
        response = await send_to_external_service(self.client, HUGGING_FACE, request)
        return ChunkEmotions(chunk=chunk, scores=parse_scores(response.content))


def parse_scores(response_body: bytes) -> dict[Emotion, float]:
    """The API's answer — a list of label and score — as a score for every emotion."""
    try:
        label_scores = LABEL_SCORES.validate_json(response_body)
    except ValidationError as error:
        raise ExternalServiceError(
            f"{HUGGING_FACE} answered in an unexpected shape: {error}"
        ) from error
    return scores_for_every_emotion(
        {label_score.label: label_score.score for label_score in label_scores}
    )


def scores_for_every_emotion(scores: Mapping[Emotion, float]) -> dict[Emotion, float]:
    """The scores, refused when one emotion of the vocabulary has none."""
    missing_emotions = set(Emotion) - set(scores)
    if missing_emotions:
        raise ExternalServiceError(
            f"The emotion model left out a score for: {', '.join(sorted(missing_emotions))}"
        )
    return dict(scores)


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
