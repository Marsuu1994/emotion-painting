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

Phase 1 — a local proof of concept behind one synchronous endpoint — is being built. So far the repository holds the project's design, its working rules and the Python environment (an empty package with its checks wired up); the pipeline isn't written yet. The pipeline's design is settled: a multilingual model on a Hugging Face Inference Endpoint scores 28 emotions straight from the Chinese text, and valence and arousal are computed from them; in parallel an LLM reads the entry for the scroll's regions and motifs; code joins the two into the image prompt.

## Docs

- [design/overall-design.md](./design/overall-design.md) — open questions first, then the goal, the phases and the pipeline
- [design/flows/](./design/flows/README.md) — per-feature flow docs
- [design/spikes/](./design/spikes/) — dated research records: how the measurement and imagery layers were chosen
- [reviews/](./reviews/README.md) — the owner's code reviews, one file per PR
- [AGENTS.md](./AGENTS.md) — the rules agents and people work by here
