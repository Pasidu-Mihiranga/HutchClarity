"""Private HTTP surface of the simulated HUTCH estate.

The service is explicitly development-only and serves synthetic data. It owns
the mock world so the Clarity API can exercise real network boundaries without
pretending that a production HUTCH interface exists.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException

from clarity.contracts.decision import ActionType
from clarity.integration.drivers.mock.adapters import MockCommandAdapter, MockReadAdapter
from clarity.integration.drivers.mock.world import SyntheticWorld, build_demo_world
from clarity.integration.ports import AdapterUnavailable, Command, CommandResult, SourceRead
from clarity.kernel.common import ClarityModel, EventSource


class ReadRequest(ClarityModel):
    subscriber_ref: str
    window_from: datetime
    window_to: datetime


def create_hutch_sim_app(world: SyntheticWorld | None = None) -> FastAPI:
    """Build the labelled simulated service around one shared mock store."""
    simulated = world or build_demo_world()
    command = MockCommandAdapter(simulated)
    reads = {source: MockReadAdapter(source, simulated) for source in EventSource}
    app = FastAPI(
        title="hutch-sim",
        version="0.1.0",
        description="SIMULATED HUTCH systems for development and contract testing only.",
    )
    app.state.world = simulated

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "system": "hutch-sim", "data": "synthetic"}

    @app.post("/v1/read/{source}", response_model=SourceRead)
    def read(source: EventSource, body: ReadRequest) -> SourceRead:
        try:
            return reads[source].read(body.subscriber_ref, body.window_from, body.window_to)
        except AdapterUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc

    @app.get("/v1/commands/supports/{action_type}")
    def supports(action_type: str) -> dict[str, bool]:
        try:
            parsed = ActionType(action_type)
        except ValueError:
            return {"supported": False}
        return {"supported": command.supports(parsed)}

    @app.post("/v1/commands", response_model=CommandResult)
    def execute(body: Command) -> CommandResult:
        try:
            return command.execute(body)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "SUBSCRIBER_NOT_FOUND", "message": str(exc)},
            ) from exc

    @app.get("/v1/commands/{idempotency_key}", response_model=CommandResult)
    def status(idempotency_key: str) -> CommandResult:
        result = command.status_of(idempotency_key)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "COMMAND_NOT_FOUND", "message": "command was not executed"},
            )
        return result

    return app


__all__ = ["ReadRequest", "create_hutch_sim_app"]
