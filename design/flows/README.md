# Flows

One doc per feature — `generate.md` for the `POST /generate` endpoint. A flow is a step contract: what triggers it, what happens, and the rules that hold.

## Format

- One flow per `##` heading, separated by `---`.
- Every flow has two required `###` sections — `Trigger / Entry Point` and `Steps` — plus an optional `### Rules` section for constraints and invariants. Extra `###` sections are allowed only for reference material that fits neither Steps nor Rules.

## Facts, not implementation detail or decisions

A flow says what triggers it, what happens (to the data, and what the caller gets back) and the rules that hold. Implementation detail — module and function names, library calls, how a step is coded — belongs in the code. Decisions and their reasons belong in `../overall-design.md` and in the PR that made them; a question that is still open belongs in that doc's Open Questions.

Bad: "`split_paragraphs()` runs `re.split` on `\n`, then `split_sentences()` on each long item." Good: "Split the text into paragraphs at line breaks; a paragraph over the chunk limit is split again at sentence ends."
