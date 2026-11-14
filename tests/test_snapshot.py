import json
from datetime import UTC, datetime
from pathlib import Path

from emotion_painting.chunking import Chunk
from emotion_painting.emotion import ChunkEmotions
from emotion_painting.image_generation import GeneratedImage, ImageChannel
from emotion_painting.pipeline import Painting
from emotion_painting.snapshot import save_snapshot
from emotion_painting.vocabulary import Emotion

CREATED_AT = datetime(2026, 11, 14, 10, 45, 12, 123456, tzinfo=UTC)


def painting_with(media_type: str = "image/jpeg") -> Painting:
    return Painting(
        text="今天去了灯塔。\nQuiet harbour.",
        chunk_emotions=[
            ChunkEmotions(
                chunk=Chunk(index=0, text="今天去了灯塔。"), scores={Emotion.HAPPY: 0.9}
            ),
            ChunkEmotions(
                chunk=Chunk(index=1, text="Quiet harbour."), scores={Emotion.HAPPY: 0.2}
            ),
        ],
        entry_emotions={Emotion.HAPPY: 0.43},
        dominant_emotion=Emotion.HAPPY,
        imagery_words=["灯塔", "harbour"],
        prompt="A painting of 灯塔, harbour, in a joyful mood.",
        image=GeneratedImage(
            content=b"image bytes",
            media_type=media_type,
            channel=ImageChannel.POLLINATIONS,
        ),
    )


def test_the_image_and_its_metadata_are_named_by_version_and_time(
    tmp_path: Path,
) -> None:
    image_path = save_snapshot(painting_with(), "0.1", CREATED_AT, tmp_path)

    assert image_path == tmp_path / "v0.1_20261114-104512-123.jpg"
    assert image_path.read_bytes() == b"image bytes"
    assert (tmp_path / "v0.1_20261114-104512-123_meta.json").exists()
    assert len(list(tmp_path.iterdir())) == 2


def test_the_metadata_holds_what_led_to_the_image(tmp_path: Path) -> None:
    save_snapshot(painting_with(), "0.1", CREATED_AT, tmp_path)

    metadata = json.loads(
        (tmp_path / "v0.1_20261114-104512-123_meta.json").read_text("utf-8")
    )
    assert metadata == {
        "version": "0.1",
        "created_at": "2026-11-14T10:45:12.123456Z",
        "text": "今天去了灯塔。\nQuiet harbour.",
        "chunks": [
            {
                "index": 0,
                "char_count": 7,
                "text": "今天去了灯塔。",
                "emotions": {"开心": 0.9},
            },
            {
                "index": 1,
                "char_count": 14,
                "text": "Quiet harbour.",
                "emotions": {"开心": 0.2},
            },
        ],
        "entry_emotions": {"开心": 0.43},
        "dominant_emotion": "开心",
        "imagery_words": ["灯塔", "harbour"],
        "prompt": "A painting of 灯塔, harbour, in a joyful mood.",
        "image_channel": "pollinations",
        "image_file": "v0.1_20261114-104512-123.jpg",
    }


def test_the_metadata_keeps_chinese_readable(tmp_path: Path) -> None:
    save_snapshot(painting_with(), "0.1", CREATED_AT, tmp_path)

    assert "灯塔" in (tmp_path / "v0.1_20261114-104512-123_meta.json").read_text(
        "utf-8"
    )


def test_the_image_extension_follows_its_media_type(tmp_path: Path) -> None:
    png_path = save_snapshot(painting_with("image/png"), "0.1", CREATED_AT, tmp_path)
    unknown_path = save_snapshot(
        painting_with("image/x-unheard-of"), "0.2", CREATED_AT, tmp_path
    )

    assert png_path.suffix == ".png"
    assert unknown_path.suffix == ".jpg"


def test_the_outputs_directory_is_created_when_missing(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "not" / "there" / "yet"

    image_path = save_snapshot(painting_with(), "0.1", CREATED_AT, outputs_dir)

    assert image_path.parent == outputs_dir
    assert image_path.exists()
