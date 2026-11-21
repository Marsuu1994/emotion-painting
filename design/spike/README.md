# Spikes

Point-in-time proposals for open questions. A complex task — several PRs, a new external service, a choice of model, or a choice with real trade-offs — starts here, not with code or a chat log. Spikes are not living docs: once decided they are frozen, and once implemented they move to `archived/`. The convention follows the owner's Mars Workbench repository.

## Lifecycle

1. **Spike** — write a self-contained doc here, headed `Status: awaiting owner review`, and point the open question it answers in `../overall-design.md` at it.
2. **Review** — go back and forth with the owner on the spike's PR, editing the spike in place each round.
3. **Decided** — once every open question is answered, record the answers in a Decision section and mark `Status: decided`. From here the spike is frozen; later decisions land in `overall-design.md` and the PRs that make them.
4. **Implement** — build what it decided, and update the living docs (`overall-design.md`, `flows/`) so they stand on their own without the spike.
5. **Archive** — in the PR that finishes step 4, `git mv` the spike to `archived/` and fix every link to it.

## Shape

- **Self-contained**: the trigger (what prompted it), options with honest pros and cons, and a concrete plan for the chosen one. Number the open questions so the owner can answer them one by one.
- **Written in Chinese with English terms.** The narrative is Chinese; technical nouns, model ids and code identifiers stay in English (segment / beat / motif / valence / arousal, `claude-sonnet-5-5`, `POST /generate`), so every term matches the code and the overall design one-to-one. Section headings pair the two (`## Trigger · 起因`). Say so in a one-line language note under the header. Bad: "情绪段的意象由大模型生成" (translated terms) or an all-English spike. Good: "每个 beat 的 motif 由 LLM 写".
