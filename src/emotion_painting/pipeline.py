"""The four steps, run in memory for one entry."""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

from emotion_painting.chunking import split_into_chunks
from emotion_painting.emotion import (
    ChunkEmotions,
    combine_chunk_emotions,
    find_dominant_emotion,
    score_chunks,
)
from emotion_painting.image_generation import GeneratedImage, generate_image
from emotion_painting.imagery import extract_imagery_words
from emotion_painting.prompt import build_prompt
from emotion_painting.vocabulary import Emotion


@dataclass(frozen=True)
class Painting:
    """One run's result: the image, and everything that led to it."""

    text: str
    chunk_emotions: Sequence[ChunkEmotions]
    entry_emotions: Mapping[Emotion, float]
    dominant_emotion: Emotion
    imagery_words: Sequence[str]
    prompt: str
    image: GeneratedImage


class EmptyEntryError(Exception):
    """The entry has nothing to paint: no text is left once it is cleaned."""


async def paint_entry(text: str, client: httpx.AsyncClient, hf_token: str) -> Painting:
    """The entry's painting: chunk it, read its emotion and imagery side by side, build the prompt, paint."""
    chunks = split_into_chunks(text)
    if not chunks:
        raise EmptyEntryError
    chunk_emotions, imagery_words = await asyncio.gather(
        score_chunks(chunks, client, hf_token),
        # Rules only, but jieba's first call loads its dictionary: off the event loop.
        asyncio.to_thread(extract_imagery_words, chunks),
    )
    entry_emotions = combine_chunk_emotions(chunk_emotions)
    dominant_emotion = find_dominant_emotion(entry_emotions)
    prompt = build_prompt(imagery_words, dominant_emotion)
    image = await generate_image(prompt, client)
    return Painting(
        text=text,
        chunk_emotions=chunk_emotions,
        entry_emotions=entry_emotions,
        dominant_emotion=dominant_emotion,
        imagery_words=imagery_words,
        prompt=prompt,
        image=image,
    )
