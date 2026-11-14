from emotion_painting.prompt import build_prompt
from emotion_painting.vocabulary import Emotion


def test_prompt_names_the_imagery_and_the_emotion() -> None:
    prompt = build_prompt(["公园", "harbour", "猫"], Emotion.HAPPY)

    assert prompt == "A painting of 公园, harbour, 猫, in a joyful mood."


def test_prompt_without_imagery_keeps_the_emotion() -> None:
    prompt = build_prompt([], Emotion.HAPPY)

    assert prompt == "A painting in a joyful mood."
