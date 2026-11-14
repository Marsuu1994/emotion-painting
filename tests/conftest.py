import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Async tests (`@pytest.mark.anyio`) run on asyncio, the loop the service uses."""
    return "asyncio"
