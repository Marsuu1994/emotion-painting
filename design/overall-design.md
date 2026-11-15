# Emotion Painting — Overall Design

The one project-wide design: what the project is for, how it is phased and how the pipeline works. It stays at design altitude — module and function names live in the code, step contracts in `flows/`. Open questions come first so the owner sees them at a glance: each says what Phase 1 does in the meantime, and leaves the list once the owner answers it, the answer moving into the section it belongs to.

## Open Questions

### Phase 1

| # | Open | Phase 1 default |
| --- | --- | --- |
| 1 | **Emotion inference in Phase 1.** Hugging Face answers the owner's token with `402`: a free account has no included credit for Inference Providers, so every call needs pre-paid credits or PRO (seen 2026-11-14). Direction (owner, 2026-11-15): Phase 1 runs the same model on the owner's machine, Phase 2 calls the Hugging Face API. Not built yet. | The step calls the Hugging Face API, so a request fails at this step and says why. Its request and response shapes come from Hugging Face's client library, not a live answer; `uv run pytest -m live` is the first check once the account can call it. |
| 2 | **Image fallback channel — pending.** Planned as `FLUX.1-schnell` over the Hugging Face Inference API with the same token. That model is no longer served by `hf-inference`, only through Inference Providers (fal-ai, wavespeed), which bill the account's inference credits and each take a different request shape (seen 2026-11-14). | No fallback: when Pollinations fails, the request fails. |
| 3 | **Pollinations without a key.** An anonymous call comes back 768×768 with a `pollinations.ai` watermark in the corner; `nologo` changes nothing (seen 2026-11-14). Whether to register for a key is open. | Called without a key, as designed, and with `private` set so a diary's prompt stays out of the service's public feed. |
| 4 | **Emotion vocabulary.** The final label list (candidates: joy, sadness, anxiety, calm, nostalgia, anger, fatigue). | One label, `开心`, scored with the model's default hypothesis template. With a single label the dominant emotion is always that label, whatever its score. |
| 5 | **Aesthetic mapping (Step 3).** A colour dictionary, emotion entropy driving how complex the composition is, arousal driving brushwork and material, a fixed style anchor. | A placeholder template joins the imagery words and the dominant emotion. |
| 6 | **Language of imagery words.** A Chinese entry yields Chinese words, and the prompt is meant to be English: translate them (and how), or pass them through? | Passed through untranslated. On sample entries the Chinese words did steer the image, loosely: `街角, 咖啡店` gave a street of shops; `公园, 湖边, 柳树` gave water and greenery, and a figure nobody asked for. |
| 7 | **Corpus for imagery scoring.** TF-IDF needs document frequencies, and a single entry has none. | A word's score is how often it occurs times how rare it is in the IDF table bundled with jieba; a word the table doesn't hold — every English word — takes the table's median. Seen on sample entries: in a mixed entry the English words tend to outrank the Chinese ones, and English verbs get through, since only Chinese has a part-of-speech filter. |
| 8 | **Combining chunks into one emotion.** How per-chunk distributions become the entry's dominant emotion: plain mean, length-weighted mean, or the peak. | Mean weighted by chunk length. |
| 9 | **One request for all chunks.** The design asks for a single batched inference call; whether `hf-inference` accepts a list of inputs for zero-shot could not be checked while the token is refused. | One call per chunk, sent concurrently. |
| 10 | **What `version` means.** A tag on the outputs, or a selector of parameter sets? | A tag: stamped on the snapshot's file names and metadata; the code at hand decides the behaviour. The base version is declared in the code, next to the parameters it describes, and is bumped in the change that alters them. |

### Later

- **Phase 2 data model**: the tables for entries, the processing state and run logs — designed and maintained by the owner.
- **Phase 2 webhook**: the secret header the database's webhook carries to the Next.js route, and where it is stored (the trigger definition is readable by any role that can log in to the database).
- **Phase 2 deployment, unverified**: Services is in beta; whether Vercel fetches a git submodule at build time, and whether a Next.js app at the repository root can sit beside a service in a subdirectory, are not stated in its docs — one trial deployment settles both.
- **Phase 2 retry numbers**: how old a `pending` row is before it is re-triggered (around 2 minutes), how often the sweep runs (around 5 minutes), and the `retry_count` cap.
- **Request time**: a Vercel Function on Hobby may run up to 300 seconds. So far, with the emotion call faked, a whole request took 5 to 6 seconds on three sample entries, nearly all of it image generation (2026-11-14).

## Goal

Turn a diary entry's plain text — written in the app's Dump feature — into a painting: extract its emotion and imagery with an open multilingual model and light feature engineering, then have a free image service paint the result.

## Phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 — Local POC | One FastAPI service on the developer's machine with one synchronous endpoint. No database, queue, webhook or deployment. | In progress |
| 2 — Exposed API | Supabase (Postgres + Storage), and this service deployed inside the mars-workbench Vercel project, triggered asynchronously per entry. | Recorded here, not started |

## Pipeline

Four steps, the same in every phase.

### Step 1 — Chunking and preprocessing (rules, no AI)

- **Light cleaning**: URLs and runs of blank lines go. Punctuation (`!!!`, `...`), letter case and emoji stay exactly as written — they signal arousal.
- **Two-level split**: first into paragraphs at line breaks; a paragraph over the model's limit (about 350 characters, 512 tokens) is split again at sentence ends (`。！？.!?`) into groups of sentences, so no sentence is cut — a single sentence over the limit stays whole.
- **Physical features**: each chunk keeps its position in the entry and its character count.
- No embedding here: the downstream model brings its own tokenizer and embedding layer.

### Step 2 — Feature extraction (two tracks, in parallel)

The ordered chunks go down two tracks that don't block each other.

- **Track A — emotion distribution** (decides colour, light and mood). A zero-shot multilingual model, `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, called over the Hugging Face Inference API — stateless HTTP, no weights on the machine, waiting out a cold model. It handles Chinese, English and mixed text. Labels are scored independently (multi-label), and each chunk keeps its whole probability distribution over the emotion vocabulary, not just the top label.
- **Track B — imagery words** (decides the subject and the scene). Rules and statistics only, no model: the text is routed by language — Chinese through jieba's part-of-speech tagging, keeping nouns, place words and time words; English through a stopword filter — and the top 3 to 5 words by score are the entry's imagery.

### Step 3 — Prompt build

The top imagery words and the dominant emotion are combined into an English prompt for the image model. The mapping from features to aesthetics is an open question; Phase 1 uses a placeholder template.

### Step 4 — Image generation

**Pollinations.ai** first: no account and no key — a plain HTTP GET with the URL-encoded prompt returns the image bytes of a Flux model. A fallback channel is pending (Open Questions).

## Phase 1 — Local POC

- **One synchronous endpoint, `POST /generate`** ([flow](./flows/generate.md)). It takes the entry's `text` — up to 10,000 characters, the Dump feature's own limit — and an optional experiment `version` (the base version when absent), runs the four steps in memory and answers with the image.
- **Two outputs per call.** The response body is the image itself, so it previews in Swagger UI (`/docs`) or any client. The same call also writes a snapshot to `./outputs/`, named by version and timestamp, for comparing versions side by side:
  - the image: `v{version}_{timestamp}.jpg`
  - its metadata: `v{version}_{timestamp}_meta.json` — the original text, the full emotion distribution, the top imagery words, the final prompt and the channel that produced the image.
- **Any failure fails the call**: an outside service that errors or times out stops the run, and the answer names the service and what it said. Nothing is retried.
- **Secrets come from the environment**: the Hugging Face token is read from `HF_TOKEN`.
- **Dependencies stay deployable to a serverless function** — no model weights and no heavy numeric stack — so Phase 2 can reuse the pipeline as it is.

## Phase 2 — Exposed API

Recorded so Phase 1 doesn't build against it; nothing here is implemented.

### Services

- **Supabase, free tier.**
  - Postgres holds each entry's metadata, its processing state (`pending` / `processing` / `completed` / `failed`) and run logs.
  - Storage holds the generated files: 1 GB in total, 50 MB per file, 5 GB of egress a month plus 5 GB of cached egress (a public bucket is served through the CDN).
  - A free project with no API activity for a week is paused; the data stays and it is resumed by hand.
- **The Python service, inside mars-workbench's Vercel project** (decided 2026-11-15). This repository joins mars-workbench as a git submodule and deploys with it as one project, through Vercel Services (beta, on every plan): the Next.js app is one service, this FastAPI app another. The Python service gets no public route — a service is internal unless a rewrite exposes it — and only the Next.js app reaches it, over an internal binding whose URL Vercel injects as an environment variable. It reaches Supabase through environment variables.
- **Limits on Hobby** (Vercel docs, 2026-11-15): 2 GB and 1 vCPU per function, fixed; up to 300 seconds per request; a Python bundle of up to 500 MB uncompressed, dependencies included; 4 CPU-hours of active CPU and 360 GB-hours of provisioned memory per 30 days, after which the feature waits for the next 30 days rather than billing. These rule out bundling the emotion model and its runtime, so inference here goes to the Hugging Face API.

### Happy path

1. The front end submits an entry's plain text.
2. It is written to the entries table as `pending`.
3. Once the transaction commits, a Supabase Database Webhook (built on `pg_net`) posts, asynchronously and with a secret header, to a route of the Next.js app, which checks the secret and calls the Python service over the internal binding.
4. The service runs the pipeline.
5. The results — the raw paint data as JSON, the image — are uploaded to Storage.
6. The row is updated to `completed` with the storage paths.

### Failure handling and logging

A Database Webhook is fire-and-forget: a failed call is not retried. Two safety nets cover that.

- **In the service**: the outermost handler catches any failure after the request arrives — inference, upload — and marks the row `failed` with the reason, so nothing stays `pending` forever.
- **In the database**: a `pg_cron` job sweeps for rows still `pending` past a threshold (a webhook lost to a network blip, a cold start that timed out) and triggers them again, capped by a `retry_count`.
- **Logs**: the key steps and the context of each error are kept in the database, to trace cold-start timeouts, external API errors and failed uploads.

## Future Directions

- **Imagery from a model**: a multilingual model over the same Hugging Face API (`Davlan/xlm-roberta-base-ner-hrl`, or embedding similarity) to catch imagery the text only implies.
- **Generative art** (p5.js, WebGL, shaders): rendering straight from the raw emotion matrix and its movement along the entry, instead of from a prompt.
