# Generate

How one diary entry becomes a painting, end to end, in Phase 1. Why each step is shaped this way is in `../overall-design.md` and the spikes; this doc is the contract.

## Generate a painting

### Trigger / Entry Point

- `POST /generate` with the entry's `text` and an optional experiment `version`: answers with the image.
- `POST /generate/stream` with the same body: answers with a stream of server-sent events, one as each step finishes (Stream events below), ending with the image.

### Steps

1. **Clean** the text: URLs and runs of blank lines go; punctuation, letter case and emoji stay as written.
2. **Chunk** it, by rules:
   - split into paragraphs at line breaks;
   - a paragraph over the chunk limit is packed sentence by sentence into chunks up to the limit, so no sentence is cut;
   - a chunk under the minimum length joins its neighbour;
   - each chunk is numbered in order and keeps its character count.
3. **Read the chunks along two tracks at once**; neither waits for the other.
   - **Emotion**, per chunk, from the emotion endpoint: 28 scores (27 emotions and `neutral`), normalised into a distribution; V and A as the distribution-weighted mean of the coordinate table.
   - **Imagery**, one LLM call over all the numbered chunks: 3 to 6 beats in order, each covering a run of chunks, with its zone (outside, struggle, core, landing), its motif in English and the objects it names; the beat at the centre; up to two quote lines.
4. **Check the imagery**: every chunk is in exactly one beat, in order; the centre names a beat; each quote line occurs verbatim in the entry, or is dropped. A refusal or a failed check replaces the whole plan with one `sealed` beat covering every chunk.
5. **Join** the tracks by chunk number. Each beat becomes a region:
   - its emotion: the length-weighted mean of its chunks' distributions, with V and A computed from that;
   - its atmosphere phrase: picked by its V and A;
   - its accent phrases: one per emotion in its top 3 above the threshold.
6. **Write the prompt**: the fixed style block, then each region top to bottom — the zone's place on the scroll (the centre beat as the largest figure), its motif, its atmosphere and its accents.
7. **Paint**: send the prompt, the size and the seed to the image service, and get the image back.
8. **Snapshot**: write the image and its metadata to `./outputs/`, named by version and timestamp.
9. **Answer**: the image (`/generate`), or the `image` event then `done` (`/generate/stream`).

### Stream events

| Event | Sent when | Carries |
| --- | --- | --- |
| `chunks` | step 2 finishes | each chunk's number and character count |
| `emotion` | each chunk's emotion returns — in any order, interleaved with `imagery` | the chunk's number, distribution, V and A |
| `imagery` | step 4 finishes | the checked plan, and whether it fell back to `sealed` |
| `regions` | step 5 finishes | each region's chunks, motif, emotion, atmosphere and accents |
| `prompt` | step 6 finishes | the prompt |
| `image` | step 7 finishes | the snapshot's file name, and the service that painted it |
| `error` | a step fails | the step and the reason; events already sent stand |
| `done` | the end | nothing |

### Rules

- **The measurement is reproducible**: the same text, endpoint revision and coordinate table always give the same numbers. The imagery is not, and is stored as data.
- **Every snapshot names what made it**: the emotion model and its revision, the coordinate table's version, the LLM and its prompt's version, the image service, the size and the seed.
- **Numbers never go into the prompt as numbers**, and the phrases stay in a warm range: a low region gets paler, emptier and further away, never darker.
- **A failed step stops the request**, naming the step: an error response from `/generate`, an `error` event from the stream. The one exception is step 4, whose failure paints `sealed`.
- **A cold emotion endpoint is waited out**, up to a limit; past it, step 3 fails.
- **A rate-limited image service is retried once**, after the wait it asks for.
