"""The one way a pipeline step calls a service this project doesn't run."""

import httpx

from emotion_painting.constants import ERROR_BODY_MAX_CHARS


class ExternalServiceError(Exception):
    """An outside service failed a step; the message names the service and what it answered."""


async def send_to_external_service(
    client: httpx.AsyncClient, service_name: str, request: httpx.Request
) -> httpx.Response:
    """The service's successful response.

    Every way the call can fail — unreachable, timed out, an error status — is raised as one error type.
    """
    try:
        response = await client.send(request)
    except httpx.HTTPError as error:
        raise ExternalServiceError(
            f"{service_name} could not be reached: {error!r}"
        ) from error
    if response.is_error:
        raise ExternalServiceError(
            f"{service_name} answered {response.status_code}: {response.text[:ERROR_BODY_MAX_CHARS]}"
        )
    return response
