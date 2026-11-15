# Generate Flows

Flows for the local POC's one endpoint, `POST /generate`: a diary entry's text in, its painting out.

> Design: `design/overall-design.md` — the pipeline's four steps, Phase 1's boundary, and what is still open.

---

## Generate Painting Flow

### Trigger / Entry Point

A client — Swagger UI at `/docs`, or any HTTP client — posts JSON to `POST /generate`: the entry's `text`, and optionally the experiment `version` this run belongs to.

### Steps

1. Validate the request: `text` is 1 to 10,000 characters; `version`, when given, is at most 32 letters, digits, dots, dashes and underscores. A request that fails is answered `422` and nothing else happens.
2. Split the text into chunks: links and blank lines go, each paragraph is a chunk, and a paragraph over 350 characters becomes groups of whole sentences. An entry with no chunks left is answered `422`.
3. Read the chunks two ways at once:
   - **Emotion**: every chunk is scored against the whole emotion vocabulary by the zero-shot model, each label on its own — on this machine, all chunks in one batch, or behind the Hugging Face API, one call per chunk (`EMOTION_BACKEND`).
   - **Imagery**: the entry's top 5 imagery words are picked by rules — Chinese nouns, place words and time words; English words that aren't stopwords.
4. Combine the chunks' emotion scores into the entry's distribution — the mean weighted by chunk length — and take its highest score as the dominant emotion.
5. Build the prompt from the imagery words and the dominant emotion.
6. Ask Pollinations to paint the prompt.
7. Save the run's snapshot to the outputs directory: the image as `v{version}_{timestamp}.jpg`, and `v{version}_{timestamp}_meta.json` beside it.
8. Answer `200` with the image itself as the response body.

### Rules

- **Nothing is cut or rewritten in a chunk**: punctuation, letter case and emoji stay as written, and a sentence longer than the chunk limit stays whole.
- **An outside service that fails stops the run.** The answer is `502`, and its detail names the service and what it said; no later step runs and no snapshot is written. The image step has no fallback yet.
- **A snapshot is written only for a run that produced an image**, before the response is sent.
- **`version` is a tag, not a switch**: it names the snapshot and nothing else. Without one, the run is filed under the base version the code declares.
- **The metadata holds what led to the image**: the version and time, the original text, every chunk with its emotion scores, the entry's distribution and dominant emotion, the imagery words, the final prompt, the channel that painted it and the image's file name.
- **Snapshot names carry local time to the millisecond**, so two runs never share one. An image that isn't a JPEG keeps its own extension.
- **The service checks its setup at startup, not at the first request**: the local model is loaded then, and the Hugging Face backend refuses to start without `HF_TOKEN`.
- **The Hugging Face token never leaves the service**: it appears in no response, snapshot or log.
- **The snapshot names where the emotion model ran**, since the two can differ slightly.
- **The prompt is sent to Pollinations marked private**, so it stays out of that service's public feed.
