"""Step 1 — chunking and preprocessing: rules only, no model."""

from dataclasses import dataclass

from emotion_painting.constants import (
    CHUNK_MAX_CHARS,
    SENTENCE_TERMINATOR_RUN_REGEX,
    URL_REGEX,
)


@dataclass(frozen=True)
class Chunk:
    """One piece of an entry, small enough for the emotion model."""

    index: int
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


def split_into_chunks(text: str) -> list[Chunk]:
    """The entry as ordered chunks: one per paragraph, a long paragraph as groups of whole sentences.

    URLs and blank lines go; punctuation, letter case and emoji stay as written.
    """
    pieces = [
        piece
        for paragraph in URL_REGEX.sub("", text).splitlines()
        for piece in split_paragraph(paragraph.strip())
    ]
    return [Chunk(index=index, text=piece) for index, piece in enumerate(pieces)]


def split_paragraph(paragraph: str) -> list[str]:
    """The paragraph itself when it fits the chunk limit, else groups of whole sentences that do.

    A single sentence over the limit stays whole: a sentence is never cut.
    """
    if len(paragraph) <= CHUNK_MAX_CHARS:
        return [paragraph] if paragraph else []
    groups: list[str] = []
    current_group = ""
    for sentence in split_sentences(paragraph):
        if current_group and len(current_group) + len(sentence) > CHUNK_MAX_CHARS:
            groups.append(current_group.strip())
            current_group = ""
        current_group += sentence
    groups.append(current_group.strip())
    return [group for group in groups if group]


def split_sentences(paragraph: str) -> list[str]:
    """The paragraph cut after each run of sentence terminators; joined back, the pieces are the paragraph."""
    sentences: list[str] = []
    sentence_start = 0
    for terminator_run in SENTENCE_TERMINATOR_RUN_REGEX.finditer(paragraph):
        if is_dot_inside_a_token(
            paragraph, terminator_run.start(), terminator_run.end()
        ):
            continue
        sentences.append(paragraph[sentence_start : terminator_run.end()])
        sentence_start = terminator_run.end()
    if sentence_start < len(paragraph):
        sentences.append(paragraph[sentence_start:])
    return sentences


def is_dot_inside_a_token(paragraph: str, run_start: int, run_end: int) -> bool:
    """A lone `.` with a letter or digit right after it: a decimal (`3.5`) or a name (`v1.2`), not a sentence end."""
    if paragraph[run_start:run_end] != "." or run_end == len(paragraph):
        return False
    next_character = paragraph[run_end]
    return next_character.isascii() and next_character.isalnum()
