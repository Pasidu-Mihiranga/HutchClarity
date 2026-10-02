"""ASGI entry point for the synthetic hutch-sim development service."""

from clarity.integration.drivers.mock.http_service import create_hutch_sim_app

app = create_hutch_sim_app()
