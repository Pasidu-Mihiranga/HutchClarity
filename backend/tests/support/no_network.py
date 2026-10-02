"""Block outbound network calls during the suite (A02).

A cassette that is merely *preferred* is not a guarantee. The suite has to be
unable to reach a provider, or a missing recording quietly becomes a live call
and the build starts depending on somebody's free-tier quota.

So the socket layer is closed. Anything attempting a real connection raises
``LiveCallAttempted`` naming the address, which turns "the tests are flaky
today" into "this test tried to call api.groq.com".

Loopback is left open, because the test suite legitimately talks to itself:
``TestClient`` drives the FastAPI app, and the `full` lane talks to PostgreSQL,
Kafka, OPA and OpenBao on localhost. Those are components under test, not
third-party endpoints that cost money.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

#: Hosts the suite may reach: itself, and the containers in the full lane.
ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "0.0.0.0"})


class LiveCallAttempted(RuntimeError):
    """A test tried to open a connection to something outside this machine."""

    def __init__(self, address: Any) -> None:
        super().__init__(
            f"a test tried to reach {address!r}. Tests must replay a cassette "
            "rather than call a provider (A02): record it once with "
            "CLARITY_RECORD_CASSETTES=1 and commit the file."
        )
        self.address = address


def _is_allowed(address: Any) -> bool:
    if not isinstance(address, tuple) or not address:
        # A unix socket or something exotic. Not a provider call.
        return True
    host = address[0]
    return isinstance(host, str) and host in ALLOWED_HOSTS


@contextmanager
def no_live_calls() -> Iterator[None]:
    """Refuse any connection that leaves this machine.

    Resolution is guarded as well as connection, and that is the half that
    makes the failure readable: by connect time the hostname is already an IP,
    so a message naming ``('2a06:98c1::6812:26ec', 443)`` tells nobody which
    provider was called. Catching ``getaddrinfo`` reports ``api.groq.com``.
    """
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(host, str) and host not in ALLOWED_HOSTS:
            raise LiveCallAttempted(f"{host}:{port}")
        return real_getaddrinfo(host, port, *args, **kwargs)

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if not _is_allowed(address):
            raise LiveCallAttempted(address)
        return real_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any) -> Any:
        if not _is_allowed(address):
            raise LiveCallAttempted(address)
        return real_connect_ex(self, address)

    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]
    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.getaddrinfo = real_getaddrinfo  # type: ignore[assignment]
        socket.socket.connect = real_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = real_connect_ex  # type: ignore[method-assign]


__all__ = ["ALLOWED_HOSTS", "LiveCallAttempted", "no_live_calls"]
