"""Stand-ins for the two outside services, at the HTTP transport — the only thing the tests fake."""

import json
from dataclasses import dataclass, field

import httpx

HUGGING_FACE_HOST = "router.huggingface.co"
POLLINATIONS_HOST = "image.pollinations.ai"
PAINTING_BYTES = b"\xff\xd8\xff\xe0 a painting"
HAPPY_SCORE = 0.8


@dataclass
class FakeServices:
    """Answers like Hugging Face and Pollinations do, and remembers every request.

    Set a response to make that service answer with it instead.
    """

    hugging_face_response: httpx.Response | None = None
    pollinations_response: httpx.Response | None = None
    requests: list[httpx.Request] = field(default_factory=list[httpx.Request])

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == HUGGING_FACE_HOST:
            return self.hugging_face_response or score_every_label(request)
        if request.url.host == POLLINATIONS_HOST:
            return self.pollinations_response or httpx.Response(
                200, content=PAINTING_BYTES, headers={"content-type": "image/jpeg"}
            )
        raise AssertionError(f"Unexpected call to {request.url}")

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    def requests_to(self, host: str) -> list[httpx.Request]:
        return [request for request in self.requests if request.url.host == host]


def score_every_label(request: httpx.Request) -> httpx.Response:
    labels = json.loads(request.content)["parameters"]["candidate_labels"]
    return httpx.Response(
        200, json=[{"label": label, "score": HAPPY_SCORE} for label in labels]
    )
