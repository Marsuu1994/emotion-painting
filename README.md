# Emotion Painting

Turns a diary entry into a painting: the entry's plain text is chunked by rules, its emotion and imagery are extracted, and a free image service paints the result.

## Getting Started

The project is managed with [uv](https://docs.astral.sh/uv/), which also installs the Python version it pins.

```bash
uv sync --extra local-model   # the virtual environment and every dependency, the emotion model's runtime included
uv run pytest                 # the tests — they call no outside service and load no model
uv run uvicorn emotion_painting.api:app --reload   # the service
```

The first start downloads the emotion model (about 560 MB, into Hugging Face's cache) and takes a while; later starts take seconds. No token or `.env` is needed; `.env.example` lists the settings there are.

With the service up, open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), expand `POST /generate`, and send an entry's `text`: the painting shows in the response, and the same run is saved under `outputs/` — the image, and a `_meta.json` with everything that led to it. From a terminal:

```bash
curl -X POST http://127.0.0.1:8000/generate -H 'content-type: application/json' -d '{"text": "今天阳光很好，我在公园的湖边散步。"}' -o painting.jpg
```

The checks CI runs — formatting, lint, types, tests with the coverage floor — are listed in [AGENTS.md](./AGENTS.md) › Commands.

## Current State

Phase 1 — a local proof of concept — runs end to end: `POST /generate` takes a diary entry, splits it into chunks, scores their emotion with a multilingual model running on this machine while picking the entry's imagery words by rules, builds a prompt from both, has Pollinations paint it, saves the run under `outputs/` and answers with the image ([flow](./design/flows/generate.md)). Nothing in it costs money.

The emotion model can also run behind the Hugging Face API (`EMOTION_BACKEND=hugging_face`), the way Phase 2 will use it; that path has never run, since the account answers `402` until it has inference credit.

Placeholders by design, each an open question in the [overall design](./design/overall-design.md): one emotion label (`开心`), a one-line prompt template, imagery words passed to the prompt untranslated, no fallback image channel.

## Docs

- [design/overall-design.md](./design/overall-design.md) — open questions first, then the goal, the phases and the pipeline
- [design/flows/](./design/flows/README.md) — per-feature flow docs: [generate](./design/flows/generate.md)
- [reviews/](./reviews/README.md) — the owner's code reviews, one file per PR
- [AGENTS.md](./AGENTS.md) — the rules agents and people work by here
