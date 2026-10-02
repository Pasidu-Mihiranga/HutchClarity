"""HTTP implementations of the HUTCH integration ports.

These drivers talk only to the labelled ``hutch-sim`` development service.
They do not imply that any real HUTCH interface or field mapping is confirmed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import httpx

from clarity.contracts.decision import ActionType
from clarity.integration.ports import (
    AdapterError,
    AdapterUnavailable,
    Command,
    CommandPort,
    CommandResult,
    SourceRead,
)
from clarity.kernel.common import EventSource


class JsonHttpClient(Protocol):
    """Small client seam shared by httpx and FastAPI's test client."""

    def get(self, url: str) -> httpx.Response: ...

    def post(self, url: str, *, json: object) -> httpx.Response: ...


class _HttpAdapter:
    def __init__(
        self,
        base_url: str,
        *,
        client: JsonHttpClient | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def _failure(self, source: EventSource, response: httpx.Response) -> AdapterError:
        code = f"HTTP_{response.status_code}"
        message = "hutch-sim refused the request"
        try:
            detail = response.json().get("detail", {})
            if isinstance(detail, dict):
                code = str(detail.get("code") or code)
                message = str(detail.get("message") or message)
            elif detail:
                message = str(detail)
        except ValueError:
            pass
        error = AdapterUnavailable if response.status_code >= 500 else AdapterError
        return error(source, code, message)


class HttpReadAdapter(_HttpAdapter):
    """Read one canonical evidence source from hutch-sim over HTTP."""

    def __init__(
        self,
        source: EventSource,
        base_url: str,
        *,
        client: JsonHttpClient | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        super().__init__(base_url, client=client, timeout_seconds=timeout_seconds)
        self.source = source

    def read(self, subscriber_ref: str, window_from: datetime, window_to: datetime) -> SourceRead:
        try:
            response = self._client.post(
                f"{self._base_url}/v1/read/{self.source.value}",
                json={
                    "subscriber_ref": subscriber_ref,
                    "window_from": window_from.isoformat(),
                    "window_to": window_to.isoformat(),
                },
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise AdapterUnavailable(
                self.source, "HUTCH_SIM_UNAVAILABLE", "hutch-sim could not be reached"
            ) from exc
        if response.is_error:
            raise self._failure(self.source, response)
        return SourceRead.model_validate(response.json())


class HttpCommandAdapter(_HttpAdapter, CommandPort):
    """Execute idempotent commands through hutch-sim's private HTTP API."""

    source = EventSource.CHARGING

    def supports(self, action_type: ActionType) -> bool:
        try:
            response = self._client.get(
                f"{self._base_url}/v1/commands/supports/{action_type.value}"
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise AdapterUnavailable(
                self.source, "HUTCH_SIM_UNAVAILABLE", "hutch-sim could not be reached"
            ) from exc
        if response.is_error:
            raise self._failure(self.source, response)
        return bool(response.json()["supported"])

    def execute(self, command: Command) -> CommandResult:
        try:
            response = self._client.post(
                f"{self._base_url}/v1/commands",
                json=command.model_dump(mode="json"),
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise AdapterUnavailable(
                self.source, "HUTCH_SIM_UNAVAILABLE", "hutch-sim could not be reached"
            ) from exc
        if response.is_error:
            raise self._failure(self.source, response)
        return CommandResult.model_validate(response.json())

    def status_of(self, idempotency_key: str) -> CommandResult | None:
        try:
            response = self._client.get(f"{self._base_url}/v1/commands/{idempotency_key}")
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise AdapterUnavailable(
                self.source, "HUTCH_SIM_UNAVAILABLE", "hutch-sim could not be reached"
            ) from exc
        if response.status_code == 404:
            return None
        if response.is_error:
            raise self._failure(self.source, response)
        return CommandResult.model_validate(response.json())
