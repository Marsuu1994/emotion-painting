# Emotion Painting

Turns a diary entry into a painting: the entry's plain text is chunked by rules, its emotion and imagery are extracted, and a free image service paints the result.

## Getting Started

The project is managed with [uv](https://docs.astral.sh/uv/), which also installs the Python version it pins.

```bash
uv sync             # the virtual environment and every dependency, from the lockfile
uv run pytest       # the tests
```

The checks CI runs — formatting, lint, types, tests with the coverage floor — are listed in [AGENTS.md](./AGENTS.md) › Commands.

## Current State

Phase 1 — a local proof of concept behind one synchronous endpoint — is being built. The pipeline's rule-based steps are written and tested: an entry is split into chunks, its imagery words are picked out, and a prompt is put together from them. The steps that call outside services — emotion scoring and image generation — and the endpoint itself are not there yet.

## Docs

- [design/overall-design.md](./design/overall-design.md) — open questions first, then the goal, the phases and the pipeline
- [design/flows/](./design/flows/README.md) — per-feature flow docs
- [reviews/](./reviews/README.md) — the owner's code reviews, one file per PR
- [AGENTS.md](./AGENTS.md) — the rules agents and people work by here
