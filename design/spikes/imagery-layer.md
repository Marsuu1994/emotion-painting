# Spike — Imagery Layer

A dated record of how the imagery layer was chosen: what it replaces, how it runs beside the measurement layer, the contract of its one LLM call, and what that costs. It is not kept current — `../overall-design.md` holds the pipeline as it is now; the measurement side is in `measurement-layer.md`.

- **Date:** 2026-11-20
- **Decided:** an LLM — Claude Sonnet 5.5 (`claude-sonnet-5-5`), not the flagship — reads the segmented entry and returns the scroll's structure as JSON. It runs in parallel with the measurement layer; code joins the two by segment number and assembles the image prompt. It replaces the rule-based Track B (jieba nouns).
- **Next:** the two phrase tables (atmosphere, accents), the style block in code, and a probe run on one entry.

## 1. The Question

What the painting shows, region by region, and how that is joined with the emotion numbers.

## 2. Constraints (from the owner)

- **Imagery is taste, not measurement.** The owner accepts that an LLM's picks vary from run to run ("看天发挥"); reproducibility is required of the measurement layer only, which stays LLM-free.
- **Not the flagship model**: Sonnet.
- **The output has to be assembled by code**, so its shape is fixed even when its content isn't.

## 3. Options

| Option | What it gets | Verdict |
| --- | --- | --- |
| Track B as designed: jieba nouns, place and time words, TF-IDF | the objects the entry names — applications, letters, a mother | replaced: imagery here means the pictures the writer uses for an inner state (a weight on the chest, being tied down), which nouns don't capture; and it can't find a turning point or group segments into regions |
| An owner-kept motif lexicon, the LLM picking ids (the diary → painting handoff) | the most control: motifs are the owner's own visual language | deferred: needs lexicon v1 first; the output field below can later switch from free text to an id |
| Embedding nearest neighbour against owner-labelled examples | deterministic picks | dropped for now: needs labels, and the clustering experiment showed embeddings confusing what writing *does* (inner critic against self-comfort) |
| **An LLM writing the structure freely, under a fixed schema** | regions, turning point, motifs and quote lines in one call | **chosen for the POC** |

## 4. Pipeline

```
entry ─rules─→ numbered segments ─┬─→ measurement (Inference Endpoint) → per segment: 28-label distribution, V/A
                                  └─→ imagery (LLM, one call)          → beats, turning point, motifs, quote lines
                                              ↓ join by segment number (code)
                                  prompt assembly (code) → image model
```

1. **Segment** (rules) and number the segments — the shared key both layers answer in.
2. **In parallel:** the measurement layer scores each segment; the LLM reads the whole entry, segment numbers included.
3. **Join** (code): each beat takes the distributions of the segments it covers, combined by a length-weighted mean; its V/A picks an atmosphere phrase, its top 3 emotions above a threshold pick accent phrases.
4. **Assemble** (code): the fixed style block, then each region top to bottom — its motif, atmosphere and accents — and the quote lines.
5. **Paint.**

**Why parallel.** The wait is the slower of the two calls, not their sum; a cold endpoint doesn't hold up the LLM; each layer is tested alone; and the LLM doesn't anchor on numbers.

**What parallel gives up.** In the earlier sequential design the LLM saw the numbers and chose accents among candidates; here accents come from code and tables alone — simpler, and deterministic. The two layers can also disagree: the LLM reads comfort where the numbers read anger. Both reach the painting, through different slots — the motif from one, the atmosphere and accents from the other.

## 5. The LLM Call

**Input:** the entry as numbered segments. The system prompt says what this is — the owner's own diary, read to plan a painting — and what to return: the structure only, no advice, no retelling. Motifs describe the picture of an inner state, borrowing the writer's own metaphors where there are any, in English, warm even when the entry is low: distance, scale and paleness carry sadness, never darkness.

**Output** — fixed by structured outputs, so it always parses:

| Field | Holds |
| --- | --- |
| `beats` | 3 to 6, in order; each covers a run of consecutive segments |
| `beats[].segments` | the segment numbers it covers |
| `beats[].zone` | where it sits on the scroll: `outside` (the world, the future), `struggle`, `core`, `landing` (the present) |
| `beats[].motif` | one or two English sentences: what is painted there |
| `beats[].objects` | concrete things the entry names, in English, for the small framed scenes |
| `turning_point` | the beat painted at the centre as the largest figure |
| `quote_lines` | up to two lines of the entry, verbatim, to write into the painting |

**Checked by code:** every segment belongs to exactly one beat, in order; `turning_point` names a beat; each quote line occurs verbatim in the entry, or is dropped. A refusal or a failed check falls back to `sealed` — a folded letter or a closed door — so the request still paints.

**Settings:** `claude-sonnet-5-5` with structured outputs; the effort level is untested. Refusals go through the API's server-side fallback (`fallbacks: "default"`), which re-runs a declined request on another model inside the same call. Each output is stored with the model id, the prompt's version and the date.

## 6. Trade-offs

- **Not reproducible.** The same entry gets different motifs on each run, and the model takes no `temperature` to turn that down. The output is stored and treated as data; the measurement numbers it is joined with stay fixed.
- **Cost.** Sonnet 5.5 is $2 per million input tokens and $10 per million output; one entry, about 1–3k tokens in and 1k out plus thinking, is an estimated 1–3 cents. Not measured.
- **Latency.** One call with thinking can take many seconds; running in parallel hides the endpoint behind it, or it behind the endpoint. Phase 2's 10-second limit gets tighter.
- **Sensitive entries.** Reading for structure is the kind of task models refuse least, but self-harm and crisis content can still change the reply; the fallback and `sealed` cover a refusal, and the product policy for such entries is still open.
- **The text leaves the machine** for the LLM provider. Privacy is out of scope for now.
- **English motifs** settle the old question of what language imagery words come in.
- **Free motifs drift** from the owner's visual language; the lexicon is how that comes back, once there is one.

## 7. Open

- The two tables: V/A → atmosphere phrases (how many bins on each axis), and emotion → accent phrase with its threshold. Candidates are in `measurement-layer.md` §8.
- The style block, from the diary → painting handoff, as a constant in code.
- How long the prompt can get before the image model drops parts.
- What a crisis entry becomes.

## Sources

- Anthropic model list and prices (Claude API reference, cached 2026-11-03): Claude Sonnet 5.5, `claude-sonnet-5-5`, $2 / $10 per million tokens.
- The diary → painting handoff (2026-11-19): style direction, scroll zones, motif lexicon, `sealed` fallback.
- The measurement handoff (2026-11-19): the clustering experiment's finding on what embeddings miss.
