"""ASGI entry point for the clarity-channel-gateway deployable (N02, #40).

Thin on purpose, matching `services/hutch-sim/src/main.py`: the app is built by
a factory inside `clarity.interfaces.channels`, so it is covered by
`make check` and by the same type and import contracts as everything else. A
service with its own copy of the logic is a service whose logic nobody tests.
"""

from clarity.app.container import Clarity
from clarity.interfaces.channels.gateway import create_channel_gateway_app

app = create_channel_gateway_app(Clarity())
