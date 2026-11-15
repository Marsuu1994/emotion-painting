"""The emotion model run on this machine, on CPU: the same weights the Hugging Face API serves, pinned.

The one module that imports transformers (AGENTS.md › Types); it needs the `local-model` extra.
"""

import asyncio
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from emotion_painting.chunking import Chunk
from emotion_painting.constants import (
    EMOTION_MODEL_ID,
    EMOTION_MODEL_REVISION,
    LOCAL_DEVICE,
    LOCAL_MODEL_EXTRA_MISSING,
    ZERO_SHOT_TASK,
)
from emotion_painting.emotion import (
    ChunkEmotions,
    EmotionBackend,
    scores_for_every_emotion,
)
from emotion_painting.vocabulary import Emotion

try:
    from transformers import pipeline
except (
    ImportError
) as error:  # pragma: no cover — the extra is installed wherever the tests run
    raise ImportError(LOCAL_MODEL_EXTRA_MISSING) from error

if TYPE_CHECKING:
    # A type from the stub only (typings/transformers): the pipeline's answer, not a class it exports.
    from transformers import ZeroShotResult


class ZeroShotClassifier(Protocol):
    """What the scorer needs of transformers' zero-shot pipeline."""

    def __call__(
        self, sequences: list[str], *, candidate_labels: list[str], multi_label: bool
    ) -> "list[ZeroShotResult] | ZeroShotResult": ...


@dataclass
class LocalEmotionScorer:
    """Scores every chunk of an entry in one batch, off the event loop, one entry at a time."""

    classifier: ZeroShotClassifier
    # One batch at a time: the model already uses every core.
    lock: threading.Lock = field(default_factory=threading.Lock)
    backend: EmotionBackend = EmotionBackend.LOCAL

    async def score_chunks(self, chunks: Sequence[Chunk]) -> list[ChunkEmotions]:
        return await asyncio.to_thread(self.score_chunks_blocking, chunks)

    def score_chunks_blocking(self, chunks: Sequence[Chunk]) -> list[ChunkEmotions]:
        with self.lock:
            answer = self.classifier(
                [chunk.text for chunk in chunks],
                candidate_labels=[emotion.value for emotion in Emotion],
                multi_label=True,
            )
        # The pipeline answers a batch of one with the item itself, not a list.
        results: list[ZeroShotResult] = answer if isinstance(answer, list) else [answer]
        return [
            ChunkEmotions(
                chunk=chunk,
                scores=scores_for_every_emotion(
                    {
                        Emotion(label): score
                        for label, score in zip(
                            result["labels"], result["scores"], strict=True
                        )
                    }
                ),
            )
            for chunk, result in zip(chunks, results, strict=True)
        ]


def load_local_emotion_scorer() -> LocalEmotionScorer:
    """Loads the pinned model, downloading it on first use (about 560 MB, kept in Hugging Face's cache)."""
    classifier = pipeline(
        ZERO_SHOT_TASK,
        model=EMOTION_MODEL_ID,
        revision=EMOTION_MODEL_REVISION,
        device=LOCAL_DEVICE,
    )
    return LocalEmotionScorer(classifier=classifier)
