from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from emotion_painting.chunking import Chunk
from emotion_painting.emotion import ChunkEmotions, EmotionBackend
from emotion_painting.external_service import ExternalServiceError
from emotion_painting.local_emotion_model import LocalEmotionScorer
from emotion_painting.vocabulary import Emotion

if TYPE_CHECKING:
    from transformers import ZeroShotResult

pytestmark = pytest.mark.anyio

SUNNY = Chunk(index=0, text="今天阳光很好！")
RAINY = Chunk(index=1, text="The rain never stopped...")


@dataclass
class FakeZeroShotPipeline:
    """Answers like transformers' zero-shot pipeline: a batch of one comes back as the item itself."""

    score_by_text: dict[str, float]
    calls: list[tuple[list[str], list[str], bool]] = field(
        default_factory=list[tuple[list[str], list[str], bool]]
    )

    def __call__(
        self, sequences: list[str], *, candidate_labels: list[str], multi_label: bool
    ) -> "list[ZeroShotResult] | ZeroShotResult":
        self.calls.append((sequences, candidate_labels, multi_label))
        results: list[ZeroShotResult] = [
            {
                "sequence": text,
                "labels": candidate_labels,
                "scores": [self.score_by_text[text]] * len(candidate_labels),
            }
            for text in sequences
        ]
        return results if len(results) > 1 else results[0]


def scorer_answering(
    score_by_text: dict[str, float],
) -> tuple[LocalEmotionScorer, FakeZeroShotPipeline]:
    classifier = FakeZeroShotPipeline(score_by_text)
    return LocalEmotionScorer(classifier=classifier), classifier


async def test_every_chunk_is_scored_in_one_batch_in_order() -> None:
    scorer, classifier = scorer_answering({SUNNY.text: 0.9, RAINY.text: 0.1})

    chunk_emotions = await scorer.score_chunks([SUNNY, RAINY])

    assert chunk_emotions == [
        ChunkEmotions(chunk=SUNNY, scores={Emotion.HAPPY: 0.9}),
        ChunkEmotions(chunk=RAINY, scores={Emotion.HAPPY: 0.1}),
    ]
    assert classifier.calls == [
        ([SUNNY.text, RAINY.text], [emotion.value for emotion in Emotion], True)
    ]


async def test_a_single_chunk_answered_without_a_list_still_scores() -> None:
    scorer, _ = scorer_answering({SUNNY.text: 0.7})

    assert await scorer.score_chunks([SUNNY]) == [
        ChunkEmotions(chunk=SUNNY, scores={Emotion.HAPPY: 0.7})
    ]


def test_the_scorer_says_where_the_model_ran() -> None:
    scorer, _ = scorer_answering({})

    assert scorer.backend is EmotionBackend.LOCAL


async def test_an_answer_missing_an_emotion_is_an_error() -> None:
    def answer_without_labels(
        sequences: list[str], *, candidate_labels: list[str], multi_label: bool
    ) -> "ZeroShotResult":
        return {"sequence": sequences[0], "labels": [], "scores": []}

    scorer = LocalEmotionScorer(classifier=answer_without_labels)

    with pytest.raises(ExternalServiceError, match="left out a score for: 开心"):
        await scorer.score_chunks([SUNNY])
