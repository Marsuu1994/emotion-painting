from emotion_painting.vocabulary import EMOTION_PROMPT_WORD, Emotion


def test_every_emotion_has_a_prompt_word() -> None:
    assert set(EMOTION_PROMPT_WORD) == set(Emotion)
