"""The pipeline's fixed values (AGENTS.md › No magic literals)."""

import re

# Step 1 — chunking
# About what the emotion model takes in one input (512 tokens).
CHUNK_MAX_CHARS = 350
SENTENCE_TERMINATORS = "。！？.!?"
SENTENCE_TERMINATOR_RUN_REGEX = re.compile(f"[{re.escape(SENTENCE_TERMINATORS)}]+")
# A URL ends at whitespace or at the first character outside printable ASCII,
# so the Chinese text right after a link survives.
URL_REGEX = re.compile(r"(?:https?://|www\.)[!-~]+")

# Step 2, track B — imagery
IMAGERY_WORD_LIMIT = 5
# One run of Chinese characters, or one English word with its apostrophes.
CHINESE_OR_ENGLISH_RUN_REGEX = re.compile(
    r"(?P<chinese>[一-鿿]+)|(?P<english>[A-Za-z]+(?:['’][A-Za-z]+)*)"
)
# jieba's part-of-speech flags: nouns (n, nr, ns, nt, nz…), place words (s), time words (t, tg).
CHINESE_IMAGERY_FLAG_PREFIXES = ("n", "s", "t")
ENGLISH_WORD_MIN_CHARS = 3
TYPOGRAPHIC_APOSTROPHE = "’"

# Step 3 — prompt
PROMPT_TEMPLATE = "A painting of {imagery}, in a {emotion} mood."
PROMPT_TEMPLATE_WITHOUT_IMAGERY = "A painting in a {emotion} mood."
IMAGERY_SEPARATOR = ", "
