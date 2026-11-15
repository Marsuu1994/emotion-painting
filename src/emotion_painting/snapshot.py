"""The record a run leaves in the outputs directory: the image, and the metadata to compare versions by."""

import mimetypes
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from emotion_painting.constants import (
    SNAPSHOT_DEFAULT_IMAGE_EXTENSION,
    SNAPSHOT_METADATA_SUFFIX,
    SNAPSHOT_NAME_TEMPLATE,
    SNAPSHOT_TIMESTAMP_CHARS,
    SNAPSHOT_TIMESTAMP_FORMAT,
)
from emotion_painting.emotion import EmotionBackend
from emotion_painting.image_generation import ImageChannel
from emotion_painting.pipeline import Painting
from emotion_painting.vocabulary import Emotion


class ChunkMetadata(BaseModel):
    index: int
    char_count: int
    text: str
    emotions: dict[Emotion, float]


class SnapshotMetadata(BaseModel):
    """The shape of `v{version}_{timestamp}_meta.json`."""

    version: str
    created_at: datetime
    text: str
    emotion_backend: EmotionBackend
    chunks: list[ChunkMetadata]
    entry_emotions: dict[Emotion, float]
    dominant_emotion: Emotion
    imagery_words: list[str]
    prompt: str
    image_channel: ImageChannel
    image_file: str


def save_snapshot(
    painting: Painting, version: str, created_at: datetime, outputs_dir: Path
) -> Path:
    """Writes the image and its metadata side by side; the image's path comes back."""
    name = SNAPSHOT_NAME_TEMPLATE.format(
        version=version,
        timestamp=created_at.strftime(SNAPSHOT_TIMESTAMP_FORMAT)[
            :SNAPSHOT_TIMESTAMP_CHARS
        ],
    )
    image_extension = (
        mimetypes.guess_extension(painting.image.media_type)
        or SNAPSHOT_DEFAULT_IMAGE_EXTENSION
    )
    image_path = outputs_dir / f"{name}{image_extension}"
    metadata = SnapshotMetadata(
        version=version,
        created_at=created_at,
        text=painting.text,
        emotion_backend=painting.emotion_backend,
        chunks=[
            ChunkMetadata(
                index=emotions.chunk.index,
                char_count=emotions.chunk.char_count,
                text=emotions.chunk.text,
                emotions=dict(emotions.scores),
            )
            for emotions in painting.chunk_emotions
        ],
        entry_emotions=dict(painting.entry_emotions),
        dominant_emotion=painting.dominant_emotion,
        imagery_words=list(painting.imagery_words),
        prompt=painting.prompt,
        image_channel=painting.image.channel,
        image_file=image_path.name,
    )
    outputs_dir.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(painting.image.content)
    (outputs_dir / f"{name}{SNAPSHOT_METADATA_SUFFIX}").write_text(
        metadata.model_dump_json(indent=2), encoding="utf-8"
    )
    return image_path
