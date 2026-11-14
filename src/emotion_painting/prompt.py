"""Step 3 — prompt build.

A placeholder template until the aesthetic mapping is designed (design/overall-design.md › Open Questions).
"""

from collections.abc import Sequence

from emotion_painting.constants import (
    IMAGERY_SEPARATOR,
    PROMPT_TEMPLATE,
    PROMPT_TEMPLATE_WITHOUT_IMAGERY,
)
from emotion_painting.vocabulary import EMOTION_PROMPT_WORD, Emotion


def build_prompt(imagery_words: Sequence[str], dominant_emotion: Emotion) -> str:
    """The image model's prompt: the imagery words as the subject, the dominant emotion as the mood."""
    emotion = EMOTION_PROMPT_WORD[dominant_emotion]
    if not imagery_words:
        return PROMPT_TEMPLATE_WITHOUT_IMAGERY.format(emotion=emotion)
    return PROMPT_TEMPLATE.format(
        imagery=IMAGERY_SEPARATOR.join(imagery_words), emotion=emotion
    )
