"""The emotion vocabulary: what the model scores, and how each emotion is worded in a prompt."""

from enum import StrEnum


class Emotion(StrEnum):
    """Each value is the label handed to the model, in the diary's own language."""

    HAPPY = "开心"


EMOTION_PROMPT_WORD: dict[Emotion, str] = {
    Emotion.HAPPY: "joyful",
}
