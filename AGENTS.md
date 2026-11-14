# Emotion Painting Agent Guide

The shared rulebook every agent session loads (Claude Code imports it through `CLAUDE.md`; Codex reads it directly). It holds the rules every task needs, plus an index of where the rest live (Workflow › Where the rules live).

## Project Overview

Turns a diary entry's plain text into a painting: rule-based chunking, emotion and imagery extraction, a prompt, then an image from a free generation service. Phase 1 is a local proof of concept behind one synchronous endpoint; the phases after it are in `design/overall-design.md`.

## Tech Stack

- Language: Python 3.13
- Project and dependencies: uv (the Python version, the virtual environment, the lockfile)
- Format and lint: Ruff
- Types: Pyright, strict
- Tests: pytest, with a coverage floor
- Chinese word segmentation: jieba

## Project Structure

Directory responsibilities only — for concrete file and function names, read the code.

```text
src/emotion_painting/    # The package (src layout)
tests/                   # pytest tests, one file per module
typings/                 # Type stubs for dependencies that ship none
design/                  # Design docs
├── overall-design.md    # The one project-wide design: open questions first, then goal, phases, pipeline
└── flows/               # Per-feature flow docs
reviews/                 # The owner's code reviews, one file per PR: each comment, its kind and its outcome — README for people, rules in its AGENTS.md
scripts/                 # Repo checks run in CI
```

## Workflow

### Session start

Read the design docs only when the task involves logic, data or new flows; skip them for pure wording or formatting changes.

- `design/overall-design.md`: what the project is, how it is phased, and what is still open. A task that runs into an open question takes the default the doc gives, or raises it with the owner — it never settles the question on its own.
- `design/flows/<feature>.md`: flow changes or additions

A fresh checkout runs `uv sync`: the virtual environment and every dependency, from the lockfile.

### Where the rules live

A rule that only one kind of file needs lives with that file. Read it before you edit:

| Before you edit… | Read first |
| --- | --- |
| a flow doc (`design/flows/`) | `design/flows/README.md` |
| `design/overall-design.md` | the paragraph at its top |
| `reviews/`, or addressing the owner's review on a PR | `reviews/AGENTS.md` |

### Adding a rule

A new rule goes where it belongs: a rule for one kind of file goes into that file's README or Conventions section; a rule a linter or script can check goes into the tool, with at most one line here; a rule that overlaps an existing one rewrites that rule instead of adding a second. Only rules every task needs live in this file.

## Design Principles

How a design should feel. Check a design against these before proposing it, and rank options by them. They are written for screens; Minimal and Consistent hold for the shape of an API or a command just as well.

1. **Minimal — fewer elements, smaller changes, fewer steps.**
   - Only the necessary elements, and one element per meaning: if one mark already says something, nothing says it again; if removing an element loses nothing, remove it.
   - When what exists works, change it the least: a small change to the current design over a new layout, the simplest behaviour over a clever one.
   - The fewest actions, the least friction: every extra step is a reason to stop, so ask first whether a step can go. The one exception: an action that can't be taken back gets one confirming state, in place.
2. **Hierarchy — the important at a glance.**
   - Order by importance: what matters most is seen first; what is secondary folds away, sits behind a tap or comes last — in the same order on every width.
   - Small visual details carry state; words don't explain it.
   - Don't crowd when there is room.
   - A layout holds when things fold: whatever can collapse, the screen still reads well collapsed.
3. **Consistent — one structure, reused by the eye and by the code.** When a design seems to need a second version of something, first ask whether it is a slot of the first.
   - One component, many places: a place fills slots, never reshapes the skeleton, and each slot keeps one job everywhere.
   - One journey on every width: a wider screen may add, never subtract.
   - Variants differ by colour and mark, never by layout.
4. **Honest controls — controls look like controls, statuses don't, feedback stays small.**
   - A status mark never looks like a control: a state the user can't change by clicking it is not drawn as a control shape.
   - Controls look tappable, and their feedback stays small: hover is the least it can be, press and selection carry the weight, and hover never changes how a selected element looks.
   - Interacting never changes size: the layout holds still.

## Documentation Style

- **Living docs are for the owner to re-orient, not the agent's work record.** README Current State and everything under `design/` say what the project is now and what's still open. Write at the doc's altitude (each doc states it at its top); length doesn't scale with diff size — a bigger change earns a higher-level summary, not a longer one; rewrite the sentence that is now wrong instead of appending a paragraph. Implementation inventory (file, function and key names, sub-change lists) lives in the code and the diff; completeness lives in PR descriptions and the git history.

## Coding Conventions

### General

- **DRY — one definition per piece of logic or type.** Logic that repeats with only data differences becomes one function driven by its parameters or a table. Identical shapes collapse to one type, and shapes sharing a core extend a base. Bad: `split_chinese_sentences` and `split_english_sentences` differing only in their punctuation set. Good: one `split_sentences(text, terminators)`.
- **Name things plainly — clear and boring beats short or clever.** A function says what it returns or does, including what it looks up by; a variable or parameter — a comprehension's or a lambda's included — says what it holds. Full words only: no single letters (`_` for a value that is never read is fine) and no abbreviations beyond `id`. Bad: `get_data(text)`, `[c for c in chunks]`, `run(ctx, fn)`. Good: `extract_imagery_words(chunks)`, `[chunk for chunk in chunks]`, `run(context, step)`.
- **No magic literals.** Fixed literals — model ids, URLs, thresholds, limits, durations, file-name patterns — are module-level `UPPER_SNAKE` constants in the package's `constants.py`. Bad: `if len(paragraph) > 350:` inline. Good: `CHUNK_MAX_CHARS` imported from `constants`.
- **A workaround is fine, but marked.** Code that exists only to get around someone else's bug or quirk — a dependency's, a service's, the runtime's — opens its comment with `Workaround (<whose>):`, says what goes wrong without it, and links the upstream issue when there is one. Upgrading a dependency starts with `grep -rn "Workaround (<name>"`: each one the new version no longer needs goes in the same change.

### Enums

- Use enum members (`Emotion.HAPPY`), never raw strings. An enum whose values cross a boundary as text — JSON, a model's labels — is a `StrEnum`.
- **A mapping over an enum is a `dict[TheEnum, T]` with a test that its keys are the whole enum; branching is a `match` whose `case _` calls `assert_never`.** Either way a new member fails — the test or the type checker — until it is handled. Bad: `case _: return "neutral"` silently covering a new `Emotion`. Good: `case _: assert_never(emotion)`.

### Types

- Every function signature is fully annotated, and nothing is typed `Any`.
- **Structured data that crosses a function boundary is a frozen `dataclass`**, never a bare `dict` or tuple. Bad: `return {"index": index, "text": text}`. Good: `return Chunk(index=index, text=text)`.
- **A dependency that ships no types gets a stub in `typings/`** covering only what the code uses, and exactly one module imports it — so its untyped surface ends there. Bad: `# type: ignore` on a `jieba` import in two modules. Good: `typings/jieba/`, imported only by `imagery.py`.

## Testing

- Tests live in `tests/`, one file per module: `tests/test_<module>.py`.
- **Mock only the outside edge** — the HTTP call to a service this project doesn't run. Everything on this side of it runs for real, so a test survives a refactor that changes how the code is put together.
- **A bug fix starts with a failing test** at the lowest layer that reproduces it.
- **A known bug is a strict `xfail`** — `@pytest.mark.xfail(strict=True, reason=…)`, the reason naming where it is tracked; the PR that fixes it removes the mark.
- **The coverage floor only goes up**: raise `fail_under` in `pyproject.toml` when coverage grows, never lower it to pass.

## Tooling

- **Ruff owns formatting** (`ruff format`); don't hand-tune spacing or quotes against it. **Ruff's linter and Pyright own correctness**: Pyright runs in strict mode, and the linter enforces annotated signatures, no `Any`, no `print` (`scripts/` excepted: its checks talk to CI through stdout) and sorted imports. The rule set is in `pyproject.toml`.
- CI runs the format check, the linter, Pyright and the tests with the coverage floor — run all four before pushing (Version Control).

## Version Control

- **Local sessions** (on the owner's machine): never commit, push or take another outward-facing VCS action without explicit permission — make and stage the changes, summarize them, and wait for approval.
- **Remote sessions** (cloud containers such as Claude Code on the web): commit, push with `git push -u origin <branch>` and open the PR without asking, then subscribe to its activity (`subscribe_pr_activity`) and see it through until it merges or closes: red CI and review comments are the session's to fix.
- Never commit or push to `main`; changes land through pull requests.
- **One task, one branch, one PR.** Everything a session's task produces — the implementation, its tests, the docs and any follow-ups the owner adds along the way — goes on one branch into one PR. A second branch or PR only when the owner asks for one. Bad: a docs PR plus a stacked implementation PR from the same session, unasked. Good: the code, its tests and its docs in one PR.
- **Branch names say what the PR does**: `claude/<feature>-<change>`, kebab-case, a few words, with the step for a multi-PR project. A remote session whose assigned branch is a random name creates a descriptive branch instead. Bad: `claude/quirky-galileo-8ofthc`, `claude/pipeline`. Good: `claude/local-poc-pr3-rule-steps`.
- **Before every push**:
  1. `design/overall-design.md`: remove each open question the change answered, moving the answer into the section it belongs to, and rewrite what the change made wrong.
  2. README Current State: rewrite the sections the change touches.
  3. AGENTS.md, or a README it indexes: only when a rule or a directory's responsibility changed.
  4. Run `uv run ruff format`, then `uv run ruff check`, `uv run pyright` and `uv run pytest --cov`.
- **Act on submitted reviews only.** A pending review — comments drafted but not yet submitted — can still change: don't reply to, resolve or push for its comments; at most mention that one is pending.

## Commands

```bash
uv sync                     # Create .venv and install everything from the lockfile
uv run ruff format          # Format all code
uv run ruff format --check  # Verify formatting (CI)
uv run ruff check           # Lint (CI); --fix applies the safe fixes
uv run pyright              # Type check, strict (CI)
uv run pytest               # Tests
uv run pytest --cov         # Tests, failing below the coverage floor (CI)
uv add <package>            # Add a dependency (--dev for a tool)
python3 scripts/check_review_log.py  # Every owner review on a PR has its entry in reviews/ (CI; GITHUB_REPOSITORY and PR_NUMBER locally)
```
