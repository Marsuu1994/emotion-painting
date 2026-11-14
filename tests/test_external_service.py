import httpx
import pytest

from emotion_painting.constants import ERROR_BODY_MAX_CHARS
from emotion_painting.external_service import (
    ExternalServiceError,
    send_to_external_service,
)

pytestmark = pytest.mark.anyio

SERVICE_URL = "https://service.example/thing"


def client_answering(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def test_a_successful_response_comes_back() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="fine"))
    async with client_answering(transport) as client:
        response = await send_to_external_service(
            client, "Some Service", client.build_request("GET", SERVICE_URL)
        )

    assert response.text == "fine"


async def test_an_error_status_names_the_service_the_status_and_the_answer() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(402, json={"error": "Purchase credits"})
    )
    async with client_answering(transport) as client:
        with pytest.raises(ExternalServiceError) as raised:
            await send_to_external_service(
                client, "Some Service", client.build_request("GET", SERVICE_URL)
            )

    assert (
        str(raised.value) == 'Some Service answered 402: {"error":"Purchase credits"}'
    )


async def test_a_long_error_body_is_cut() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, text="x" * 5000)
    )
    async with client_answering(transport) as client:
        with pytest.raises(ExternalServiceError) as raised:
            await send_to_external_service(
                client, "Some Service", client.build_request("GET", SERVICE_URL)
            )

    assert str(raised.value).endswith(": " + "x" * ERROR_BODY_MAX_CHARS)


async def test_a_timeout_is_the_same_kind_of_error() -> None:
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("took too long", request=request)

    async with client_answering(httpx.MockTransport(time_out)) as client:
        with pytest.raises(
            ExternalServiceError, match="Some Service could not be reached"
        ):
            await send_to_external_service(
                client, "Some Service", client.build_request("GET", SERVICE_URL)
            )
