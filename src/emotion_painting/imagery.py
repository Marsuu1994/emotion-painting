"""Step 2, track B — imagery words: rules and statistics, no model.

The one module that imports jieba (AGENTS.md › Types).
"""

import logging
from collections import Counter
from collections.abc import Iterator, Sequence

import jieba
import jieba.analyse
import jieba.posseg

from emotion_painting.chunking import Chunk
from emotion_painting.constants import (
    CHINESE_IMAGERY_FLAG_PREFIXES,
    CHINESE_OR_ENGLISH_RUN_REGEX,
    ENGLISH_WORD_MIN_CHARS,
    IMAGERY_WORD_LIMIT,
    TYPOGRAPHIC_APOSTROPHE,
)
from emotion_painting.english_stopwords import ENGLISH_STOPWORDS

# jieba reports loading its dictionary at DEBUG, on a logger it sets to DEBUG itself.
jieba.setLogLevel(logging.INFO)


def extract_imagery_words(chunks: Sequence[Chunk]) -> list[str]:
    """The entry's top imagery words, best first: scored by how often a word occurs times how rare it is."""
    occurrences = Counter(
        word for chunk in chunks for word in find_candidate_words(chunk.text)
    )
    ranked_words = sorted(
        occurrences,
        key=lambda word: occurrences[word] * inverse_document_frequency(word),
        reverse=True,
    )
    return ranked_words[:IMAGERY_WORD_LIMIT]


def find_candidate_words(text: str) -> Iterator[str]:
    """The words that can be imagery, in the order they occur, routed by language."""
    for run in CHINESE_OR_ENGLISH_RUN_REGEX.finditer(text):
        chinese_run: str | None = run.group("chinese")
        if chinese_run is None:
            yield from keep_english_candidate(run.group("english"))
        else:
            yield from find_chinese_candidates(chinese_run)


def find_chinese_candidates(chinese_run: str) -> Iterator[str]:
    """Nouns, place words and time words, by jieba's part-of-speech tagging."""
    for tagged_word in jieba.posseg.cut(chinese_run):
        if tagged_word.flag.startswith(CHINESE_IMAGERY_FLAG_PREFIXES):
            yield tagged_word.word


def keep_english_candidate(english_word: str) -> Iterator[str]:
    """The word in lower case, unless it is a stopword or too short to mean much."""
    word = english_word.lower().replace(TYPOGRAPHIC_APOSTROPHE, "'")
    if len(word) >= ENGLISH_WORD_MIN_CHARS and word not in ENGLISH_STOPWORDS:
        yield word


def inverse_document_frequency(word: str) -> float:
    """How rare the word is, from the table bundled with jieba.

    A word the table doesn't hold — every English word — takes the table's median.
    """
    table = jieba.analyse.default_tfidf
    return table.idf_freq.get(word, table.median_idf)
