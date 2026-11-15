"""transformers' pipeline factory is untyped: these stubs cover only the zero-shot pipeline the package uses (AGENTS.md › Types)."""

from typing import Literal, TypedDict

class ZeroShotResult(TypedDict):
    sequence: str
    labels: list[str]
    scores: list[float]

class ZeroShotClassificationPipeline:
    def __call__(
        self, sequences: list[str], *, candidate_labels: list[str], multi_label: bool
    ) -> list[ZeroShotResult] | ZeroShotResult: ...

def pipeline(
    task: Literal["zero-shot-classification"], *, model: str, revision: str, device: str
) -> ZeroShotClassificationPipeline: ...
