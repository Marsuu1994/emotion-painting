# Emotion Painting — Overall Design

The one project-wide design: what the project is for, how it is phased and how the pipeline works. It stays at design altitude — module and function names live in the code, step contracts in `flows/`. Open questions come first so the owner sees them at a glance: each says what Phase 1 does in the meantime, and leaves the list once the owner answers it, the answer moving into the section it belongs to.

## Open Questions

### Phase 1

| # | Open | Phase 1 default |
| --- | --- | --- |
| 2 | **Image fallback channel — pending.** Planned as `FLUX.1-schnell` over the Hugging Face Inference API with the same token. That model is no longer served by `hf-inference`, only through Inference Providers (fal-ai, wavespeed), which bill the account's inference credits and each take a different request shape (seen 2026-11-14). | No fallback: when Pollinations fails, the request fails. |
| 3 | **Valence/arousal coordinates.** Each of the 28 emotion labels needs one (V, A) point: written by us from Russell's circumplex, or taken from published norms (NRC-VAD forbids redistribution; Warriner's licence is unchecked). | The provisional table v0 in the measurement spike. |
| 4 | **Phrase tables (Step 3).** Which atmosphere phrase a region's V/A picks (light, warmth, density; how many bins on each axis), and which accent phrase each emotion picks, above what threshold. Candidates are in the measurement spike. | A placeholder table: three bins on each axis, one accent per emotion family, threshold 0.1. |
| 7 | **Combining chunks into a region.** How the distributions of the chunks a beat covers become that region's emotion: plain mean, length-weighted mean, or the peak. | Mean weighted by chunk length. |
| 8 | **One request for all chunks.** The design asks for a single batched inference call; whether the endpoint accepts a list of chunks in one request is untested until it is deployed. | One call per chunk, sent concurrently. |
| 9 | **What `version` means.** A tag on the outputs, or a selector of parameter sets? | A tag: stamped on the snapshot's file names and metadata; the code at hand decides the behaviour. |

### Later

- **Phase 2 data model**: the tables for entries, the processing state and run logs — designed and maintained by the owner.
- **Phase 2 webhook**: how the Python service knows a call really comes from the database.
- **Phase 2 retry numbers**: how old a `pending` row is before it is re-triggered (around 2 minutes), how often the sweep runs (around 5 minutes), and the `retry_count` cap.
- **The 10-second limit against the pipeline's slow calls** (a cold emotion endpoint and the LLM, in parallel, then image generation): whether one request can hold them is to be measured on Phase 1's runs.
- **Crisis entries**: whether an entry about self-harm still becomes a warm painting, and whether resources are shown.

## Goal

Turn a diary entry's plain text — written in the app's Dump feature — into a painting: measure its emotion with a fixed open model, read its imagery with an LLM, then have a free image service paint the result.

## Phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 — Local POC | One FastAPI service on the developer's machine with one synchronous endpoint. No database, queue, webhook or deployment. | In progress |
| 2 — Exposed API | Supabase (Postgres + Storage) and a Vercel Python service, triggered asynchronously per entry. | Recorded here, not started |

## Pipeline

Four steps, the same in every phase.

### Step 1 — Chunking and preprocessing (rules, no AI)

- **Light cleaning**: URLs and runs of blank lines go. Punctuation (`!!!`, `...`), letter case and emoji stay exactly as written — they signal arousal.
- **Two-level split**: first into paragraphs at line breaks; a paragraph over the model's limit (about 350 characters, 512 tokens) is split again at sentence ends (`。！？.!?`) into groups of sentences, so no sentence is cut.
- **Physical features**: each chunk keeps its position in the entry and its character count.
- No embedding here: the downstream model brings its own tokenizer and embedding layer.

### Step 2 — Feature extraction (two tracks, in parallel)

The ordered chunks go down two tracks that don't block each other.

- **Track A — emotion distribution** (decides colour, light and mood). A fixed multilingual model, `Horizon-Labs/multilingual-emotions-base` (or its `-small` sibling), reads each chunk in Chinese, English or both, with no translation. How it was chosen, and what it costs, is in `spikes/measurement-layer.md`.
  - **Emotion**: the 28 GoEmotions labels (27 emotions and `neutral`), each scored independently (multi-label). The scores are normalised into a distribution, and each chunk keeps all of it, not just the top label.
  - **Valence and arousal**: computed, not measured — the distribution-weighted mean of a fixed (V, A) point per label (question 3).
  - **Served from a dedicated Hugging Face Inference Endpoint**, since no inference provider serves the model: stateless HTTP calls, no weights on the machine, waiting out a cold start. It runs on CPU, billed by the minute while it runs (from $0.033 an hour), and needs an active subscription and a card on file; it is deployed from a chosen commit, so the model's revision is pinned. Instance size, and `base` against `small`, are set when it is deployed.
  - Every output records the model id and revision and the coordinate table's version, so a change of model or table shows in the data.
- **Track B — imagery** (decides the subject and the scene). One call to an LLM, Claude Sonnet 5.5, with the whole entry as numbered chunks. How it was chosen, and what it costs, is in `spikes/imagery-layer.md`.
  - **What it returns**, in a fixed JSON shape: 3 to 6 beats in order, each covering a run of chunks, with its zone on the scroll (outside, struggle, core, landing), its motif in English and the objects it names; the beat painted at the centre; and up to two lines of the entry to write into the painting.
  - **Checked by code**: every chunk in exactly one beat, in order; quote lines verbatim, or dropped. A refusal or a failed check falls back to a `sealed` motif — a folded letter, a closed door.
  - **Not reproducible**: the same entry gets different motifs on each run, so the output is stored with the model id and the prompt's version.

### Step 3 — Prompt build

Code joins the two tracks by chunk number and writes the English prompt: the fixed style block, then each beat top to bottom — its motif, an atmosphere phrase from its V/A (light, warmth, density) and accent phrases from its top emotions — and the quote lines. Numbers never go into the prompt as numbers, and the phrases keep to a warm range: sadness can make a region paler, emptier and further away, never darker. The phrase tables are open (question 4).

### Step 4 — Image generation

**Pollinations.ai** first: no account and no key — a plain HTTP GET with the URL-encoded prompt returns the image bytes of a Flux model. A fallback channel is pending (question 2).

## Phase 1 — Local POC

- **One synchronous endpoint, `POST /generate`.** It takes the entry's `text` and an optional experiment `version` (the configured base version when absent), runs the four steps in memory and answers with the image.
- **Two outputs per call.** The response body is the image itself, so it previews in Swagger UI (`/docs`) or any client. The same call also writes a snapshot to `./outputs/`, named by version and timestamp, for comparing versions side by side:
  - the image: `v{version}_{timestamp}.jpg`
  - its metadata: `v{version}_{timestamp}_meta.json` — the original text, each chunk's emotion distribution and V/A with the model revision, the LLM's beats with its model and prompt version, the final prompt and the channel that produced the image.
- **Secrets come from the environment**: the Hugging Face token is read from `HF_TOKEN`, the emotion endpoint's URL from the environment too, and the LLM's key from `ANTHROPIC_API_KEY`.
- **Dependencies stay deployable to a serverless function** — no model weights and no heavy numeric stack — so Phase 2 can reuse the pipeline as it is.

## Phase 2 — Exposed API

Recorded so Phase 1 doesn't build against it; nothing here is implemented.

### Services

- **Supabase, free tier.**
  - Postgres holds each entry's metadata, its processing state (`pending` / `processing` / `completed` / `failed`) and run logs.
  - Storage holds the generated files: 1 GB in total, 50 MB per file, 5 GB of egress a month plus 5 GB of cached egress (a public bucket is served through the CDN).
  - A free project with no API activity for a week is paused; the data stays and it is resumed by hand.
- **Vercel Python service**: FastAPI as serverless functions, connected to Supabase through environment variables. The Hobby tier limits a request to 10 seconds and can't package heavy models, so all inference goes to stateless external APIs.

### Happy path

1. The front end submits an entry's plain text.
2. It is written to the entries table as `pending`.
3. Once the transaction commits, a Supabase Database Webhook (built on `pg_net`) posts to the Python service, asynchronously.
4. The service runs the pipeline.
5. The results — the raw paint data as JSON, the image — are uploaded to Storage.
6. The row is updated to `completed` with the storage paths.

### Failure handling and logging

A Database Webhook is fire-and-forget: a failed call is not retried. Two safety nets cover that.

- **In the service**: the outermost handler catches any failure after the request arrives — inference, upload — and marks the row `failed` with the reason, so nothing stays `pending` forever.
- **In the database**: a `pg_cron` job sweeps for rows still `pending` past a threshold (a webhook lost to a network blip, a cold start that timed out) and triggers them again, capped by a `retry_count`.
- **Logs**: the key steps and the context of each error are kept in the database, to trace cold-start timeouts, external API errors and failed uploads.

## Future Directions

- **Translate first, if direct scoring reads poorly**: translate to English and score with the English GoEmotions classifier (`SamLowe/roberta-base-go_emotions`) — the same 28 labels, so the coordinate table and everything downstream stay. The spike records what translation costs.
- **A motif lexicon**: the owner's own motifs, each with a prompt template, and the LLM picking ids from it instead of writing motifs freely — more control, the same output shape.
- **Generative art** (p5.js, WebGL, shaders): rendering straight from the raw emotion matrix and its movement along the entry, instead of from a prompt.
