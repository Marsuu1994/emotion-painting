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

# Step 2, track A — emotion
HUGGING_FACE = "Hugging Face"
EMOTION_MODEL_URL = "https://router.huggingface.co/hf-inference/models/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
# Asks Hugging Face to hold the request while a cold model loads instead of answering 503.
HUGGING_FACE_WAIT_FOR_MODEL_HEADER = "x-wait-for-model"

# Step 4 — image
POLLINATIONS = "Pollinations"
POLLINATIONS_URL_TEMPLATE = "https://image.pollinations.ai/prompt/{prompt}"
# private: the image stays out of Pollinations' public feed — the prompt comes from a diary.
POLLINATIONS_QUERY = {"model": "flux", "private": "true"}
IMAGE_MEDIA_TYPE_PREFIX = "image/"

# Outside services
# A cold model or a queued image can take a while; past this the step fails.
EXTERNAL_SERVICE_TIMEOUT_SECONDS = 120.0
# How much of a failed response's body goes into the error message.
ERROR_BODY_MAX_CHARS = 300

# The endpoint
# The Dump feature's own limit on an entry.
ENTRY_MAX_CHARS = 10_000
# The experiment version stamped on a snapshot when the request names none.
# Bump it in the change that alters a model, a parameter or the prompt template.
BASE_VERSION = "0.1"
# A version goes into file names: letters, digits, dots, dashes and underscores only.
VERSION_PATTERN = r"^[0-9A-Za-z][0-9A-Za-z._-]*$"
VERSION_MAX_CHARS = 32
NOTHING_TO_PAINT_DETAIL = (
    "The entry has no text left to paint once links and blank lines are removed."
)

# Snapshots
SNAPSHOT_NAME_TEMPLATE = "v{version}_{timestamp}"
# Local time, to the millisecond: two calls never share a name.
SNAPSHOT_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S-%f"
SNAPSHOT_TIMESTAMP_CHARS = len("20261114-104512-123")
SNAPSHOT_METADATA_SUFFIX = "_meta.json"
# The extension of an image whose media type the standard library doesn't know.
SNAPSHOT_DEFAULT_IMAGE_EXTENSION = ".jpg"
