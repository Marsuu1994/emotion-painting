# Emotion Painting — Overall Design

The one project-wide design: what the project is for, how it is phased and how the pipeline works. It stays at design altitude — module and function names live in the code, step contracts in `flows/`. Open questions come first so the owner sees them at a glance: each says what Phase 1 does in the meantime, and leaves the list once the owner answers it, the answer moving into the section it belongs to.

## Open Questions

### Phase 1

| # | Open | Phase 1 default |
| --- | --- | --- |
| 1 | **Image fallback channel — pending.** Planned as `FLUX.1-schnell` over the Hugging Face Inference API with the same token. That model is no longer served by `hf-inference`, only through Inference Providers (fal-ai, wavespeed), which bill the account's inference credits and each take a different request shape (seen 2026-11-14). | No fallback: when Pollinations fails, the request fails. |
| 2 | **Pollinations without a key.** An anonymous call comes back 768×768 with a `pollinations.ai` watermark in the corner; `nologo` changes nothing (seen 2026-11-14). Whether to register for a key is open. | Called without a key, as designed, and with `private` set so a diary's prompt stays out of the service's public feed. The same prompt came back as the same image, byte for byte, a day apart (2026-11-15): a changed prompt is what changes the painting. |
| 3 | **Emotion vocabulary.** The final label list (candidates: joy, sadness, anxiety, calm, nostalgia, anger, fatigue). | One label, `开心`, scored with the model's default hypothesis template. With a single label the dominant emotion is always that label, whatever its score. Seen on the first real runs: an English entry about a calm, happy morning scored `开心` at 0.24, a Chinese entry 0.91 — whether a label should be written in the entry's language is part of this question. |
| 4 | **Aesthetic mapping (Step 3).** A colour dictionary, emotion entropy driving how complex the composition is, arousal driving brushwork and material, a fixed style anchor. | A placeholder template joins the imagery words and the dominant emotion. |
| 5 | **Language of imagery words.** A Chinese entry yields Chinese words, and the prompt is meant to be English: translate them (and how), or pass them through? | Passed through untranslated. On sample entries the Chinese words did steer the image, loosely: `街角, 咖啡店` gave a street of shops; `公园, 湖边, 柳树` gave water and greenery, and a figure nobody asked for. |
| 6 | **Corpus for imagery scoring.** TF-IDF needs document frequencies, and a single entry has none. | A word's score is how often it occurs times how rare it is in the IDF table bundled with jieba; a word the table doesn't hold — every English word — takes the table's median. Seen on sample entries: in a mixed entry the English words tend to outrank the Chinese ones, and English verbs get through, since only Chinese has a part-of-speech filter. |
| 7 | **Combining chunks into one emotion.** How per-chunk distributions become the entry's dominant emotion: plain mean, length-weighted mean, or the peak. | Mean weighted by chunk length. |
| 8 | **What `version` means.** A tag on the outputs, or a selector of parameter sets? | A tag: stamped on the snapshot's file names and metadata; the code at hand decides the behaviour. The base version is declared in the code, next to the parameters it describes, and is bumped in the change that alters them. |

### Later

- **The Hugging Face API path has never run**: the owner's account answers `402` until it has inference credit, so its request and response shapes come from Hugging Face's client library, not a live answer; `uv run pytest -m live` runs it once `HF_TOKEN` can pay. It sends one call per chunk; whether `hf-inference` takes the whole entry in one batched call, as the local model does, is unchecked.
- **Phase 2 data model**: the tables for entries, the processing state and run logs — designed and maintained by the owner.
- **Phase 2 deployment, unverified**: Services is in beta; whether Vercel fetches a git submodule at build time, and whether a Next.js app at the repository root can sit beside a service in a subdirectory, are not stated in its docs — one trial deployment settles both.
- **Phase 2 sweep numbers**: the age at which a `pending` or `processing` row counts as stuck (above the function's 300-second limit), and the `retry_count` cap.
- **Phase 2 cron route**: whether a cron job can target a route in a project using Services, and how that route rejects callers other than the cron — Vercel's docs read so far don't say. Cron Jobs are also marked legacy, to move to Schedules.
- **Request time**: a Vercel Function on Hobby may run up to 300 seconds. With the emotion call faked, a whole request took 5 to 6 seconds on three sample entries, nearly all of it image generation (2026-11-14).

## Goal

Turn a diary entry's plain text — written in the app's Dump feature — into a painting: extract its emotion and imagery with an open multilingual model and light feature engineering, then have a free image service paint the result.

## Phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 — Local POC | One FastAPI service on the developer's machine with one synchronous endpoint, the emotion model running beside it. No database, queue or deployment. | Runs end to end |
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

- **Track A — emotion distribution** (decides colour, light and mood). A zero-shot multilingual model, `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, which handles Chinese, English and mixed text. It runs in one of two places, the same weights either way: on the developer's machine, on CPU (Phase 1), or behind the Hugging Face Inference API, waiting out a cold model (Phase 2, where the serverless function can't hold it). Labels are scored independently (multi-label), and each chunk keeps its whole probability distribution over the emotion vocabulary, not just the top label.
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
- **The emotion model runs on the developer's machine** (decided 2026-11-15): free, and pinned to one revision of its weights, so a run scores the same today and next month. Measured on a 4-core container (2026-11-15): the weights are about 560 MB, downloaded once; the service starts in about 6 seconds once they are cached and holds about 1.1 GB of memory; an entry's chunks are scored in one batch, in 0.1 to 2 seconds. The model and its runtime (PyTorch, transformers) are an optional install, so the Phase 2 service can leave them out and call the Hugging Face API instead — set by `EMOTION_BACKEND`, which then needs `HF_TOKEN`.
- **The snapshot says where the model ran**: scores from the local model and from the API can differ in the last decimals, since the API can't be pinned to a revision.

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

1. The Dump page submits an entry's plain text to the Next.js app's server action.
2. The entry is written to the entries table as `pending`, and the action answers at once: the submit never waits on the painting.
3. After the response, the same function — through Next.js `after()` — calls the Python service over the internal binding and waits for it. That wait is not the user's; it runs within the function's maximum duration (300 seconds on Hobby).
4. The service runs the pipeline.
5. The results — the raw paint data as JSON, the image — are uploaded to Storage.
6. The row is updated to `completed` with the storage paths.

The Python service talks to Supabase itself (decided 2026-11-15): it claims the row, uploads to Storage and writes the outcome. The Next.js app only writes the `pending` row and starts the call.

No database webhook (decided 2026-11-15): the write and the trigger live in the same server action. The Python service doesn't acknowledge early and work on in the background: Vercel documents work after the response (`waitUntil`) for Node.js and the Edge runtime, and points Python at queues instead. `after()` keeps the deferred work in Next.js, where it is documented, and lets the Python service stay one plain synchronous request.

### Failure handling and logging

The deferred call runs once and is not retried. Three rules cover that.

- **A run claims its row first**: one conditional update moves it from `pending` to `processing`, and a run that finds the row already claimed stops. So the deferred call and the sweep never paint the same entry twice.
- **In the service**: any failure after the claim — inference, upload — marks the row `failed` with the reason.
- **A daily sweep for what is left** (decided 2026-11-15): a cancelled `after()` (the function timed out, or a new deployment replaced it) writes nothing, so its row stays `pending` or `processing`. A Vercel cron job, once a day — the most Hobby allows, at any time within the hour it names — re-runs rows stuck past a threshold, capped by a `retry_count`. A stuck entry may wait up to about a day for its painting.
- **Logs**: the key steps and the context of each error are kept in the database, to trace cold-start timeouts, external API errors and failed uploads.

## Future Directions

- **Imagery from a model**: a multilingual model over the same Hugging Face API (`Davlan/xlm-roberta-base-ner-hrl`, or embedding similarity) to catch imagery the text only implies.
- **Generative art** (p5.js, WebGL, shaders): rendering straight from the raw emotion matrix and its movement along the entry, instead of from a prompt.
