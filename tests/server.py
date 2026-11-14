"""Local HTTPS server standing in for the DPC hosts.

A fake DNS resolver sends the DPC hosts to a local aiohttp test server whose
certificate is issued by a test CA, so the client runs unchanged against real
aiohttp responses (pattern of aiohttp's "fake server" example).
"""

from __future__ import annotations

import asyncio
import socket
import ssl
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiohttp import ClientSession, TCPConnector, web
from aiohttp.abc import AbstractResolver, ResolveResult
from aiohttp.test_utils import TestServer

if TYPE_CHECKING:
    import trustme

HOSTS = ("mappe.protezionecivile.gov.it", "raw.githubusercontent.com")


@dataclass(frozen=True, slots=True)
class Route:
    """Response served for a URL."""

    body: str | bytes = b""
    status: int = 200
    before: Callable[[], Awaitable[None]] | None = None
    disconnect: bool = False


class FakeResolver(AbstractResolver):
    """Resolve the DPC hosts to the local server and fail for unknown hosts."""

    def __init__(self, port: int, unresolvable: set[str]) -> None:
        """Initialize the resolver."""
        self._port = port
        self._unresolvable = unresolvable

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        """Return the address of the local server."""
        del port, family
        if host not in HOSTS or host in self._unresolvable:
            msg = f"Name or service not known: {host}"
            raise OSError(msg)
        return [
            {
                "hostname": host,
                "host": "127.0.0.1",
                "port": self._port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
        ]

    async def close(self) -> None:
        """Release the resolver."""


class FakeDpc:
    """Local server answering the configured DPC URLs.

    Unknown URLs answer 404. Every request is recorded in ``requests``.
    """

    def __init__(self, ca: trustme.CA) -> None:
        """Initialize the server."""
        self._ca = ca
        self._routes: dict[str, Route] = {}
        self._released = asyncio.Event()
        self._server: TestServer | None = None
        self.unresolvable: set[str] = set()
        self.requests: list[str] = []

    def add(
        self,
        url: str,
        *,
        body: str | bytes = b"",
        status: int = 200,
        before: Callable[[], Awaitable[None]] | None = None,
        disconnect: bool = False,
    ) -> None:
        """Serve a response for a URL, replacing any previous one."""
        self._routes[url] = Route(body, status, before, disconnect)

    async def hang(self) -> None:
        """Wait until the server closes (to simulate a stalled response)."""
        await self._released.wait()

    async def start(self) -> None:
        """Start the server."""
        app = web.Application()
        app.router.add_route("GET", "/{path:.*}", self._handle)
        server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self._ca.issue_cert(*HOSTS).configure_cert(server_context)
        self._server = TestServer(app)
        await self._server.start_server(ssl=server_context)

    async def close(self) -> None:
        """Release the stalled responses and stop the server."""
        self._released.set()
        if self._server is not None:
            await self._server.close()

    def client_session(self) -> ClientSession:
        """Return a session whose requests to the DPC hosts reach this server."""
        assert self._server is not None
        assert self._server.port is not None
        client_context = ssl.create_default_context()
        self._ca.configure_trust(client_context)
        connector = TCPConnector(
            resolver=FakeResolver(self._server.port, self.unresolvable),
            ssl=client_context,
        )
        # Bound at import time: tests may replace aiohttp.ClientSession.
        return ClientSession(connector=connector)

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        url = str(request.url.with_port(None))
        self.requests.append(url)
        route = self._routes.get(url)
        if route is None:
            return web.Response(status=404, text="404: Not Found")
        if route.before is not None:
            await route.before()
        if route.disconnect:
            assert request.transport is not None
            request.transport.close()
        return web.Response(status=route.status, body=route.body)
