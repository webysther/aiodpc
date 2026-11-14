"""Fixtures of the aiodpc tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import trustme

from aiodpc import DpcClient

from .server import FakeDpc

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import aiohttp


@pytest.fixture(scope="session")
def ca() -> trustme.CA:
    """Return the certificate authority of the local DPC server."""
    return trustme.CA()


@pytest.fixture
async def dpc(ca: trustme.CA) -> AsyncIterator[FakeDpc]:
    """Run a local server answering for the DPC hosts."""
    server = FakeDpc(ca)
    await server.start()
    yield server
    await server.close()


@pytest.fixture
async def session(dpc: FakeDpc) -> AsyncIterator[aiohttp.ClientSession]:
    """Return an aiohttp session reaching the local DPC server."""
    async with dpc.client_session() as client_session:
        yield client_session


@pytest.fixture
def client(session: aiohttp.ClientSession) -> DpcClient:
    """Return a client using the injected session."""
    return DpcClient(session)
